using System;
using System.Collections.Generic;
using System.Linq;

namespace RubikSolverAR.Core
{
    /// <summary>
    /// Result of a validation tier. Direct port of validation.py's
    /// ValidationResult namedtuple; the tier-specific extra data Python
    /// stuffed into a loose `details` dict is instead split into typed,
    /// nullable properties here (only the tier that produced a given result
    /// sets its own).
    /// </summary>
    public sealed class ValidationResult
    {
        public readonly bool Ok;
        public readonly string ErrorCode;
        public readonly string Message;

        public Dictionary<string, int> ColorCounts { get; set; }
        public Dictionary<char, string> Centers { get; set; }
        public Dictionary<string, char> ColorToFace { get; set; }

        public ValidationResult(bool ok, string errorCode, string message)
        {
            Ok = ok;
            ErrorCode = errorCode;
            Message = message;
        }
    }

    /// <summary>
    /// Checks a scan is a physically legal cube state (right color counts,
    /// no impossible corners/edges, correct permutation and orientation
    /// parity) before attempting to solve it. Direct port of
    /// cube/validation.py.
    /// </summary>
    public static class Validation
    {
        public static readonly List<P3> CornerPositions = BuildCornerPositions();
        public static readonly List<P3> EdgePositions = BuildEdgePositions();

        static List<P3> BuildCornerPositions()
        {
            var list = new List<P3>();
            int[] signs = { -1, 1 };
            foreach (var sx in signs)
                foreach (var sy in signs)
                    foreach (var sz in signs)
                        list.Add(new P3(sx, sy, sz));
            return list;
        }

        static List<P3> BuildEdgePositions()
        {
            var list = new List<P3>();
            int[] signs = { -1, 1 };
            foreach (var sx in signs) foreach (var sy in signs) list.Add(new P3(sx, sy, 0));
            foreach (var sx in signs) foreach (var sz in signs) list.Add(new P3(sx, 0, sz));
            foreach (var sy in signs) foreach (var sz in signs) list.Add(new P3(0, sy, sz));
            return list;
        }

        /// <summary>
        /// 3 facelet indices for corner `p`, in a fixed clockwise-as-viewed-
        /// from-outside order. The raw (x,y,z) axis order is clockwise for
        /// one of the two corner "checkerboard" parity classes and mirrored
        /// for the other, so it's flipped for odd-parity corners to keep the
        /// order consistently clockwise everywhere -- required for
        /// orientation to reduce to a simple cyclic-rotation check.
        /// </summary>
        public static int[] CornerFaceletIndices(P3 p)
        {
            int sx = p.X, sy = p.Y, sz = p.Z;
            int xi = Moves.Index(p, new P3(sx, 0, 0));
            int yi = Moves.Index(p, new P3(0, sy, 0));
            int zi = Moves.Index(p, new P3(0, 0, sz));
            if (sx * sy * sz == 1) return new[] { xi, yi, zi };
            return new[] { xi, zi, yi };
        }

        public static int[] EdgeFaceletIndices(P3 p)
        {
            var dirs = new List<P3>();
            if (p.X != 0) dirs.Add(new P3(p.X, 0, 0));
            if (p.Y != 0) dirs.Add(new P3(0, p.Y, 0));
            if (p.Z != 0) dirs.Add(new P3(0, 0, p.Z));
            return dirs.Select(d => Moves.Index(p, d)).ToArray();
        }

        /// <summary>Canonical key for a frozenset-of-letters lookup: sorted chars as a string.</summary>
        public static string SlotKey(IEnumerable<char> letters)
        {
            var sorted = letters.ToArray();
            Array.Sort(sorted);
            return new string(sorted);
        }

        public static readonly char[] SolvedArr = CubeState.Solved().Arr;

        public static readonly Dictionary<string, P3> CornerSlotByLetters =
            BuildSlotMap(CornerPositions, CornerFaceletIndices);
        public static readonly Dictionary<string, P3> EdgeSlotByLetters =
            BuildSlotMap(EdgePositions, EdgeFaceletIndices);

        static Dictionary<string, P3> BuildSlotMap(List<P3> positions, Func<P3, int[]> faceletFn)
        {
            var map = new Dictionary<string, P3>();
            foreach (var p in positions)
            {
                var idxs = faceletFn(p);
                var letters = idxs.Select(i => SolvedArr[i]);
                map[SlotKey(letters)] = p;
            }
            return map;
        }

        public static List<char[]> Rotations(char[] t)
        {
            int n = t.Length;
            var result = new List<char[]>();
            for (int k = 0; k < n; k++)
            {
                var r = new char[n];
                for (int i = 0; i < n; i++) r[i] = t[(i + k) % n];
                result.Add(r);
            }
            return result;
        }

        public static int IndexOfRotation(List<char[]> rotations, char[] observed)
        {
            for (int k = 0; k < rotations.Count; k++)
                if (rotations[k].SequenceEqual(observed)) return k;
            return -1;
        }

        static int PermutationParity(int[] perm)
        {
            int n = perm.Length;
            var visited = new bool[n];
            int parity = 0;
            for (int i = 0; i < n; i++)
            {
                if (visited[i]) continue;
                int length = 0;
                int k = i;
                while (!visited[k])
                {
                    visited[k] = true;
                    k = perm[k];
                    length++;
                }
                parity += length - 1;
            }
            return parity % 2;
        }

        static string Describe(IEnumerable<char> letters) => "(" + string.Join(", ", letters) + ")";

        /// <summary>
        /// Tier 1: 9-of-each-color + 6 distinct centers. `colorGrid` maps
        /// each face letter to a list of 9 color-name strings from the scan.
        /// </summary>
        public static ValidationResult ValidateColors(Dictionary<char, List<string>> colorGrid)
        {
            var allColors = new List<string>();
            foreach (var f in CubeLayout.Faces) allColors.AddRange(colorGrid[f]);
            var counts = allColors.GroupBy(c => c).ToDictionary(g => g.Key, g => g.Count());
            if (counts.Count != 6 || counts.Values.Any(v => v != 9))
            {
                var countsStr = string.Join(", ", counts.Select(kv => $"{kv.Key}: {kv.Value}"));
                return new ValidationResult(false, "ERROR_COLOR_COUNT",
                    $"Expected exactly 9 stickers of each of 6 colors, got: {{{countsStr}}}. " +
                    "Re-scan the face(s) that look off.")
                { ColorCounts = counts };
            }

            var centers = new Dictionary<char, string>();
            foreach (var f in CubeLayout.Faces) centers[f] = colorGrid[f][4];
            if (centers.Values.Distinct().Count() != 6)
            {
                var centersStr = string.Join(", ", centers.Select(kv => $"{kv.Key}: {kv.Value}"));
                return new ValidationResult(false, "ERROR_DUPLICATE_CENTER",
                    $"Two faces were scanned with the same center color: {{{centersStr}}}. Re-scan.")
                { Centers = centers };
            }

            var colorToFace = centers.ToDictionary(kv => kv.Value, kv => kv.Key);
            return new ValidationResult(true, null, "ok") { ColorToFace = colorToFace, Centers = centers };
        }

        public static CubeState TranslateToFaceLetters(
            Dictionary<char, List<string>> colorGrid,
            Dictionary<string, char> colorToFace)
        {
            var arr = new char[54];
            foreach (var f in CubeLayout.Faces)
            {
                var colors = colorGrid[f];
                for (int i = 0; i < colors.Count; i++)
                    arr[CubeLayout.FaceOffset[f] + i] = colorToFace[colors[i]];
            }
            return new CubeState(arr);
        }

        /// <summary>
        /// Tier 2: every corner/edge slot must hold a physically legal
        /// cubie (distinct, mutually-adjacent face letters -- no
        /// duplicates, no opposites).
        /// </summary>
        public static ValidationResult ValidatePieceLegality(CubeState state)
        {
            foreach (var p in CornerPositions)
            {
                var idxs = CornerFaceletIndices(p);
                var letters = idxs.Select(i => state.Arr[i]).ToArray();
                if (letters.Distinct().Count() != 3)
                    return new ValidationResult(false, "ERROR_BAD_CORNER",
                        $"A corner has a repeated color: {Describe(letters)}. Re-scan.");
                foreach (var a in letters)
                    foreach (var b in letters)
                        if (a != b && CubeLayout.OppositeFace[a] == b)
                            return new ValidationResult(false, "ERROR_BAD_CORNER",
                                $"A corner has two opposite colors together: {Describe(letters)}. Re-scan.");
            }

            foreach (var p in EdgePositions)
            {
                var idxs = EdgeFaceletIndices(p);
                var letters = idxs.Select(i => state.Arr[i]).ToArray();
                if (letters.Distinct().Count() != 2)
                    return new ValidationResult(false, "ERROR_BAD_EDGE",
                        $"An edge has a repeated color: {Describe(letters)}. Re-scan.");
                if (CubeLayout.OppositeFace[letters[0]] == letters[1])
                    return new ValidationResult(false, "ERROR_BAD_EDGE",
                        $"An edge has two opposite colors together: {Describe(letters)}. Re-scan.");
            }

            return new ValidationResult(true, null, "ok");
        }

        /// <summary>Tier 3: group-theory parity/orientation invariants that any legally scrambled cube must satisfy.</summary>
        public static ValidationResult ValidateParity(CubeState state)
        {
            var cornerPerm = new List<int>();
            int cornerOrientationSum = 0;
            foreach (var p in CornerPositions)
            {
                var idxs = CornerFaceletIndices(p);
                var observed = idxs.Select(i => state.Arr[i]).ToArray();
                if (!CornerSlotByLetters.TryGetValue(SlotKey(observed), out var home))
                    return new ValidationResult(false, "ERROR_BAD_CORNER",
                        $"Corner colors {Describe(observed)} don't match any legal cubie.");
                cornerPerm.Add(CornerPositions.IndexOf(home));
                var homeTriple = CornerFaceletIndices(home).Select(i => SolvedArr[i]).ToArray();
                int k = IndexOfRotation(Rotations(homeTriple), observed);
                if (k < 0)
                    return new ValidationResult(false, "ERROR_BAD_CORNER",
                        $"Corner {Describe(observed)} is a mirror image of a legal cubie (impossible).");
                cornerOrientationSum += k;
            }

            var edgePerm = new List<int>();
            int edgeOrientationSum = 0;
            foreach (var p in EdgePositions)
            {
                var idxs = EdgeFaceletIndices(p);
                var observed = idxs.Select(i => state.Arr[i]).ToArray();
                if (!EdgeSlotByLetters.TryGetValue(SlotKey(observed), out var home))
                    return new ValidationResult(false, "ERROR_BAD_EDGE",
                        $"Edge colors {Describe(observed)} don't match any legal cubie.");
                edgePerm.Add(EdgePositions.IndexOf(home));
                var homePair = EdgeFaceletIndices(home).Select(i => SolvedArr[i]).ToArray();
                int k = IndexOfRotation(Rotations(homePair), observed);
                if (k < 0)
                    return new ValidationResult(false, "ERROR_BAD_EDGE",
                        $"Edge {Describe(observed)} is a mirror image of a legal cubie (impossible).");
                edgeOrientationSum += k;
            }

            int cornerParity = PermutationParity(cornerPerm.ToArray());
            int edgeParity = PermutationParity(edgePerm.ToArray());
            if (cornerParity != edgeParity)
                return new ValidationResult(false, "ERROR_PARITY",
                    "Corner and edge permutation parity don't match -- this cube state is physically " +
                    "impossible (likely two stickers were swapped during scanning). Re-scan.");
            if (cornerOrientationSum % 3 != 0)
                return new ValidationResult(false, "ERROR_CORNER_TWIST",
                    "A corner appears twisted independently of the others -- this can't happen on a real cube. Re-scan.");
            if (edgeOrientationSum % 2 != 0)
                return new ValidationResult(false, "ERROR_EDGE_FLIP",
                    "A single edge appears flipped independently of the others -- this can't happen on a real cube. Re-scan.");

            return new ValidationResult(true, null, "ok");
        }

        /// <summary>
        /// Full pipeline: raw scanned colors -> (CubeState in face-letter
        /// alphabet, ValidationResult). Returns (null, result) if any tier fails.
        /// </summary>
        public static (CubeState state, ValidationResult result) ValidateScan(
            Dictionary<char, List<string>> colorGrid)
        {
            var r1 = ValidateColors(colorGrid);
            if (!r1.Ok) return (null, r1);
            var state = TranslateToFaceLetters(colorGrid, r1.ColorToFace);
            var r2 = ValidatePieceLegality(state);
            if (!r2.Ok) return (null, r2);
            var r3 = ValidateParity(state);
            if (!r3.Ok) return (null, r3);
            return (state, new ValidationResult(true, null, "ok"));
        }

        /// <summary>Validate an already-translated (face-letter alphabet) CubeState -- tiers 2+3 only.</summary>
        public static ValidationResult Validate(CubeState state)
        {
            var r2 = ValidatePieceLegality(state);
            if (!r2.Ok) return r2;
            return ValidateParity(state);
        }
    }
}
