# Pyraminx Tutor AR (branch `pyraminx`)

The webcam tutor of port 5174, for the **Pyraminx** (the pyramid puzzle): show
it to the camera, it reads the colours, works out the shortest solution and
guides you move by move: an arrow on your real pyramid marked **x1**, a ghost
pyramid playing the move, a warning plus the undo move when you turn the
wrong corner, then the same plan carries on.

This branch is separate: the cube apps (`ar-webcam` on 5173, `webcam-anyside`
on 5174, the original demo, the glasses) are not changed. It runs on its own
ports, so it can run beside them.

```
git clone -b pyraminx https://github.com/Suganya123-ai/rubik_solver_AR.git
cd rubik_solver_AR
./run_pyra.sh            # then open http://localhost:5175/pyra.html  (vision server on 8102)
```

## Using it

1. **Start scan.** Hold the pyramid with **a corner pointing at the camera**,
   so three faces show, and hold still: "3 of 4 faces scanned".
2. **Point another corner at the camera** (any one), so the fourth face comes
   into view: "4 of 4" and the colour check.
3. **Check colours.** The 4 faces are drawn as triangles; highlighted
   stickers were unclear: tap one to change its colour, or confirm.
4. **Follow the moves.** "Turn the top corner" (the tip and the layer under
   it, a third of a turn) or "Twist the tip of …" (only the small tip), as the
   arrow shows, then hold still: ✓ and the next move. At most 11 turns plus
   up to 4 tip twists.
5. **Wrong move:** "Undo the step" with the turn that reverses it; more than
   3 off, or *New plan instead*, gives a new plan from where the puzzle is.

Keys: `S` scan, `Enter` confirm/solve, `→` "I did it", `N` new plan, `Esc` stop.

## How it works

| Part | How | Code |
|---|---|---|
| Geometry and moves | The 36 stickers in 3D; each move worked out by rotating them about a corner (WCA notation, tips included) | `pyra/geometry.py`, `pyra/model.py` |
| **Solver** | A table of **every** position's distance to solved (933,120, built in ~4 s, matches the published distribution exactly: God's number 11). Solutions are always the **shortest**; of the equally short ones, the **easiest to follow** (fewest changes of corner); tips last. Checked against [PyraminXolver](https://github.com/Odder/PyraminXolver) on 300 scrambles: same length every time | `pyra/solver.py` |
| Finding the pyramid | A YOLO pose model (4 corners: the near one, then clockwise from the highest), fine-tuned from the cube model on 6,000 rendered pictures (angles, near and far, hands, blur, light, empty pictures) | `bench/render_pyra.py`, `bench/make_pyra_data.py`, `bench/run_pyra_training.sh`, `models/pyra_pose_v1.pt` |
| Reading stickers | The 4 corners place the three faces; each of the 27 stickers in view is the median of its middle | `pyra/view.py` |
| Scan | Views from any corner; each new one is placed by the colours it shares with what is scanned; stickers seen twice are averaged | `pyra/scan.py` |
| **Colours** | Grouped into 4 x 9 by hue, then **the possible position (933,120 x 81 tip turns) that best matches all 36 colours**: a finger or glare on a few stickers can't give an impossible puzzle; corrected pieces are highlighted | `pyra/colours.py` |
| Move tracking | Every still view is compared with how the puzzle would look after each of the 16 possible moves, held any of 12 ways; decided on the stickers that differ; "wrong move" needs stronger evidence than "correct" | `pyra/tracker.py` |
| Server and app | Same protocol as the cube app; the page reuses its camera, hand mesh, HUD and cards, with a ghost pyramid, arrows and a 4-face colour check | `main_pyra.py`, `pyra/live.py`, `web/pyra.html`, `web/src/pyra/` |

## Tests

- `python -m pytest tests/test_pyra.py`: moves, the solver (distribution, shortest solutions, tips).
- `cd bench && PYTHONPATH=.. python bench_pyra_e2e.py normal|hard|real 15`: rendered scans and guided
  solves with a deliberate wrong move (14 Oct 2026: scans 45/45, wrong move caught 42/45, no false
  "wrong move" calls).
- `cd bench && PYTHONPATH=.. python make_pyra_video.py out.y4m`: a test video for Chrome's fake camera
  (scan, a wrong move and its undo, the solve).

## Not done yet

- Trained on rendered pyramids only: real frames from your puzzle (the app can record them) would
  make finding it more reliable, as they did for the cube.
- No hand masking: fingers on stickers are handled by the colour decoding and by waiting for still,
  clear views.
