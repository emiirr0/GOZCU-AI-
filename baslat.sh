#!/usr/bin/env sh
# GÖZCÜ·AI — macOS / Linux / Raspberry Pi: ./baslat.sh <komut>   (ör. ./baslat.sh demo)
cd "$(dirname "$0")" || exit 1
if [ -x .venv/bin/python ]; then PY=.venv/bin/python
elif command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
exec "$PY" -m gozcu "$@"
