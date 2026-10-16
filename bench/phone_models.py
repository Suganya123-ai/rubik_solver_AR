"""The phone's cube finder (android_phone/.../CubeFinder.kt), step for step on the laptop, to compare model
files before putting one in the app: on the glasses session never trained on (600 frames), how many
frames the cube is found in, how close its corners are to the full model's at 640, how many model runs a
frame takes (each costs ~25-80 ms on the Beam Pro), and the time per run here (laptop processor, 4
threads: only a relative measure).

    PYTHONPATH=.. python phone_models.py <model.onnx> [<model.onnx> ...]
"""
import glob
import os
import sys
import time

import cv2
import numpy as np
import onnxruntime as ort

FRAMES = sorted(glob.glob(os.path.expanduser('~/rubik_solver_AR_glasses/data/sessions/2026-10-13/173502/*.jpg')))
KEEP, MIN, AROUND = 0.5, 0.25, 1.5


def letterbox(img, box, size):
    """CubeFinder.run: the box (may reach past the frame: grey there) drawn to fit a size x size square."""
    x0, y0, x1, y1 = box
    scale = min(size / (x1 - x0), size / (y1 - y0))
    pad_x, pad_y = (size - (x1 - x0) * scale) / 2, (size - (y1 - y0) * scale) / 2
    m = np.float32([[scale, 0, pad_x - x0 * scale], [0, scale, pad_y - y0 * scale]])
    sq = cv2.warpAffine(img, m, (size, size), flags=cv2.INTER_LINEAR, borderValue=(114, 114, 114))
    x = cv2.cvtColor(sq, cv2.COLOR_BGR2RGB).astype(np.float32).transpose(2, 0, 1)[None] / 255.0
    return x, scale, pad_x, pad_y


class Finder:
    def __init__(self, path):
        o = ort.SessionOptions()
        o.intra_op_num_threads = 4
        self.s = ort.InferenceSession(path, o, providers=['CPUExecutionProvider'])
        self.name = self.s.get_inputs()[0].name
        self.size = self.s.get_inputs()[0].shape[2]
        self.around = None
        self.runs = 0
        self.ms = []

    def run(self, img, box):
        x, scale, px, py = letterbox(img, box, self.size)
        t = time.perf_counter()
        out = self.s.run(None, {self.name: x})[0][0]          # (26, N)
        self.ms.append((time.perf_counter() - t) * 1000)
        self.runs += 1
        i = int(out[4].argmax())
        pts = np.stack([(out[5 + 3 * k, i] - px) / scale + box[0] for k in range(7)] +
                       [(out[6 + 3 * k, i] - py) / scale + box[1] for k in range(7)]).reshape(2, 7).T
        return pts, float(out[4, i])

    def square(self, pts):
        x0, y0 = pts.min(0)
        x1, y1 = pts.max(0)
        half = max(x1 - x0, y1 - y0, 40) * AROUND / 2
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        return cx - half, cy - half, cx + half, cy + half

    def find(self, img):
        h, w = img.shape[:2]
        found = None
        if self.around is not None:
            found = self.run(img, self.around)
            if found[1] < KEEP:
                found = None
        if found is None:
            coarse = self.run(img, (0, 0, w, h))
            found = self.run(img, self.square(coarse[0])) if coarse[1] >= MIN else None   # as CubeFinder.kt
        result = found if found is not None and found[1] >= MIN else None
        self.around = self.square(result[0]) if result is not None and result[1] >= KEEP else None
        return result


def reference():
    """The full model at 640 on each frame (corners where it is sure)."""
    from ultralytics import YOLO
    m = YOLO(os.path.join(os.path.dirname(__file__), '..', 'models', 'cube_pose_v3.pt'))
    out = {}
    for f in FRAMES:
        r = m.predict(f, imgsz=640, verbose=False, device='mps')[0]
        if len(r.boxes) and float(r.boxes.conf.max()) >= 0.5:
            out[f] = r.keypoints.xy[int(r.boxes.conf.argmax())].cpu().numpy()
    return out


if __name__ == '__main__':
    ref = reference()
    print(f'{len(FRAMES)} frames; the full model at 640 is sure of the cube in {len(ref)}')
    for path in sys.argv[1:]:
        f = Finder(path)
        found, errs = 0, []
        for fr in FRAMES:
            img = cv2.imread(fr)
            got = f.find(img)
            if got is None or got[1] < KEEP:
                continue
            found += 1
            if fr in ref:
                t = ref[fr]
                errs.append(np.max(np.linalg.norm(got[0] - t, axis=1)) / np.ptp(t, 0).max() * 100)
        print(f'{os.path.basename(path):28s} found {found:3d} | corners vs full model: median {np.median(errs):4.1f}% '
              f'90th {np.percentile(errs, 90):4.1f}% | model runs a frame {f.runs / len(FRAMES):.2f} | {np.median(f.ms):5.1f} ms a run here')
