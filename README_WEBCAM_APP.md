# Rubik's Cube Tutor — webcam AR app (branch `ar-webcam`)

Hold a scrambled 3x3 cube up to your laptop webcam. The app finds the cube,
reads all its colours from two views, works out a ~20-move solution, then
guides you move by move: an arrow on your real cube, a ghost cube playing the
move, and your hands traced. It checks every move; if you make a wrong one it
tells you and shows the turn that undoes it, then carries on.

> **This branch is separate work.** `main` and the original demo (branch
> `live-solver`, tag `demo-v1`) are not changed by anything here.

## Start here: clone and run the webcam app

You need **Python 3.11+**, **Node.js 20.19+ (or 22.12+)** and Chrome.

```
git clone -b ar-webcam https://github.com/Suganya123-ai/rubik_solver_AR.git
cd rubik_solver_AR
./run_webcam.sh
```

Then open **<http://localhost:5173>** and allow the camera.

- `-b ar-webcam` matters: a plain `git clone` gives you `main`, which is the
  old version. (Already cloned? `git checkout ar-webcam`.)
- The first run sets everything up by itself: a Python environment with
  PyTorch (a large download, several minutes) and the web app's packages.
  Later runs start in a few seconds.
- Open it on the same computer at `localhost:5173`. Through a forwarded port
  or tunnel the camera frames arrive slowly and scanning takes longer.

**Using it**, step by step (scan, check colours, follow the moves, undo a
mistake): see **[README_WEBCAM.md](README_WEBCAM.md)**.

**On the XREAL glasses** (this branch, `xreal-glasses`): the same app opened
in the Beam Pro's browser, with the camera looking your way. See
**[README_GLASSES.md](README_GLASSES.md)**: `./run_glasses.sh`, then open the
address it prints on the Beam Pro.

### What's in this repository

| | Webcam AR app (this branch's main work) | Original demo |
|---|---|---|
| Start | `./run_webcam.sh` | `./run.sh` |
| Open | <http://localhost:5173> | <http://localhost:8000/live> |
| Code | `web/` (the screen) + the Python server | `static/` + the Python server |
| Guide | [README_WEBCAM.md](README_WEBCAM.md) | the rest of this page |

Both use the same Python "vision server" (`main.py`, `vision/`, `cube/`):
it finds the cube (YOLO), tracks hands (MediaPipe), reads colours, solves
(Kociemba) and checks each move. The XREAL glasses app is in
[xreal_ar/](xreal_ar/README.md).

---

# The original demo and the vision server

Everything below describes the original demo page and the shared server.

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
| `RUBIK_PRELOAD` | `1` | Load the models at startup (`0` loads on the first frame; used by CI) |
| `RUBIK_HANDS` | `1` | Hand tracking (`0` turns it off; everything else works the same) |

`GET /health` reports whether the model is loaded and which one.

## Using it (`/live`)

1. **Scan.** Press *Scan & solve*. Hold the cube with Top, Front and Right
   toward the camera and keep it still; it captures automatically. Then turn
   the cube upside down and give it a quarter turn as shown, and hold still
   again.
2. **Check.** The cube net appears. Any sticker the app is unsure about is
   outlined; tap it to confirm or pick the right color. Then *Start solving*.
3. **Solve.** Turn the cube back to the first position. The next move is drawn
   on your cube in the camera picture (the stickers that turn, outlined, and an
   arrow showing which way), and played on a 3D copy of your cube beside it. Do
   it and hold still; a correct move gets a tick.
4. **Mistakes.** If you turn something else, it says what you did and shows
   (in amber) the move that undoes it; once you've undone it, the same plan
   carries on. More than 3 moves off, or *New plan instead*, makes a new plan
   from wherever the cube is. Untick "After a wrong move, show me how to undo
   it" before solving to always get a new plan instead. *I did this move*
   skips a move if the camera can't see it.

**Glasses view** (button, or press `G`; `Esc` to leave): the camera picture
full screen with a heads-up display, as it will look through the XREAL
glasses: the move drawn on your cube, a 3D copy of your cube floating beside
it playing the move, progress, mistake/undo messages, and your hands traced.
While your hands are turning the cube it shows "Turning…" and judges nothing
until you stop; stickers a finger covers are outlined dashed and left out.

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
| Hands | [vision/hands.py](vision/hands.py) | MediaPipe Hand Landmarker (21 points per hand, ~25 ms on CPU, run alongside YOLO): which stickers a finger covers (near a finger *and* skin-coloured, since MediaPipe also guesses fingers hidden behind the cube), and whether the hands are turning the cube. |
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

95 tests: move engine, validation, solver, color handling, hands, the two-view
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
- Third-party code: [third_party/rubikscolorresolver](third_party/) (MIT);
  MediaPipe and its hand model `models/hand_landmarker.task` (Apache-2.0).
  Ultralytics YOLO is AGPL-3.0: fine for internal use and this project, but
  shipping a closed product needs an Ultralytics license or a different
  detector.
