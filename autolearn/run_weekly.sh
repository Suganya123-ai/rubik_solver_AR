#!/usr/bin/env bash
# The self-improving loop, once a week: label the frames saved during demos, retrain both corner models,
# switch the apps to a new model only if it tests better (autolearn/retrain.py). Started every night by
# launchd (autolearn/install_schedule.sh); it does the work only when
#   - the last round was 7 or more days ago (or --force),
#   - the laptop is on mains power (training takes about an hour and works the GPU),
#   - no demo is running (it would slow the demo down, and the demo would slow training).
# Otherwise it tries again the next night. Log: data/autolearn/logs/<date>.log; reports: data/autolearn/reports/.
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${RUBIK_PYTHON:-}"
[ -n "$PY" ] || { [ -x .venv/bin/python ] && PY=.venv/bin/python || PY=../rubik_solver_AR/.venv/bin/python; }
WORK=data/autolearn
mkdir -p "$WORK/logs"
LOG="$WORK/logs/$(date +%Y-%m-%d).log"
exec >>"$LOG" 2>&1
echo "== $(date) =="
FORCE=0; [ "${1:-}" = "--force" ] && FORCE=1
if [ $FORCE = 0 ]; then
  if [ -f "$WORK/last_round" ] && [ $(( $(date +%s) - $(cat "$WORK/last_round") )) -lt $(( 7 * 86400 - 3600 )) ]; then
    echo "last round less than a week ago: nothing to do"; exit 0; fi
  if ! pmset -g batt | grep -q "AC Power"; then echo "on battery: trying again tomorrow"; exit 0; fi
  for port in 5173 5174 5175 5176 5177 8000 8100 8101 8102 8103 8104 5273; do
    if lsof -nP -iTCP:$port -sTCP:LISTEN >/dev/null 2>&1; then echo "a demo is running (port $port): trying again tomorrow"; exit 0; fi
  done
fi
if ! mkdir "$WORK/lock" 2>/dev/null; then echo "another round is running"; exit 0; fi
trap 'rmdir "$WORK/lock"' EXIT
OK=1
for puzzle in pyra cube; do
  caffeinate -i env PYTHONPATH=. "$PY" -m autolearn.retrain $puzzle $([ $FORCE = 1 ] && echo --force) || OK=0
done
[ $OK = 1 ] && date +%s > "$WORK/last_round"
SUMMARY=$(tail -n 200 "$LOG" | grep -E "^(pyra|cube): (switched|kept|skipped)" | tr '\n' ' ')
osascript -e "display notification \"${SUMMARY:-see data/autolearn/reports}\" with title \"Puzzle tutor: weekly retraining done\"" 2>/dev/null || true
echo "== done $(date) =="
