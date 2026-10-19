# Benchmarks

The tests behind `docs/Benchmark_Report.pdf`: every open-source option for each
part of the live solver, scored on the same images. Results live in
`results/`; the report and summary PDFs are generated from them.

## Setup

```
cd bench
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./setup_third_party.sh        # qbr, rubiks-cube-tracker, ephynes, cubejs at the tested commits
```

Run everything from `bench/` with `.venv/bin/python <script>`. The YOLO data
(`data/yolo/`, 2,800 images) and `third_party/` are local only (gitignored);
`make_yolo_data.py` regenerates the data and `setup_third_party.sh` re-downloads
the projects.

## What each script does

| Script | Test | Writes |
|---|---|---|
| `render.py` | Synthetic webcam frames of a cube in any state, with lighting, glare, fingers, blur and noise, plus exact ground truth (library used by the others) | — |
| `bench_solvers.py [N] [solvers]` | Solvers on the same N random cubes; every solution replayed on our cube model | `results_solvers_*.json` |
| `bench_solver_depth25.py` | The ephynes C# solver settings (two-phase, maxDepth 25) | `results_solver_ephynes_settings.json` |
| `bench_scan_detect.py [N]` | Finding the 9 stickers of a face: lined-up, hand-held, hard lighting | `results_scan_detect.json` |
| `bench_real.py` | The same detectors on dwalton76's 6 real photos | `results_real.json` |
| `bench_color.py [N]` | Naming colours on whole cubes (6 scans, one lighting session) | `results_color.json` |
| `bench_visibility.py [N]` | Which visible sides make every move identifiable | `results_visibility.json` |
| `bench_tracking.py N sources [model]` | Move tracking from before/after frames; `sources` = `gt`, `noiseK` (K% point error) or `yolo` | `results_tracking_*.json` |
| `bench_corner_classic.py [N]` | Classical detectors on the corner-on view | `results_corner_classic.json` |
| `make_yolo_data.py [train] [val]` | Labelled corner-view frames for YOLO (stickered cubes, synthetic clutter) | `data/yolo/` |
| `make_yolo_data_v2.py [train] [val]` | Second set closer to real webcam use: stickerless cubes, real photo backgrounds with people (COCO128), a hand holding the cube, close-ups, 16:9 | `data/yolo_v2/` |
| `train_yolo.py --data ... --base ... --out ...` | Trains / fine-tunes the 7-corner-point model | `../models/cube_pose_*.pt` |
| `eval_yolo.py model [N]` | YOLO point error, detection rate, speed (GPU and CPU) | `results_yolo_kpts.json` |
| `detectors.py`, `tracking.py`, `ephynes_port.py` | Adapters around each project's code, the 7-point reader + move matcher, and the line-by-line Python port of the ephynes C# detector and colours | — |

The v2 set needs COCO128 photos as backgrounds (Ultralytics' 128-image COCO sample, about 7 MB):

```
curl -sL -o data/coco128.zip https://github.com/ultralytics/assets/releases/download/v0.0.0/coco128.zip
unzip -q data/coco128.zip -d data/ && mkdir -p data/backgrounds && cp data/coco128/images/train2017/*.jpg data/backgrounds/
.venv/bin/python make_yolo_data_v2.py 4000 400
.venv/bin/python train_yolo.py --data data/yolo_v2/cube.yaml --base ../models/cube_pose_synthetic.pt \
    --epochs 8 --out ../models/cube_pose_v2.pt --name cube_v2
```

Typical full run (about an hour on an M1 Pro, most of it YOLO training):

```
.venv/bin/python bench_solvers.py 200 app,kociemba,cubejs
.venv/bin/python bench_solvers.py 200 twophase      # first run builds ~80 MB of tables (~30 min)
.venv/bin/python bench_solver_depth25.py
.venv/bin/python bench_scan_detect.py 200
.venv/bin/python bench_real.py
.venv/bin/python bench_color.py 150
.venv/bin/python bench_visibility.py 300
.venv/bin/python bench_tracking.py 300 gt,noise2,noise4,noise6,noise8,noise12
.venv/bin/python bench_corner_classic.py 150
.venv/bin/python make_yolo_data.py 2500 300 && .venv/bin/python train_yolo.py 8
.venv/bin/python eval_yolo.py ../models/cube_pose_synthetic.pt 300
.venv/bin/python bench_tracking.py 300 yolo ../models/cube_pose_synthetic.pt
```

All tests use fixed random seeds, so reruns give the same images and numbers
(timings vary with the machine).

## Retraining on real photos (Day 3)

1. In the app's live view (`/live`), press **Save frame** on 300–500 varied moments: angles, distances,
   lighting, hands, people in the shot, and especially moments where YOLO is wrong or unsure.
2. In `/label`, check each frame: drag wrong points onto the right corners and save (S), or mark "no cube" (N).
3. Build the mixed set, fine-tune, and compare on real frames the model never trained on:

```
.venv/bin/python build_real_dataset.py
.venv/bin/python train_yolo.py --data data/yolo_real/cube.yaml --base ../models/cube_pose_v2.pt \
    --epochs 15 --out ../models/cube_pose_real.pt --name cube_real
.venv/bin/python eval_real.py ../models/cube_pose_v2.pt ../models/cube_pose_real.pt
```

Target on real test frames: cube found ≥ 98%, median point error < 5%. The app picks up a newer model
once `vision/detector.py` lists it first.

## Rebuilding the documents

The generators write HTML to `reports_out/`; headless Chrome prints them to PDF:

```
.venv/bin/python build_report_v2.py      # -> reports_out/benchmark_report.html
.venv/bin/python make_team_summary.py    # -> reports_out/team_summary.html
.venv/bin/python make_impl_plan.py       # -> reports_out/implementation_plan.html
.venv/bin/python export_gallery.py       # -> ../docs/test_images/ (exact frames the tests used)
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --no-pdf-header-footer \
    --print-to-pdf=../docs/Benchmark_Report.pdf reports_out/benchmark_report.html
```

## Caveats

Almost all images are synthetic. The only real photos are dwalton76's 6
photos of one robot-held cube. `models/cube_pose_synthetic.pt` has only seen
synthetic frames and needs fine-tuning on real photos before it can be trusted.
