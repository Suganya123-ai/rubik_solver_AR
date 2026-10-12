#!/usr/bin/env bash
# Cube Tutor on the XREAL glasses, through the Beam Pro's browser (branch xreal-glasses).
#   ./run_glasses.sh          over Wi-Fi: open the https address it prints on the Beam Pro
#   ./run_glasses.sh --usb    Beam Pro plugged into this laptop by USB: open http://localhost:5273 on it
# Starts this branch's vision server on port 8200 and the web app on port 5273.
# The webcam demo (branch ar-webcam, ports 8100/5173) is separate and can run at the same time.
set -euo pipefail
cd "$(dirname "$0")"
PY="${RUBIK_PYTHON:-}"
if [ -z "$PY" ]; then
  if [ -x .venv/bin/python ]; then PY=.venv/bin/python
  elif [ -x ../rubik_solver_AR/.venv/bin/python ]; then PY=../rubik_solver_AR/.venv/bin/python  # share the demo's environment
  else python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt && PY=.venv/bin/python; fi
fi
[ -d web/node_modules ] || (cd web && npm install)
"$PY" -m uvicorn main:app --host 127.0.0.1 --port 8200 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT
if [ "${1:-}" = "--usb" ]; then
  export RUBIK_HTTP=1
  if command -v adb >/dev/null && adb reverse tcp:5273 tcp:5273 2>/dev/null; then
    echo "USB link ready. On the Beam Pro open:  http://localhost:5273"
  else
    echo "Plug the Beam Pro into this laptop (USB debugging on), then run:  adb reverse tcp:5273 tcp:5273"
    echo "Then on the Beam Pro open:  http://localhost:5273"
  fi
else
  IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "<this-laptop-ip>")
  echo "On the Beam Pro (same Wi-Fi) open:  https://${IP}:5273"
  echo "The browser will warn about the certificate once: choose Advanced, then Proceed."
  echo "If it can't connect, allow incoming connections for node in the laptop's firewall."
fi
cd web && npx vite
