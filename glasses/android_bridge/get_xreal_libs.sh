#!/usr/bin/env bash
# The bridge switches the glasses' camera on with XREAL's own native libraries
# (libnr_glasses_api.so, libota-lib.so). They are XREAL's, so they are not kept
# in this repository; this copies them from the open-source XR Cam project,
# which bundles them: https://github.com/Aloim/Xreal-One-Pro-Eye-RGB-Camera-feed-on-Android
set -euo pipefail
cd "$(dirname "$0")"
DEST=app/src/main/jniLibs/arm64-v8a
if [ -f "$DEST/libnr_glasses_api.so" ] && [ -f "$DEST/libota-lib.so" ]; then echo "Libraries already in place."; exit 0; fi
TMP=$(mktemp -d)
git clone -q --depth 1 https://github.com/Aloim/Xreal-One-Pro-Eye-RGB-Camera-feed-on-Android.git "$TMP/xrcam"
mkdir -p "$DEST"
cp "$TMP/xrcam/app/src/main/jniLibs/arm64-v8a/"*.so "$DEST/"
rm -rf "$TMP"
echo "Copied XREAL's libraries into $DEST"
