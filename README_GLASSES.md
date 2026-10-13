# Cube Tutor on the XREAL glasses (branch `xreal-glasses`)

The tutor seen **in the XREAL One Pro glasses**, using the **glasses' own
add-on camera** (XREAL Eye), so it sees what you see. The laptop does the
heavy work (finding the cube, colours, solving, checking moves); a small app
on the **Beam Pro** reads the glasses' camera, sends the picture to the laptop
over a hotspot, and shows the tutor on the glasses.

```
glasses' camera ─► Cube Tutor Bridge (Beam Pro) ──hotspot──► laptop: ./run_glasses.sh
glasses' screen ◄── tutor, floating in view ◄───────────────┘
phone screen    ◄── the same tutor, with the buttons (the remote control)
```

This branch is separate: the webcam demo (branch `ar-webcam`, port 5173) and
the original demo (`live-solver`, port 8000) are not changed. It uses its own
port (5273), so it can run at the same time as the webcam demo.

## Start here: the glasses' own camera (what works today)

**Once:** build and install the bridge app, see [android_bridge/README.md](android_bridge/README.md).

**Each time:**

1. **One network for the laptop and the Beam Pro.** A phone hotspot works
   (connect both to it). Hotel, guest and office Wi-Fi usually stop devices
   seeing each other. The Beam Pro has a single data port, used by the
   glasses, so this link has to be wireless.
2. **On the laptop:** `./run_glasses.sh`. It prints an address like
   `https://172.20.10.14:5273/glasses/`; the part to remember is
   `172.20.10.14:5273`.
3. **On the Beam Pro:** open **Cube Tutor Bridge**, check the laptop's address,
   then plug in the glasses and tap **OK** on the USB prompt straight away.
4. Tap **Start the tutor**, and **OK** straight away on the second prompt (the
   glasses reconnect when their camera is switched on).
5. The tutor appears **in the glasses** (floating: ghost cube top right,
   instruction at the bottom) and **on the phone** (with the buttons). Hold
   the phone upright; it is the remote control.

**Scanning:** tap **Start scan** on the phone. Show the cube with a corner
toward you, three sides showing, in the middle of your view at about 25-30 cm,
and hold still: "3 of 6 sides scanned". Then turn the cube **any way you
like** to show the rest; sides already scanned may show again, and it tells
you how many are left (usually the underside last). Check the colours on the
phone, then **Solve**.

**Solving:** do the move shown, then show the cube again (on your palm or held
by two opposite sides, a corner toward you) and hold still for half a second.
A wrong move is announced with the turn that undoes it.

**Buttons on the phone (top bar):**

| Button | What it does |
|---|---|
| Zoom 2x | How much of the wide camera view is used: 2x, 3x, 1x. The window follows the cube and searches for it when it is lost. |
| Glasses: floating / picture | What the glasses show: only the ghost cube and instructions (black is invisible on see-through glasses), or the camera picture with the arrows on the cube. |
| Camera / Tutor | Show the raw camera picture on the phone instead of the tutor. |
| Close | Stop. |

### What is not there yet

- Arrows that sit exactly on the real cube *as seen through the lenses*. That
  needs the camera and the display calibrated to each other.
- The cube finder was trained on rendered cubes that fill more of the picture.
  With this wide camera it relies on the zoom window; a model retrained on
  frames from this camera (the recordings in `data/` are the raw material)
  would find the cube more often, also while it is held in two hands.
- Over a phone hotspot about 5-10 frames a second reach the laptop.

## The other way: the Beam Pro's own camera, in its browser

No app needed, but it uses the Beam Pro's back camera (a browser cannot open
the glasses' camera). Open the address `./run_glasses.sh` prints in Chrome on
the Beam Pro, accept the certificate warning (Advanced, Proceed) and allow the
camera. By USB instead of a network: `./run_glasses.sh --usb`, then
`http://localhost:5273/glasses/` on the Beam Pro (needs `adb` and USB
debugging; the glasses cannot be plugged in at the same time).

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

## Status (13 Oct 2026)

- **Glasses' own camera: working** on the user's XREAL One Pro + Eye + Beam Pro
  (X4200, Android 14) over a phone hotspot: scans complete, moves are followed
  (a session reached move 10 of 14, including a wrong move that was undone).
  The zoom window that follows the cube was added after that session and has
  not been tried on the device yet.
- Browser route with the Beam Pro's camera: working over USB (~25 replies/s)
  and over a hotspot (slower).
- The laptop side is covered by 97 automated tests and an end-to-end run with
  a simulated camera.

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
