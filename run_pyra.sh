#!/usr/bin/env bash
# Pyraminx Tutor AR on the laptop webcam (branch pyraminx). Starts the Pyraminx vision
# server on port 8102 and the web app on http://localhost:5175/pyra.html.
# The cube apps (ports 5173 / 5174) are separate and unaffected.
set -euo pipefail
cd "$(dirname "$0")"
PY="${RUBIK_PYTHON:-}"
if [ -z "$PY" ]; then
  if [ -x .venv/bin/python ]; then PY=.venv/bin/python
  elif [ -x ../rubik_solver_AR/.venv/bin/python ]; then PY=../rubik_solver_AR/.venv/bin/python  # share the demo's environment
  else python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt && PY=.venv/bin/python; fi
fi
[ -f models/pyra_pose_v2.pt ] || { echo "models/pyra_pose_v2.pt is missing: train it with bench/run_pyra_training.sh (v1) then bench/run_pyra_training_v2.sh"; exit 1; }
[ -d web/node_modules ] || (cd web && npm install)
"$PY" -m uvicorn main_pyra:app --host 127.0.0.1 --port "${VISION_PORT:-8102}" &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT
echo "Open http://localhost:${APP_PORT:-5175}/pyra.html  (Pyraminx vision server on :${VISION_PORT:-8102})"
cd web && RUBIK_SERVER="http://127.0.0.1:${VISION_PORT:-8102}" npx vite --port "${APP_PORT:-5175}" --strictPort
