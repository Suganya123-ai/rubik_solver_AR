#!/usr/bin/env bash
# Pyraminx corner model v2: v1 trained further on hard, unclear pictures, pyramids in real hands,
# and 3x3 cubes as counter-examples (so a cube is no longer taken for a pyramid).
# Needs models/pyra_pose_v1.pt (run_pyra_training.sh) and the cube apps' recordings for the real frames.
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-../../rubik_solver_AR/.venv/bin/python}
APPS=${APPS:-"../../rubik_solver_AR_webcam ../../rubik_solver_AR_glasses"}   # the recordings v2 was made from
PYTHONPATH=.. $PY make_pyra_hard.py
PYTHONPATH=.. $PY make_pyra_real_hands.py ../models/cube_pose_v3.pt $APPS
# half of the original renders (every other one), so the new pictures weigh more
for d in images labels; do
    mkdir -p data/pyra_v1_subset/$d/train
    ls data/pyra_v1/$d/train | awk 'NR % 2 == 0' | while read -r f; do
        ln -sf "$PWD/data/pyra_v1/$d/train/$f" data/pyra_v1_subset/$d/train/$f
    done
done
cat > data/pyra_mix_v2.yaml <<YAML
path: $PWD/data
train:
  - pyra_v1_subset/images/train
  - pyra_hard/images/train
  - pyra_real_hands/images/train
val:
  - pyra_v1/images/val
  - pyra_hard/images/val
  - pyra_real_hands/images/val
kpt_shape: [4, 3]
flip_idx: [0, 1, 3, 2]
names:
  0: pyraminx
YAML
PYTHONPATH=.. $PY train_yolo.py --data data/pyra_mix_v2.yaml --base ../models/pyra_pose_v1.pt \
    --epochs 10 --out ../models/pyra_pose_v2.pt --name pyra_v2
