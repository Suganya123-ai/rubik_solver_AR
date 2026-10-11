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

## Using it

1. **Start scan** (or ). Hold the cube corner-on so three sides show; it
   captures by itself when you hold still ("✓ Side 1 of 2 captured" + beep).
   Flip it as shown for side 2.
2. **Check colours**: a cube net appears; highlighted stickers were unclear --
   tap one to fix its colour, or confirm (). Then **Solve**.
3. **Hold the cube like in the first scan.** Each move is shown as a green
   arrow on your cube, played on the ghost cube beside it, and written out by
   the side's centre colour ("Turn the blue side clockwise", looking straight
   at that side). Do it and hold still: ✓ and the next move.
4. **Wrong move**: the hand mesh turns red, the ghost cube shows ⚠, and
   "Undo the step" shows the turn that reverses it (red-orange arrow). Undo
   it and the same plan carries on. *New plan instead* () solves again
   from where the cube is.
5. **Solved**: heartbeat line, confetti, and your time / moves / mistakes.

Keys:  scan,  confirm/solve,  or  "I did it" (if the
camera missed a move),  new plan,  stop.

Why colours instead of letters: the webcam faces you, so the camera's
"Front" is the side facing away from you. A side's centre colour never
changes, so "the blue side" means the same from every angle.

## Status

- Done: camera + hand mesh, scanning, solving, ghost cube, guided moves with
  mistake detection and undo, solved screen. Tested end to end with a
  simulated camera (scan, a wrong move, its undo, solved).
- Next (polish): HUD leader-line labels and picture-in-picture inset from the
  reference video, a Three.js ghost cube (the current one is the demo's
  canvas renderer), and tuning on your real camera.
