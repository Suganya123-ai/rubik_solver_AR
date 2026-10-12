# Cube Tutor AR — laptop webcam (branch `ar-webcam`)

An AR-glasses-style Rubik's cube tutor on a laptop webcam, after the
reference concept video: the mirrored camera picture full screen, a glowing
hand mesh, a wireframe box on the cube, a floating ghost cube, arrows on the
real cube, mistake warnings with "undo the step", and a sci-fi HUD.

This lives on its own branch so the original demo is never touched:

| | Original demo | This app |
|---|---|---|
| Branch | `live-solver` (tagged `demo-v1`) | `ar-webcam` |
| Start | `./run.sh` | `./run_webcam.sh` |
| Open | http://localhost:8000/live | http://localhost:5173 |

The vision (cube corners, colour reading, solving, move tracking, undo) is the
same Python server as the demo; this branch adds a new front end in `web/`.

## Run

Needs Python 3.11+, Node.js 20.19+ (or 22.12+) and Chrome.

```
git clone -b ar-webcam https://github.com/Suganya123-ai/rubik_solver_AR.git
cd rubik_solver_AR
./run_webcam.sh
```

Open http://localhost:5173 and allow camera access. The script starts this
branch's vision server on port 8100 and the web app on port 5173. The first
run creates a Python environment and installs everything (PyTorch is a large
download); if the demo's environment is in a folder next to this one, it is
reused instead. To use a particular Python: `RUBIK_PYTHON=/path/to/python ./run_webcam.sh`.

URL options: `?hands=cpu` runs hand tracking on the CPU (if the GPU version
misbehaves), `?hands=off` turns it off.

## Code (`web/src`)

| File | Job |
|---|---|
| `main.ts` | Starts everything and draws each frame. |
| `flow.ts` | The tutor's stages: scan, colour check, guided moves, undo, solved. |
| `moveText.ts` | Turns a move into words from the user's seat ("the green side (facing you)…"). |
| `camera.ts` | Opens the webcam (1280x720). |
| `view.ts` | Maps video pixels to the mirrored full-screen picture; every overlay uses it. |
| `handTracking.ts` | MediaPipe Hand Landmarker in the browser (21 points per hand), adaptive so rendering stays smooth. |
| `serverLink.ts` | WebSocket to the vision server: one JPEG in flight at a time, smaller frames on a slow link. |
| `cubeView.ts` | The cube's 7 corners from the server, eased between replies. |
| `cube3d.js` | The ghost cube and the move arrows on the real cube (copied from the demo). |
| `overlay/` | Canvas drawing: hand mesh, cube box, move arrows, check/heartbeat/confetti; `hud.ts` for the text parts. |
| `appState.ts` | The app's current stage. |

The vision server it talks to is the Python code in this repository
(`main.py`, `vision/`, `cube/`); its messages are described in
[docs/PROTOCOL.md](docs/PROTOCOL.md).

## Using it

1. **Start scan** (or `S`). Hold the cube with a corner pointing at the
   camera, so three sides show. It captures by itself when you hold still:
   "✓ Side 1 of 2 captured" and a beep.
2. **Show the other three sides.** Turn the cube so the corner that was
   pointing away from the camera points at it. The card shows the three
   centre colours already scanned: those sides must not face the camera. Any
   way of holding that corner works. If an old side is showing, it says where
   ("the side on the right was already scanned").
3. **Check colours.** A cube net appears; highlighted stickers were unclear:
   tap one to fix its colour, or confirm (`Enter`). Then **Solve**.
4. **Follow the moves.** Hold the cube corner-on, however you like: the app
   follows it. Each move is a green arrow on your cube, played on the ghost
   cube beside it (drawn as you see it), and written from where you sit:
   "Turn the green side (facing you): its top edge moves to your left". Do
   it and hold still for about half a second: ✓, a beep and the next move.
5. **Wrong move.** The hand mesh turns red, the ghost cube shows ⚠, and
   "Undo the step" shows the turn that reverses it (red-orange arrow). Undo
   it and the same plan carries on. *New plan instead* (`N`) solves again
   from where the cube is.
6. **Solved.** Heartbeat line, confetti, and your time / moves / mistakes.

Keys: `S` scan, `Enter` confirm/solve, `→` or `Space` "I did it" (if the
camera missed a move), `N` new plan, `Esc` stop.

Tips: good, even light; keep three sides visible (a hint appears if the cube
is held too face-on); open the app at `localhost:5173` on the same computer.

Why colours and "your left" instead of letters like R and F: the webcam
faces you, so it sees the cube from the opposite side. The camera's "Front"
is the side facing away from you. Centre colours and directions from your
seat mean the same thing whichever way you look at it.

## Recordings (on your computer only)

To help fix problems, each scan and solving session is saved under `data/`
(`data/scans/`, `data/sessions/`): the camera frames used and what was
decided. They are never committed (see `.gitignore`). `RUBIK_RECORD=0
./run_webcam.sh` turns this off.

## Status

- Working end to end with a simulated camera (scan, a wrong move, its undo,
  solved) and 95 automated tests (`python -m pytest -q`).
- Still being tuned on real cubes and lighting.
- Not done yet from the concept video: HUD labels with leader lines, the
  picture-in-picture inset, a Three.js ghost cube (the current one is the
  demo's canvas renderer).
