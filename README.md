# AR Puzzle Tutor — latest version (branch `latest`)

Everything newest, in one place. A camera finds the puzzle, reads its colours, works out the solution
and guides you move by move, catching mistakes; it **talks you through each step**, **listens for spoken
commands**, and **answers spoken questions**. A weekly loop retrains the puzzle finders on frames saved
during demos.

```
git clone -b latest https://github.com/Suganya123-ai/rubik_solver_AR.git && cd rubik_solver_AR
./start.sh             # cube tutor on the laptop webcam      -> http://localhost:5176
./start.sh pyramid     # Pyraminx tutor                       -> http://localhost:5177
./start.sh both        # both
./start.sh glasses     # build the glasses app; add --install to put it on the Beam Pro (glasses unplugged)
```

| Part | Where | What | Guide |
|---|---|---|---|
| Cube tutor, laptop | top level, port 5176 | Webcam, any-side scan, arrows, undo, voice, **assistant** (questions, solve report), self-improving | [README_AUTOLEARN.md](README_AUTOLEARN.md), [README_ANYSIDE.md](README_ANYSIDE.md) |
| Pyraminx tutor, laptop | top level, port 5177 | Two-view edge-on scan, lit-up part to turn, wrong-way fix, voice | [README_PYRAMINX.md](README_PYRAMINX.md) |
| Self-improving loop | `autolearn/` | Auto-labels demo frames, retrains weekly, switches only if better | [autolearn/README.md](autolearn/README.md) |
| Cube tutor, glasses only | `glasses/` | XREAL glasses + Beam Pro, no laptop: faster finder (8-bit model, corner following), voice | [glasses/README_VOICE.md](glasses/README_VOICE.md) |

**Voice:** say *scan*, *solve*, *next* (the move is done), *repeat*, *new plan*, *stop*, *quiet* / *speak*,
*help*; or ask: *why this move?*, *what did I do wrong?*, *how many moves are left?* The laptop uses
Chrome's speech (click the page once if the indicator at the top asks); the glasses use Android's.

**Assistant:** a language model answers questions from the tutor's real state only, and never decides a
move. Set it up once in `~/.cube_tutor_llm.env` (Azure OpenAI: `AZURE_OPENAI_API_KEY`,
`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`; never in git), or run
a local Ollama model; without one, everything else works. See `vision/assistant.py`.

**Why two code lines:** the laptop tutors and the glasses app grew from different starting points (the
glasses page has its own camera handling and wording), so the glasses version sits in `glasses/` as it
was tested. Merging their shared code is later work. The older branches (`live-solver`, `ar-webcam`,
`webcam-anyside`, `pyraminx`, `auto-learn`, `xreal-glasses`, `phone-standalone`, `glasses-fast`,
`voice`, `laptop-voice`, `assistant`) are unchanged.

Not in git (on purpose): camera recordings and training data (`data/`, `bench/data/`), the XREAL
libraries, the Android SDK path, built web pages, the assistant's key.
