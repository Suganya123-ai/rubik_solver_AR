# Cube Tutor on the XREAL glasses (branch `xreal-glasses`)

The webcam app, adapted to run in the **Beam Pro's browser** and be seen in
the **XREAL One Pro** glasses. The laptop still does the heavy work (finding
the cube, colours, solving, checking moves); the Beam Pro sends camera frames
to it over Wi-Fi and shows the guidance.

```
camera ──► Beam Pro browser ──(Wi-Fi or USB)──► laptop: vision server
glasses ◄── Beam Pro ◄────────── guidance ──────────┘
```

This branch is separate: the webcam demo (branch `ar-webcam`, port 5173) and
the original demo (`live-solver`, port 8000) are not changed. It uses its own
port (5273), so it can run at the same time as the webcam demo.

## What is different from the webcam app

| | Webcam app | Glasses (this branch) |
|---|---|---|
| Camera | faces you | looks the way you look |
| Picture | mirrored | not mirrored |
| Instructions | turned round to your seat | as the camera sees it: "the green side (facing you)", "on your right" |
| Ghost cube | turned round | same way round as your cube |
| Hand mesh | drawn by the browser | drawn from the server's hand tracking (lighter for the Beam Pro) |
| Extra | | camera chooser; "Floating display only" view |

`?mode=laptop` on the address switches back to the webcam behaviour.

## Run it

On the laptop (Python 3.11+ and Node.js 20.19+):

```
git clone -b xreal-glasses https://github.com/Suganya123-ai/rubik_solver_AR.git
cd rubik_solver_AR
./run_glasses.sh
```

It builds the web app, then prints an address like
`https://192.168.1.23:5273/glasses/`. One program (the Python server) does
the vision and serves the page; it is the program macOS's firewall normally
already allows, so the Beam Pro can reach it.

### On the Beam Pro, over Wi-Fi

1. Connect the Beam Pro to the **same Wi-Fi** as the laptop, and plug in the glasses.
2. Open **Chrome** on the Beam Pro and go to the address the laptop printed.
3. Chrome warns about the certificate (it is made on your laptop, not by a
   public authority). Tap **Advanced**, then **Proceed**. This is needed
   once: browsers only allow the camera on https pages.
4. Allow the camera when asked.
5. Top right, open the **Camera** list and pick the camera to use (see below).

If the page does not load: check both devices are on the same Wi-Fi, and
that the laptop's firewall allows incoming connections for Python. Hotel,
guest and office Wi-Fi networks often stop devices talking to each other: use
a phone hotspot for both, or the USB way below.

### Or by USB (no Wi-Fi needed, no certificate warning)

1. On the Beam Pro, turn on **Developer options ▸ USB debugging**.
2. Plug the Beam Pro into the laptop (its second USB-C port; the glasses use the other).
3. On the laptop: `./run_glasses.sh --usb` (needs `adb`, from Android platform-tools).
4. On the Beam Pro open `http://localhost:5273/glasses/`.

## Which camera? (the thing to find out first)

The **Camera** list shows every camera Chrome can use on the Beam Pro.

- **If the glasses' add-on camera (XREAL Eye) is in the list:** pick it. The
  camera then sees what you see, hands-free. This is the result we want.
- **If only the Beam Pro's own cameras are listed:** the Eye is not offered to
  browsers (XREAL's own SDK may be the only way to read it). The app still
  works with the Beam Pro's rear camera pointed at the cube, for trying it
  out, and the next step is the native app in [xreal_ar/](xreal_ar/README.md),
  which reads the Eye through XREAL's SDK.

Please note down exactly what the list shows; it decides the next step.

## Two ways to look at it

- **Camera picture** (default): the camera's picture fills the display with
  the arrows drawn on the cube, the ghost cube beside it and the instruction
  card. In the glasses this is a screen floating in front of you.
- **Floating display only** (button, top right; or add `?hud=1`): no camera
  picture and a black background. Black is invisible on see-through glasses,
  so only the ghost cube, the instruction and the progress bars float in your
  view, next to your real cube. Nothing is drawn on the real cube in this view.

Arrows that sit exactly on the real cube *as seen through the lenses* need the
glasses' camera and display to be calibrated to each other. That is not done
yet; it belongs with the native app.

## Using it

The same steps as the webcam app ([README_WEBCAM.md](README_WEBCAM.md)):
start the scan, show three sides, show the other three, check the colours,
then follow the moves. Keys work if a keyboard is attached; otherwise use the
buttons on the card.

## Status

- **Works on a Beam Pro (X4200, Android 14) over USB** (12 Oct 2026): the page
  loads in Chrome, the back camera streams to the laptop at ~25 replies a
  second with ~15 ms delay, the cube and the hand are found.
- **Chrome lists only the Beam Pro's own cameras** ("camera 0, facing back",
  "camera 1, facing front"). The glasses' add-on camera was not offered to
  the browser in that test, so for now the Beam Pro's back camera is pointed
  at the cube. Reading the glasses' camera needs the native app in
  [xreal_ar/](xreal_ar/README.md) (XREAL's SDK).
- Also tested on the laptop with a simulated camera through the Wi-Fi address
  over https: scan, a wrong move, its undo, solved; both views.
- Not yet checked: a full scan-and-solve on the Beam Pro, and how it looks in
  the glasses.

## What the glasses offer over USB (checked 13 Oct 2026, XREAL One Pro on a Mac)

Plugged straight into a computer, the glasses are **not** a webcam. Their USB
interfaces are: a control channel (HID), two network links (USB Ethernet,
NCM and ECM) and audio. There is no video (UVC) interface, so no operating
system or browser lists a camera for them.

Over the network links the glasses answer at `169.254.2.1` (and `169.254.1.1`):

| Port | What it is |
|---|---|
| 52998 | Motion sensors, streaming by default: ~1,400 packets/s of 134 bytes |
| 52996 | A small status stream (~4.5 KB/s) |
| 50051 | A gRPC control service (HTTP/2); it does not list its commands (no reflection) |
| 1234, 50052, 50180, 52988-52995, 52997, 52999 | Open but silent until asked |

The camera picture is not streamed by default. It has to be requested through
XREAL's own protocol, which is not published, so the supported way to read the
add-on camera is **XREAL's SDK** (the native app in [xreal_ar/](xreal_ar/README.md)).
Nothing was sent to the glasses to find this out; the ports were only listened to.

## For development

`cd web && npx vite` runs the web app with live reload on port 5273 (it
expects the vision server on port 8200: `uvicorn main:app --port 8200`). On
macOS the firewall may hold back `node` for other devices until you allow it,
which is why `run_glasses.sh` serves the built app from Python instead.
