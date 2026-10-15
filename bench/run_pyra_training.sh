#!/usr/bin/env bash
# Pyraminx corner model: make the training pictures, then fine-tune from the cube model
# (its backbone already knows plastic puzzles, stickers, hands and webcam pictures).
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-../../rubik_solver_AR/.venv/bin/python}
PYTHONPATH=.. $PY make_pyra_data.py 6000 600
PYTHONPATH=.. $PY train_yolo.py --data data/pyra_v1/pyra.yaml --base ../models/cube_pose_v3.pt \
    --epochs 15 --out ../models/pyra_pose_v1.pt --name pyra_v1
