#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "${SCRIPT_PATH}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  lushvideo status
  lushvideo logs
  lushvideo backup
  lushvideo redeploy
  lushvideo update
  lushvideo set-admin [--current <current_username>] [--username <new_username>] [--password <new_password>]
EOF
}

command="${1:-}"
shift || true

case "${command}" in
  status)
    cd "${DEPLOY_DIR}"
    docker compose -f docker-compose.vps.yml --env-file .env ps
    ;;
  logs)
    cd "${DEPLOY_DIR}"
    docker compose -f docker-compose.vps.yml --env-file .env logs -f app
    ;;
  backup)
    "${SCRIPT_DIR}/backup_data.sh"
    ;;
  redeploy)
    "${SCRIPT_DIR}/redeploy.sh"
    ;;
  update)
    "${SCRIPT_DIR}/update_app.sh"
    ;;
  set-admin)
    "${SCRIPT_DIR}/set_admin_credentials.sh" "$@"
    ;;
  *)
    usage
    exit 1
    ;;
esac
