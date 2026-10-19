using System;
using System.Linq;

namespace RubikSolverAR.Core
{
    /// <summary>
    /// Face letters and index-layout constants. Direct port of
    /// cube/cube_state.py's module-level constants (FACES, FACE_OFFSET,
    /// CENTER_INDEX, OPPOSITE_FACE, flat_index).
    /// </summary>
    public static class CubeLayout
    {
        public static readonly char[] Faces = { 'U', 'R', 'F', 'D', 'L', 'B' };

        public static readonly System.Collections.Generic.Dictionary<char, int> FaceOffset = BuildFaceOffset();
        public static readonly System.Collections.Generic.Dictionary<char, int> CenterIndex = BuildCenterIndex();

        public static readonly System.Collections.Generic.Dictionary<char, char> OppositeFace =
            new System.Collections.Generic.Dictionary<char, char>
            {
                ['U'] = 'D', ['D'] = 'U', ['L'] = 'R', ['R'] = 'L', ['F'] = 'B', ['B'] = 'F',
            };

        static System.Collections.Generic.Dictionary<char, int> BuildFaceOffset()
        {
            var d = new System.Collections.Generic.Dictionary<char, int>();
            for (int i = 0; i < Faces.Length; i++) d[Faces[i]] = i * 9;
            return d;
        }

        static System.Collections.Generic.Dictionary<char, int> BuildCenterIndex()
        {
            var d = new System.Collections.Generic.Dictionary<char, int>();
            foreach (var f in Faces) d[f] = FaceOffset[f] + 4;
            return d;
        }

        public static int FlatIndex(char face, int r, int c) => FaceOffset[face] + r * 3 + c;
    }

    /// <summary>
    /// 54-sticker cube state. The engine's internal sticker alphabet is the
    /// face letters themselves -- a solved cube has every sticker on face X
    /// labeled 'X'. This keeps the engine agnostic to any real-world color
    /// scheme: translating a physical scan's color names to this alphabet
    /// (via each face's scanned center color) is a one-time step done at the
    /// app boundary (see Validation.TranslateToFaceLetters), not here.
    ///
    /// Direct port of cube/cube_state.py's CubeState / solved_state /
    /// solved_array.
    /// </summary>
    public sealed class CubeState : IEquatable<CubeState>
    {
        public readonly char[] Arr; // length 54

        public CubeState(char[] arr)
        {
            if (arr == null || arr.Length != 54)
                throw new ArgumentException("CubeState array must have length 54");
            Arr = arr;
        }

        public static CubeState Solved()
        {
            var arr = new char[54];
            foreach (var f in CubeLayout.Faces)
            {
                int o = CubeLayout.FaceOffset[f];
                for (int i = 0; i < 9; i++) arr[o + i] = f;
            }
            return new CubeState(arr);
        }

        public char Sticker(char face, int r, int c) => Arr[CubeLayout.FlatIndex(face, r, c)];

        public CubeState Copy() => new CubeState((char[])Arr.Clone());

        public bool Equals(CubeState other)
        {
            if (other == null) return false;
            for (int i = 0; i < 54; i++) if (Arr[i] != other.Arr[i]) return false;
            return true;
        }

        public override bool Equals(object obj) => Equals(obj as CubeState);
        public override int GetHashCode() => new string(Arr).GetHashCode();

        public override string ToString()
        {
            return string.Join(" | ", CubeLayout.Faces.Select(f =>
                f + ": " + new string(Arr, CubeLayout.FaceOffset[f], 9)));
        }
    }
}
