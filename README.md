# Rubik's Cube Tutor on XREAL AR glasses (branch `phone-standalone`)

The tutor runs **entirely on the XREAL Beam Pro**, with no laptop and no
internet. The glasses' own camera (XREAL Eye) sees the cube in your hands.
The app reads its colours, works out the solution, and guides you move by
move in the glasses: an arrow on your cube marked **x1** or **x2**, a floating
3D copy of the cube, and a warning plus the undo move when you turn the
wrong side. The Beam Pro's screen is the remote control.

**Start here: [README_PHONE.md](README_PHONE.md)** (install once, then how to
start and show the demo, with troubleshooting).

## The other demos (separate branches, unchanged by this one)

| Demo | Branch | How to run |
|---|---|---|
| Webcam AR app, laptop webcam, port 5173 | `ar-webcam` | `git clone -b ar-webcam https://github.com/Suganya123-ai/rubik_solver_AR.git`, then `./run_webcam.sh`, open http://localhost:5173 |
| Glasses with the laptop doing the work (over Wi-Fi) | `xreal-glasses` | see `README_GLASSES.md` on that branch |
| Original demo, port 8000 | `live-solver` (tag `demo-v1`) | `./run.sh` |

This branch also still contains the webcam app's code (its guide is now
[README_WEBCAM_APP.md](README_WEBCAM_APP.md)); the `ar-webcam` branch is the
one to use for the webcam demo.
