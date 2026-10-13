# Cube Tutor on the phone alone (branch `phone-standalone`)

The glasses tutor with **no laptop and no network**: everything runs in one
Android app on the Beam Pro. The glasses demo (branch `xreal-glasses`), the
webcam demo (`ar-webcam`) and the original demo (`live-solver`) are not changed.

```
glasses' camera ─► app on the Beam Pro: finds the cube ─► reads colours, scans, solves, follows moves
glasses' screen ◄── tutor page, served by the app to itself ◄──┘
```

**Status (14 Oct 2026): builds, not yet run on the Beam Pro.** The parts were
checked on the laptop (below); the first run on the device is the next step.

## What runs where

| Part | Laptop version | In this app |
|---|---|---|
| Finding the cube | PyTorch, 640 px | The same model converted to ONNX at 320 px, run by ONNX Runtime ([CubeFinder.kt](android_phone/app/src/main/java/com/reveng26/xrcam/CubeFinder.kt)). It looks at the whole frame only to find the cube, then at a square around it. |
| Colours, scan, move tracking, undo | Python (`cube/`, `vision/`) | The **same Python files**, run inside the app by Chaquopy; entry point [vision/phone.py](vision/phone.py) |
| Solver | `kociemba` (no Android build) | min2phase, the same two-phase method in Java (`cs.min2phase`, MIT / GPLv3) |
| Page server | `glasses_server.py` | [LocalServer.kt](android_phone/app/src/main/java/com/reveng26/xrcam/LocalServer.kt), reachable only from the phone itself |
| The per-frame loop | bridge app uploads JPEGs | [TutorEngine.kt](android_phone/app/src/main/java/com/reveng26/xrcam/TutorEngine.kt): copy, find, tutor, show; no JPEG, no network |
| Hand tracking | MediaPipe on the laptop | **Not in yet** (the tutor runs without it; fingers over stickers are not masked) |

## Build and install

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

It installs as **Cube Tutor Phone**, beside the bridge app. Use it like the
bridge app (plug in the glasses, OK the USB prompt, **Start the tutor**, OK
again), without the address box. The status line on the phone shows the speed:
`frames/s · cube in N of M · copy, find, tutor ms` (the time spent copying the
picture, finding the cube, and in the tutor's Python code).

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
