using RubikSolverAR.Core;
using UnityEngine;

namespace RubikSolverAR.CameraSource
{
    /// <summary>
    /// Camera source backed by the host phone's own camera via Unity's
    /// standard WebCamTexture API. This is the confident, always-available
    /// default: works on any Android/iOS device NRSDK runs on, no extra SDK
    /// needed. Mirrors static/scan.js's captureCroppedSquare(): crop to the
    /// largest centered square in the frame, then inset 8% to frame just
    /// the 3x3 sticker grid (keeping cube edges/background out of shot).
    /// </summary>
    public sealed class PhoneCameraSource : MonoBehaviour, ICubeCameraSource
    {
        [Tooltip("Fraction of the cropped square's side to inset on each edge, matching the web UI's guide square.")]
        [Range(0f, 0.3f)]
        public float InsetFraction = 0.08f;

        [Tooltip("Preferred capture resolution; the device substitutes its closest supported mode.")]
        public int RequestedWidth = 1280;
        public int RequestedHeight = 720;

        WebCamTexture _webCamTexture;

        public bool IsReady => _webCamTexture != null && _webCamTexture.isPlaying && _webCamTexture.didUpdateThisFrame;

        public void StartCapture()
        {
            if (_webCamTexture != null) return;

            string deviceName = null;
            foreach (var device in WebCamTexture.devices)
            {
                if (!device.isFrontFacing)
                {
                    deviceName = device.name;
                    break;
                }
            }

            _webCamTexture = deviceName != null
                ? new WebCamTexture(deviceName, RequestedWidth, RequestedHeight)
                : new WebCamTexture(RequestedWidth, RequestedHeight);
            _webCamTexture.Play();
        }

        public void StopCapture()
        {
            if (_webCamTexture == null) return;
            _webCamTexture.Stop();
            Destroy(_webCamTexture);
            _webCamTexture = null;
        }

        void OnDestroy() => StopCapture();

        public IPixelSource CaptureSquareFrame()
        {
            if (!IsReady) return null;

            int vw = _webCamTexture.width, vh = _webCamTexture.height;
            int side = Mathf.Min(vw, vh);
            int sx = (vw - side) / 2, sy = (vh - side) / 2;
            int inset = Mathf.RoundToInt(side * InsetFraction);
            int gridSide = side - inset * 2;
            if (gridSide <= 0) return null;

            var pixels = _webCamTexture.GetPixels(sx + inset, sy + inset, gridSide, gridSide);
            var tex = new Texture2D(gridSide, gridSide, TextureFormat.RGBA32, false);
            tex.SetPixels(pixels);
            tex.Apply();
            var result = new TextureHsvPixelSource(tex);
            // TextureHsvPixelSource copies pixel data out in its constructor,
            // so the Texture2D itself isn't needed past this point.
            Destroy(tex);
            return result;
        }
    }
}
