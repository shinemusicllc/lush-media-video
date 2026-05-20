# VPS Deploy Normalization

## Goal

Make GitHub `origin/main`, the VPS checkout, and the running `lushvideo-app-1` container agree on the same clean commit, while preserving `deploy/.env` and `deploy/data/`.

## Findings

- VPS Git HEAD was `267b1f5`, but the working tree and container included later manual changes.
- `deploy/data/` was untracked under the repo and risked polluting status/build context.
- `lushvideo-app-1` had Telegram bot code running, but the image was not clearly tied to a clean commit.
- `lush-media-backup.service` ran as `deploy`, but some upload files are `root:root 0600`, causing backup failures.

## Completion Criteria

- Repo has ignore rules and deploy scripts that enforce clean builds.
- New standardization commit is pushed to GitHub.
- VPS checkout is reset to the standardization commit with runtime data preserved.
- Container is rebuilt from that commit and exposes matching `APP_COMMIT`.
- Backup service unit is updated so it can read current runtime files.

