#!/usr/bin/env bash
# Cube Tutor on the XREAL glasses, through the Beam Pro's browser (branch xreal-glasses).
#   ./run_glasses.sh          over Wi-Fi: open the https address it prints on the Beam Pro
#   ./run_glasses.sh --usb    Beam Pro plugged into this laptop by USB: open http://localhost:5273/glasses/ on it
# One program (the Python server) does the vision and serves the web app, on port 5273.
# The webcam demo (branch ar-webcam, ports 8100/5173) is separate and can run at the same time.
set -euo pipefail
cd "$(dirname "$0")"
PORT="${RUBIK_PORT:-5273}"
PY="${RUBIK_PYTHON:-}"
if [ -z "$PY" ]; then
  if [ -x .venv/bin/python ]; then PY=.venv/bin/python
  elif [ -x ../rubik_solver_AR/.venv/bin/python ]; then PY=../rubik_solver_AR/.venv/bin/python  # share the demo's environment
  else python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt && PY=.venv/bin/python; fi
fi
echo "Building the web app..."
(cd web && { [ -d node_modules ] || npm install; } && npm run --silent build >/dev/null)

if [ "${1:-}" = "--usb" ]; then
  if command -v adb >/dev/null && adb reverse "tcp:$PORT" "tcp:$PORT" 2>/dev/null; then
    echo "USB link ready. On the Beam Pro open:  http://localhost:$PORT/glasses/"
  else
    echo "Plug the Beam Pro into this laptop (USB debugging on), then run:  adb reverse tcp:$PORT tcp:$PORT"
    echo "Then on the Beam Pro open:  http://localhost:$PORT/glasses/"
  fi
  exec "$PY" -m uvicorn glasses_server:app --host 127.0.0.1 --port "$PORT"
fi

IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
# Browsers only allow the camera on https, so make a certificate for this laptop's address (once per address).
mkdir -p .certs
if [ ! -f .certs/cert.pem ] || [ "$(cat .certs/ip 2>/dev/null)" != "$IP" ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 365 -keyout .certs/key.pem -out .certs/cert.pem \
    -subj "/CN=Cube Tutor ($IP)" -addext "subjectAltName=IP:$IP,IP:127.0.0.1,DNS:localhost" >/dev/null 2>&1
  echo "$IP" > .certs/ip
fi
NAME=$(scutil --get LocalHostName 2>/dev/null || hostname -s 2>/dev/null || echo "")
echo "On the Beam Pro (same Wi-Fi) open:  https://${IP}:${PORT}/glasses/"
if [ -n "$NAME" ]; then
  # A hotspot hands out a new number when devices reconnect; the name stays the same.
  echo "In the Cube Tutor Bridge app, use this laptop's NAME as the address:  ${NAME}.local:${PORT}"
fi
echo "The browser warns about the certificate once: choose Advanced, then Proceed."
exec "$PY" -m uvicorn glasses_server:app --host 0.0.0.0 --port "$PORT" \
  --ssl-keyfile .certs/key.pem --ssl-certfile .certs/cert.pem
