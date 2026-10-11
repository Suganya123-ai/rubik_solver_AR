# Cube Tutor AR — laptop webcam (branch `ar-webcam`)

An AR-glasses-style Rubik's cube tutor on a laptop webcam, after the
reference concept video: the mirrored camera picture full screen, a glowing
hand mesh, a wireframe box on the cube, a floating ghost cube, arrows on the
real cube, mistake warnings with "undo the step", and a sci-fi HUD.

This lives on its own branch so the original demo is never touched:

| | Original demo | This app |
|---|---|---|
| Branch | `live-solver` (tagged `demo-v1`) | `ar-webcam` |
| Folder | `rubik_solver_AR/` | `rubik_solver_AR_webcam/` (a git worktree) |
| Start | `./run.sh` | `./run_webcam.sh` |
| Open | http://localhost:8000/live | http://localhost:5173 |

The vision (cube corners, colour reading, solving, move tracking, undo) is the
same Python server as the demo; this branch adds a new front end in `web/`.

## Run

Needs Python 3.11+ and Node 20+.

```
./run_webcam.sh
```

It starts this branch's vision server on port 8100 (reusing the demo's Python
environment if there is one) and the web app on http://localhost:5173. Allow
camera access.

URL options: `?hands=cpu` runs hand tracking on the CPU (if the GPU version
misbehaves), `?hands=off` turns it off.

## Code (`web/src`)

| File | Job |
|---|---|
| `camera.ts` | Opens the webcam (1280x720). |
| `view.ts` | Maps video pixels to the mirrored full-screen picture; every overlay uses it. |
| `handTracking.ts` | MediaPipe Hand Landmarker in the browser (21 points per hand), adaptive so rendering stays smooth. |
| `serverLink.ts` | WebSocket to the vision server: one JPEG in flight at a time. |
| `cubeView.ts` | The cube's 7 corners from the server, eased between replies. |
| `overlay/` | Canvas drawing: `handMesh.ts`, `cubeBox.ts`, `theme.ts`; `hud.ts` for the text parts. |
| `appState.ts` | The app's stage (camera, scan, review, guided, undo, solved). |

## Milestones

1. **Camera + hand mesh** — done: mirrored full-screen camera, glowing hand
   mesh, cube wireframe box with label, live readouts, "hold the cube steady
   inside the box" hint when the cube isn't found.
2. Face scanning (two views, guided, fix stickers).
3. Solver + ghost cube (Three.js).
4. Guided moves with mistake detection and undo.
5. Polish: HUD details, picture-in-picture, heartbeat + confetti, stats.
