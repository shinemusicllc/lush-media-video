#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="$(cd "${DEPLOY_DIR}/.." && pwd)"

git_app() {
  git -c safe.directory="${APP_DIR}" -C "${APP_DIR}" "$@"
}

if git_app rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if ! git_app diff --quiet || ! git_app diff --cached --quiet; then
    echo "Refusing to build from a dirty tracked working tree: ${APP_DIR}" >&2
    echo "Run deploy/scripts/update_app.sh, or commit/stash the local changes first." >&2
    exit 2
  fi
  export APP_COMMIT="$(git_app rev-parse HEAD)"
else
  export APP_COMMIT="${APP_COMMIT:-unknown}"
fi

cd "${DEPLOY_DIR}"

docker compose -f docker-compose.vps.yml --env-file .env up -d --build
docker compose -f docker-compose.vps.yml --env-file .env ps
