#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${DEPLOY_DIR}"

BACKUP_ROOT="${BACKUP_ROOT:-/opt/lush-media-video/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
DATA_RETENTION_DAYS="${DATA_RETENTION_DAYS:-7}"
TIMESTAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
ARCHIVE_FILE="${BACKUP_ROOT}/lush-media-data_${TIMESTAMP}.tar.gz"

mkdir -p "${BACKUP_ROOT}"
mkdir -p data

DATA_RETENTION_DAYS="${DATA_RETENTION_DAYS}" "${SCRIPT_DIR}/cleanup_data.py"

# Prune before creating a new archive so retention still works when disk is tight.
find "${BACKUP_ROOT}" -maxdepth 1 -type f -name 'lush-media-data_*.tar.gz' -size 0 -delete
find "${BACKUP_ROOT}" -maxdepth 1 -type f -name 'lush-media-data_*.tar.gz' -mtime +"${RETENTION_DAYS}" -delete

tar -czf "${ARCHIVE_FILE}" -C "${DEPLOY_DIR}" data

# Prune once more after success in case the archive crossed the retention boundary mid-run.
find "${BACKUP_ROOT}" -maxdepth 1 -type f -name 'lush-media-data_*.tar.gz' -size 0 -delete
find "${BACKUP_ROOT}" -maxdepth 1 -type f -name 'lush-media-data_*.tar.gz' -mtime +"${RETENTION_DAYS}" -delete

echo "Backup created: ${ARCHIVE_FILE}"
