"""The current model, given more chances than it gets live: the whole picture, the picture mirrored,
and zoomed-in crops around where the puzzle was seen (also where the live model last saw it). Every
corner set it proposes goes to the colour check (verify.py); the best that passes is the label. So a
frame the live model missed, but a closer look finds and the colours confirm, becomes a lesson.
"""
import cv2
import numpy as np

MIN_CONF = 0.1      # proposals this weak are still checked: the colour check decides
CROP = 1.6          # zoom crop: this many times the puzzle's size around it
MIN_CROP = 160


class Teacher:
    def __init__(self, model_path, device='mps'):
        from ultralytics import YOLO
        self.model = YOLO(model_path)
        self.device = device
        self.multi = len(self.model.names) > 1      # the Pyraminx model: class 0 corner-on, 1 edge-on

    def _predict(self, img):
        r = self.model.predict(img, imgsz=640, conf=MIN_CONF, device=self.device, verbose=False)[0]
        out = []
        if r.keypoints is None:
            return out
        for i in np.argsort(-r.boxes.conf.cpu().numpy())[:3]:
            cls = int(r.boxes.cls[i]) if self.multi else 0
            out.append((r.keypoints.xy[i].cpu().numpy().astype(float), float(r.boxes.conf[i]), cls))
        return out

    def proposals(self, img, hints=()):
        """[(corners in the model's order, confidence, class)] from all the looks."""
        h, w = img.shape[:2]
        props = self._predict(img)
        for k, c, cls in self._predict(cv2.flip(img, 1)):
            k = k.copy()
            k[:, 0] = w - 1 - k[:, 0]
            props.append((k, c, cls))       # mirrored order: autolearn.canon puts it right
        around = [p[0] for p in props[:2]] + [np.asarray(x, float) for x in hints if x is not None]
        for k in around:
            centre, size = k.mean(0), max(float(np.ptp(k, 0).max()) * CROP, MIN_CROP)
            x0, y0 = int(max(0, centre[0] - size / 2)), int(max(0, centre[1] - size / 2))
            x1, y1 = int(min(w, centre[0] + size / 2)), int(min(h, centre[1] + size / 2))
            if x1 - x0 < 40 or y1 - y0 < 40:
                continue
            crop = img[y0:y1, x0:x1]
            scale = 640 / max(crop.shape[:2])
            big = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            for kk, c, cls in self._predict(big):
                props.append((kk / scale + [x0, y0], c, cls))
        return props
