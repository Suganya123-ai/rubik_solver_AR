using System.Collections.Generic;
using NUnit.Framework;
using RubikSolverAR.Core;

namespace RubikSolverAR.Tests
{
    /// <summary>Simple in-memory IPixelSource for tests -- (0,0) is top-left, matching ColorDetect's documented convention.</summary>
    sealed class ArrayPixelSource : IPixelSource
    {
        readonly Rgb[,] _pixels; // [y, x]
        public ArrayPixelSource(int width, int height, Rgb fill)
        {
            Width = width;
            Height = height;
            _pixels = new Rgb[height, width];
            for (int y = 0; y < height; y++)
                for (int x = 0; x < width; x++)
                    _pixels[y, x] = fill;
        }
        public int Width { get; }
        public int Height { get; }
        public Rgb GetPixel(int x, int y) => _pixels[y, x];
        public void SetPixel(int x, int y, Rgb value) => _pixels[y, x] = value;
    }

    /// <summary>Port of tests/test_color_detect.py.</summary>
    public class ColorDetectTests
    {
        static readonly Dictionary<string, Rgb> SampleRgb = new Dictionary<string, Rgb>
        {
            ["white"] = new Rgb(245, 245, 245),
            ["yellow"] = new Rgb(255, 213, 0),
            ["red"] = new Rgb(200, 15, 30),
            ["orange"] = new Rgb(255, 100, 0),
            ["green"] = new Rgb(0, 150, 70),
            ["blue"] = new Rgb(0, 70, 180),
        };

        static string ClassifyRgb(Rgb rgb)
        {
            var hsv = ColorDetect.RgbToPillowHsv(rgb.R, rgb.G, rgb.B);
            return ColorDetect.ClassifyHsv(hsv.h, hsv.s, hsv.v);
        }

        [Test]
        public void EachReferenceColorClassifiesCorrectly()
        {
            foreach (var kv in SampleRgb)
            {
                var result = ClassifyRgb(kv.Value);
                Assert.AreEqual(kv.Key, result, $"{kv.Key} {kv.Value} classified as {result}");
            }
        }

        [Test]
        public void DetectFaceColorsOnSyntheticGrid()
        {
            // A 300x300 image, all one color, like a real solved face.
            var img = new ArrayPixelSource(300, 300, SampleRgb["green"]);
            var colors = ColorDetect.DetectFaceColors(img);
            CollectionAssert.AreEqual(new[] { "green", "green", "green", "green", "green", "green", "green", "green", "green" }, colors);
        }

        [Test]
        public void DetectFaceColorsOnMixedGrid()
        {
            var layout = new[]
            {
                "white", "red", "green",
                "yellow", "white", "blue",
                "orange", "green", "white",
            };
            var img = new ArrayPixelSource(300, 300, new Rgb(0, 0, 0));
            const int cell = 100;
            for (int i = 0; i < layout.Length; i++)
            {
                int row = i / 3, col = i % 3;
                var rgb = SampleRgb[layout[i]];
                for (int y = row * cell; y < (row + 1) * cell; y++)
                    for (int x = col * cell; x < (col + 1) * cell; x++)
                        img.SetPixel(x, y, rgb);
            }
            var colors = ColorDetect.DetectFaceColors(img);
            CollectionAssert.AreEqual(layout, colors, "got " + string.Join(",", colors));
        }

        [Test]
        public void AllColorNamesReachable()
        {
            foreach (var name in ColorDetect.ColorNames)
                Assert.IsTrue(SampleRgb.ContainsKey(name));
        }
    }
}
