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

1. **Start scan.** Hold the pyramid **tip up, with an edge pointing at the camera**, so two whole
   faces show (like a tent), and hold still: "2 of 4 faces scanned". While scanning, the sticker grid
   is drawn on your pyramid, each sticker filled with the colour the camera reads there.
2. **Turn it around** so the other two faces show, again tip up with an edge toward the camera:
   "All 4 faces scanned" and the colour check. Showing the same faces again is refused ("already
   scanned"); there is no need to show the bottom on its own.
3. **Check colours.** The 4 faces are drawn as triangles; highlighted stickers were unclear: tap one
   to change its colour, or confirm.
4. **Follow the moves.** On your pyramid: the part to turn **lights up**, a dashed outline **shows it
   turning**, and an arrow marked **x1** goes the way to turn. The card says it in words from what you
   see: "Turn the top corner to the right", "Twist the tip of the left corner up". Then hold still:
   ✓ and the next move. At most 11 turns plus up to 4 tip twists. You can keep holding it edge-on
   (or corner-on: both are followed).
5. **Wrong move:** "Undo the step" with the turn that reverses it; more than 3 off, or *New plan
   instead*, gives a new plan from where the puzzle is.

Keys: `S` scan, `Enter` confirm/solve, `→` "I did it", `N` new plan, `Esc` stop.

## How it works

| Part | How | Code |
|---|---|---|
| Geometry and moves | The 36 stickers in 3D; each move worked out by rotating them about a corner (WCA notation, tips included) | `pyra/geometry.py`, `pyra/model.py` |
| **Solver** | A table of **every** position's distance to solved (933,120, built in ~4 s, matches the published distribution exactly: God's number 11). Solutions are always the **shortest**; of the equally short ones, the **easiest to follow** (fewest changes of corner); tips last. Checked against [PyraminXolver](https://github.com/Odder/PyraminXolver) on 300 scrambles: same length every time | `pyra/solver.py` |
| Finding the pyramid | A YOLO pose model (4 corners: the near one, then clockwise from the highest), fine-tuned from the cube model on 6,000 rendered pictures (v1), then trained further on very unclear pictures, pyramids in real hands and 3x3 cubes as counter-examples (v2, see below) | `bench/render_pyra.py`, `bench/make_pyra_data.py`, `bench/make_pyra_hard.py`, `bench/make_pyra_real_hands.py`, `bench/run_pyra_training.sh`, `bench/run_pyra_training_v2.sh`, `models/pyra_pose_v2.pt` |
| Reading stickers | The model also says how it is held: **edge-on** (two faces, 18 stickers) or corner-on (three faces, 27). The 4 corners place the faces; each sticker is the median of its middle | `pyra/view.py`, `pyra/live.py` |
| Scan | Two edge-on views. The second shares no sticker with the first, so how it was turned (2 ways) is decided by decoding both: only the right one gives a possible Pyraminx that matches the colours well. A view showing faces already scanned is placed by their colours ("already scanned") | `pyra/scan.py` |
| **Colours** | Grouped into 4 x 9 by hue, then **the possible position (933,120 x 81 tip turns) that best matches all 36 colours**: a finger or glare on a few stickers can't give an impossible puzzle; corrected pieces are highlighted | `pyra/colours.py` |
| Move tracking | Every still view is compared with how the puzzle would look after each of the 16 possible moves, held any of 12 ways (edge-on or corner-on); decided on the stickers that differ; "wrong move" needs stronger evidence than "correct" | `pyra/tracker.py` |
| Server and app | Same protocol as the cube app; the page reuses its camera, hand mesh, HUD and cards, with a ghost pyramid, arrows and a 4-face colour check | `main_pyra.py`, `pyra/live.py`, `web/pyra.html`, `web/src/pyra/` |

## Tests

- `python -m pytest tests/test_pyra.py`: moves, the solver (distribution, shortest solutions, tips).
- `cd bench && PYTHONPATH=.. python bench_pyra_edge_e2e.py normal|hard|real 15`: the edge-on scan (two
  faces, the same again: refused, then the other two) and guided solves seen edge-on with a
  deliberate wrong move (16 Oct 2026: scans right 44/45, same faces refused 45/45, wrong move caught
  44/45, solves to the end 42/45, 1 false "wrong move" call in about 450 moves). A "wrong move" needs at
  least 2 changed stickers in view: held edge-on, a far corner's tip shows one small sticker at the
  outline, and a misread there once stopped a solve.
- `cd bench && PYTHONPATH=.. python bench_pyra_e2e.py normal|hard|real 15`: the earlier corner-on scan
  (runs against commit 99e9b79; the scan now takes edge-on views only) and guided
  solves with a deliberate wrong move (14 Oct 2026: scans 45/45, wrong move caught 42/45, no false
  "wrong move" calls).
- `cd bench && PYTHONPATH=.. python make_pyra_video.py out.y4m`: a test video for Chrome's fake camera
  (scan, a wrong move and its undo, the solve); `EDGE=1` makes it edge-on, as the scan now asks. With
  `models/pyra_pose_v3.pt`, edge-on (16 Oct 2026): every sticker read clearly, wrong move caught and
  undone, 8 moves followed, solved.

### The pyramid finder

**v1** (`models/pyra_pose_v1.pt`, 15 passes, ~1h40 on an M1 Pro): 6,000 rendered pictures.

**v3** (`models/pyra_pose_v3.pt`, the one the app uses; v2 trained 8 more passes, ~2h): also tells
**how it is held**: edge-on (class 1, the scan's hold) or corner-on (class 0). Adds 6,050 edge-on
renders (normal to extreme, half of them standing on the base seen from above, as people hold it,
fingers across) and 1,127 edge-on pyramids drawn into the real frames (`make_pyra_edge.py`,
`EDGE=1 make_pyra_real_hands.py`, `run_pyra_training_v3.sh`). On test pictures it never trained on
(16 Oct 2026):

| Test | v2 | v3 |
|---|---|---|
| Edge-on renders: found / hold told right / corner error | 60% / - / 101% (useless) | 99.6% / 99.6% / 4.7% |
| Edge-on in real hands: found / hold told right / corner error | 39% / - / 98% | 100% / 100% / 3.5% |
| Corner-on renders / very unclear / in real hands: found | 99.8% / 99.6% / 100% | 99.4% / 99.6% / 100% |
| Cubes taken for a pyramid (rendered, real frames, other unseen) | 0/100, 0/62, 60/310 | 0/100, 0/62, 49/310 |
| Empty pictures with a pyramid imagined | 0 of 119 | 2 of 119 |
| The user's two photos of their real Pyraminx (edge-on) | not found | found, edge-on, corners within 3-8% |

The two real photos, through the whole app (model corners, scan, decoding): the right position
(the same as with corners placed by hand), valid, 5 stickers highlighted to check (all read right).

**v2** (`models/pyra_pose_v2.pt`; v1 trained 10 more passes): adds
- 2,500 pyramids in the hardest conditions (heavy blur and motion, very dark or bright, colour casts,
  noise, strong compression, up to four fingers across, steep angles) and 1,000 rendered 3x3 cubes
  marked "not a pyramid" (`make_pyra_hard.py`);
- **pyramids in real hands**: real frames from the cube apps' recordings (your hands, real light, the
  webcam and glasses cameras); the cube is painted out, a pyramid is drawn in its place and the real
  fingers in front of it are put back; the original frames are kept as "not a pyramid"
  (`make_pyra_real_hands.py`, ~1,700 pictures);
- half of v1's renders, so it doesn't forget them.

On test pictures neither model trained on (16 Oct 2026):

| Test | v1 | v2 |
|---|---|---|
| Original renders: found / corner error (median) | 99.6% / 2.5% | 99.8% / 2.6% |
| Very unclear renders: found / corner error | 98.8% / 3.5% | 99.6% / 3.2% |
| Pyramids in real hands: found / corner error | 100% / 1.8% | 100% / 1.7% |
| Rendered cubes taken for a pyramid | 98 of 100 | 0 of 100 |
| Real cube frames taken for a pyramid | 53 of 62 | 0 of 62 |
| Other unseen cubes (110 real, 200 rendered) taken for a pyramid | 264 of 310 | 60 of 310 |
| Empty pictures with a pyramid imagined | 0 of 119 | 0 of 119 |

Open-source photos: very few usable ones exist. Wikimedia Commons gave 22 (most of them other
puzzles or diagrams; 2 real Pyraminx photos, v2 finds 1); Openverse was unreachable; the 11k Hands
dataset was not used (academic use only). Those 22 are only used for testing.

## Not done yet

- The pyramids it trained on are drawn, even the ones in real hands: real frames from your own
  puzzle (the app can record them) would make finding it more reliable, as they did for the cube.
- A 3x3 cube is still taken for a pyramid in about 1 picture in 6 it has never seen.
- Tested on two real photos only; a recording of your own puzzle (scan and moves) would show more,
  and those frames could train the next model.
- Held edge-on, a tip twist at a far corner shows on one small sticker: if one isn't picked up, hold
  that corner nearer the camera, or press "I did it".
- No hand masking: fingers on stickers are handled by the colour decoding and by waiting for still,
  clear views.
