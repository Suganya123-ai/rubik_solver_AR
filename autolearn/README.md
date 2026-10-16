# Self-improving loop (branch `auto-learn`)

Every demo makes the puzzle finders better, with no manual labelling. Once a week the laptop labels
the frames the apps saved during demos, retrains the cube and Pyraminx corner models on them, and
switches the apps to a new model **only if it tests better**.

```
./autolearn/install_schedule.sh          # once: runs every night at 03:00, does the work weekly
./autolearn/run_weekly.sh --force        # a round now (about an hour for both puzzles)
./autolearn/install_schedule.sh --remove # stop it
```

The apps on this branch use whichever model the loop last switched to: cube `./run_webcam.sh`
(http://localhost:5176), Pyraminx `./run_pyra.sh` (http://localhost:5177). Their own ports, so the
demos on 5173-5175 are untouched. `models/current.json` says which model is in use; delete it to go back
to the built-in models (cube v3, Pyraminx v3).

## How a frame gets a label without a person

The apps know the puzzle's position at every moment (the scan, then each move followed), and save it
with the frames. For each saved frame:

1. **Many looks.** The current model looks at the whole picture, the picture mirrored, and zoomed-in
   crops around where the puzzle was ([teacher.py](teacher.py)).
2. **Same corner order as training,** from the picture itself ([canon.py](canon.py)): cube top face
   first then clockwise; Pyraminx near corner (or near edge) first.
3. **The looks must agree:** at least 2 put every corner within 7% of the puzzle's size of each other;
   the label is their average ([label.py](label.py)).
4. **The colours must agree:** the stickers read at those corners must match the known position, held
   some way, now or after the move the user was asked for: at least 80% of the stickers in view, at
   least half around every corner (or on every face), and one way of holding it clearly best
   ([verify.py](verify.py)).

Frames that fail are skipped, not guessed: mid-turn frames, hands over the puzzle, frames from a
session where the app itself had lost track. Frames the live model **missed** but the closer look
finds and the colours confirm are the most valuable: they count three times in training.

Tests on drawn pictures (`tests/test_autolearn.py`): the corner order is never wrong (an unclear frame
is skipped); right corners pass the colour check, corners in the wrong place almost never do.

## A round ([retrain.py](retrain.py))

| Step | What |
| --- | --- |
| Label | Only new frames, and frames an older model couldn't label (cached in `data/autolearn/labels/`) |
| Set aside | One stretch of 40 frames (~20 s) in 5, by a fixed hash: never trained on, the real test |
| Train | From the model in use, 5 passes: the real labelled frames, the other puzzle's real frames as "nothing here", 4,000 earlier training pictures (so nothing is forgotten) |
| Test | Old and new model on the real frames set aside (found; how well the stickers at its corners match the known position), the other puzzle's frames set aside (false finds), and 300 drawn test pictures per set (found, corner error, false finds) |
| Whole solves | If it passes: a whole guided solve with each model ([e2e.py](e2e.py)). Pyraminx: 3 test videos replayed through the app's scan and move tracking, every call checked against when the move is on screen. Cube: the move-tracking test (`bench/bench_tracking.py`) |
| Switch | Only if no worse anywhere (drawn pictures found within 1 point, corner error within 0.3, false finds within 1 point, colour match within 0.01, no more whole-solve problems, no more moves judged wrong) **and** better on the real frames, with at least 25 real test frames |
| Report | `data/autolearn/reports/<date>-<puzzle>.md` and `history.jsonl`, plus a notification |

It skips a round with fewer than 30 new labelled frames, when the laptop is on battery, or when a demo
is running (it tries again the next night). Log: `data/autolearn/logs/`.

Why corner placement on real frames is judged by colours: the real labels are made from the model in
use, so distance to them always favours it. The drawn pictures, with their true corners, measure corner
error; the colours measure, without labels, whether a model's corners sit on the right stickers.

## First round (17 Oct 2026)

| | Pyraminx | Cube |
| --- | --- | --- |
| Saved frames with a known position | 806 | 1,725 |
| Labelled automatically | 296 (10 the live model had missed) | 243 (21 the live model had missed) |
| Real frames found, in use -> new | 98.5% -> 100% | 100% -> 100% |
| Stickers matching at the corners | 0.873 -> 0.886 | 0.929 -> 0.926 |
| Drawn pictures: corner error | 3.87% -> 3.51% | 2.95% -> 3.48% |
| Other puzzle taken for this one | 0% -> 0% | 7.6% -> 0% |
| Whole guided solves: problems | 24 -> 3 | (not run: failed earlier tests) |
| Outcome | **Switched** to `pyra_pose_auto_20261017.pt` | **Kept** v3: drawn corner error worse, and only 12 real test frames (25 needed) |

Few real test frames so far (66 Pyraminx, 12 cube): small differences there are a frame or two. They
grow with every demo; the cube's will grow faster once demos are run on this branch's cube app.

## Where the frames come from

Every app folder on this laptop (read only): `rubik_solver_AR_webcam`, `_anyside`, `_glasses`,
`_pyraminx` and this one (`AUTOLEARN_APPS` to change). Pyraminx frames: `data/pyra_sessions/`
(saved by every session). Cube frames: `data/sessions/` (saved while solving: every judged frame, and
one missed frame every 2 s). Test videos of drawn puzzles are excluded (`config.EXCLUDE`, or
`data/autolearn/exclude.txt`). All of it stays on this laptop; none of it goes to git.
