"""8-bit version of a phone model (ONNX, QDQ: 8-bit weights per channel, 8-bit activations), calibrated on
what the phone actually feeds it: windows of the glasses' camera and the zoomed squares around the cube,
from glasses sessions other than the test one (phone_models.py). 8-bit models run faster on the phone's
processor, and are what its neural engine needs.

    PYTHONPATH=.. python quantize_phone_model.py ../models/cube_pose_v3_256.onnx   -> ..._int8.onnx
"""
import glob
import os
import random
import sys

import cv2
import numpy as np
from onnxruntime.quantization import CalibrationDataReader, QuantFormat, QuantType, quantize_static
from onnxruntime.quantization.shape_inference import quant_pre_process

from phone_models import FRAMES as TEST, letterbox

src = sys.argv[1]
size = int(src.rsplit('_', 1)[1].split('.')[0])
frames = [f for f in glob.glob(os.path.expanduser('~/rubik_solver_AR_glasses/data/*/*/*/*.jpg')) if f not in set(TEST)]
random.Random(0).shuffle(frames)


class Reader(CalibrationDataReader):
    def __init__(self):
        from ultralytics import YOLO
        m = YOLO(os.path.join(os.path.dirname(__file__), '..', 'models', 'cube_pose_v3.pt'))
        self.items = []
        for f in frames[:400]:
            img = cv2.imread(f)
            if img is None:
                continue
            if img.shape[:2] != (472, 640):   # early sessions sent another window size
                continue
            self.items.append(letterbox(img, (0, 0, 640, 472), size)[0])           # the whole window
            r = m.predict(img, imgsz=640, verbose=False, device='mps')[0]
            if len(r.boxes) and float(r.boxes.conf.max()) > 0.5:                    # and the square around the cube
                k = r.keypoints.xy[int(r.boxes.conf.argmax())].cpu().numpy()
                (x0, y0), (x1, y1) = k.min(0), k.max(0)
                half = max(x1 - x0, y1 - y0, 40) * 0.75
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                self.items.append(letterbox(img, (cx - half, cy - half, cx + half, cy + half), size)[0])
            if len(self.items) >= 300:
                break
        print('calibration pictures', len(self.items))
        self.it = iter(self.items)

    def get_next(self):
        x = next(self.it, None)
        return None if x is None else {'images': x}


pre = src.replace('.onnx', '_pre.onnx')
quant_pre_process(src, pre)
# Kept at full precision: the head's decoding (boxes and corner points to pixel coordinates: ranges of
# hundreds that 8 bits can't hold) and the convolutions that feed it directly. With them in 8 bits the
# model finds nothing.
import onnx  # noqa: E402
g = onnx.load(pre).graph
consumers = {}
for n in g.node:
    for i in n.input:
        consumers.setdefault(i, []).append(n)
head = [n for n in g.node if '/model.23/' in n.name]
keep = [n.name for n in head if n.op_type != 'Conv' or all(
    c.op_type in ('Reshape', 'Concat', 'Slice', 'Split') for c in consumers.get(n.output[0], []))]
out = src.replace('.onnx', '_int8.onnx')
quantize_static(pre, out, Reader(), quant_format=QuantFormat.QDQ, per_channel=True,
                activation_type=QuantType.QUInt8, weight_type=QuantType.QInt8,
                nodes_to_exclude=keep, extra_options={'ActivationSymmetric': False, 'WeightSymmetric': True})
os.remove(pre)
print('made', out, os.path.getsize(out) // 1024, 'KB')
