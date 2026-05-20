#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${SCRIPT_PATH}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${DEPLOY_DIR}/.env"

usage() {
  cat <<'EOF'
Usage:
  lushvideo set-admin [--current <current_admin>] [--username <new_username>] [--password <new_password>]

Notes:
  - At least one of --username or --password is required.
  - If --current is omitted, the script auto-selects the only admin user.
  - If --password is omitted, the script prompts securely.
  - The script updates both SQLite and deploy/.env so future restarts stay in sync.
EOF
}

current_username=""
new_username=""
new_password=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --current)
      [[ $# -ge 2 ]] || { echo "Missing value for --current" >&2; exit 1; }
      current_username="$2"
      shift 2
      ;;
    --username)
      [[ $# -ge 2 ]] || { echo "Missing value for --username" >&2; exit 1; }
      new_username="$2"
      shift 2
      ;;
    --password)
      [[ $# -ge 2 ]] || { echo "Missing value for --password" >&2; exit 1; }
      new_password="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${new_username}" && -z "${new_password}" ]]; then
  echo "At least one of --username or --password is required." >&2
  usage >&2
  exit 1
fi

if [[ -z "${new_password}" ]]; then
  read -r -s -p "New admin password: " new_password
  echo
fi

if [[ ${#new_password} -lt 4 ]]; then
  echo "Password must be at least 4 characters." >&2
  exit 1
fi

cd "${DEPLOY_DIR}"

docker compose -f docker-compose.vps.yml --env-file .env exec -T app \
  env CURRENT_USERNAME="${current_username}" NEW_USERNAME="${new_username}" NEW_PASSWORD="${new_password}" \
  python - <<'PY'
import asyncio
import json
import os
import sys

import aiosqlite

sys.path.insert(0, "/app")

from auth import hash_password
from config import DB_PATH


def fail(message: str, code: int = 1) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


async def main() -> None:
    current_username = (os.environ.get("CURRENT_USERNAME") or "").strip()
    new_username = (os.environ.get("NEW_USERNAME") or "").strip()
    new_password = os.environ["NEW_PASSWORD"]

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row

        if current_username:
            async with conn.execute(
                "SELECT * FROM users WHERE username = ?",
                (current_username,),
            ) as cur:
                admin = await cur.fetchone()
            if admin is None:
                fail(f"Admin user '{current_username}' was not found.")
            if admin["role"] != "admin":
                fail(f"User '{current_username}' exists but is not an admin.")
        else:
            async with conn.execute(
                "SELECT * FROM users WHERE role = 'admin' ORDER BY id"
            ) as cur:
                admins = await cur.fetchall()
            if not admins:
                fail("No admin user found in the database.")
            if len(admins) > 1:
                fail(
                    "Multiple admin users found. Re-run with --current. Available admins: "
                    + ", ".join(row["username"] for row in admins),
                    code=2,
                )
            admin = admins[0]

        original_username = admin["username"]
        final_username = original_username

        if new_username and new_username != original_username:
            async with conn.execute(
                "SELECT 1 FROM users WHERE username = ? AND id != ?",
                (new_username, admin["id"]),
            ) as cur:
                duplicate = await cur.fetchone()
            if duplicate is not None:
                fail(f"Username '{new_username}' is already in use.")

            await conn.execute(
                "UPDATE users SET username = ? WHERE id = ?",
                (new_username, admin["id"]),
            )
            await conn.execute(
                "UPDATE jobs SET username = ? WHERE username = ?",
                (new_username, original_username),
            )
            final_username = new_username

        await conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(new_password), admin["id"]),
        )
        await conn.commit()

        print(
            json.dumps(
                {
                    "current_username": original_username,
                    "updated_username": final_username,
                    "password_updated": True,
                },
                ensure_ascii=True,
            )
        )


asyncio.run(main())
PY

if [[ -f "${ENV_FILE}" ]]; then
  if [[ -n "${new_username}" ]]; then
    python3 - "${ENV_FILE}" "ADMIN_USERNAME" "${new_username}" <<'PY'
import pathlib
import sys

env_path = pathlib.Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]

lines = env_path.read_text(encoding="utf-8").splitlines()
prefix = f"{key}="
updated = False
result = []
for line in lines:
    if line.startswith(prefix):
        result.append(f"{key}={value}")
        updated = True
    else:
        result.append(line)
if not updated:
    result.append(f"{key}={value}")
env_path.write_text("\n".join(result) + "\n", encoding="utf-8")
PY
  fi

  python3 - "${ENV_FILE}" "ADMIN_PASSWORD" "${new_password}" <<'PY'
import pathlib
import sys

env_path = pathlib.Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]

lines = env_path.read_text(encoding="utf-8").splitlines()
prefix = f"{key}="
updated = False
result = []
for line in lines:
    if line.startswith(prefix):
        result.append(f"{key}={value}")
        updated = True
    else:
        result.append(line)
if not updated:
    result.append(f"{key}={value}")
env_path.write_text("\n".join(result) + "\n", encoding="utf-8")
PY
fi
