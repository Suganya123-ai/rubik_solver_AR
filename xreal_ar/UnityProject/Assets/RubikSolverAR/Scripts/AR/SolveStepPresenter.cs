using RubikSolverAR.App;
using UnityEngine;
using UnityEngine.UI;

namespace RubikSolverAR.AR
{
    /// <summary>
    /// AR-anchored step-by-step solve display: port of guide.js's
    /// renderStep(). Shows one move at a time with big notation, a
    /// plain-English description, a progress bar, and the
    /// CubeDiagramBuilder turn indicator.
    /// </summary>
    public sealed class SolveStepPresenter : MonoBehaviour
    {
        public Text StepCountText;
        public Text StageNameText;
        public Text MoveNotationText;
        public Text MoveDescriptionText;
        [Tooltip("Image.Type = Filled, FillMethod = Horizontal, matching the web progress bar.")]
        public Image ProgressFill;
        public CubeDiagramBuilder Diagram;
        public GameObject MoveView;
        public GameObject SolvedView;
        public Button BackButton;

        public void ShowStep(StepView step)
        {
            if (step == null) return;

            if (step.Done)
            {
                if (MoveView != null) MoveView.SetActive(false);
                if (SolvedView != null) SolvedView.SetActive(true);
                if (ProgressFill != null) ProgressFill.fillAmount = 1f;
                if (StepCountText != null) StepCountText.text = $"{step.TotalSteps}/{step.TotalSteps} moves complete";
                if (StageNameText != null) StageNameText.text = "";
                return;
            }

            if (MoveView != null) MoveView.SetActive(true);
            if (SolvedView != null) SolvedView.SetActive(false);

            var instr = step.Instruction;
            float pct = instr.TotalSteps > 0 ? (instr.StepIndex - 1) / (float)instr.TotalSteps : 0f;
            if (ProgressFill != null) ProgressFill.fillAmount = pct;
            if (StepCountText != null) StepCountText.text = $"Step {instr.StepIndex}/{instr.TotalSteps}";
            if (StageNameText != null) StageNameText.text = instr.Stage.Replace('_', ' ');
            if (MoveNotationText != null) MoveNotationText.text = instr.Notation;
            if (MoveDescriptionText != null) MoveDescriptionText.text = instr.Description;
            if (BackButton != null) BackButton.interactable = instr.StepIndex > 1;
            Diagram?.Render(instr.Face, instr.Direction);
        }
    }
}
