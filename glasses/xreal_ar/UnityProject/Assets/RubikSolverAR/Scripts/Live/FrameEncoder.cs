using UnityEngine;

namespace RubikSolverAR.Live
{
    /// <summary>
    /// Shrinks any texture to the send width on the GPU, reads it back and
    /// JPEG-encodes it. Reuses its buffers between frames.
    /// </summary>
    public sealed class FrameEncoder
    {
        readonly int sendWidth;
        readonly int quality;
        RenderTexture target;
        Texture2D readback;

        public FrameEncoder(int sendWidth = 640, int quality = 80)
        {
            this.sendWidth = sendWidth;
            this.quality = quality;
        }

        /// <param name="flipVertically">True for cameras that deliver upside-down images
        /// (WebCamTexture.videoVerticallyMirrored, some GPU readbacks).</param>
        public byte[] Encode(Texture source, bool flipVertically = false, Material material = null)
        {
            int width = sendWidth;
            int height = Mathf.Max(2, Mathf.RoundToInt(sendWidth * (float)source.height / source.width));
            if (target == null || target.width != width || target.height != height)
            {
                if (target != null) target.Release();
                target = new RenderTexture(width, height, 0, RenderTextureFormat.ARGB32);
                readback = new Texture2D(width, height, TextureFormat.RGB24, false);
            }

            var scale = new Vector2(1f, flipVertically ? -1f : 1f);
            var offset = new Vector2(0f, flipVertically ? 1f : 0f);
            if (material != null)
            {
                // Blit with a material ignores scale/offset, so convert first, then flip.
                var temp = RenderTexture.GetTemporary(width, height, 0, RenderTextureFormat.ARGB32);
                Graphics.Blit(source, temp, material);
                Graphics.Blit(temp, target, scale, offset);
                RenderTexture.ReleaseTemporary(temp);
            }
            else
            {
                Graphics.Blit(source, target, scale, offset);
            }

            var previous = RenderTexture.active;
            RenderTexture.active = target;
            readback.ReadPixels(new Rect(0, 0, width, height), 0, 0, false);
            readback.Apply(false);
            RenderTexture.active = previous;
            return readback.EncodeToJPG(quality);
        }

        public void Dispose()
        {
            if (target != null) target.Release();
            if (readback != null) Object.Destroy(readback);
        }
    }
}
