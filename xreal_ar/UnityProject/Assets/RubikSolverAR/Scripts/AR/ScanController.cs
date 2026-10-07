using System;
using System.Collections.Generic;
using RubikSolverAR.CameraSource;
using RubikSolverAR.Core;
using UnityEngine;
using UnityEngine.UI;

namespace RubikSolverAR.AR
{
    /// <summary>
    /// Per-face scanning flow: AR port of static/scan.js's scan screen.
    /// Drives an ICubeCameraSource through the fixed face order, runs
    /// ColorDetect on each capture, and lets the wearer correct any
    /// misdetected sticker from a palette before confirming -- the same UX
    /// contract as the original web scan screen, on AR UI widgets instead
    /// of DOM elements.
    /// </summary>
    public sealed class ScanController : MonoBehaviour
    {
        public static readonly char[] FaceOrder = { 'U', 'F', 'D', 'B', 'L', 'R' };

        static readonly Dictionary<char, string> FaceInstructions = new Dictionary<char, string>
        {
            ['U'] = "Hold the cube normally, then tilt it back so the TOP face points at the camera.",
            ['F'] = "Hold the cube normally and show the FRONT face (the one facing you) to the camera.",
            ['D'] = "Flip the cube upside down (keep the same face toward you) and show the BOTTOM face.",
            ['B'] = "Turn the cube around to show the BACK face to the camera.",
            ['L'] = "Turn the cube to show the LEFT face to the camera.",
            ['R'] = "Turn the cube to show the RIGHT face to the camera.",
        };

        [Header("Wiring")]
        [Tooltip("Must implement ICubeCameraSource -- PhoneCameraSource or NrealRgbCameraSource.")]
        public MonoBehaviour CameraSourceBehaviour;
        public Text FaceProgressText;
        public Text InstructionsText;
        public Text ErrorText;
        [Tooltip("9 sticker-grid cells, each needs an Image + Button component.")]
        public Image[] GridPreviewCells = new Image[9];
        [Tooltip("6 palette buttons, in ColorDetect.ColorNames order: white, yellow, red, orange, green, blue.")]
        public Button[] PaletteButtons = new Button[6];
        public GameObject CameraPanel;
        public GameObject ConfirmPanel;

        ICubeCameraSource _cameraSource;
        int _faceIndex;
        string[] _detectedColors;
        int _selectedCell = -1;

        public Dictionary<char, List<string>> ConfirmedFaces { get; } = new Dictionary<char, List<string>>();

        /// <summary>Raised once all 6 faces are confirmed, with the final color grid.</summary>
        public event Action<Dictionary<char, List<string>>> OnAllFacesScanned;

        void Awake()
        {
            _cameraSource = CameraSourceBehaviour as ICubeCameraSource;
            if (_cameraSource == null)
                Debug.LogError("ScanController.CameraSourceBehaviour must implement ICubeCameraSource");

            for (int i = 0; i < PaletteButtons.Length && i < ColorDetect.ColorNames.Length; i++)
            {
                string color = ColorDetect.ColorNames[i];
                PaletteButtons[i].onClick.AddListener(() => OnPaletteColorPicked(color));
            }
        }

        void Start()
        {
            _cameraSource?.StartCapture();
            RenderProgress();
        }

        void OnDestroy() => _cameraSource?.StopCapture();

        char CurrentFace => FaceOrder[_faceIndex];

        void RenderProgress()
        {
            if (FaceProgressText != null)
            {
                var chips = new List<string>();
                for (int i = 0; i < FaceOrder.Length; i++)
                    chips.Add(i < _faceIndex ? $"[{FaceOrder[i]}]" : i == _faceIndex ? $">{FaceOrder[i]}<" : FaceOrder[i].ToString());
                FaceProgressText.text = string.Join(" ", chips);
            }
            if (InstructionsText != null) InstructionsText.text = FaceInstructions[CurrentFace];
        }

        /// <summary>Wire to whatever "capture" input you use -- an XREAL controller trigger, an air-tap, or a phone on-screen button.</summary>
        public void OnCaptureTriggered()
        {
            ClearError();
            var frame = _cameraSource?.CaptureSquareFrame();
            if (frame == null)
            {
                ShowError("Camera not ready -- try again in a moment.");
                return;
            }
            _detectedColors = ColorDetect.DetectFaceColors(frame);
            ShowConfirmPanel();
        }

        void ShowConfirmPanel()
        {
            if (CameraPanel != null) CameraPanel.SetActive(false);
            if (ConfirmPanel != null) ConfirmPanel.SetActive(true);
            _selectedCell = -1;
            RenderGridPreview();
        }

        void RenderGridPreview()
        {
            for (int i = 0; i < GridPreviewCells.Length && _detectedColors != null && i < _detectedColors.Length; i++)
            {
                GridPreviewCells[i].color = ColorToUnity(_detectedColors[i]);
                int captured = i;
                var button = GridPreviewCells[i].GetComponent<Button>();
                if (button != null)
                {
                    button.onClick.RemoveAllListeners();
                    button.onClick.AddListener(() => _selectedCell = captured);
                }
            }
        }

        void OnPaletteColorPicked(string color)
        {
            if (_selectedCell < 0 || _detectedColors == null) return;
            _detectedColors[_selectedCell] = color;
            RenderGridPreview();
        }

        public void OnRetake()
        {
            if (ConfirmPanel != null) ConfirmPanel.SetActive(false);
            if (CameraPanel != null) CameraPanel.SetActive(true);
            _detectedColors = null;
        }

        public void OnConfirmFace()
        {
            ConfirmedFaces[CurrentFace] = new List<string>(_detectedColors);
            _faceIndex++;
            if (ConfirmPanel != null) ConfirmPanel.SetActive(false);
            if (CameraPanel != null) CameraPanel.SetActive(true);
            _detectedColors = null;

            if (_faceIndex >= FaceOrder.Length)
                OnAllFacesScanned?.Invoke(ConfirmedFaces);
            else
                RenderProgress();
        }

        /// <summary>Call after a rejected build-and-solve (AppController) to re-scan from the top.</summary>
        public void ResetScan()
        {
            ConfirmedFaces.Clear();
            _faceIndex = 0;
            _detectedColors = null;
            if (ConfirmPanel != null) ConfirmPanel.SetActive(false);
            if (CameraPanel != null) CameraPanel.SetActive(true);
            RenderProgress();
        }

        void ShowError(string message)
        {
            if (ErrorText == null) return;
            ErrorText.text = message;
            ErrorText.gameObject.SetActive(true);
        }

        void ClearError()
        {
            if (ErrorText != null) ErrorText.gameObject.SetActive(false);
        }

        static Color ColorToUnity(string name)
        {
            switch (name)
            {
                case "white": return Color.white;
                case "yellow": return Color.yellow;
                case "red": return new Color(0.78f, 0.06f, 0.12f);
                case "orange": return new Color(1f, 0.39f, 0f);
                case "green": return new Color(0f, 0.59f, 0.27f);
                case "blue": return new Color(0f, 0.27f, 0.71f);
                default: return Color.magenta;
            }
        }
    }
}
