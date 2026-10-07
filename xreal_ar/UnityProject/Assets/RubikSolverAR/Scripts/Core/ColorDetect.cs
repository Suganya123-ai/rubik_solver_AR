using System;
using System.Collections.Generic;

namespace RubikSolverAR.Core
{
    /// <summary>8-bit RGB pixel, framework-agnostic.</summary>
    public struct Rgb
    {
        public byte R, G, B;
        public Rgb(byte r, byte g, byte b) { R = r; G = g; B = b; }
    }

    /// <summary>
    /// Minimal pixel source ColorDetect needs, so this file has zero
    /// UnityEngine (or any other framework) dependency and can be unit
    /// tested standalone. (0,0) is the top-left pixel, matching the
    /// PIL/image convention the original Python module assumed -- when
    /// adapting a Unity Texture2D (which has (0,0) at bottom-left), flip Y
    /// in the adapter, not here. See Camera/TextureHsvPixelSource.cs.
    /// </summary>
    public interface IPixelSource
    {
        int Width { get; }
        int Height { get; }
        Rgb GetPixel(int x, int y);
    }

    /// <summary>
    /// Sticker color detection from a photo. Direct port of
    /// cube/color_detect.py, minus the Pillow/base64 decoding (that was a
    /// Python-web-request concern; here the caller supplies an
    /// IPixelSource already framing the 3x3 sticker grid).
    /// </summary>
    public static class ColorDetect
    {
        public static readonly string[] ColorNames = { "white", "yellow", "red", "orange", "green", "blue" };

        // Hue ranges in Pillow's HSV convention (H, S, V all 0-255, so hue
        // is degrees/360*255 rather than degrees/360*360). Red wraps around 0/255.
        static readonly (string name, (int lo, int hi)[] ranges)[] HueRanges =
        {
            ("red", new[] { (0, 6), (245, 255) }),
            ("orange", new[] { (7, 26) }),
            ("yellow", new[] { (27, 52) }),
            ("green", new[] { (53, 115) }),
            ("blue", new[] { (122, 180) }),
        };

        const double WhiteMaxSaturation = 55;
        const double WhiteMinValue = 130;

        public static string ClassifyHsv(double h, double s, double v)
        {
            if (s <= WhiteMaxSaturation && v >= WhiteMinValue) return "white";

            foreach (var entry in HueRanges)
                foreach (var range in entry.ranges)
                    if (h >= range.lo && h <= range.hi) return entry.name;

            // Fall back to nearest hue range's midpoint if nothing matched
            // cleanly (e.g. unusual lighting) -- better to guess than to
            // error out, since the UI lets the user correct any
            // misdetected cell before confirming.
            string bestName = "white";
            double? bestDist = null;
            foreach (var entry in HueRanges)
            {
                foreach (var range in entry.ranges)
                {
                    double mid = (range.lo + range.hi) / 2.0;
                    double dist = Math.Min(Math.Abs(h - mid), 255 - Math.Abs(h - mid));
                    if (bestDist == null || dist < bestDist)
                    {
                        bestName = entry.name;
                        bestDist = dist;
                    }
                }
            }
            return bestName;
        }

        /// <summary>
        /// RGB (0-255 each) -> Pillow-style HSV (H,S,V each scaled 0-255).
        /// This is a standard HSV conversion, not byte-identical to
        /// Pillow's internal rounding, but close enough given the
        /// generous threshold margins above (and the scan UI lets a user
        /// correct any misclassified cell regardless).
        /// </summary>
        public static (double h, double s, double v) RgbToPillowHsv(byte r8, byte g8, byte b8)
        {
            double r = r8 / 255.0, g = g8 / 255.0, b = b8 / 255.0;
            double max = Math.Max(r, Math.Max(g, b));
            double min = Math.Min(r, Math.Min(g, b));
            double delta = max - min;

            double hue;
            if (delta == 0) hue = 0;
            else if (max == r) hue = (((g - b) / delta) % 6) / 6.0;
            else if (max == g) hue = (((b - r) / delta) + 2) / 6.0;
            else hue = (((r - g) / delta) + 4) / 6.0;
            if (hue < 0) hue += 1.0;

            double sat = max == 0 ? 0 : delta / max;
            double val = max;
            return (hue * 255.0, sat * 255.0, val * 255.0);
        }

        static double Median(List<double> values)
        {
            if (values.Count == 0) return 0;
            values.Sort();
            int n = values.Count;
            if (n % 2 == 1) return values[n / 2];
            return (values[n / 2 - 1] + values[n / 2]) / 2.0;
        }

        // Sample the center 50% of the cell to avoid grout lines/glare at edges.
        static (double h, double s, double v) CellHsv(IPixelSource image, int row, int col, int rows, int cols)
        {
            int w = image.Width, h = image.Height;
            double cellH = (double)h / rows, cellW = (double)w / cols;
            double y0 = row * cellH, y1 = (row + 1) * cellH;
            double x0 = col * cellW, x1 = (col + 1) * cellW;
            double padY = (y1 - y0) * 0.25, padX = (x1 - x0) * 0.25;
            int yStart = (int)(y0 + padY), yEnd = (int)(y1 - padY);
            int xStart = (int)(x0 + padX), xEnd = (int)(x1 - padX);

            var hs = new List<double>();
            var ss = new List<double>();
            var vs = new List<double>();
            for (int y = yStart; y < yEnd; y++)
            {
                for (int x = xStart; x < xEnd; x++)
                {
                    var px = image.GetPixel(x, y);
                    var hsv = RgbToPillowHsv(px.R, px.G, px.B);
                    hs.Add(hsv.h);
                    ss.Add(hsv.s);
                    vs.Add(hsv.v);
                }
            }
            return (Median(hs), Median(ss), Median(vs));
        }

        /// <summary>
        /// `image` is already cropped to the sticker grid square. Returns a
        /// flat array of `grid*grid` color names in raster order.
        /// </summary>
        public static string[] DetectFaceColors(IPixelSource image, int grid = 3)
        {
            var colors = new string[grid * grid];
            int k = 0;
            for (int row = 0; row < grid; row++)
            {
                for (int col = 0; col < grid; col++)
                {
                    var hsv = CellHsv(image, row, col, grid, grid);
                    colors[k++] = ClassifyHsv(hsv.h, hsv.s, hsv.v);
                }
            }
            return colors;
        }
    }
}
