#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${DEPLOY_DIR}"

docker compose -f docker-compose.vps.yml --env-file .env up -d --build
docker compose -f docker-compose.vps.yml --env-file .env ps
