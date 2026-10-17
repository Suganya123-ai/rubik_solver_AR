# Puzzle Tutor that improves with use (branch `auto-learn`)

The cube and Pyraminx webcam tutors, plus a **self-improving loop**: every week the frames saved during
demos are labelled automatically (checked against the puzzle's known position, no person needed), both
corner models are retrained on them, and the apps switch to a new model only if it tests better.

```
git clone -b auto-learn https://github.com/Suganya123-ai/rubik_solver_AR.git && cd rubik_solver_AR
./run_webcam.sh                        # cube tutor:     http://localhost:5176
./run_pyra.sh                          # Pyraminx tutor: http://localhost:5177
./autolearn/install_schedule.sh        # weekly retraining (nightly check at 03:00)
./autolearn/run_weekly.sh --force      # or a round right now
```

**Voice (branch `laptop-voice`):** both tutors say each step out loud and listen for spoken commands,
as on the glasses (`web/src/voice.ts`, Chrome's speech: click once on the page or press S so Chrome may
use the microphone, and allow it). Say **next** (done), **repeat**, **scan**, **solve**, **new plan**,
**stop**, **quiet** / **speak**, **help**. It doesn't listen while it talks.

How it works, what it checks and where the reports are: [autolearn/README.md](autolearn/README.md).
The other branches' demos (ports 5173-5175, the glasses) are separate and unchanged.
