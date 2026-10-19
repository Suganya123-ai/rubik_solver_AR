using System.Collections.Generic;
using NUnit.Framework;
using RubikSolverAR.Core;

namespace RubikSolverAR.Tests
{
    /// <summary>Port of tests/test_validation.py.</summary>
    public class ValidationTests
    {
        static readonly Dictionary<char, string> ColorOfFace = new Dictionary<char, string>
        {
            ['U'] = "white", ['D'] = "yellow", ['F'] = "green", ['B'] = "blue", ['L'] = "orange", ['R'] = "red",
        };

        /// <summary>Build a raw scan-shaped color_grid from a translated CubeState, for tier-1 tests.</summary>
        static Dictionary<char, List<string>> MakeColorGridFromState(CubeState state)
        {
            var grid = new Dictionary<char, List<string>>();
            foreach (var f in CubeLayout.Faces)
            {
                int o = CubeLayout.FaceOffset[f];
                var colors = new List<string>();
                for (int i = 0; i < 9; i++) colors.Add(ColorOfFace[state.Arr[o + i]]);
                grid[f] = colors;
            }
            return grid;
        }

        [Test]
        public void SolvedStateIsValid()
        {
            var r = Validation.Validate(CubeState.Solved());
            Assert.IsTrue(r.Ok, r.Message);
        }

        [Test]
        public void LegalScrambleIsAlwaysValid()
        {
            var rng = new DeterministicRandom(7);
            for (int trial = 0; trial < 15; trial++)
            {
                var scramble = new List<string>();
                for (int i = 0; i < 20; i++) scramble.Add(rng.Choice(Moves.AllMoves));
                var s = Moves.ApplyMoves(CubeState.Solved(), scramble);
                var r = Validation.Validate(s);
                Assert.IsTrue(r.Ok, $"[{string.Join(" ", scramble)}] produced invalid state: {r.Message}");
            }
        }

        [Test]
        public void FullScanPipelineRoundTrip()
        {
            var s = Moves.ApplyMoves(CubeState.Solved(), new[] { "R", "U", "F'", "L2", "D", "B'" });
            var grid = MakeColorGridFromState(s);
            var (translated, result) = Validation.ValidateScan(grid);
            Assert.IsTrue(result.Ok, result.Message);
            Assert.AreEqual(s, translated);
        }

        [Test]
        public void ColorCountError()
        {
            var grid = MakeColorGridFromState(CubeState.Solved());
            grid['U'][0] = "yellow"; // break the 9-of-each-color count
            var r = Validation.ValidateColors(grid);
            Assert.IsFalse(r.Ok);
            Assert.AreEqual("ERROR_COLOR_COUNT", r.ErrorCode);
        }

        [Test]
        public void DuplicateCenterError()
        {
            var grid = MakeColorGridFromState(CubeState.Solved());
            // Swap U's center with a non-center D sticker so both totals
            // stay at 9, but U and D centers now show the same color.
            (grid['U'][4], grid['D'][0]) = (grid['D'][0], grid['U'][4]);
            var r = Validation.ValidateColors(grid);
            Assert.IsFalse(r.Ok);
            Assert.AreEqual("ERROR_DUPLICATE_CENTER", r.ErrorCode);
        }

        [Test]
        public void TwistedCornerDetected()
        {
            // Cyclically rotate the 3 stickers of the UFR corner (1,1,1) in
            // place -- a twist impossible on a real cube.
            var s = CubeState.Solved().Copy();
            var idxs = Validation.CornerFaceletIndices(new P3(1, 1, 1));
            char a = s.Arr[idxs[0]], b = s.Arr[idxs[1]], c = s.Arr[idxs[2]];
            s.Arr[idxs[0]] = b;
            s.Arr[idxs[1]] = c;
            s.Arr[idxs[2]] = a;
            var r = Validation.Validate(s);
            Assert.IsFalse(r.Ok);
            Assert.AreEqual("ERROR_CORNER_TWIST", r.ErrorCode, r.Message);
        }

        [Test]
        public void FlippedEdgeDetected()
        {
            var s = CubeState.Solved().Copy();
            var idxs = Validation.EdgeFaceletIndices(new P3(0, 1, 1)); // UF edge
            (s.Arr[idxs[0]], s.Arr[idxs[1]]) = (s.Arr[idxs[1]], s.Arr[idxs[0]]);
            var r = Validation.Validate(s);
            Assert.IsFalse(r.Ok);
            Assert.AreEqual("ERROR_EDGE_FLIP", r.ErrorCode, r.Message);
        }

        [Test]
        public void SwappedEdgesParityError()
        {
            // Swap the UF edge pair with the UB edge pair (2-cycle only ->
            // odd permutation on edges while corners stay solved -> parity mismatch).
            var s = CubeState.Solved().Copy();
            var uf = Validation.EdgeFaceletIndices(new P3(0, 1, 1));
            var ub = Validation.EdgeFaceletIndices(new P3(0, 1, -1));
            for (int i = 0; i < uf.Length; i++)
                (s.Arr[uf[i]], s.Arr[ub[i]]) = (s.Arr[ub[i]], s.Arr[uf[i]]);
            var r = Validation.Validate(s);
            Assert.IsFalse(r.Ok);
            Assert.AreEqual("ERROR_PARITY", r.ErrorCode, r.Message);
        }

        [Test]
        public void OppositeColorsOnOneCornerDetected()
        {
            var s = CubeState.Solved().Copy();
            var idxs = Validation.CornerFaceletIndices(new P3(1, 1, 1));
            s.Arr[idxs[0]] = 'D'; // opposite of U -- impossible on any one corner
            var r = Validation.Validate(s);
            Assert.IsFalse(r.Ok);
            Assert.AreEqual("ERROR_BAD_CORNER", r.ErrorCode, r.Message);
        }
    }
}
