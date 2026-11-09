#!/usr/bin/env bash
# Uploads the site to a server over SSH.
#
#   ./deploy/deploy.sh user@server
#
# Copies the code and static files, then restarts the service.
# It deliberately NEVER overwrites these three things on the server:
#   .env          — the real passwords and secret key
#   store.db      — every order, product and customer message
#   backups/      — existing backups
#
# That means you can deploy updates repeatedly without ever risking the data.

set -euo pipefail

TARGET="${1:-}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_DIR="/srv/cm-surgical"

if [ -z "$TARGET" ]; then
  echo "Usage: ./deploy/deploy.sh user@server" >&2
  echo "Example: ./deploy/deploy.sh root@203.0.113.10" >&2
  exit 1
fi

echo "Deploying from $SRC"
echo "           to   $TARGET:$REMOTE_DIR"
echo

# Dry run first, so you can see exactly what would change.
echo "--- files that will be uploaded ---"
rsync -av --dry-run \
  --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.env' --exclude='store.db' --exclude='backups' \
  --exclude='.DS_Store' --exclude='deploy' \
  "$SRC/" "$TARGET:$REMOTE_DIR/"
echo

read -r -p "Upload these files? [y/N] " reply
case "$reply" in
  [yY]|[yY][eE][sS]) ;;
  *) echo "Cancelled — nothing was changed."; exit 0 ;;
esac

rsync -a \
  --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.env' --exclude='store.db' --exclude='backups' \
  --exclude='.DS_Store' --exclude='deploy' \
  "$SRC/" "$TARGET:$REMOTE_DIR/"

echo
echo "--- installing the service and nginx config (first time only) ---"
ssh -t "$TARGET" "sudo cp $REMOTE_DIR/deploy/cm-surgical.service /etc/systemd/system/ 2>/dev/null || echo '(skipped - already installed)'; sudo systemctl daemon-reload; sudo systemctl restart cm-surgical; sleep 3; sudo systemctl status cm-surgical --no-pager -n 5 || true"

echo
echo "--- health check ---"
if ssh "$TARGET" "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/" | grep -q 200; then
  echo "Site is responding on the server."
else
  echo "WARNING: the site did not respond. Check:  sudo journalctl -u cm-surgical -n 40"
fi