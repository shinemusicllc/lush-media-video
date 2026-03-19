#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="$(cd "${DEPLOY_DIR}/.." && pwd)"

install -d -m 755 /opt/lush-media-video/backups
chown -R deploy:deploy /opt/lush-media-video/backups

ln -sfn "${SCRIPT_DIR}/lushvideo.sh" /usr/local/bin/lushvideo
install -m 644 "${DEPLOY_DIR}/systemd/lush-media-backup.service" /etc/systemd/system/lush-media-backup.service
install -m 644 "${DEPLOY_DIR}/systemd/lush-media-backup.timer" /etc/systemd/system/lush-media-backup.timer

ln -sfn "${APP_DIR}" /home/deploy/lush-media-video
cat > /home/deploy/.bash_aliases_lush <<'EOF'
alias lv='cd /opt/lush-media-video/app/deploy'
alias lvapp='cd /opt/lush-media-video/app'
alias lvstatus='lushvideo status'
alias lvlogs='lushvideo logs'
EOF
chown -h deploy:deploy /home/deploy/lush-media-video
chown deploy:deploy /home/deploy/.bash_aliases_lush

systemctl daemon-reload
systemctl enable --now lush-media-backup.timer
systemctl restart lush-media-backup.timer

echo "Installed helper command: /usr/local/bin/lushvideo"
echo "Installed timer: lush-media-backup.timer"
