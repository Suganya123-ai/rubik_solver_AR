using System;
using System.Collections.Generic;
using System.Linq;

namespace RubikSolverAR.Core
{
    readonly struct PiecePosOri : IEquatable<PiecePosOri>
    {
        public readonly P3 Pos;
        public readonly int Ori;
        public PiecePosOri(P3 pos, int ori) { Pos = pos; Ori = ori; }
        public bool Equals(PiecePosOri o) => Pos.Equals(o.Pos) && Ori == o.Ori;
        public override bool Equals(object obj) => obj is PiecePosOri p && Equals(p);
        public override int GetHashCode() => Pos.GetHashCode() * 31 + Ori;
    }

    sealed class SearchState : IEquatable<SearchState>
    {
        public readonly PiecePosOri[] Items;
        public SearchState(PiecePosOri[] items) { Items = items; }

        public bool Equals(SearchState other)
        {
            if (other == null || other.Items.Length != Items.Length) return false;
            for (int i = 0; i < Items.Length; i++)
                if (!Items[i].Equals(other.Items[i])) return false;
            return true;
        }

        public override bool Equals(object obj) => Equals(obj as SearchState);

        public override int GetHashCode()
        {
            int h = 17;
            foreach (var it in Items) h = h * 31 + it.GetHashCode();
            return h;
        }
    }

    /// <summary>A piece being tracked by the search: its kind, home slot, and current (position, orientation).</summary>
    public struct TrackedPiece
    {
        public readonly bool IsEdge;
        public readonly P3 Home;
        public readonly P3 Pos;
        public readonly int Ori;

        public TrackedPiece(bool isEdge, P3 home, P3 pos, int ori)
        {
            IsEdge = isEdge; Home = home; Pos = pos; Ori = ori;
        }
    }

    /// <summary>
    /// Fast piece-tracking search used by the solver. Direct port of
    /// cube/fast_search.py: precompute, once, from the verified move engine,
    /// a per-move transition table for each of the 8 corner slots and 12
    /// edge slots ("whatever sits at position p, after this move, ends up at
    /// position p' with orientation shifted by k"). Search then operates on
    /// tuples of (position, orientation) for just the handful of pieces a
    /// stage cares about, via bidirectional BFS.
    /// </summary>
    public static class FastSearch
    {
        public static readonly Dictionary<string, Dictionary<P3, (P3 pos, int ori)>> CornerTable;
        public static readonly Dictionary<string, Dictionary<P3, (P3 pos, int ori)>> EdgeTable;

        static readonly Dictionary<string, string> InvSuffix =
            new Dictionary<string, string> { [""] = "'", ["'"] = "", ["2"] = "2" };

        static FastSearch()
        {
            CornerTable = BuildTable(Validation.CornerPositions, Validation.CornerFaceletIndices, Validation.CornerSlotByLetters);
            EdgeTable = BuildTable(Validation.EdgePositions, Validation.EdgeFaceletIndices, Validation.EdgeSlotByLetters);
        }

        static Dictionary<string, Dictionary<P3, (P3, int)>> BuildTable(
            List<P3> positions, Func<P3, int[]> faceletFn, Dictionary<string, P3> slotByLetters)
        {
            var solved = CubeState.Solved();
            var table = new Dictionary<string, Dictionary<P3, (P3, int)>>();
            foreach (var move in Moves.AllMoves)
            {
                var after = Moves.ApplyMove(solved, move);
                var mapping = new Dictionary<P3, (P3, int)>();
                foreach (var p in positions)
                {
                    var idxs = faceletFn(p);
                    var observed = idxs.Select(i => after.Arr[i]).ToArray();
                    var q = slotByLetters[Validation.SlotKey(observed)];
                    var homeTuple = faceletFn(q).Select(i => Validation.SolvedArr[i]).ToArray();
                    int k = Validation.IndexOfRotation(Validation.Rotations(homeTuple), observed);
                    mapping[q] = (p, k);
                }
                table[move] = mapping;
            }
            return table;
        }

        static Dictionary<P3, (P3 pos, int ori)> Analyze(
            CubeState state, List<P3> positions, Func<P3, int[]> faceletFn, Dictionary<string, P3> slotByLetters)
        {
            var result = new Dictionary<P3, (P3, int)>();
            foreach (var p in positions)
            {
                var idxs = faceletFn(p);
                var observed = idxs.Select(i => state.Arr[i]).ToArray();
                var q = slotByLetters[Validation.SlotKey(observed)];
                var homeTuple = faceletFn(q).Select(i => Validation.SolvedArr[i]).ToArray();
                int k = Validation.IndexOfRotation(Validation.Rotations(homeTuple), observed);
                result[q] = (p, k);
            }
            return result;
        }

        public static Dictionary<P3, (P3 pos, int ori)> AnalyzeCorners(CubeState state) =>
            Analyze(state, Validation.CornerPositions, Validation.CornerFaceletIndices, Validation.CornerSlotByLetters);

        public static Dictionary<P3, (P3 pos, int ori)> AnalyzeEdges(CubeState state) =>
            Analyze(state, Validation.EdgePositions, Validation.EdgeFaceletIndices, Validation.EdgeSlotByLetters);

        static string InverseMove(string move) => move[0] + InvSuffix[move.Substring(1)];

        /// <summary>
        /// Bidirectional BFS: the shortest move list (from allowedMoves)
        /// that brings every tracked piece to (home, 0), or null if none
        /// exists within maxDepth.
        /// </summary>
        public static List<string> FindMoves(List<TrackedPiece> pieces, IReadOnlyList<string> allowedMoves, int maxDepth)
        {
            int n = pieces.Count;
            var tables = new Dictionary<string, Dictionary<P3, (P3, int)>>[n];
            var mods = new int[n];
            for (int i = 0; i < n; i++)
            {
                tables[i] = pieces[i].IsEdge ? EdgeTable : CornerTable;
                mods[i] = pieces[i].IsEdge ? 2 : 3;
            }

            var startItems = new PiecePosOri[n];
            var goalItems = new PiecePosOri[n];
            for (int i = 0; i < n; i++)
            {
                startItems[i] = new PiecePosOri(pieces[i].Pos, pieces[i].Ori);
                goalItems[i] = new PiecePosOri(pieces[i].Home, 0);
            }
            var start = new SearchState(startItems);
            var goal = new SearchState(goalItems);
            if (start.Equals(goal)) return new List<string>();

            SearchState Transition(SearchState s, string move)
            {
                var items = new PiecePosOri[n];
                for (int i = 0; i < n; i++)
                {
                    var (pos, ori) = (s.Items[i].Pos, s.Items[i].Ori);
                    var step = tables[i][move][pos];
                    items[i] = new PiecePosOri(step.Item1, (ori + step.Item2) % mods[i]);
                }
                return new SearchState(items);
            }

            var inverses = new Dictionary<string, string>();
            foreach (var m in allowedMoves) inverses[m] = InverseMove(m);

            var pathF = new Dictionary<SearchState, List<string>> { { start, new List<string>() } };
            var pathB = new Dictionary<SearchState, List<string>> { { goal, new List<string>() } };
            var frontierF = new List<SearchState> { start };
            var frontierB = new List<SearchState> { goal };

            for (int depth = 0; depth < maxDepth; depth++)
            {
                if (frontierF.Count == 0 && frontierB.Count == 0) return null;

                var nextF = new List<SearchState>();
                foreach (var s in frontierF)
                {
                    foreach (var move in allowedMoves)
                    {
                        var ns = Transition(s, move);
                        if (pathB.TryGetValue(ns, out var backPath))
                        {
                            var result = new List<string>(pathF[s]);
                            result.Add(move);
                            result.AddRange(backPath);
                            return result;
                        }
                        if (!pathF.ContainsKey(ns))
                        {
                            var p = new List<string>(pathF[s]);
                            p.Add(move);
                            pathF[ns] = p;
                            nextF.Add(ns);
                        }
                    }
                }
                frontierF = nextF;

                var nextB = new List<SearchState>();
                foreach (var s in frontierB)
                {
                    foreach (var move in allowedMoves)
                    {
                        var pred = Transition(s, inverses[move]);
                        if (pathF.TryGetValue(pred, out var fwdPath))
                        {
                            var result = new List<string>(fwdPath);
                            result.Add(move);
                            result.AddRange(pathB[s]);
                            return result;
                        }
                        if (!pathB.ContainsKey(pred))
                        {
                            var p = new List<string> { move };
                            p.AddRange(pathB[s]);
                            pathB[pred] = p;
                            nextB.Add(pred);
                        }
                    }
                }
                frontierB = nextB;
            }

            return null;
        }
    }
}
