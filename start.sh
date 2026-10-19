#!/usr/bin/env bash
# The latest version of everything, from one place (branch `latest`, see README.md):
#   ./start.sh            the cube tutor on the laptop webcam   -> http://localhost:5176
#   ./start.sh pyramid    the Pyraminx tutor                    -> http://localhost:5177
#   ./start.sh both       both
#   ./start.sh glasses    build the glasses app (Cube Tutor Fast: glasses-only, with voice)
#   ./start.sh glasses --install    ...and install it on the Beam Pro (unplug the glasses first!)
# Both laptop tutors talk (voice), listen for commands and, with a language model set up
# (~/.cube_tutor_llm.env), answer spoken questions. Ctrl+C stops them.
set -euo pipefail
cd "$(dirname "$0")"
what="${1:-cube}"

case "$what" in
  cube)    exec ./run_webcam.sh ;;
  pyramid|pyra|pyraminx) exec ./run_pyra.sh ;;
  both)
    ./run_webcam.sh & cube=$!
    ./run_pyra.sh & pyra=$!
    trap 'kill $cube $pyra 2>/dev/null' INT TERM EXIT
    echo "Cube tutor: http://localhost:5176    Pyraminx tutor: http://localhost:5177"
    wait ;;
  glasses)
    cd glasses
    [ -d web/node_modules ] || (cd web && npm install)
    (cd web && npm run build)
    [ -f android_phone/local.properties ] || { echo "android_phone/local.properties is missing (sdk.dir=...): see glasses/README_PHONE.md"; exit 1; }
    [ -d android_phone/app/src/main/jniLibs ] || { echo "The XREAL libraries are missing: run glasses/android_phone/get_xreal_libs.sh (see glasses/README_PHONE.md)"; exit 1; }
    (cd android_phone && ./gradlew assembleDebug -q)
    apk=android_phone/app/build/outputs/apk/debug/app-debug.apk
    echo "Built: glasses/$apk"
    if [ "${2:-}" = "--install" ]; then
      read -r -p "Are the glasses unplugged from the Beam Pro? (installing while the camera runs sticks it) [y/N] " ok
      [ "$ok" = "y" ] || [ "$ok" = "Y" ] || { echo "Not installed."; exit 0; }
      adb install -r "$apk"
      adb shell pm grant com.cubetutor.phonefast android.permission.RECORD_AUDIO || true
      echo "Installed Cube Tutor Fast. Plug the glasses in and put them on (glasses/README_VOICE.md)."
    else
      echo "To install it: ./start.sh glasses --install   (with the Beam Pro connected, glasses unplugged)"
    fi ;;
  *) sed -n 2,10p "$0"; exit 1 ;;
esac
