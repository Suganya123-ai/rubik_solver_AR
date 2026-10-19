# Cube Tutor Bridge (Android app for the Beam Pro)

Reads the **XREAL glasses' add-on camera** and sends the picture to the Cube
Tutor server on the laptop, then shows the tutor on top, so it is seen in the
glasses. A browser cannot open that camera; this app can.

```
glasses' camera ─► this app (Beam Pro) ──Wi-Fi/hotspot──► laptop: ./run_glasses.sh
glasses display ◄── tutor page shown by this app ◄────────┘
```

## Credit and licence

This is the open-source **XR Cam** by Aloim
(<https://github.com/Aloim/Xreal-One-Pro-Eye-RGB-Camera-feed-on-Android>, MIT,
see `LICENSE`) with two additions: `FrameUploader.kt` (uploads the picture)
and the tutor page shown over the camera view. XR Cam worked out how to switch
the camera on: XREAL's own native library sets the glasses' USB configuration
(`NRBSPSetUsbConfigAll`), the glasses reconnect with a video interface, and the
picture arrives as H.265 over USB.

XREAL's two native libraries are **not** in this repository. Run
`./get_xreal_libs.sh` once to copy them from the XR Cam project.

## Build and install

Needs the Android SDK (platform 35, build-tools) and Java 17+.

```
./get_xreal_libs.sh
echo "sdk.dir=/path/to/android/sdk" > local.properties
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## Use

1. On the laptop: `./run_glasses.sh` (in the repository root). Note the address it prints.
2. Laptop and Beam Pro on the same network (a phone hotspot works; hotel Wi-Fi usually does not).
3. On the Beam Pro: open **Cube Tutor Bridge**, type the laptop's address,
   then plug in the glasses. Use the laptop's **name** (`./run_glasses.sh`
   prints it, e.g. `My-MacBook.local:5273`) rather than its number: a hotspot
   gives the laptop a new number when it reconnects, and the app then can't
   find it ("Can't reach ..." at the top of the phone screen).
4. Tap **OK** on the USB prompt straight away, tap **Start the tutor**, and
   tap **OK** on the second prompt straight away (the glasses reconnect).
5. The tutor appears. Bottom left shows the upload speed. **Camera** (bottom
   right) shows the raw camera picture instead; **Tutor** goes back.

The Beam Pro has one data port, used by the glasses, so the link to the laptop
is wireless.

## How it sends the picture

`FrameUploader` takes the picture the decoder is drawing, shrinks it to
640x472, and sends it as JPEG to `wss://<laptop>/ws/feed`, one frame at a time
(the next when the server has answered). The server (`glasses_server.py`)
runs the tutor on those frames and passes the results to the page, which is
opened as `https://<laptop>/glasses/?camera=remote`.

The server's certificate is self-made, so the app accepts it without
checking. It only talks to the address typed on its first screen.
