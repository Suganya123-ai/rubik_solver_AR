namespace RubikSolverAR.Live
{
    /// <summary>
    /// A camera that can hand the live client its newest frame as a JPEG
    /// (about 640 px wide). Implementations: <see cref="WebCamFrameSource"/>
    /// (any webcam / the Beam Pro camera, also works in the Unity Editor) and
    /// <see cref="XrealEyeFrameSource"/> (the XREAL Eye on the glasses).
    /// </summary>
    public interface ILiveFrameSource
    {
        bool IsReady { get; }
        void StartCapture();
        void StopCapture();

        /// <summary>Encodes the newest frame. Returns false if none is available yet.</summary>
        bool TryGetJpeg(out byte[] jpeg);
    }
}
