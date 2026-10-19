using System;
using System.Collections.Generic;
using System.Linq;

namespace RubikSolverAR.Core
{
    public class SolverException : Exception
    {
        public SolverException(string message) : base(message) { }
    }

    /// <summary>
    /// Solves first two layers (cross, corners, middle-layer edges) via a
    /// small bounded search against the real move engine, then finishes the
    /// last layer with a handful of standard, empirically verified
    /// commutators (they don't disturb the solved layers below, by
    /// construction). Direct port of cube/solver.py. Move counts run
    /// 60-150ish moves (not move-optimal -- irrelevant here since a human
    /// executes each move anyway).
    /// </summary>
    public static class Solver
    {
        // ---------------------------------------------------------------
        // Generic per-slot helpers: does slot p currently show the letters
        // it would show in a solved cube? Works for ANY position (cross,
        // corner, middle edge, last layer).
        // ---------------------------------------------------------------

        static Dictionary<char, int> EdgeIndicesByAxis(P3 p)
        {
            var d = new Dictionary<char, int>();
            if (p.X != 0) d['x'] = Moves.Index(p, new P3(p.X, 0, 0));
            if (p.Y != 0) d['y'] = Moves.Index(p, new P3(0, p.Y, 0));
            if (p.Z != 0) d['z'] = Moves.Index(p, new P3(0, 0, p.Z));
            return d;
        }

        static Dictionary<char, int> CornerIndicesByAxis(P3 p) => new Dictionary<char, int>
        {
            ['x'] = Moves.Index(p, new P3(p.X, 0, 0)),
            ['y'] = Moves.Index(p, new P3(0, p.Y, 0)),
            ['z'] = Moves.Index(p, new P3(0, 0, p.Z)),
        };

        static Dictionary<char, char> LettersByAxis(P3 p)
        {
            var d = new Dictionary<char, char>();
            if (p.X != 0) d['x'] = p.X == 1 ? 'R' : 'L';
            if (p.Y != 0) d['y'] = p.Y == 1 ? 'U' : 'D';
            if (p.Z != 0) d['z'] = p.Z == 1 ? 'F' : 'B';
            return d;
        }

        public static bool PieceIsSolved(CubeState state, P3 p, bool isEdge)
        {
            var idxs = isEdge ? EdgeIndicesByAxis(p) : CornerIndicesByAxis(p);
            var expect = LettersByAxis(p);
            foreach (var kv in idxs)
                if (state.Arr[kv.Value] != expect[kv.Key]) return false;
            return true;
        }

        /// <summary>Is the up-facing sticker of whatever edge currently sits at last-layer slot p showing 'U'?</summary>
        static bool EdgeOriented(CubeState state, P3 p) => state.Arr[EdgeIndicesByAxis(p)['y']] == 'U';

        /// <summary>Is the up-facing sticker of whatever corner currently sits at last-layer slot p showing 'U'?</summary>
        public static bool CornerOriented(CubeState state, P3 p) => state.Arr[CornerIndicesByAxis(p)['y']] == 'U';

        /// <summary>Correct cubie in this corner slot, ignoring twist.</summary>
        public static bool CornerPositionOk(CubeState state, P3 p)
        {
            var idxs = CornerIndicesByAxis(p);
            var expect = new HashSet<char>(LettersByAxis(p).Values);
            var observed = new HashSet<char>(idxs.Values.Select(i => state.Arr[i]));
            return expect.SetEquals(observed);
        }

        // ---------------------------------------------------------------
        // Generic bounded search: find a short move sequence that solves
        // `target` while keeping every already-`locked` slot solved.
        // ---------------------------------------------------------------

        static List<TrackedPiece> AnalyzeTracked(CubeState state, List<(P3 home, bool isEdge)> tracked)
        {
            var edgeAnalysis = FastSearch.AnalyzeEdges(state);
            var cornerAnalysis = FastSearch.AnalyzeCorners(state);
            var pieces = new List<TrackedPiece>();
            foreach (var (home, isEdge) in tracked)
            {
                var (pos, ori) = isEdge ? edgeAnalysis[home] : cornerAnalysis[home];
                pieces.Add(new TrackedPiece(isEdge, home, pos, ori));
            }
            return pieces;
        }

        static List<string> FindForTracked(CubeState state, List<(P3 home, bool isEdge)> tracked, IReadOnlyList<string> allowedMoves, int maxDepth) =>
            FastSearch.FindMoves(AnalyzeTracked(state, tracked), allowedMoves, maxDepth);

        static List<char> FacesTouching(P3 p)
        {
            var faces = new List<char>();
            if (p.X != 0) faces.Add(p.X == 1 ? 'R' : 'L');
            if (p.Y != 0) faces.Add(p.Y == 1 ? 'U' : 'D');
            if (p.Z != 0) faces.Add(p.Z == 1 ? 'F' : 'B');
            return faces;
        }

        public static readonly string[] NoDMoves = Moves.AllMoves.Where(m => m[0] != 'D').ToArray();

        /// <summary>
        /// U never disturbs the D or middle layers, so it's always safe to
        /// include. Restricting the rest to just the faces the target
        /// itself touches keeps branching small; falls back to the full
        /// move set if this is too narrow to find a solution.
        /// </summary>
        static List<string> RestrictedMoves(P3 target)
        {
            var faces = new HashSet<char>(FacesTouching(target)) { 'U' };
            return Moves.AllMoves.Where(m => faces.Contains(m[0])).ToList();
        }

        /// <summary>
        /// Find a sequence placing `target` without disturbing `locked`,
        /// widening the tracked set (and retrying) only if a found sequence
        /// turns out to disturb something. Returns null instead of
        /// throwing if no luck.
        /// </summary>
        static List<string> SolveOne(CubeState state, P3 target, bool isEdge, List<(P3 home, bool isEdge)> locked,
            int maxDepth, IReadOnlyList<string> allowedMoves)
        {
            var tracked = new List<(P3 home, bool isEdge)> { (target, isEdge) };
            int attempts = locked.Count + 2;
            for (int i = 0; i < attempts; i++)
            {
                var seq = FindForTracked(state, tracked, allowedMoves, maxDepth);
                if (seq == null)
                    seq = FindForTracked(state, tracked, allowedMoves, maxDepth + 2);
                if (seq == null)
                    return null;
                var trial = Moves.ApplyMoves(state, seq);
                var broken = locked.Where(l => !tracked.Contains(l) && !PieceIsSolved(trial, l.home, l.isEdge)).ToList();
                if (broken.Count == 0)
                    return seq;
                tracked.AddRange(broken);
            }
            return null;
        }

        /// <summary>
        /// Place each of `targets` (tracked by home slot) while keeping
        /// every already-`locked` piece solved. Tries a move set restricted
        /// to the target's own faces (+U/D) first; falls back to the full
        /// move set only if that's not enough.
        /// </summary>
        static (List<string> moves, CubeState state, List<(P3 home, bool isEdge)> locked) SolvePieces(
            CubeState state, IReadOnlyList<P3> targets, bool isEdge, List<(P3 home, bool isEdge)> locked,
            int maxDepth, IReadOnlyList<string> allowedMoves)
        {
            var moves = new List<string>();
            foreach (var target in targets)
            {
                if (PieceIsSolved(state, target, isEdge))
                {
                    locked.Add((target, isEdge));
                    continue;
                }
                var seq = SolveOne(state, target, isEdge, locked, maxDepth, RestrictedMoves(target));
                if (seq == null)
                    seq = SolveOne(state, target, isEdge, locked, maxDepth, allowedMoves);
                if (seq == null)
                    throw new SolverException($"couldn't place piece at {target}");
                state = Moves.ApplyMoves(state, seq);
                moves.AddRange(seq);
                locked.Add((target, isEdge));
            }
            return (moves, state, locked);
        }

        // D-layer cross+corners and the middle-layer edges are solved first
        // ("first two layers" in the classic method); the U layer is solved last.
        public static readonly P3[] Stage1CrossTargets = { new P3(1, -1, 0), new P3(0, -1, 1), new P3(0, -1, -1), new P3(-1, -1, 0) };
        public static readonly P3[] Stage2CornerTargets = { new P3(1, -1, 1), new P3(1, -1, -1), new P3(-1, -1, -1), new P3(-1, -1, 1) };
        public static readonly P3[] Stage3MiddleEdgeTargets = { new P3(1, 0, 1), new P3(-1, 0, 1), new P3(1, 0, -1), new P3(-1, 0, -1) };
        public static readonly P3[] LastLayerEdgeTargets = { new P3(1, 1, 0), new P3(-1, 1, 0), new P3(0, 1, 1), new P3(0, 1, -1) };
        public static readonly P3[] LastLayerCornerTargets = { new P3(1, 1, 1), new P3(1, 1, -1), new P3(-1, 1, -1), new P3(-1, 1, 1) };

        // ---------------------------------------------------------------
        // Last layer: fixed, empirically-verified-against-the-real-engine
        // algorithms (F2L-safe commutators -- see cube/solver.py's
        // comments for the group-theory reasoning behind each).
        // ---------------------------------------------------------------

        static readonly Dictionary<string, string> InvSuffix =
            new Dictionary<string, string> { [""] = "'", ["'"] = "", ["2"] = "2" };

        static List<string> InvertSequence(IEnumerable<string> seq)
        {
            var list = new List<string>(seq);
            list.Reverse();
            return list.Select(m => m[0] + InvSuffix[m.Substring(1)]).ToList();
        }

        static readonly List<List<string>> AlignOptions = new List<List<string>>
        {
            new List<string>(),
            new List<string> { "U" },
            new List<string> { "U2" },
            new List<string> { "U'" },
        };

        static readonly List<string> EdgeOrientAlg = new List<string> { "F", "R", "U", "R'", "U'", "F'" };
        static readonly List<string> CornerCycleAlg = new List<string> { "U", "R", "U'", "L'", "U", "R'", "U'", "L" };
        static readonly List<string> CornerCycleAlgInv = InvertSequence(CornerCycleAlg);
        static readonly List<string> CornerSwapAlg = CornerCycleAlg.Concat(new[] { "U" }).Concat(CornerCycleAlg).Concat(new[] { "U'" }).ToList();
        static readonly List<string> TPerm = new List<string> { "R", "U", "R'", "U'", "R'", "F", "R2", "U'", "R'", "U'", "R", "U", "R'", "F'" };
        static readonly List<string> CornerTwistAlg = new List<string> { "R", "U", "R'", "U", "R", "U2", "R'" };
        static readonly List<string> CornerTwistAlgInv = InvertSequence(CornerTwistAlg);
        static readonly List<string> EdgeCycleAlg = new List<string> { "R", "U'", "R", "U", "R", "U", "R", "U'", "R'", "U'", "R2" };
        static readonly List<string> EdgeCycleAlgInv = InvertSequence(EdgeCycleAlg);
        static readonly List<string> EdgeSwapAlg = EdgeCycleAlg.Concat(new[] { "U" }).Concat(EdgeCycleAlg).Concat(new[] { "U'" }).ToList();

        /// <summary>
        /// BFS over applications of (pre-rotation, algorithm) combos to
        /// find the shortest sequence reaching target_score. A pure greedy
        /// hill-climb gets stuck on cases where every immediate option ties
        /// (e.g. a diagonal corner swap); BFS explores both branches of a
        /// tie and finds the multi-step fix.
        /// </summary>
        static (List<string> moves, CubeState state) ApplyBest(
            CubeState state, List<List<string>> candidates, Func<CubeState, int> scoreFn, int targetScore, int maxRounds)
        {
            if (scoreFn(state) >= targetScore) return (new List<string>(), state);

            var metaMoves = new List<List<string>>();
            foreach (var alg in candidates)
                foreach (var pre in AlignOptions)
                {
                    var mm = new List<string>();
                    mm.AddRange(pre);
                    mm.AddRange(alg);
                    mm.AddRange(InvertSequence(pre));
                    metaMoves.Add(mm);
                }

            string StateKey(CubeState s) => new string(s.Arr);
            var visited = new HashSet<string> { StateKey(state) };
            var queue = new Queue<(CubeState state, List<string> path, int rounds)>();
            queue.Enqueue((state, new List<string>(), 0));

            while (queue.Count > 0)
            {
                var (curState, path, rounds) = queue.Dequeue();
                if (rounds >= maxRounds) continue;
                foreach (var mm in metaMoves)
                {
                    var trial = Moves.ApplyMoves(curState, mm);
                    if (scoreFn(trial) >= targetScore)
                    {
                        var result = new List<string>(path);
                        result.AddRange(mm);
                        return (result, trial);
                    }
                    var key = StateKey(trial);
                    if (!visited.Contains(key))
                    {
                        visited.Add(key);
                        var newPath = new List<string>(path);
                        newPath.AddRange(mm);
                        queue.Enqueue((trial, newPath, rounds + 1));
                    }
                }
            }
            throw new SolverException("last-layer algorithm did not converge");
        }

        static (List<string> moves, CubeState state) SolveLastLayer(CubeState state)
        {
            var moves = new List<string>();

            // Edge orientation first -- stable under every corner algorithm below.
            var (seq1, s1) = ApplyBest(state, new List<List<string>> { EdgeOrientAlg },
                s => LastLayerEdgeTargets.Count(t => EdgeOriented(s, t)), 4, 4);
            moves.AddRange(seq1);
            state = s1;

            // Position and orientation together -- a twist alg applied before
            // corners are positioned can shuffle which cubie is where even
            // while satisfying "shows U on top", so these must be solved jointly.
            var (seq2, s2) = ApplyBest(state,
                new List<List<string>> { TPerm, CornerCycleAlg, CornerCycleAlgInv, CornerSwapAlg, CornerTwistAlg, CornerTwistAlgInv },
                s => LastLayerCornerTargets.Count(t => PieceIsSolved(s, t, false)), 4, 8);
            moves.AddRange(seq2);
            state = s2;

            var (seq3, s3) = ApplyBest(state,
                new List<List<string>> { EdgeCycleAlg, EdgeCycleAlgInv, EdgeSwapAlg },
                s => LastLayerEdgeTargets.Count(t => PieceIsSolved(s, t, true)), 4, 3);
            moves.AddRange(seq3);
            state = s3;

            return (moves, state);
        }

        public const int MaxSaneMoves = 400;

        public static (List<string> moves, List<(string name, int end)> stageBounds) Solve(
            CubeState state, int crossDepth = 6, int cornerDepth = 7, int edgeDepth = 7)
        {
            var result = Validation.Validate(state);
            if (!result.Ok)
                throw new SolverException($"{result.ErrorCode}: {result.Message}");

            var s = state.Copy();
            var solution = new List<string>();
            var stageBounds = new List<(string name, int end)>();

            void Record(string name, List<string> seq)
            {
                solution.AddRange(seq);
                stageBounds.Add((name, solution.Count));
            }

            var locked = new List<(P3 home, bool isEdge)>();
            List<string> seq;
            (seq, s, locked) = SolvePieces(s, Stage1CrossTargets, true, locked, crossDepth, Moves.AllMoves);
            Record("cross", seq);
            (seq, s, locked) = SolvePieces(s, Stage2CornerTargets, false, locked, cornerDepth, Moves.AllMoves);
            Record("first_layer_corners", seq);
            (seq, s, locked) = SolvePieces(s, Stage3MiddleEdgeTargets, true, locked, edgeDepth, NoDMoves);
            Record("middle_layer", seq);
            var (llSeq, llState) = SolveLastLayer(s);
            s = llState;
            Record("last_layer", llSeq);

            if (!s.Equals(CubeState.Solved()))
                throw new SolverException("internal error: solver finished but the cube is not solved");
            if (solution.Count > MaxSaneMoves)
                throw new SolverException($"internal error: solution unexpectedly long ({solution.Count} moves)");

            return (solution, stageBounds);
        }

        // ---------------------------------------------------------------
        // Human-facing move enrichment
        // ---------------------------------------------------------------

        public static readonly Dictionary<char, string> FaceNames = new Dictionary<char, string>
        {
            ['U'] = "Top", ['D'] = "Bottom", ['L'] = "Left", ['R'] = "Right", ['F'] = "Front", ['B'] = "Back",
        };

        static readonly Dictionary<string, string> DirectionPhrase = new Dictionary<string, string>
        {
            ["CW"] = "clockwise (like turning a doorknob to the right), looking straight at that face",
            ["CCW"] = "counter-clockwise (like turning a doorknob to the left), looking straight at that face",
            ["180"] = "180 degrees (a half turn -- direction doesn't matter)",
        };

        static readonly Dictionary<string, string> DirectionBySuffix =
            new Dictionary<string, string> { [""] = "CW", ["'"] = "CCW", ["2"] = "180" };

        public sealed class MoveInstruction
        {
            public string Notation;
            public char Face;
            public string FaceName;
            public string Direction;
            public int StepIndex;
            public int TotalSteps;
            public string Stage;
            public string Description;
        }

        static string StageForIndex(int i, List<(string name, int end)> stageBounds)
        {
            foreach (var (name, end) in stageBounds)
                if (i < end) return name;
            return stageBounds.Count > 0 ? stageBounds[stageBounds.Count - 1].name : "unknown";
        }

        public static List<MoveInstruction> Enrich(List<string> moves, List<(string name, int end)> stageBounds)
        {
            int total = moves.Count;
            var result = new List<MoveInstruction>();
            for (int i = 0; i < moves.Count; i++)
            {
                string m = moves[i];
                char face = m[0];
                string suffix = m.Substring(1);
                string direction = DirectionBySuffix[suffix];
                string stage = StageForIndex(i, stageBounds);
                result.Add(new MoveInstruction
                {
                    Notation = m,
                    Face = face,
                    FaceName = FaceNames[face],
                    Direction = direction,
                    StepIndex = i + 1,
                    TotalSteps = total,
                    Stage = stage,
                    Description = $"Turn the {FaceNames[face]} ({face}) face {DirectionPhrase[direction]}.",
                });
            }
            return result;
        }
    }
}
