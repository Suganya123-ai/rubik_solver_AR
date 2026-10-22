"""Trains the any-hold cube model (bench/make_yolo_data_anyhold.py): 4 classes (corner, top_front,
front_right, face), 7 keypoints, hidden ones with visibility 0. Starts from the corner-only v3 model
and mixes in v3's corner frames and the real webcam frames so it keeps what it knew. No left-right
flips: a mirrored cube is not a real cube, and it would swap the corners' names by hold.
    python train_anyhold.py          -> ../models/cube_pose_anyhold.pt
"""
import os
import shutil

from ultralytics import YOLO

project = os.path.abspath('runs')
model = YOLO('../models/cube_pose_v3.pt')
model.train(data='data/mix_anyhold.yaml', epochs=12, imgsz=640, batch=16, device='mps', workers=4,
            fliplr=0.0, project=project, name='cube_anyhold', exist_ok=True, plots=True)
shutil.copy(os.path.join(project, 'cube_anyhold', 'weights', 'best.pt'), '../models/cube_pose_anyhold.pt')
print('saved ../models/cube_pose_anyhold.pt')
