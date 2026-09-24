"""ComfyUI node that downloads a shared Google Drive image on the GPU worker."""

import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit


_ALLOWED_HOSTS = {"drive.google.com", "drive.usercontent.google.com"}
_FILE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,200}$")
_PATH_PATTERNS = (
    re.compile(r"/file/d/([A-Za-z0-9_-]+)"),
    re.compile(r"/d/([A-Za-z0-9_-]+)"),
)
_MAX_IMAGE_BYTES = 64 * 1024 * 1024
_DOWNLOAD_ATTEMPTS = 3
_DOWNLOAD_STALL_SECONDS = 180
_DOWNLOAD_TOTAL_SECONDS = 600


def google_drive_file_id(value: str) -> str | None:
    try:
        parsed = urlsplit((value or "").strip())
    except ValueError:
        return None
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in _ALLOWED_HOSTS:
        return None

    query_id = next((item for item in parse_qs(parsed.query).get("id", []) if item), "")
    if query_id and _FILE_ID_PATTERN.fullmatch(query_id):
        return query_id
    for pattern in _PATH_PATTERNS:
        match = pattern.search(parsed.path)
        if match and _FILE_ID_PATTERN.fullmatch(match.group(1)):
            return match.group(1)
    return None


def _download_activity_size(target: Path) -> int:
    candidates = [target, *target.parent.glob(f"{target.name}*.part")]
    total = 0
    for candidate in candidates:
        try:
            total += candidate.stat().st_size
        except OSError:
            pass
    return total


def _remove_partial_files(target: Path) -> None:
    for candidate in [target, *target.parent.glob(f"{target.name}*.part")]:
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            pass


def _stop_download_process(process) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _run_gdown(url: str, target: Path) -> None:
    command = [
        sys.executable,
        "-m",
        "gdown",
        "--fuzzy",
        "--quiet",
        url,
        "-O",
        str(target),
    ]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    started_at = time.monotonic()
    last_activity_at = started_at
    last_size = _download_activity_size(target)

    while process.poll() is None:
        time.sleep(1)
        now = time.monotonic()
        size = _download_activity_size(target)
        if size != last_size:
            last_size = size
            last_activity_at = now
            if size > _MAX_IMAGE_BYTES:
                _stop_download_process(process)
                raise ValueError("Ảnh Google Drive vượt quá giới hạn 64 MB")
        elif now - last_activity_at >= _DOWNLOAD_STALL_SECONDS:
            _stop_download_process(process)
            raise TimeoutError("Tải Google Drive không có dữ liệu mới trong 180 giây")
        if now - started_at >= _DOWNLOAD_TOTAL_SECONDS:
            _stop_download_process(process)
            raise TimeoutError("Tải Google Drive vượt quá 10 phút")

    if process.returncode != 0 or not target.exists() or target.stat().st_size <= 0:
        raise RuntimeError(f"gdown thoát với mã lỗi {process.returncode}")
    if target.stat().st_size > _MAX_IMAGE_BYTES:
        raise ValueError("Ảnh Google Drive vượt quá giới hạn 64 MB")


def _download_direct(file_id: str, target: Path) -> None:
    import requests

    urls = (
        f"https://drive.usercontent.google.com/download?id={quote(file_id)}&export=download&confirm=t",
        f"https://drive.google.com/uc?export=download&id={quote(file_id)}",
    )
    errors = []
    for url in urls:
        try:
            with requests.get(url, stream=True, timeout=(30, 180), allow_redirects=True) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if content_type == "text/html":
                    raise RuntimeError("Google Drive trả trang quyền truy cập thay vì dữ liệu ảnh")
                content_length = int(response.headers.get("content-length") or 0)
                if content_length > _MAX_IMAGE_BYTES:
                    raise ValueError("Ảnh Google Drive vượt quá giới hạn 64 MB")

                received = 0
                with target.open("wb") as output:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        received += len(chunk)
                        if received > _MAX_IMAGE_BYTES:
                            raise ValueError("Ảnh Google Drive vượt quá giới hạn 64 MB")
                        output.write(chunk)
                if received:
                    return
                raise RuntimeError("Google Drive trả về file rỗng")
        except Exception as exc:
            errors.append(str(exc))
            _remove_partial_files(target)
            if isinstance(exc, ValueError):
                raise
    raise RuntimeError("Không tải được file Drive trực tiếp: " + "; ".join(errors))


def download_google_drive_image(url: str, target: Path) -> Path:
    file_id = google_drive_file_id(url)
    if not file_id:
        raise ValueError("Link Google Drive không hợp lệ")

    last_error = None
    for attempt in range(_DOWNLOAD_ATTEMPTS):
        _remove_partial_files(target)
        try:
            _run_gdown(url, target)
            return target
        except Exception as exc:
            last_error = exc
            _remove_partial_files(target)
            if isinstance(exc, ValueError):
                raise
            if attempt + 1 < _DOWNLOAD_ATTEMPTS:
                time.sleep(5)

    try:
        _download_direct(file_id, target)
        return target
    except Exception as direct_error:
        raise RuntimeError(
            f"Không tải được ảnh Google Drive sau {_DOWNLOAD_ATTEMPTS} lần: "
            f"gdown={last_error}; direct={direct_error}. "
            "Hãy kiểm tra quyền 'Bất kỳ ai có đường liên kết'."
        ) from direct_error


class LushLoadImageFromDrive:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"drive_url": ("STRING", {"default": "", "multiline": False})}}

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "mask")
    FUNCTION = "load_image"
    CATEGORY = "Lush Media"

    def load_image(self, drive_url: str):
        import numpy as np
        import torch
        from PIL import Image, ImageOps

        with tempfile.TemporaryDirectory(prefix="lush-drive-image-") as temp_dir:
            source_path = Path(temp_dir) / "input-image"
            download_google_drive_image(drive_url, source_path)
            with Image.open(source_path) as source:
                image = ImageOps.exif_transpose(source)
                alpha = None
                if "A" in image.getbands():
                    alpha = np.asarray(image.getchannel("A"), dtype=np.float32) / 255.0
                rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0

        image_tensor = torch.from_numpy(rgb.copy())[None, ...]
        if alpha is None:
            mask_tensor = torch.zeros(
                (1, image_tensor.shape[1], image_tensor.shape[2]), dtype=torch.float32
            )
        else:
            mask_tensor = torch.from_numpy((1.0 - alpha).copy())[None, ...]
        return (image_tensor, mask_tensor)
