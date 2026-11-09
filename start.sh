#!/usr/bin/env bash
# Starts the CM SURGICAL site, loading settings from .env if present.
# Usage:  ./start.sh          normal start (production-safe)
#         ./start.sh --dev    start with debug mode and auto-reload

set -euo pipefail
cd "$(dirname "$0")"

DEV=0
[ "${1:-}" = "--dev" ] && DEV=1

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
  echo "Loaded settings from .env"
else
  echo "No .env found — starting with built-in defaults."
  echo "For a live site run:  cp .env.example .env  and fill it in."
  echo
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Python 3.9 or newer." >&2
  exit 1
fi

if ! python3 -c "import flask" >/dev/null 2>&1; then
  echo "Installing dependencies..."
  python3 -m pip install -r requirements.txt
fi

# Keep the database schema up to date on every start.
python3 -c "import app; app.init_db()"

if [ "$DEV" = "1" ]; then
  echo ">>> DEVELOPMENT MODE (debug on — do not use on a live site)"
  FLASK_DEBUG=1 exec python3 app.py
else
  exec python3 app.py
fi
