using UnityEngine;
#if RUBIK_XREAL_SDK3
using Unity.XR.XREAL;
#endif

namespace RubikSolverAR.Live
{
    /// <summary>
    /// Frames from the XREAL Eye (the RGB camera add-on on the One Pro), via
    /// XREAL SDK 3.x. The SDK delivers YUV_420_888 as three textures (Y, U, V);
    /// the YuvToRgb shader turns them into a colour image, which is then
    /// JPEG-encoded like any other frame.
    ///
    /// Compiled only with the scripting define RUBIK_XREAL_SDK3 (Project
    /// Settings > Player > Scripting Define Symbols) once the SDK is imported,
    /// so the rest of the project builds without it.
    ///
    /// VERIFY against XREAL's "Access RGB Camera" sample for your SDK version:
    /// the lines marked TODO-SDK (how the camera texture is created/started).
    /// The class name XREALRGBCameraTexture and GetYUVFormatTextures() come from
    /// XREAL's SDK 3.x documentation.
    /// </summary>
    public sealed class XrealEyeFrameSource : MonoBehaviour, ILiveFrameSource
    {
        [Tooltip("Material using the shader 'Hidden/RubikSolverAR/YuvToRgb'.")]
        public Material yuvToRgb;
        public int sendWidth = 640;
        [Range(10, 100)] public int jpegQuality = 80;
        [Tooltip("Flip if the image arrives upside down.")]
        public bool flipVertically = false;

        FrameEncoder encoder;
#if RUBIK_XREAL_SDK3
        XREALRGBCameraTexture cameraTexture;
#endif

        public bool IsReady
        {
            get
            {
#if RUBIK_XREAL_SDK3
                return cameraTexture != null;
#else
                return false;
#endif
            }
        }

        void Start() => StartCapture();

        public void StartCapture()
        {
            encoder ??= new FrameEncoder(sendWidth, jpegQuality);
#if RUBIK_XREAL_SDK3
            if (cameraTexture == null)
            {
                cameraTexture = XREALRGBCameraTexture.CreateSingleton();  // TODO-SDK: check creation call
            }
            cameraTexture.Play();                                         // TODO-SDK: check start call
#else
            Debug.LogWarning("XrealEyeFrameSource: import XREAL SDK 3.x and add the RUBIK_XREAL_SDK3 define. " +
                             "Use WebCamFrameSource meanwhile.");
#endif
        }

        public void StopCapture()
        {
#if RUBIK_XREAL_SDK3
            if (cameraTexture != null) cameraTexture.Stop();             // TODO-SDK: check stop call
#endif
        }

        public bool TryGetJpeg(out byte[] jpeg)
        {
            jpeg = null;
#if RUBIK_XREAL_SDK3
            if (cameraTexture == null || yuvToRgb == null) return false;
            Texture2D[] yuv = cameraTexture.GetYUVFormatTextures();      // Y, U, V
            if (yuv == null || yuv.Length < 3 || yuv[0] == null) return false;
            yuvToRgb.SetTexture("_UTex", yuv[1]);
            yuvToRgb.SetTexture("_VTex", yuv[2]);
            jpeg = encoder.Encode(yuv[0], flipVertically, yuvToRgb);
            return true;
#else
            return false;
#endif
        }

        void OnDestroy()
        {
            StopCapture();
            encoder?.Dispose();
        }
    }
}
