using UnityEngine;

namespace RubikSolverAR.Live
{
    /// <summary>
    /// Frames from a normal camera via WebCamTexture: the laptop webcam when
    /// testing in the Unity Editor, or the Beam Pro's own camera on device.
    /// Use this first to check the whole pipeline before the XREAL Eye.
    /// </summary>
    public sealed class WebCamFrameSource : MonoBehaviour, ILiveFrameSource
    {
        [Tooltip("Leave empty for the default camera.")]
        public string deviceName = "";
        public int requestWidth = 1280;
        public int requestHeight = 720;
        public int sendWidth = 640;
        [Range(10, 100)] public int jpegQuality = 80;

        WebCamTexture camera;
        FrameEncoder encoder;

        public bool IsReady => camera != null && camera.isPlaying && camera.width > 16;

        void Start() => StartCapture();

        public void StartCapture()
        {
            if (camera == null)
            {
                camera = string.IsNullOrEmpty(deviceName)
                    ? new WebCamTexture(requestWidth, requestHeight, 30)
                    : new WebCamTexture(deviceName, requestWidth, requestHeight, 30);
                encoder = new FrameEncoder(sendWidth, jpegQuality);
            }
            camera.Play();
        }

        public void StopCapture()
        {
            if (camera != null) camera.Stop();
        }

        public bool TryGetJpeg(out byte[] jpeg)
        {
            jpeg = null;
            if (!IsReady || !camera.didUpdateThisFrame) return false;
            jpeg = encoder.Encode(camera, camera.videoVerticallyMirrored);
            return true;
        }

        void OnDestroy()
        {
            StopCapture();
            encoder?.Dispose();
        }
    }
}
