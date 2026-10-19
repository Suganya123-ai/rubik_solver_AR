using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace RubikSolverAR.AR
{
    /// <summary>
    /// AR-appropriate reinterpretation of static/cube_diagram.js. Rather
    /// than a pixel-exact SVG unfolded net with hand-drawn curved arrows
    /// (fine on a web page, fussy to read at a glance through AR optics),
    /// this shows:
    ///   (a) a small unfolded net with the target face highlighted -- the
    ///       same "which face" information, via plain colored squares, and
    ///   (b) a turn-direction ring built from Unity UI's built-in radial
    ///       Image fill, reading clearly as "mostly clockwise" /
    ///       "mostly counter-clockwise" / "full turn" at HUD distance.
    /// The step's own big text (face name + CW/CCW/180, from
    /// Solver.MoveInstruction) remains the precise instruction; this is a
    /// glanceable visual aid, not the sole source of truth.
    /// </summary>
    public sealed class CubeDiagramBuilder : MonoBehaviour
    {
        [Header("Wiring")]
        [Tooltip("Parent RectTransform the 6-face net is built under (sized ~240x180).")]
        public RectTransform NetContainer;
        [Tooltip("Image.Type = Filled, FillMethod = Radial360.")]
        public Image TurnRing;
        [Tooltip("Small triangle graphic rotated to the ring's leading edge; hidden for 180-degree turns.")]
        public RectTransform ArrowHead;
        [Tooltip("Optional big face-letter label at the ring's center.")]
        public Text FaceLabel;

        static readonly Color RestingCellColor = new Color(0.133f, 0.145f, 0.173f); // #22252c
        static readonly Color HighlightCellColor = new Color(0.165f, 0.208f, 0.314f); // #2a3550

        static readonly Dictionary<char, Vector2> FaceNetPos = new Dictionary<char, Vector2>
        {
            ['U'] = new Vector2(60, 0),
            ['L'] = new Vector2(0, 60),
            ['F'] = new Vector2(60, 60),
            ['R'] = new Vector2(120, 60),
            ['B'] = new Vector2(180, 60),
            ['D'] = new Vector2(60, 120),
        };

        readonly Dictionary<char, Image> _faceCells = new Dictionary<char, Image>();
        bool _built;

        void Awake()
        {
            if (NetContainer != null) BuildNet();
        }

        void BuildNet()
        {
            if (_built) return;
            foreach (var kv in FaceNetPos)
            {
                var cellGo = new GameObject("face_" + kv.Key, typeof(RectTransform), typeof(Image));
                var rt = (RectTransform)cellGo.transform;
                rt.SetParent(NetContainer, false);
                rt.pivot = new Vector2(0, 1);
                rt.anchorMin = rt.anchorMax = new Vector2(0, 1);
                rt.anchoredPosition = new Vector2(kv.Value.x, -kv.Value.y);
                rt.sizeDelta = new Vector2(58, 58);
                cellGo.GetComponent<Image>().color = RestingCellColor;
                _faceCells[kv.Key] = cellGo.GetComponent<Image>();
            }
            _built = true;
        }

        /// <summary>Call once per solve step. `direction` is "CW", "CCW" or "180" (Solver.MoveInstruction.Direction).</summary>
        public void Render(char face, string direction)
        {
            if (!_built) BuildNet();

            foreach (var kv in _faceCells)
                kv.Value.color = kv.Key == face ? HighlightCellColor : RestingCellColor;

            if (FaceLabel != null) FaceLabel.text = face.ToString();

            if (TurnRing != null)
            {
                TurnRing.type = Image.Type.Filled;
                TurnRing.fillMethod = Image.FillMethod.Radial360;
                TurnRing.fillOrigin = (int)Image.Origin360.Top;
                if (direction == "180")
                {
                    TurnRing.fillAmount = 1f;
                    TurnRing.fillClockwise = true;
                }
                else
                {
                    TurnRing.fillAmount = 0.72f;
                    TurnRing.fillClockwise = direction == "CW";
                }
            }

            if (ArrowHead != null && TurnRing != null)
            {
                bool hideArrow = direction == "180"; // full ring: direction doesn't matter, no single arrowhead
                ArrowHead.gameObject.SetActive(!hideArrow);
                if (!hideArrow)
                {
                    float sweepDeg = TurnRing.fillAmount * 360f;
                    float endDeg = TurnRing.fillClockwise ? sweepDeg : -sweepDeg; // 0 deg = top (Origin360.Top)
                    ArrowHead.localRotation = Quaternion.Euler(0, 0, -endDeg);
                }
            }
        }
    }
}
