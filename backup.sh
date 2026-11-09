#!/usr/bin/env bash
# Backs up everything that matters: the database and all uploaded images.
# Usage:  ./backup.sh            -> writes to  backups/
#         ./backup.sh /my/folder -> writes to that folder instead

set -euo pipefail
cd "$(dirname "$0")"

DEST="${1:-backups}"
STAMP="$(date +%Y-%m-%d_%H%M%S)"
OUT="$DEST/cm-surgical_$STAMP"

mkdir -p "$OUT"

# The database. Copied with sqlite3's own backup command so that a backup taken
# while the site is busy is still consistent.
if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 store.db ".backup '$OUT/store.db'"
else
  python3 - "$OUT/store.db" <<'PY'
import shutil, sqlite3, sys
src = sqlite3.connect("store.db")
dst = sqlite3.connect(sys.argv[1])
src.backup(dst)
dst.close(); src.close()
PY
fi

# Uploaded product images and ad creatives.
cp -R static/img "$OUT/img"

# Settings, without the secrets.
[ -f .env.example ] && cp .env.example "$OUT/.env.example"

# Source code, in case the backup is all they have left.
cp app.py db.py requirements.txt start.sh "$OUT/" 2>/dev/null || true
cp -R templates static/css static/js "$OUT/" 2>/dev/null || true

echo "Backup written to: $OUT"
du -sh "$OUT" | sed 's/^/  size: /'

# Keep only the 14 most recent backups.
if [ "$DEST" = "backups" ]; then
  ls -1dt backups/*/ 2>/dev/null | tail -n +15 | xargs rm -rf 2>/dev/null || true
fi
