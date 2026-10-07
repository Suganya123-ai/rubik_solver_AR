# Rubik's Cube Solver

Scan all 6 faces of a physical 3x3 cube with your webcam, then get guided,
one-move-at-a-time instructions (with a diagram) to solve it.

## Run it

```
pip install -r requirements.txt   # fastapi, uvicorn, pillow, numpy -- no other deps
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open the forwarded URL for port 8000 in your browser. Camera access requires
a secure context (localhost is fine; some remote-tunnel URLs may need HTTPS).

## Using it

1. **Scan**: for each of the 6 faces (prompted in order: Top, Front, Bottom,
   Back, Left, Right), hold that face up to the camera inside the on-screen
   guide square and hit Capture. Detected colors are shown on a 3x3 grid --
   click any square to correct it from the palette before confirming.
2. **Solve**: once all 6 faces are confirmed, you'll see one move at a time
   (e.g. "R", turn clockwise) with a diagram highlighting which face and
   which direction. Perform it on your physical cube, then tap "Done, next
   move". Use Back to redo the previous instruction.
3. If the scan turns out to be physically impossible (a misread sticker),
   you'll get an error explaining what's wrong and be sent back to re-scan.

## How it's built

- `cube/moves.py` -- the move engine: a 3D-coordinate model of the 26
  non-center cubies, from which all 18 quarter/half turns are derived as
  precomputed sticker permutations.
- `cube/validation.py` -- checks a scan is a physically legal cube state
  (right color counts, no impossible corners/edges, correct permutation and
  orientation parity) before attempting to solve it.
- `cube/solver.py` -- solves first two layers (cross, corners, middle-layer
  edges) via a small bounded search against the real move engine, then
  finishes the last layer with a handful of standard, empirically verified
  commutators (they don't disturb the solved layers below, by construction).
  Move counts run 60-150ish moves (not move-optimal like a full two-phase
  solver -- irrelevant here since a human executes each move anyway).
- `cube/color_detect.py` -- classifies each of the 9 stickers per photo by
  HSV thresholds (Pillow + numpy only; OpenCV isn't available in this
  environment).
- `main.py` -- FastAPI routes tying it together; `static/` is the vanilla
  HTML/CSS/JS frontend (no build step, no CDN dependency).

## Tests

```
python3 tests/test_moves.py
python3 tests/test_validation.py
python3 tests/test_solver.py
python3 tests/test_color_detect.py
```

`test_solver.py` is the main correctness gate: it scrambles a solved cube,
runs the solver, replays the solution, and asserts the result is solved
again -- across 300+ scrambles including edge cases (already solved, every
single-move scramble, 2-generator scrambles).
