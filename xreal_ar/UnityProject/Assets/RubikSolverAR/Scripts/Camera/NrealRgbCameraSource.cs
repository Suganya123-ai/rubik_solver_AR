using RubikSolverAR.Core;
using UnityEngine;

namespace RubikSolverAR.CameraSource
{
    /// <summary>
    /// Camera source backed by the XREAL device's own outward RGB camera,
    /// via NRSDK.
    ///
    /// IMPORTANT CAVEAT -- READ BEFORE USING: standard XREAL One hardware,
    /// as publicly documented at the time this was written, does NOT
    /// expose a world-facing RGB camera to third-party apps -- it has 3DoF
    /// IMU head tracking only. This class targets NRSDK's RGB-camera API
    /// (the same one NRSDK exposes on XREAL Light and any other
    /// NRSDK-supported device that does have one). Confirm your specific
    /// unit/firmware actually exposes this before relying on it; if it
    /// doesn't, use PhoneCameraSource instead (the default, and a solid
    /// fallback regardless).
    ///
    /// This file only compiles its real NRSDK calls when the
    /// RUBIK_XREAL_NRSDK scripting define symbol is set (Project Settings >
    /// Player > Other Settings > Scripting Define Symbols), so the rest of
    /// this project -- Core logic, EditMode tests, PhoneCameraSource --
    /// builds and the test suite runs cleanly even before NRSDK is
    /// imported. Once you've imported NRSDK:
    ///   1. Add RUBIK_XREAL_NRSDK to Scripting Define Symbols.
    ///   2. Check the NRRGBCamTexture API referenced below against the
    ///      NRSDK version you actually have -- class/method names have
    ///      changed across NRSDK releases -- and adjust the marked lines.
    ///      See xreal_ar/README.md's "Camera source" section.
    /// </summary>
    public sealed class NrealRgbCameraSource : MonoBehaviour, ICubeCameraSource
    {
        [Range(0f, 0.3f)]
        public float InsetFraction = 0.08f;

        public bool IsReady { get; private set; }

#if RUBIK_XREAL_NRSDK
        // TODO verify against your NRSDK version: this targets NRSDK's RGB
        // camera component (NRRGBCamTexture in NRSDK 1.x/2.x). If your
        // version renamed or restructured it, update just this block --
        // everything else in this file (cropping, the ICubeCameraSource
        // contract) stays the same.
        NRKernal.NRRGBCamTexture _camTexture;
        Texture2D _latestFrame;

        public void StartCapture()
        {
            if (_camTexture != null) return;
            _camTexture = new NRKernal.NRRGBCamTexture();
            _camTexture.OnUpdate += OnFrameUpdate;
            _camTexture.Play();
        }

        public void StopCapture()
        {
            if (_camTexture == null) return;
            _camTexture.OnUpdate -= OnFrameUpdate;
            _camTexture.Stop();
            _camTexture = null;
            IsReady = false;
        }

        void OnFrameUpdate()
        {
            // TODO verify: NRRGBCamTexture historically exposes the decoded
            // frame as GetTexture() (Texture2D). Adjust if your NRSDK
            // version instead hands back a raw YUV buffer needing conversion.
            _latestFrame = _camTexture.GetTexture();
            IsReady = _latestFrame != null;
        }

        public IPixelSource CaptureSquareFrame()
        {
            if (!IsReady || _latestFrame == null) return null;
            return CropToSquare(_latestFrame, InsetFraction);
        }
#else
        public void StartCapture()
        {
            Debug.LogError(
                "NrealRgbCameraSource requires NRSDK and the RUBIK_XREAL_NRSDK scripting define symbol. " +
                "See xreal_ar/README.md's 'Camera source' section -- and confirm your XREAL unit actually " +
                "exposes an RGB camera via NRSDK before relying on this. PhoneCameraSource is the safe default.");
        }

        public void StopCapture() { }

        public IPixelSource CaptureSquareFrame() => null;
#endif

        static IPixelSource CropToSquare(Texture2D source, float insetFraction)
        {
            int side = Mathf.Min(source.width, source.height);
            int sx = (source.width - side) / 2, sy = (source.height - side) / 2;
            int inset = Mathf.RoundToInt(side * insetFraction);
            int gridSide = side - inset * 2;
            if (gridSide <= 0) return null;

            var pixels = source.GetPixels(sx + inset, sy + inset, gridSide, gridSide);
            var cropped = new Texture2D(gridSide, gridSide, TextureFormat.RGBA32, false);
            cropped.SetPixels(pixels);
            cropped.Apply();
            var result = new TextureHsvPixelSource(cropped);
            Destroy(cropped);
            return result;
        }
    }
}
