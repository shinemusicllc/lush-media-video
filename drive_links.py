"""Google Drive shared-file link parsing."""

import re
from urllib.parse import parse_qs, urlsplit


_ALLOWED_HOSTS = {"drive.google.com", "drive.usercontent.google.com"}
_FILE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,200}$")
_PATH_PATTERNS = (
    re.compile(r"/file/d/([A-Za-z0-9_-]+)"),
    re.compile(r"/d/([A-Za-z0-9_-]+)"),
)


def google_drive_file_id(value: str) -> str | None:
    """Return the file ID for a supported Google Drive share URL."""
    try:
        parsed = urlsplit((value or "").strip())
    except ValueError:
        return None

    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in _ALLOWED_HOSTS:
        return None

    query_id = next((part for part in parse_qs(parsed.query).get("id", []) if part), "")
    if query_id and _FILE_ID_PATTERN.fullmatch(query_id):
        return query_id

    for pattern in _PATH_PATTERNS:
        match = pattern.search(parsed.path)
        if match and _FILE_ID_PATTERN.fullmatch(match.group(1)):
            return match.group(1)
    return None
