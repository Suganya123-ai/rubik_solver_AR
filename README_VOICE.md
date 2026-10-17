# Cube Tutor on the glasses: faster, and with a voice (branch `voice`)

The glasses-only tutor (no laptop: everything runs on the Beam Pro) from branch `glasses-fast`, plus a
voice: it **says each step out loud** and **listens for spoken commands**, so your hands stay on the cube.
It installs as its own app, **Cube Tutor Fast** (`com.cubetutor.phonefast`), beside the demo app
(Cube Tutor Phone, branch `phone-standalone`), which it doesn't change.

## Using it

Only one glasses app can answer when the glasses are plugged in: switch the other one off first
(`adb shell pm disable-user --user 0 com.cubetutor.phone`; back on with `pm enable`).

1. Plug the glasses into the Beam Pro, put them on. The tutor opens on the glasses and talks through
   their speakers.
2. Say **"scan"** and hold the cube up as it asks (two corner-on views, then the sides not seen yet).
3. At the colour check say **"solve"**.
4. It says each move: "Move 3 of 18. Turn the green side, facing you. Its top edge moves to your left."
   Do it and hold the cube still: "Correct" and the next move. A wrong move: what to undo.

| Say | Does |
|---|---|
| next, done, I did it | the move is done (when the camera missed it) |
| repeat, again, what | says the step again |
| scan / solve / new plan / stop | as the buttons |
| quiet / speak | voice off / on |
| help | lists the commands |

How: `web/src/voice.ts` (the page: what is said and when, the commands) and
`android_phone/.../TutorVoice.kt` (Android's text-to-speech and speech recognition, on the phone
itself; one voice for the whole app, owned by the glasses' page). The microphone is off while the
tutor talks (it would cut the voice off and hear its own words); one long listening session
(Android 13+) keeps it on otherwise. In a browser (the laptop app) the same page uses the Web Speech API.

## Faster (from `glasses-fast`)

Measured on the Beam Pro (Snapdragon 6 Gen 1), 17 Oct 2026:

| | Before | Now |
|---|---|---|
| Cube finder model | v2, 320 px | v3, 256 px, 8-bit (`models/cube_pose_v3_256_int8.onnx`) |
| One look, phone idle | 25.8 ms | 11.1 ms |
| Real glasses frames the cube was found in (600) | 93 | 132 |
| Model runs while the cube is followed | every frame | every 3rd (corners followed in between) |
| Tutor (Python) a frame, cube in view | ~37 ms | ~27 ms |
| Frames a second, glasses in use | 7-13 | 11-16 |

The phone's neural engine (NNAPI) was 15x slower than the processor and XNNPACK slower too: the
processor is used. With the glasses running, XREAL's software and the system leave ~20% of the
processor free, so a look that takes 11 ms on an idle phone takes 50-90 ms; that, not the camera
(30 frames a second), is the limit. Next: the cube finder on the GPU (TensorFlow Lite GPU), off the
crowded processor.

Also: the steadier scan from `webcam-anyside` (fixes "5 of 6 sides" when all were shown), "Solved!"
when the cube in view is plainly finished even if a move was missed, the camera's picture sizes in the
log, and `files/finder.txt` (model=, every=, threads=, spin=) re-read while running.

## Build and install

As `README_PHONE.md` (the XREAL libraries and `web/dist` are not in git): `cd web && npm run build`,
then `cd android_phone && ./gradlew assembleDebug`, `adb install -r app/build/outputs/apk/debug/app-debug.apk`.
Unplug the glasses before installing (installing while the camera runs leaves it stuck until replugged).
