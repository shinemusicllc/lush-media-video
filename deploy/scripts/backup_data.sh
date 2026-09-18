#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${DEPLOY_DIR}"

BACKUP_ROOT="${BACKUP_ROOT:-/opt/lush-media-video/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
DATA_RETENTION_DAYS="${DATA_RETENTION_DAYS:-7}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
TIMESTAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
ARCHIVE_FILE="${BACKUP_ROOT}/lush-media-data_${TIMESTAMP}.tar.gz"
ARCHIVE_PARTIAL="${ARCHIVE_FILE}.partial"

mkdir -p "${BACKUP_ROOT}"
mkdir -p data

DATA_RETENTION_DAYS="${DATA_RETENTION_DAYS}" "${PYTHON_BIN}" "${SCRIPT_DIR}/cleanup_data.py"

# Prune before creating a new archive so retention still works when disk is tight.
find "${BACKUP_ROOT}" -maxdepth 1 -type f -name 'lush-media-data_*.tar.gz' -size 0 -delete
find "${BACKUP_ROOT}" -maxdepth 1 -type f -name 'lush-media-data_*.tar.gz' -mtime +"${RETENTION_DAYS}" -delete

rm -f -- "${ARCHIVE_PARTIAL}"
set +e
tar -czf "${ARCHIVE_PARTIAL}" -C "${DEPLOY_DIR}" data
TAR_STATUS=$?
set -e

# A live upload can legitimately change while the app data directory is read.
# Accept that warning only after proving the resulting archive is readable; all
# other tar failures leave no archive that looks complete to the retention job.
if [[ "${TAR_STATUS}" -ne 0 ]]; then
  if [[ "${TAR_STATUS}" -ne 1 ]] || ! tar -tzf "${ARCHIVE_PARTIAL}" >/dev/null; then
    rm -f -- "${ARCHIVE_PARTIAL}"
    echo "Backup archive failed with tar status ${TAR_STATUS}." >&2
    exit "${TAR_STATUS}"
  fi
  echo "Backup archive completed while live files changed; archive verified readable."
fi
mv -f -- "${ARCHIVE_PARTIAL}" "${ARCHIVE_FILE}"

# Prune once more after success in case the archive crossed the retention boundary mid-run.
find "${BACKUP_ROOT}" -maxdepth 1 -type f -name 'lush-media-data_*.tar.gz' -size 0 -delete
find "${BACKUP_ROOT}" -maxdepth 1 -type f -name 'lush-media-data_*.tar.gz' -mtime +"${RETENTION_DAYS}" -delete

echo "Backup created: ${ARCHIVE_FILE}"
