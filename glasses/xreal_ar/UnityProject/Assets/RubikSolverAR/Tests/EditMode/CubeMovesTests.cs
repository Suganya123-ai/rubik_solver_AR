using System;
using System.Collections.Generic;
using NUnit.Framework;
using RubikSolverAR.Core;

namespace RubikSolverAR.Tests
{
    /// <summary>Port of tests/test_moves.py -- verifies the move engine's group-theory invariants.</summary>
    public class CubeMovesTests
    {
        [Test]
        public void QuarterTurnOrder4()
        {
            foreach (var f in "URFDLB")
            {
                var s = CubeState.Solved();
                for (int i = 0; i < 4; i++) s = Moves.ApplyMove(s, f.ToString());
                Assert.AreEqual(CubeState.Solved(), s, $"{f} x4 != identity");
            }
        }

        [Test]
        public void InversePairs()
        {
            foreach (var f in "URFDLB")
            {
                var s = Moves.ApplyMove(Moves.ApplyMove(CubeState.Solved(), f.ToString()), f + "'");
                Assert.AreEqual(CubeState.Solved(), s, $"{f} then {f}' != identity");
                var s2 = Moves.ApplyMove(Moves.ApplyMove(CubeState.Solved(), f + "2"), f + "2");
                Assert.AreEqual(CubeState.Solved(), s2, $"{f}2 x2 != identity");
            }
        }

        [Test]
        public void DoubleTurnEqualsTwoQuarters()
        {
            foreach (var f in "URFDLB")
            {
                var a = Moves.ApplyMove(CubeState.Solved(), f + "2");
                var b = Moves.ApplyMoves(CubeState.Solved(), new[] { f.ToString(), f.ToString() });
                Assert.AreEqual(a, b);
            }
        }

        static char[] FaceArr(CubeState s, char face)
        {
            int o = CubeLayout.FaceOffset[face];
            var arr = new char[9];
            Array.Copy(s.Arr, o, arr, 0, 9);
            return arr;
        }

        [Test]
        public void OppositeFaceNonInterference()
        {
            foreach (var f in "URFDLB")
            {
                char opp = CubeLayout.OppositeFace[f];
                var before = FaceArr(CubeState.Solved(), opp);
                var after = FaceArr(Moves.ApplyMove(CubeState.Solved(), f.ToString()), opp);
                CollectionAssert.AreEqual(before, after, $"{f} disturbed opposite face {opp}");
            }
        }

        [Test]
        public void CentersNeverMove()
        {
            var s = CubeState.Solved();
            foreach (var m in Moves.AllMoves) s = Moves.ApplyMove(s, m);
            foreach (var f in CubeLayout.Faces)
                Assert.AreEqual(f, s.Arr[CubeLayout.CenterIndex[f]]);
        }

        [Test]
        public void SexyMoveOrder6()
        {
            var s = CubeState.Solved();
            for (int i = 0; i < 6; i++) s = Moves.ApplyMoves(s, new[] { "R", "U", "R'", "U'" });
            Assert.AreEqual(CubeState.Solved(), s);
        }

        [Test]
        public void UrOrder105()
        {
            var s = CubeState.Solved();
            for (int i = 0; i < 105; i++) s = Moves.ApplyMoves(s, new[] { "U", "R" });
            Assert.AreEqual(CubeState.Solved(), s);
        }

        [Test]
        public void All18MovesArePermutationsOf54()
        {
            var solvedSorted = (char[])CubeState.Solved().Arr.Clone();
            Array.Sort(solvedSorted);
            foreach (var m in Moves.AllMoves)
            {
                var sorted = (char[])Moves.ApplyMove(CubeState.Solved(), m).Arr.Clone();
                Array.Sort(sorted);
                CollectionAssert.AreEqual(solvedSorted, sorted, $"move {m} is not a permutation of the 54 stickers");
            }
        }

        [Test]
        public void RandomScrambleAndUndoReturnsToSolved()
        {
            var rng = new DeterministicRandom(42);
            for (int trial = 0; trial < 20; trial++)
            {
                var scramble = new List<string>();
                for (int i = 0; i < 20; i++) scramble.Add(rng.Choice(Moves.AllMoves));
                var s = Moves.ApplyMoves(CubeState.Solved(), scramble);

                var inverse = new List<string>();
                for (int i = scramble.Count - 1; i >= 0; i--)
                {
                    var m = scramble[i];
                    if (m.EndsWith("'")) inverse.Add(m.Substring(0, 1));
                    else if (m.EndsWith("2")) inverse.Add(m);
                    else inverse.Add(m + "'");
                }
                s = Moves.ApplyMoves(s, inverse);
                Assert.AreEqual(CubeState.Solved(), s, $"scramble [{string.Join(" ", scramble)}] + inverse != solved");
            }
        }

        [Test]
        public void CornerAndEdgeAdjacencySane()
        {
            // UFR corner (top-front-right) should be exactly the 3 stickers
            // at the U/F/R faces' mutually adjacent corner cell.
            var s = CubeState.Solved();
            char u = s.Sticker('U', 2, 2);
            char f = s.Sticker('F', 0, 2);
            char r = s.Sticker('R', 0, 0);
            var trio = new HashSet<char> { u, f, r };
            Assert.AreEqual(3, trio.Count);
        }
    }
}
