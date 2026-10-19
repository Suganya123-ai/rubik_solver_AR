using System.Collections.Generic;

namespace RubikSolverAR.Tests
{
    /// <summary>
    /// Thin seeded-RNG helper for reproducible test scrambles. Not
    /// bit-compatible with Python's random module -- these tests check
    /// cube-engine invariants that hold for ANY scramble (round-trips,
    /// legality, solvability), not a specific RNG sequence, so exact
    /// cross-language reproducibility isn't needed.
    /// </summary>
    public sealed class DeterministicRandom
    {
        readonly System.Random _r;
        public DeterministicRandom(int seed) { _r = new System.Random(seed); }
        public T Choice<T>(IReadOnlyList<T> items) => items[_r.Next(items.Count)];
        public int NextInclusive(int minInclusive, int maxInclusive) => _r.Next(minInclusive, maxInclusive + 1);
    }
}
