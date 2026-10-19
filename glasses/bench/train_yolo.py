"""Trains the cube keypoint model (7 corner points).

models/cube_pose_synthetic.pt: yolo26n-pose from scratch on data/yolo, 8 passes.
models/cube_pose_v2.pt: fine-tuned from that on data/yolo_v2 (stickerless cubes,
real photo backgrounds, hands, close-ups, 16:9):
    python train_yolo.py --data data/yolo_v2/cube.yaml --base ../models/cube_pose_synthetic.pt \
        --epochs 8 --out ../models/cube_pose_v2.pt --name cube_v2
"""
import argparse
import os
import shutil

from ultralytics import YOLO

p = argparse.ArgumentParser()
p.add_argument('--data', default='data/yolo/cube.yaml')
p.add_argument('--base', default='yolo26n-pose.pt', help='starting weights')
p.add_argument('--epochs', type=int, default=8)
p.add_argument('--device', default='mps', help="'mps', 'cpu' or a CUDA index")
p.add_argument('--out', default='../models/cube_pose_synthetic.pt')
p.add_argument('--name', default='cube')
a = p.parse_args()

model = YOLO(a.base)
# An absolute project path stops Ultralytics nesting the run under runs/pose/.
project = os.path.abspath('runs')
model.train(data=a.data, epochs=a.epochs, imgsz=640, batch=16, device=a.device, workers=4,
            project=project, name=a.name, exist_ok=True, plots=True)
shutil.copy(os.path.join(project, a.name, 'weights', 'best.pt'), a.out)
print('saved', a.out)
