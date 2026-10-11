#!/usr/bin/env bash
# Starts the cube solver server.
#   ./run.sh          this laptop only:  http://localhost:8000
#   ./run.sh --lan    also reachable from the XREAL glasses / other devices on the same Wi-Fi
# Environment: RUBIK_PORT (default 8000), RUBIK_LOG_LEVEL (INFO), RUBIK_PRELOAD (1 = load the model at startup)
set -euo pipefail
cd "$(dirname "$0")"
PORT="${RUBIK_PORT:-8000}"
HOST=127.0.0.1
if [ "${1:-}" = "--lan" ]; then
  HOST=0.0.0.0
  IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "<this-laptop-ip>")
  echo "Glasses app server address: ws://${IP}:${PORT}/ws/live   (health: http://${IP}:${PORT}/health)"
  echo "If the glasses can't connect, allow incoming connections for Python in the firewall settings."
fi
if [ ! -x .venv/bin/uvicorn ]; then
  echo "First run: creating .venv and installing requirements (PyTorch is a large download)..."
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
echo "Open http://localhost:${PORT}/live"
exec .venv/bin/uvicorn main:app --host "$HOST" --port "$PORT"
