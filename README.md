# Rubik's Cube Solver (live camera, laptop first, XREAL glasses next)

Hold a scrambled 3x3 cube up to the camera. The app finds the cube, reads the
stickers from two views, works out a ~20-move solution, then watches you turn
the cube: it ticks off each correct move, and if you make a different move it
says what you did and re-plans from the real cube. It only asks you to rescan
if it loses track of the cube.

- **Laptop (now):** webcam + Python server + browser page at `/live`.
- **XREAL One Pro + Eye camera (next):** the glasses stream camera frames to
  the same server over Wi-Fi and show the guidance. See
  [xreal_ar/README.md](xreal_ar/README.md).

## Run it

```
./run.sh            # first run creates .venv and installs everything
```

Then open <http://localhost:8000/live>. The first run downloads PyTorch, so it
takes a few minutes. Python 3.11+ is needed (tested on 3.13, macOS on Apple
Silicon; CUDA or CPU also work).

```
./run.sh --lan      # also reachable from the glasses / phones on the same Wi-Fi
```

`--lan` prints the address to put in the glasses app
(`ws://<laptop-ip>:8000/ws/live`). If the glasses can't connect, allow
incoming connections for Python in the macOS firewall.

Settings (environment variables):

| Variable | Default | Meaning |
|---|---|---|
| `RUBIK_PORT` | `8000` | Port |
| `RUBIK_LOG_LEVEL` | `INFO` | Python log level |
| `RUBIK_PRELOAD` | `1` | Load the model at startup (`0` loads on the first frame; used by CI) |

`GET /health` reports whether the model is loaded and which one.

## Using it (`/live`)

1. **Scan.** Press *Scan & solve*. Hold the cube with Top, Front and Right
   toward the camera and keep it still; it captures automatically. Then turn
   the cube upside down and give it a quarter turn as shown, and hold still
   again.
2. **Check.** The cube net appears. Any sticker the app is unsure about is
   outlined; tap it to confirm or pick the right color. Then *Start solving*.
3. **Solve.** Turn the cube back to the first position. Each move is shown
   large; do it and hold still. A correct move gets a tick. A different move
   gets "You did U instead of L" and a new plan. *I did it* skips a move if
   the camera can't see it.

Other pages: `/` is the original six-photo scanner (kept as a fallback),
`/label` is the tool for correcting saved frames for retraining.

## How it works

```
camera frame ─► YOLO pose (7 cube corners) ─► per-face homography ─► 27 sticker colors
                                                                         │
   scan:  two steady views ─► piece-level color matching ─► 54 stickers ─► kociemba (~21 moves)
   solve: compare frame with ~290 predicted outcomes (no move, any move, any two moves)
          ─► correct / different move (re-plan) / unsure (wait) / lost (ask to rescan)
```

| Part | File | Notes |
|---|---|---|
| Cube detector | [vision/detector.py](vision/detector.py) | Ultralytics YOLO pose, 7 keypoints. Loads `models/cube_pose_real.pt` if present, else `cube_pose_v2.pt`. Warmed up at startup. |
| Sticker reader | [vision/reader.py](vision/reader.py) | Maps each visible face to a square, takes the median of the middle of each cell. |
| Live loop | [vision/live.py](vision/live.py), [vision/live_session.py](vision/live_session.py) | One `LiveClient` per WebSocket connection; holds scan and tracking state. |
| Two-view scan | [vision/scan_session.py](vision/scan_session.py), [cube/scan.py](cube/scan.py) | Steady-hold capture and wrong-flip check. Colors are compared by hue (shading barely matters), the 48 side stickers are grouped 8 per color, centers are named from those groups (logo centers can't throw it off), then whole corner/edge pieces are matched so only real pieces come out. Unsure stickers are flagged for you to confirm. |
| Move tracking | [vision/tracker.py](vision/tracker.py) | Scores every predicted outcome; adapts to lighting changes; "lost" after 3 s of nothing fitting. |
| Solver | [cube/solver.py](cube/solver.py) | kociemba two-phase. The original layer-by-layer solver is kept as `solve_layer_by_layer`. |
| Server | [main.py](main.py) | FastAPI. `/ws/live` is the live protocol, documented in [docs/PROTOCOL.md](docs/PROTOCOL.md). |
| Browser UI | [static/live.*](static/), [static/scan_ui.js](static/scan_ui.js) | Plain HTML/JS, no build step. |
| Glasses client | [xreal_ar/…/Scripts/Live/](xreal_ar/UnityProject/Assets/RubikSolverAR/Scripts/Live/) | Unity C#: camera source, WebSocket client, HUD. |

## Tests

```
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

73 tests: move engine, validation, solver, color handling, the two-view
mapping, piece matching, the scan and tracking state machines (simulated
clock), the WebSocket protocol, the HTTP API. CI runs them on every push
([.github/workflows/tests.yml](.github/workflows/tests.yml)).

End-to-end checks (fake camera in Chrome, and the Unity client compiled
against the real server) and all the accuracy benchmarks live in
[bench/](bench/README.md).

## Improving detection on your cube (retraining)

The shipped model was trained on rendered cubes. To fit it to your real cube
and room:

1. On `/live`, press **Save frame** on 300–500 varied frames: different
   angles, distances, lighting, with and without your hands. Include some frames
   without a cube.
2. Open `/label`, check each frame, drag the corner points where needed, and
   save. Saved labels are marked as reviewed.
3. Build the dataset and train:
   ```
   cd bench
   ../.venv/bin/python build_real_dataset.py
   ../.venv/bin/python train_yolo.py --data data/yolo_real/cube.yaml --base ../models/cube_pose_v2.pt \
       --epochs 15 --out ../models/cube_pose_real.pt --name cube_real
   ../.venv/bin/python eval_real.py ../models/cube_pose_v2.pt ../models/cube_pose_real.pt
   ```
   `eval_real.py` compares the old and new model on real frames held out from
   training; keep the new one only if it scores better.
4. Restart the server; it picks up `cube_pose_real.pt` automatically.

Saved frames are in `data/captures/` (not committed).

## Limits

- Tested end to end with a simulated camera and on a handful of real frames.
  Accuracy on your cube and lighting needs testing with real use; retraining
  (above) is the main fix if detection is weak.
- Tracking needs the cube in the home position (Top, Front, Right visible)
  between moves. Moves that turn the hidden faces (D, L, B) are still seen
  through the stickers they move onto the visible faces.
- One person per server connection; the server holds no state between
  connections.
- Third-party code: [third_party/rubikscolorresolver](third_party/) (MIT).
  Ultralytics YOLO is AGPL-3.0: fine for internal use and this project, but
  shipping a closed product needs an Ultralytics license or a different
  detector.
