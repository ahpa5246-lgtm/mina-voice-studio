#!/usr/bin/env bash
# Start the UI only. Model engines are separately installed.
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f .venv/bin/python ]; then
  python3.11 -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn studio.app:app --host 127.0.0.1 --port 7860
