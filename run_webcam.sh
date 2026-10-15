#!/usr/bin/env bash
# Cube Tutor AR on the laptop webcam (branch ar-webcam). Starts this branch's
# vision server on port 8101 and the web app on http://localhost:5174.
# (Branch webcam-anyside: its own ports, so the webcam demo on branch ar-webcam,
# ports 8100 / 5173, can run at the same time.)
# The original demo (branch live-solver, ./run.sh, port 8000) is separate and untouched.
set -euo pipefail
cd "$(dirname "$0")"
PY="${RUBIK_PYTHON:-}"
if [ -z "$PY" ]; then
  if [ -x .venv/bin/python ]; then PY=.venv/bin/python
  elif [ -x ../rubik_solver_AR/.venv/bin/python ]; then PY=../rubik_solver_AR/.venv/bin/python  # share the demo's environment
  else python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt && PY=.venv/bin/python; fi
fi
[ -d web/node_modules ] || (cd web && npm install)
"$PY" -m uvicorn main:app --host 127.0.0.1 --port "${VISION_PORT:-8101}" &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT
echo "Open http://localhost:${APP_PORT:-5174}  (vision server on :${VISION_PORT:-8101})"
cd web && RUBIK_SERVER="http://127.0.0.1:${VISION_PORT:-8101}" npx vite --port "${APP_PORT:-5174}" --strictPort
