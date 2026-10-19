using RubikSolverAR.Core;
using UnityEngine;

namespace RubikSolverAR.CameraSource
{
    /// <summary>
    /// Adapts a Unity Texture2D (or a WebCamTexture snapshot copied into
    /// one) to Core's IPixelSource. Unity textures have (0,0) at the
    /// BOTTOM-left; IPixelSource documents (0,0) as top-left (the
    /// PIL/image convention the original Python module assumed), so Y is
    /// flipped here -- once, in the one Unity-aware adapter -- rather than
    /// in the framework-agnostic Core.
    /// </summary>
    public sealed class TextureHsvPixelSource : IPixelSource
    {
        readonly Color32[] _pixels;

        public int Width { get; }
        public int Height { get; }

        public TextureHsvPixelSource(Texture2D texture)
        {
            Width = texture.width;
            Height = texture.height;
            _pixels = texture.GetPixels32();
        }

        public Rgb GetPixel(int x, int y)
        {
            int flippedY = Height - 1 - y;
            var c = _pixels[flippedY * Width + x];
            return new Rgb(c.r, c.g, c.b);
        }
    }
}
