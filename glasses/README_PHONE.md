# Cube Tutor on the phone alone (branch `phone-standalone`)

The glasses tutor with **no laptop and no network**: everything runs in one
Android app on the Beam Pro. Install it once (see **Install** below), then
follow **Showing the demo**. The glasses demo (branch `xreal-glasses`), the
webcam demo (`ar-webcam`) and the original demo (`live-solver`) are not changed.

```
glasses' camera ─► app on the Beam Pro: finds the cube ─► reads colours, scans, solves, follows moves
glasses' screen ◄── tutor page, served by the app to itself ◄──┘
```

**Status (14 Oct 2026): working on the real glasses.** XREAL One Pro + XREAL
Eye camera + Beam Pro (Android 14): 7-13 frames a second, the cube is found,
scanned and the moves guided. Known limits are listed at the end of the next
section.

## Showing the demo (each time)

1. **Clean start.** Unplug the glasses from the Beam Pro, swipe
   **Cube Tutor Phone** away from the recent apps, wait 5 seconds, plug the
   glasses back in. (Do this before every demo: it resets the glasses' camera.)
2. Open **Cube Tutor Phone** on the Beam Pro and tap **Start the tutor**.
3. **Tap OK on every "Allow Cube Tutor Phone to access XREAL One Pro?" box.**
   There are usually two; the second comes a few seconds after the tutor
   screen opens. XREAL's own screens may flash past; that is normal, the
   tutor comes back to the phone by itself.
4. The phone now shows the tutor with **Start scan**; its top bar shows the
   speed (`frames/s · cube in N of M`). The glasses show the tutor too.
   - **Glasses: floating / picture** (top bar) switches the glasses between
     only the floating ghost cube and instructions (black is see-through), and
     the camera picture with the arrows drawn on the cube.
   - **Show camera picture** on the phone page shows the camera on the phone.
5. **Scan.** Tap **Start scan**. Hold the cube **corner-on, three sides
   showing**, about 25-30 cm in front of you, and hold still until it says the
   side is captured. Then turn it to show the other three sides. Check the
   colours on the phone, then **Solve**.
6. **Solve.** Do the move shown (the arrow says **x1** for a quarter turn,
   **x2** for a half turn), then **turn a corner back toward you** and hold
   still for a moment: it ticks the move and shows the next. A wrong move is
   announced with the turn that undoes it.

### If something goes wrong

| What you see | What to do |
|---|---|
| Black screen on the phone and the glasses, no camera | An "Allow … XREAL One Pro?" box is waiting: tap OK. If none shows, wait 15 s (the app asks again). |
| The phone says "The glasses' camera is stuck. Unplug the glasses…" | Do the clean start (step 1). |
| The glasses' camera stops in the middle | The app restarts it by itself within ~15 s; if not, clean start. |
| The cube is not found ("cube in 0 of …") | Hold it corner-on with three sides showing, in good light, 25-30 cm away. It does not recognise a cube held face-on. |
| Slow (under 5 frames/s) | The Beam Pro is hot: let it cool a few minutes. |
| The wrong app opens when the glasses are plugged in | Only one of the two glasses apps can be on: **Cube Tutor Bridge** (the laptop version) is switched off on the demo Beam Pro (`adb shell pm disable-user com.cubetutor.bridge`; `pm enable` to switch it back on). |

### Known limits

- The cube finder only recognises the cube held **corner-on** (it was trained
  on computer-made pictures); after a move, turn a corner back toward you.
  Retraining it on more angles and on this camera's pictures is the next step.
- No hand tracking on the glasses yet.
- The Beam Pro gets hot and slows down after a while.
- XREAL's own software sometimes closes and reopens the tutor screen; the app
  keeps the camera and the tutor running through that.

## What runs where

| Part | Laptop version | In this app |
|---|---|---|
| Finding the cube | PyTorch, 640 px | The same model converted to ONNX at 320 px, run by ONNX Runtime ([CubeFinder.kt](android_phone/app/src/main/java/com/reveng26/xrcam/CubeFinder.kt)). It looks at the whole frame only to find the cube, then at a square around it. |
| Colours, scan, move tracking, undo | Python (`cube/`, `vision/`) | The **same Python files**, run inside the app by Chaquopy; entry point [vision/phone.py](vision/phone.py) |
| Solver | `kociemba` (no Android build) | min2phase, the same two-phase method in Java (`cs.min2phase`, MIT / GPLv3) |
| Page server | `glasses_server.py` | [LocalServer.kt](android_phone/app/src/main/java/com/reveng26/xrcam/LocalServer.kt), reachable only from the phone itself |
| The per-frame loop | bridge app uploads JPEGs | [TutorEngine.kt](android_phone/app/src/main/java/com/reveng26/xrcam/TutorEngine.kt): copy, find, tutor, show; no JPEG, no network |
| Hand tracking | MediaPipe on the laptop | **Not in yet** (the tutor runs without it; fingers over stickers are not masked) |

## Install (once)

Needs the Android SDK, Node.js 20.19+ and **Python 3.10** on the computer that
builds (`brew install python@3.10`; Chaquopy uses it to fetch the Android
builds of NumPy and OpenCV).

```
cd web && npm install && npm run build && cd ..
cd android_phone
./get_xreal_libs.sh          # XREAL's camera libraries (not kept in this repository)
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

It installs as **Cube Tutor Phone**. Turn on **USB debugging** on the Beam Pro
first (Settings ▸ About ▸ tap Build number 7 times, then Developer options ▸
USB debugging) and plug the Beam Pro into the computer for the install; then
unplug it and plug in the glasses. If the laptop version (**Cube Tutor
Bridge**) is also installed, switch it off (`adb shell pm disable-user
com.cubetutor.bridge`): both apps open when the glasses are plugged in.

The status line on the phone shows the speed: `frames/s · cube in N of M ·
copy, find, tutor ms` (the time spent copying the picture, finding the cube,
and in the tutor's Python code).

**Testing from the computer** (taps from `adb` don't reach the app while the
glasses are in use): `adb shell am start -n
com.cubetutor.phone/com.reveng26.xrcam.MainActivity --ez autostart true`
starts the tutor; the latest camera picture the tutor used is saved every 3 s
(`adb exec-out run-as com.cubetutor.phone cat files/last.jpg > last.jpg`).
Don't force-stop or reinstall the app while the camera is running: that leaves
the glasses' camera stuck until they are unplugged.

## Checked on the Beam Pro (self-test, no glasses)

`SelfTest.kt` runs each part on a saved frame from the glasses' camera:

```
adb shell "run-as com.cubetutor.phone sh -c 'cat > files/test.jpg'" < some_frame.jpg
adb shell am start -S -n com.cubetutor.phone/com.reveng26.xrcam.MainActivity --ez selftest true
adb logcat -s SelfTest
```

With the screen awake (a sleeping phone is 5-10 times slower): finding the cube
**27 ms**, the tutor's Python code **7 ms**, so about **28 frames a second**
before the camera and the screen take their share. The cube was found (0.93
sure), the scan took its first view, the solver gave 21 moves, the page was
served. Python takes 2-4 s to start. The phone's neural accelerator (NNAPI) was
9 times slower than its processor for this model, so the processor is used.

## Checked on the laptop

- The converted model against the original on 200 recorded frames from the
  glasses: the zoom-in method found the cube in 50, the original in 39; where
  both did, the corners differ by 2% of the cube's size (median).
- The Python code on Python 3.10 with the phone's NumPy and OpenCV versions:
  the same tests pass as on the laptop (the web-server tests don't apply).
- The Java solver on 20 scrambles: all solved, 21 moves at most.
- `tests/test_phone.py`: the app's entry point.

## To remake the model file

`models/cube_pose_320.onnx` comes from `models/cube_pose_v2.pt`:

```
pip install onnx onnxruntime onnxslim
yolo export model=models/cube_pose_v2.pt format=onnx imgsz=320 opset=17 simplify=True
```
