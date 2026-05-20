#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="$(cd "${DEPLOY_DIR}/.." && pwd)"
BRANCH="${BRANCH:-main}"
REMOTE="${REMOTE:-origin}"
FORCE_SYNC="${FORCE_SYNC:-0}"
BUNDLE_PATH="${BUNDLE_PATH:-}"
BACKUP_DIR="${DEPLOY_DIR}/backups/code-state"

cd "${APP_DIR}"

git_app() {
  git -c safe.directory="${APP_DIR}" -C "${APP_DIR}" "$@"
}

if [[ -n "${BUNDLE_PATH}" ]]; then
  git_app bundle verify "${BUNDLE_PATH}"
  git_app fetch "${BUNDLE_PATH}" "${BRANCH}:refs/remotes/${REMOTE}/${BRANCH}"
else
  git_app fetch --prune "${REMOTE}" "${BRANCH}"
fi
TARGET="${REMOTE}/${BRANCH}"

if ! git_app rev-parse --verify "${TARGET}" >/dev/null 2>&1; then
  echo "Cannot resolve ${TARGET}; check Git remote credentials and branch name." >&2
  exit 2
fi

if ! git_app diff --quiet || ! git_app diff --cached --quiet; then
  if [[ "${FORCE_SYNC}" != "1" ]]; then
    echo "Tracked working tree is dirty; refusing to update automatically." >&2
    echo "Set FORCE_SYNC=1 to save a patch under ${BACKUP_DIR} and reset to ${TARGET}." >&2
    git_app status --short
    exit 2
  fi

  mkdir -p "${BACKUP_DIR}"
  TS="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
  git_app status --short > "${BACKUP_DIR}/status_${TS}.txt"
  git_app diff > "${BACKUP_DIR}/tracked_${TS}.patch"
fi

git_app checkout "${BRANCH}"
git_app reset --hard "${TARGET}"

# Remove stale untracked source files while preserving ignored runtime state
# such as deploy/.env, deploy/data, and deploy/backups.
git_app clean -fd

"${SCRIPT_DIR}/redeploy.sh"
