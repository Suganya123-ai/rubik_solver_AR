"""Finds the cube and its 7 corner points with our YOLO pose model.

Keypoint order (fixed by how the model was trained): 0 is the corner nearest
the camera (Front-Right-Top), then 1 Front-Left-Top, 2 Back-Left-Top,
3 Back-Right-Top, 4 Back-Right-Bottom, 5 Front-Right-Bottom,
6 Front-Left-Bottom -- the hexagon you see when the cube is held corner-on.
"""
import os

import numpy as np

_MODELS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models')
# Newest model first: v2 adds stickerless cubes, real backgrounds with people,
# hands and close-ups; the first model only saw stickered cubes on plain clutter.
MODEL_PATH = next((os.path.join(_MODELS, m) for m in ('cube_pose_real.pt', 'cube_pose_v2.pt', 'cube_pose_synthetic.pt')
                   if os.path.exists(os.path.join(_MODELS, m))), os.path.join(_MODELS, 'cube_pose_synthetic.pt'))


def _best_device():
    import torch
    if torch.cuda.is_available():
        return 0
    if torch.backends.mps.is_available():
        return 'mps'
    return 'cpu'


class CubeDetector:
    def __init__(self, model_path=MODEL_PATH, device=None):
        from ultralytics import YOLO  # heavy import, only when the live view is used

        self.device = device if device is not None else _best_device()
        self.model = YOLO(model_path)
        # Warm up on the frame shapes webcams send (4:3 and 16:9): on Apple GPUs the
        # first frame of each new shape takes seconds while it's compiled.
        for h in (480, 360):
            self.detect(np.zeros((h, 640, 3), np.uint8), min_confidence=1.0)

    def detect(self, frame, min_confidence=0.25):
        """frame: BGR image. Returns (7x2 float32 keypoints in frame pixels,
        confidence) for the most confident cube, or None."""
        result = self.model.predict(frame, imgsz=640, device=self.device, verbose=False)[0]
        if result.keypoints is None or len(result.boxes) == 0:
            return None
        best = int(result.boxes.conf.argmax())
        confidence = float(result.boxes.conf[best])
        if confidence < min_confidence:
            return None
        return result.keypoints.xy[best].cpu().numpy().astype(np.float32), confidence


_detector = None


def get_detector():
    """One shared detector, loaded on first use (loading takes a few seconds)."""
    global _detector
    if _detector is None:
        _detector = CubeDetector()
    return _detector
