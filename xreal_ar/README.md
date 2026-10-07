# Rubik's Cube Solver -- XREAL One (NRSDK/Unity) port

A native AR port of the `rubik_solver` web app for XREAL One glasses, built
against XREAL's NRSDK/Unity toolchain. This is a **C# code scaffold**, not a
built app: this environment has no Unity Editor, Android SDK, or NRSDK
installed, so nothing here has been compiled or run. Open it in Unity, wire
up the scene as described below, and the EditMode test suite (ported from
the original Python tests) is your first checkpoint that the port behaves
correctly.

## Read this first: hardware assumption

**Standard XREAL One hardware, as publicly documented, has 3DoF IMU head
tracking only -- no outward-facing RGB camera an app can read frames
from.** You confirmed your setup has a camera attached to the XREAL device
itself, so [`NrealRgbCameraSource`](UnityProject/Assets/RubikSolverAR/Scripts/Camera/NrealRgbCameraSource.cs)
targets NRSDK's RGB-camera API (`NRRGBCamTexture`, the same one used on
XREAL Light and other NRSDK-supported devices that do expose a camera) --
but that class/method surface has changed across NRSDK releases and I
couldn't check it against your actual SDK version here. Before you rely on
it:

1. Confirm your XREAL unit/firmware genuinely exposes an RGB camera to
   NRSDK (check NRSDK's own camera sample scene first).
2. Open `NrealRgbCameraSource.cs` and check the marked `// TODO verify`
   lines against your installed NRSDK version's actual API.
3. Until you've done that, [`PhoneCameraSource`](UnityProject/Assets/RubikSolverAR/Scripts/Camera/PhoneCameraSource.cs)
   (the host Android phone's own camera via Unity's standard
   `WebCamTexture`) is a confident, zero-risk fallback -- both implement
   the same `ICubeCameraSource` interface, so swapping is a one-line change
   in the scene (see "Scene setup" below).

`NrealRgbCameraSource`'s real NRSDK calls are compiled only behind the
`RUBIK_XREAL_NRSDK` scripting define symbol (Project Settings > Player >
Other Settings > Scripting Define Symbols), specifically so the rest of
this project -- all the solving/validation logic, the EditMode tests,
`PhoneCameraSource` -- builds and runs **before** you've imported NRSDK or
sorted out the camera question at all.

## What's here vs. what you build

| Original (`rubik_solver/`) | This port | Notes |
|---|---|---|
| `cube/cube_state.py` | `Scripts/Core/CubeState.cs` | Direct port, zero UnityEngine dependency |
| `cube/moves.py` | `Scripts/Core/Moves.cs` | Direct port |
| `cube/validation.py` | `Scripts/Core/Validation.cs` | Direct port |
| `cube/fast_search.py` | `Scripts/Core/FastSearch.cs` | Direct port |
| `cube/solver.py` | `Scripts/Core/Solver.cs` | Direct port |
| `cube/color_detect.py` | `Scripts/Core/ColorDetect.cs` | Ported against a framework-agnostic `IPixelSource`, not Pillow |
| `main.py` + in-memory `SESSION` | `Scripts/App/AppController.cs` | Same state machine, plain method calls instead of HTTP routes (no server -- everything's on-device now) |
| `static/scan.js` | `Scripts/AR/ScanController.cs` | Same scan flow; AR UI widgets instead of DOM |
| `static/guide.js` | `Scripts/AR/SolveStepPresenter.cs` | Same step-by-step display logic |
| `static/cube_diagram.js` | `Scripts/AR/CubeDiagramBuilder.cs` | **Reinterpreted**, not pixel-ported -- see below |
| (new) | `Scripts/Camera/*.cs` | Camera abstraction: `ICubeCameraSource`, `PhoneCameraSource`, `NrealRgbCameraSource` |
| `tests/test_*.py` | `Tests/EditMode/*.cs` | Same assertions, NUnit/Unity Test Framework |

**`CubeDiagramBuilder` is deliberately not a pixel port.** The original's
SVG unfolded net with hand-drawn curved arrows is fine on a web page but
fussy to read at a glance through AR optics. Instead it shows a small
highlighted-face net (same "which face" information) plus a turn-direction
ring built from Unity's built-in radial `Image` fill (clear at HUD distance
as "mostly clockwise" / "mostly counter-clockwise" / "full turn"). The big
text label (face name + CW/CCW/180) carries the precise instruction either
way.

## Why this is trustworthy (and where to double-check)

The solving/validation engine (`Scripts/Core/*.cs`) is a line-by-line port
of the Python originals -- same algorithms, same move-engine coordinate
conventions, same last-layer commutators. I could not compile or run any of
it here (no .NET/Mono/Unity toolchain in this environment), so **treat it
as unverified until you run the test suite**:

```
Unity Editor > Window > General > Test Runner > EditMode > Run All
```

`Tests/EditMode/SolverTests.cs` is the main gate (ported from
`test_solver.py`): it scrambles a solved cube, solves it, replays the
solution, and asserts the result is solved again, across 300+ scrambles
including every single-move scramble and several edge cases. If that suite
is green, the C# engine agrees with the original Python engine on
everything it's been checked against. `CubeMovesTests.cs`,
`ValidationTests.cs`, and `ColorDetectTests.cs` cover the move engine, the
3-tier scan validator, and the HSV color classifier respectively.

These tests only need Unity's Editor + Test Framework package (included by
default) -- no NRSDK, no device, no camera. Run them as your very first
step after opening the project, before touching any hardware.

## Project layout

```
xreal_ar/
  README.md                         <- this file
  UnityProject/
    Assets/RubikSolverAR/
      Scripts/
        RubikSolverAR.asmdef        <- assembly def for all runtime scripts
        Core/                       <- ported engine, zero UnityEngine dependency
        Camera/                     <- ICubeCameraSource + two implementations
        AR/                         <- ScanController, SolveStepPresenter, CubeDiagramBuilder
        App/                        <- AppController (the session/state machine)
      Tests/EditMode/
        RubikSolverAR.Tests.asmdef
        CubeMovesTests.cs
        ValidationTests.cs
        SolverTests.cs
        ColorDetectTests.cs
        DeterministicRandom.cs
```

There's no `.unity` scene file or prefabs here -- binary Unity assets can't
be hand-authored reliably outside the Editor. "Scene setup" below is the
exact hierarchy to build once you have the project open.

## Setup

### Prerequisites

- Unity (an LTS version your NRSDK release supports -- check XREAL's NRSDK
  release notes; NRSDK has historically targeted Unity 2020.3 LTS or
  2021.3 LTS). Install via Unity Hub with Android Build Support.
- Android SDK/NDK/JDK (installed automatically with Unity's Android Build
  Support module).
- NRSDK, downloaded from XREAL's developer portal, imported as a
  `.unitypackage` into this project.
- A compatible Android phone to pair with the XREAL One over USB-C
  (NRSDK apps run on the phone; the glasses are the display + head
  tracker).
- XREAL One glasses, USB-C cable.

### Import this code

1. Create a new Unity 3D project (or open an existing NRSDK sample
   project).
2. Copy `UnityProject/Assets/RubikSolverAR/` into your project's `Assets/`
   folder.
3. Import NRSDK's `.unitypackage`.
4. Let Unity recompile. With no scripting define symbols set, everything
   compiles already -- `Scripts/Core`, `Scripts/Camera/PhoneCameraSource.cs`,
   and the test suite. `NrealRgbCameraSource`'s NRSDK-specific code stays
   inert (behind `#if RUBIK_XREAL_NRSDK`) until you opt in.
5. Run the EditMode tests (see above). Fix anything red before moving on
   to scene setup -- it's much easier to debug the pure logic in isolation
   than inside a running AR scene.

### Scene setup

Build this hierarchy (a plain `Canvas` in Screen Space - Camera or World
Space, per NRSDK's recommended UI setup for its camera rig):

```
NRCameraRig                          <- from NRSDK's sample/prefab
Canvas (World Space, parented under NRCameraRig's center camera per NRSDK's UI guide)
  ScanScreen
    CameraPanel
      [RawImage showing the live camera feed -- PhoneCameraSource's
       WebCamTexture or NrealRgbCameraSource's frame, your choice of UI]
      FaceProgressText (Text)
      InstructionsText (Text)
      ErrorText (Text, start inactive)
      CaptureButton (Button) -> ScanController.OnCaptureTriggered
    ConfirmPanel (start inactive)
      GridPreviewCells[0..8]  <- 9 GameObjects, each with Image + Button
      PaletteButtons[0..5]    <- 6 Buttons, one per color (see ColorDetect.ColorNames order)
      RetakeButton (Button) -> ScanController.OnRetake
      ConfirmButton (Button) -> ScanController.OnConfirmFace
  SolveScreen (start inactive)
    MoveView
      StepCountText, StageNameText, MoveNotationText, MoveDescriptionText (Text)
      ProgressFill (Image, Type=Filled, Horizontal)
      DiagramRoot
        NetContainer (RectTransform, ~240x180)   <- CubeDiagramBuilder builds 6 cells under this
        TurnRing (Image, Type=Filled, Radial360)
        ArrowHead (small triangle Image/RectTransform)
        FaceLabel (Text, optional)
      BackButton (Button) -> AppController.BackStep
      NextButton (Button) -> AppController.NextStep
    SolvedView (start inactive)
    RestartButton (Button) -> AppController.ResetAll

CameraSourceHost (empty GameObject)
  PhoneCameraSource   <- or NrealRgbCameraSource, per the camera-source decision above

AppHost (empty GameObject)
  ScanController       <- wire CameraSourceBehaviour to CameraSourceHost above, plus all the Text/Image/Button refs
  SolveStepPresenter    <- wire Text/Image/CubeDiagramBuilder refs
  CubeDiagramBuilder    <- wire NetContainer/TurnRing/ArrowHead/FaceLabel
  AppController         <- wire Scan and Presenter fields
```

Toggling `ScanScreen`/`SolveScreen` and `MoveView`/`SolvedView` active state
is left to you (a couple of lines in `AppController`/`SolveStepPresenter`,
or just drive it from the `Active`/inactive state already described above
via a small screen-manager script) -- deliberately not hard-coded here
since it depends on how you've laid out your canvases.

### Input mapping

Nothing in this scaffold hard-codes a specific XREAL controller/hand-
tracking API, since that surface is even less certain than the camera
question. Wire these yourself based on what input NRSDK gives you on your
setup:

- `ScanController.OnCaptureTriggered()` -- "take the photo"
- `ScanController.OnRetake()` / `OnConfirmFace()` -- confirm-panel actions
- `AppController.NextStep()` / `BackStep()` -- step navigation
- `AppController.ResetAll()` -- restart

The simplest starting point: use the paired Android phone's touchscreen as
a trackpad/button source (NRSDK supports this out of the box on most
samples) and wire `Button.onClick` the normal Unity UI way, exactly as
listed in "Scene setup" above. Upgrade to air-tap/controller-trigger input
later without touching any of the app logic.

### Build & deploy

1. File > Build Settings > switch platform to Android.
2. Player Settings: set minimum API level and other Android settings per
   NRSDK's documented requirements for your SDK version.
3. Build an APK -- either via the Build Settings window, or with
   [`Editor/BuildScript.cs`](UnityProject/Assets/RubikSolverAR/Editor/BuildScript.cs):
   - In-Editor: **Tools > Rubik Solver AR > Build Android APK**.
   - Command line (e.g. for CI, or to script repeat builds):
     ```
     "<UnityPath>/Unity" -batchmode -quit -projectPath /path/to/project \
       -buildTarget Android -executeMethod RubikSolverAR.EditorTools.BuildScript.BuildApk
     ```
     Add `-sceneList path/to/Scene.unity` if you haven't added your scene to
     File > Build Settings yet, and `-apkOutput path/to/out.apk` to change
     where it's written (default `Builds/Android/RubikSolverAR.apk`). For a
     release-signed build, set the `ANDROID_KEYSTORE_PATH` /
     `ANDROID_KEYSTORE_PASS` / `ANDROID_KEY_ALIAS` / `ANDROID_KEY_PASS`
     environment variables first; without them it signs with Unity's
     default debug keystore (fine for sideloading to a dev-registered phone).
4. `adb install` the resulting APK to the phone paired with your XREAL One.
5. Launch the app with the XREAL One connected via USB-C.

Note: this only runs on a machine with Unity, Android Build Support, and
NRSDK actually installed -- none of which exist in the environment this
scaffold was written in, so the script itself is untested. It's a thin
wrapper over `BuildPipeline.BuildPlayer`, so if something's off it should
be a quick fix once you see the actual Unity error.

## Building the APK via CI (no local build step)

[`.github/workflows/build-apk.yml`](.github/workflows/build-apk.yml) builds
the APK on GitHub's servers via [game-ci/unity-builder](https://game.ci/),
so once it's set up, every `git push` produces a fresh downloadable APK --
no Unity build step on your own machine after the one-time setup below.

### One-time local setup for CI

CI needs a *complete* Unity project (`ProjectSettings/`, `Packages/`), which
only the Editor can generate -- this one step can't be skipped or scripted
around:

1. Create a new Unity project locally (Unity Hub), ideally starting from an
   NRSDK sample project so Android/XR Player Settings are already correct
   for your SDK version.
2. Copy this scaffold's `UnityProject/Assets/RubikSolverAR/` into that
   project's `Assets/` folder.
3. Import NRSDK's `.unitypackage`.
4. Build the scene from "Scene setup" above, save it, add it to File > Build
   Settings.
5. Open **Tools > Rubik Solver AR > Build Android APK** once locally just to
   confirm it builds clean (optional but recommended before trusting CI to it).
6. `git init` (if not already), copy in [`.gitignore`](.gitignore) from this
   scaffold to the project root, then commit everything: `Assets/`,
   `ProjectSettings/`, `Packages/`, `.github/`, `.gitignore` -- NOT
   `Library/`, `Temp/`, or `Builds/`.
7. Push to a GitHub repo.

### One-time Unity license setup

Free Unity personal licenses work fine for CI builds of a project like this:

1. In your new repo's Actions tab, manually run **"Activate Unity license
   (one-time)"** ([`.github/workflows/activate-unity-license.yml`](.github/workflows/activate-unity-license.yml)).
   First edit its `unityVersion` to match the Editor version you used above.
2. Download the `.alf` file it produces as an artifact.
3. Upload it at <https://license.unity3d.com/manual> with your Unity
   account to get a `.ulf` license file back.
4. `base64 -w0 your-license.ulf` (macOS: drop `-w0`) and save that output as
   a repo secret named `UNITY_LICENSE` (Settings > Secrets and variables >
   Actions). Also add `UNITY_EMAIL` and `UNITY_PASSWORD` secrets (your Unity
   account credentials -- game-ci uses these only to activate the license
   inside the CI runner).
5. Delete the activation workflow file (or leave it; it only runs when you
   trigger it manually) and you won't need to repeat this unless the
   license expires.

### Triggering a build

Edit `build-apk.yml`'s `unityVersion` and `UNITY_PROJECT_PATH` to match your
setup, then push to `main` (or run it manually from the Actions tab). Once
it finishes, the APK is attached to that workflow run under **Artifacts** --
download it, then `adb install` it to your phone as in step 4 above.

## Known limitations / things to revisit

- **Camera source is unverified** -- see "Read this first" above. This is
  the single biggest risk in this port; everything else is a mechanical
  translation of already-tested logic.
- **No scene/prefab files** -- you build the hierarchy by hand once, per
  "Scene setup". Consider saving it as a prefab afterwards for reuse.
- **`ColorDetect`'s HSV conversion** is a standard RGB->HSV formula, not
  byte-identical to Pillow's internal rounding (which the original
  Python thresholds were tuned against). The threshold margins are
  generous and the scan UI lets the wearer correct any misclassified
  sticker regardless, but if you see systematically off classifications
  under your specific camera/lighting, recalibrate the hue ranges and
  white thresholds at the top of `ColorDetect.cs`.
- **No persistence** -- like the original (an explicit single-user,
  in-memory design choice), `AppController`'s state lives only for the
  current app session.
