# Webcam app: scan from any side + a retrained cube finder (branch `webcam-anyside`)

A copy of the webcam app (branch `ar-webcam`, port 5173, unchanged) with two
improvements. It runs on its own ports, so both can run at once:

```
git clone -b webcam-anyside https://github.com/Suganya123-ai/rubik_solver_AR.git
cd rubik_solver_AR
./run_webcam.sh          # then open http://localhost:5174  (vision server on 8101)
```

## 1. Scan from any side

Show the cube corner-on once (3 sides). After that, show the rest **any way
you hold it**: the app remembers every sticker it has seen and works out how
the cube was turned from the sides it already knows. It stops when all 6
sides are known ("N of 6 sides scanned"); usually 2 views, sometimes 3.

- A side only counts as "already scanned" if its centre colour matches too
  (some scrambles leave two sides with the same outer stickers).
- A view is only captured when all three sides show properly (the smallest at
  least 15% of the largest); held nearly face-on, a side is a sliver whose
  colours can't be read.

Code: `vision/scan_session.py`; tests in `tests/test_scan.py`.

## 2. The cube finder, retrained on harder pictures (`models/cube_pose_v3.pt`)

Fine-tuned from `cube_pose_v2.pt` for 12 passes (~1h45 on an M1 Pro) on:

| Pictures | How many | What |
|---|---|---|
| New hard renders (`bench/make_yolo_data_v3.py`) | 5,000 | steep angles (a side nearly edge-on), small and far cubes, fingers across the stickers, heavy blur / motion / noise / JPEG, dark and over-exposed light, colour casts, ~8% with no cube |
| Earlier renders (v2) | 2,000 | so nothing learned before is lost |
| Real frames (`bench/make_real_pseudo.py`) | 989 | webcam and glasses recordings where the old model was sure (local files, not in git) |

Results (`bench/compare_models.py`, `bench_two_view_scan.py`, `bench_tracking.py`):

| Test | Old (v2) | New (v3) |
|---|---|---|
| Hard renders: cube found | 80.0% | **99.3%** |
| Hard renders: corner error (median / 90th pct, % of cube size) | 4.9 / 20.9 | **2.7 / 6.1** |
| Earlier renders: cube found / corner error median | 100% / 2.0 | 100% / **1.7** |
| Real glasses frames never trained on (600): cube found | 33 | **133** |
| Pictures with no cube: false cubes | 0 | 0 |
| Scan benchmark (12 conditions x 100 cubes): scans right | 96-100% | 97-100% (same) |
| Move-tracking benchmark: correct (normal / hard) | 100% / 91.3% | 100% / 91.3% (same) |

`RUBIK_MODEL=/path/to/model.pt ./run_webcam.sh` runs it with another model.

To remake it: `cd bench && python make_yolo_data_v3.py 5000 500`,
`python make_real_pseudo.py ../models/cube_pose_v2.pt <app folders>`, then
`python train_yolo.py --data data/mix_v3.yaml --base ../models/cube_pose_v2.pt --epochs 12 --out ../models/cube_pose_v3.pt --name cube_v3`
(the training mix lists `data/yolo_v3`, half of `data/yolo_v2` and `data/real_pseudo`).

## Known limits

- Still a corner-on model: a cube held fully face-on (only one side showing)
  is not tracked; turn a corner toward the camera.
- On the automated test video the very first view has one side as a thin
  sliver with a finger across it; there both models read some stickers
  differently and the new one gets a different (wrong) cube, which the colour
  check screen shows as 12 highlighted stickers to confirm. In normal use,
  check the highlighted stickers before Solve.
