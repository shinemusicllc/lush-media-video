#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${DEPLOY_DIR}"

BACKUP_ROOT="${BACKUP_ROOT:-/opt/lush-media-video/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
ARCHIVE_FILE="${BACKUP_ROOT}/lush-media-data_${TIMESTAMP}.tar.gz"

mkdir -p "${BACKUP_ROOT}"
mkdir -p data

tar -czf "${ARCHIVE_FILE}" -C "${DEPLOY_DIR}" data
find "${BACKUP_ROOT}" -type f -name 'lush-media-data_*.tar.gz' -mtime +"${RETENTION_DAYS}" -delete

echo "Backup created: ${ARCHIVE_FILE}"
