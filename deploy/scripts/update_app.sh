#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="$(cd "${DEPLOY_DIR}/.." && pwd)"
BRANCH="${BRANCH:-main}"
REMOTE="${REMOTE:-origin}"
FORCE_SYNC="${FORCE_SYNC:-0}"
BACKUP_DIR="${DEPLOY_DIR}/backups/code-state"

cd "${APP_DIR}"
git fetch --prune "${REMOTE}" "${BRANCH}"
TARGET="${REMOTE}/${BRANCH}"

if ! git rev-parse --verify "${TARGET}" >/dev/null 2>&1; then
  echo "Cannot resolve ${TARGET}; check Git remote credentials and branch name." >&2
  exit 2
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  if [[ "${FORCE_SYNC}" != "1" ]]; then
    echo "Tracked working tree is dirty; refusing to update automatically." >&2
    echo "Set FORCE_SYNC=1 to save a patch under ${BACKUP_DIR} and reset to ${TARGET}." >&2
    git status --short
    exit 2
  fi

  mkdir -p "${BACKUP_DIR}"
  TS="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
  git status --short > "${BACKUP_DIR}/status_${TS}.txt"
  git diff > "${BACKUP_DIR}/tracked_${TS}.patch"
fi

git checkout "${BRANCH}"
git reset --hard "${TARGET}"

# Remove stale untracked source files while preserving ignored runtime state
# such as deploy/.env, deploy/data, and deploy/backups.
git clean -fd

"${SCRIPT_DIR}/redeploy.sh"
