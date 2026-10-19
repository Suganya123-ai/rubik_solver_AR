using System.Collections.Generic;
using NUnit.Framework;
using RubikSolverAR.Core;

namespace RubikSolverAR.Tests
{
    /// <summary>
    /// Port of tests/test_solver.py -- THE main correctness gate for this
    /// whole port. Scrambles a solved cube, runs the solver, replays the
    /// solution, and asserts the result is solved again, across 300+
    /// scrambles including edge cases. If this suite is green, the C#
    /// engine agrees with the original Python engine's behavior on every
    /// case it was validated against.
    /// </summary>
    public class SolverTests
    {
        static List<string> CheckRoundTrip(List<string> scramble)
        {
            var s = Moves.ApplyMoves(CubeState.Solved(), scramble);
            var (moves, _) = Solver.Solve(s);
            var result = Moves.ApplyMoves(s, moves);
            Assert.AreEqual(CubeState.Solved(), result,
                $"scramble [{string.Join(" ", scramble)}] -> solution [{string.Join(" ", moves)}] did not solve");
            Assert.LessOrEqual(moves.Count, Solver.MaxSaneMoves,
                $"solution too long ({moves.Count}) for scramble [{string.Join(" ", scramble)}]");
            return moves;
        }

        [Test]
        public void AlreadySolvedCube()
        {
            var moves = CheckRoundTrip(new List<string>());
            Assert.AreEqual(0, moves.Count);
        }

        [Test]
        public void EverySingleMoveScramble()
        {
            foreach (var m in Moves.AllMoves)
                CheckRoundTrip(new List<string> { m });
        }

        [Test]
        public void RandomScramblesManySeeds()
        {
            for (int seed = 0; seed < 200; seed++)
            {
                var rng = new DeterministicRandom(seed);
                var scramble = new List<string>();
                for (int i = 0; i < 25; i++) scramble.Add(rng.Choice(Moves.AllMoves));
                CheckRoundTrip(scramble);
            }
        }

        [Test]
        public void RandomScramblesVariedLength()
        {
            for (int seed = 0; seed < 100; seed++)
            {
                var rng = new DeterministicRandom(seed + 10_000);
                int length = rng.NextInclusive(1, 40);
                var scramble = new List<string>();
                for (int i = 0; i < length; i++) scramble.Add(rng.Choice(Moves.AllMoves));
                CheckRoundTrip(scramble);
            }
        }

        [Test]
        public void TwoGeneratorScrambles()
        {
            // Scrambles using only 2 of the 6 faces exercise different
            // stage-skip patterns than typical random scrambles (many
            // pieces stay untouched).
            var rng = new DeterministicRandom(99);
            var faceSets = new List<(char, char)> { ('U', 'D'), ('R', 'L'), ('F', 'B'), ('U', 'R') };
            foreach (var (f1, f2) in faceSets)
            {
                var pool = new List<string>();
                foreach (var f in new[] { f1, f2 })
                    foreach (var suffix in new[] { "", "'", "2" })
                        pool.Add(f + suffix);
                var scramble = new List<string>();
                for (int i = 0; i < 20; i++) scramble.Add(rng.Choice(pool));
                CheckRoundTrip(scramble);
            }
        }

        [Test]
        public void SolutionIsDeterministic()
        {
            var rng = new DeterministicRandom(7);
            var scramble = new List<string>();
            for (int i = 0; i < 25; i++) scramble.Add(rng.Choice(Moves.AllMoves));
            var s = Moves.ApplyMoves(CubeState.Solved(), scramble);
            var (moves1, _) = Solver.Solve(s);
            var (moves2, _) = Solver.Solve(s);
            CollectionAssert.AreEqual(moves1, moves2);
        }

        [Test]
        public void EnrichProducesValidInstructions()
        {
            var rng = new DeterministicRandom(3);
            var scramble = new List<string>();
            for (int i = 0; i < 25; i++) scramble.Add(rng.Choice(Moves.AllMoves));
            var s = Moves.ApplyMoves(CubeState.Solved(), scramble);
            var (moves, stageBounds) = Solver.Solve(s);
            var instructions = Solver.Enrich(moves, stageBounds);
            Assert.AreEqual(moves.Count, instructions.Count);
            for (int i = 0; i < instructions.Count; i++)
            {
                var instr = instructions[i];
                Assert.AreEqual(i + 1, instr.StepIndex);
                Assert.AreEqual(moves.Count, instr.TotalSteps);
                Assert.AreEqual(moves[i], instr.Notation);
                Assert.That(instr.Direction, Is.EqualTo("CW").Or.EqualTo("CCW").Or.EqualTo("180"));
            }
        }

        [Test]
        public void InvalidScanRejected()
        {
            var s = CubeState.Solved().Copy();
            s.Arr[4] = 'D'; // break U's center to create an illegal state
            Assert.Throws<SolverException>(() => Solver.Solve(s));
        }
    }
}
