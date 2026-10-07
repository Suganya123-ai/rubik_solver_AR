using System;
using System.Collections.Generic;
using System.Linq;

namespace RubikSolverAR.Core
{
    /// <summary>
    /// Integer 3-vector, each axis restricted to {-1,0,1} in practice.
    /// Stands in for Python's plain (x,y,z) tuples used throughout the
    /// original engine as both cubie positions and facelet directions.
    /// </summary>
    public readonly struct P3 : IEquatable<P3>
    {
        public readonly int X, Y, Z;
        public P3(int x, int y, int z) { X = x; Y = y; Z = z; }

        public bool Equals(P3 o) => X == o.X && Y == o.Y && Z == o.Z;
        public override bool Equals(object obj) => obj is P3 p && Equals(p);
        public override int GetHashCode() => (X + 2) * 25 + (Y + 2) * 5 + (Z + 2);
        public override string ToString() => $"({X},{Y},{Z})";
    }

    readonly struct StickerKey : IEquatable<StickerKey>
    {
        public readonly P3 CubiePos, FaceletDir;
        public StickerKey(P3 cubiePos, P3 faceletDir) { CubiePos = cubiePos; FaceletDir = faceletDir; }
        public bool Equals(StickerKey o) => CubiePos.Equals(o.CubiePos) && FaceletDir.Equals(o.FaceletDir);
        public override bool Equals(object obj) => obj is StickerKey k && Equals(k);
        public override int GetHashCode() => CubiePos.GetHashCode() * 31 + FaceletDir.GetHashCode();
    }

    /// <summary>
    /// The move engine: direct port of cube/moves.py. Each sticker is
    /// (cubie_pos, facelet_dir): cubie_pos identifies which of the 26
    /// non-center cubies it belongs to, facelet_dir is the unit axis vector
    /// the sticker is glued to. All 18 quarter/half turns are derived as
    /// precomputed sticker permutations from this 3D coordinate model, not
    /// hand-authored -- same approach as the Python original, so this port
    /// only needs the coordinate conventions below to match exactly.
    /// </summary>
    public static class Moves
    {
        // Axes: +x=R, -x=L, +y=U, -y=D, +z=F, -z=B.
        public static readonly IReadOnlyDictionary<char, P3> FaceletDir = new Dictionary<char, P3>
        {
            ['U'] = new P3(0, 1, 0),
            ['D'] = new P3(0, -1, 0),
            ['F'] = new P3(0, 0, 1),
            ['B'] = new P3(0, 0, -1),
            ['R'] = new P3(1, 0, 0),
            ['L'] = new P3(-1, 0, 0),
        };

        // cubie_pos for grid cell (r,c) on `face`, viewed head-on from
        // outside that face (right-handed screen convention: right x up =
        // outward normal), identical to Python's _grid_cubie_pos.
        static P3 GridCubiePos(char face, int r, int c)
        {
            switch (face)
            {
                case 'U': return new P3(c - 1, 1, r - 1);
                case 'D': return new P3(c - 1, -1, 1 - r);
                case 'F': return new P3(c - 1, 1 - r, 1);
                case 'B': return new P3(1 - c, 1 - r, -1);
                case 'R': return new P3(1, 1 - r, 1 - c);
                case 'L': return new P3(-1, 1 - r, c - 1);
                default: throw new ArgumentException(face.ToString());
            }
        }

        static readonly Dictionary<StickerKey, int> PosToIndexMap = new Dictionary<StickerKey, int>();
        static readonly Dictionary<int, StickerKey> IndexToPosMap = new Dictionary<int, StickerKey>();

        public static readonly Dictionary<char, int[]> MovePerm = new Dictionary<char, int[]>();
        public static readonly Dictionary<char, int[]> InvMoves = new Dictionary<char, int[]>();
        public static readonly string[] AllMoves = BuildAllMoves();

        static Moves()
        {
            foreach (var face in CubeLayout.Faces)
            {
                for (int r = 0; r < 3; r++)
                {
                    for (int c = 0; c < 3; c++)
                    {
                        int idx = CubeLayout.FlatIndex(face, r, c);
                        var cp = GridCubiePos(face, r, c);
                        var fd = FaceletDir[face];
                        var key = new StickerKey(cp, fd);
                        PosToIndexMap[key] = idx;
                        IndexToPosMap[idx] = key;
                    }
                }
            }

            foreach (var f in "URFDLB")
            {
                var perm = BuildMovePerm(f);
                MovePerm[f] = perm;
                InvMoves[f] = InvertPerm(perm);
            }
        }

        /// <summary>Flat sticker index for a given cubie position + facelet direction.</summary>
        public static int Index(P3 cubiePos, P3 faceletDir) => PosToIndexMap[new StickerKey(cubiePos, faceletDir)];

        // 90-degree rotation of (x,y,z), clockwise as viewed by someone
        // standing outside that face looking at it (the physical turning
        // convention) -- identical to Python's _ROTATE.
        static P3 Rotate(char face, P3 p)
        {
            int x = p.X, y = p.Y, z = p.Z;
            switch (face)
            {
                case 'U': return new P3(-z, y, x);
                case 'D': return new P3(z, y, -x);
                case 'F': return new P3(y, -x, z);
                case 'B': return new P3(-y, x, z);
                case 'R': return new P3(x, z, -y);
                case 'L': return new P3(x, -z, y);
                default: throw new ArgumentException(face.ToString());
            }
        }

        // (axis index 0=x,1=y,2=z, layer value) of the 9 cubies a face turn
        // affects -- identical to Python's _LAYER.
        static void Layer(char face, out int axis, out int layerValue)
        {
            switch (face)
            {
                case 'U': axis = 1; layerValue = 1; return;
                case 'D': axis = 1; layerValue = -1; return;
                case 'F': axis = 2; layerValue = 1; return;
                case 'B': axis = 2; layerValue = -1; return;
                case 'R': axis = 0; layerValue = 1; return;
                case 'L': axis = 0; layerValue = -1; return;
                default: throw new ArgumentException(face.ToString());
            }
        }

        static int AxisOf(P3 p, int axis)
        {
            if (axis == 0) return p.X;
            if (axis == 1) return p.Y;
            return p.Z;
        }

        static int[] BuildMovePerm(char face)
        {
            Layer(face, out int axis, out int layerValue);
            var perm = new int[54];
            for (int j = 0; j < 54; j++) perm[j] = j;
            for (int j = 0; j < 54; j++)
            {
                var key = IndexToPosMap[j];
                if (AxisOf(key.CubiePos, axis) != layerValue) continue;
                var cp2 = Rotate(face, key.CubiePos);
                var fd2 = Rotate(face, key.FaceletDir);
                int i = PosToIndexMap[new StickerKey(cp2, fd2)];
                perm[i] = j;
            }
            return perm;
        }

        static int[] InvertPerm(int[] p)
        {
            var inv = new int[p.Length];
            for (int i = 0; i < p.Length; i++) inv[p[i]] = i;
            return inv;
        }

        static string[] BuildAllMoves()
        {
            var list = new List<string>();
            foreach (var f in "URFDLB")
                foreach (var s in new[] { "", "'", "2" })
                    list.Add(f + s);
            return list.ToArray();
        }

        static char[] Permute(char[] arr, int[] perm)
        {
            var result = new char[arr.Length];
            for (int i = 0; i < perm.Length; i++) result[i] = arr[perm[i]];
            return result;
        }

        public static CubeState ApplyMove(CubeState state, string move)
        {
            char baseFace = move[0];
            string suffix = move.Substring(1);
            char[] arr = state.Arr;
            char[] result;
            switch (suffix)
            {
                case "":
                    result = Permute(arr, MovePerm[baseFace]);
                    break;
                case "'":
                    result = Permute(arr, InvMoves[baseFace]);
                    break;
                case "2":
                    result = Permute(Permute(arr, MovePerm[baseFace]), MovePerm[baseFace]);
                    break;
                default:
                    throw new ArgumentException($"bad move '{move}'");
            }
            return new CubeState(result);
        }

        public static CubeState ApplyMoves(CubeState state, IEnumerable<string> moves)
        {
            foreach (var m in moves) state = ApplyMove(state, m);
            return state;
        }

        public static char CenterColor(CubeState state, char face) => state.Arr[CubeLayout.CenterIndex[face]];
    }
}
