using RubikSolverAR.Core;

namespace RubikSolverAR.CameraSource
{
    /// <summary>
    /// Supplies cropped, square sticker-grid frames for color detection.
    /// The rest of the app (ScanController, AppController) depends only on
    /// this interface, never on a specific camera API -- swap
    /// implementations (phone camera vs. an XREAL-side camera) freely.
    /// </summary>
    public interface ICubeCameraSource
    {
        bool IsReady { get; }
        void StartCapture();
        void StopCapture();

        /// <summary>
        /// The current camera frame, cropped to a centered square (matching
        /// the on-screen guide square the wearer aligns a cube face
        /// within), or null if no frame is available yet.
        /// </summary>
        IPixelSource CaptureSquareFrame();
    }
}
