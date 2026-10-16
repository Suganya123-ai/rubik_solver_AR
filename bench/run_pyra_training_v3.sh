#!/usr/bin/env bash
# Pyraminx model v3: two kinds of hold, class 0 corner-on (as v1/v2) and class 1 edge-on (an edge toward
# the camera, two whole faces: how the scan asks for it). v2 trained further on v2's pictures plus
# edge-on renders (normal to extreme, natural "standing on its base" holds, fingers) and edge-on
# pyramids in real hands. Needs v2's pictures (run_pyra_training_v2.sh) and models/pyra_pose_v2.pt.
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-../../rubik_solver_AR/.venv/bin/python}
APPS=${APPS:-"../../rubik_solver_AR_webcam ../../rubik_solver_AR_glasses"}
PYTHONPATH=.. $PY make_pyra_edge.py 5500 550
EDGE=1 PYTHONPATH=.. $PY make_pyra_real_hands.py ../models/cube_pose_v3.pt $APPS
cat > data/pyra_mix_v3.yaml <<YAML
path: $PWD/data
train:
  - pyra_v1_subset/images/train
  - pyra_hard/images/train
  - pyra_real_hands/images/train
  - pyra_edge/images/train
  - pyra_edge_hands/images/train
val:
  - pyra_v1/images/val
  - pyra_hard/images/val
  - pyra_real_hands/images/val
  - pyra_edge/images/val
  - pyra_edge_hands/images/val
kpt_shape: [4, 3]
flip_idx: [0, 1, 3, 2]
names:
  0: corner_on
  1: edge_on
YAML
PYTHONPATH=.. $PY train_yolo.py --data data/pyra_mix_v3.yaml --base ../models/pyra_pose_v2.pt \
    --epochs 8 --out ../models/pyra_pose_v3.pt --name pyra_v3
