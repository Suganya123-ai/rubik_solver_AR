using System.Collections.Generic;
using RubikSolverAR.AR;
using RubikSolverAR.Core;
using UnityEngine;

namespace RubikSolverAR.App
{
    /// <summary>One step's worth of info for the presenter -- local replacement for main.py's /api/step JSON shape.</summary>
    public sealed class StepView
    {
        public bool Done;
        public int TotalSteps;
        public Solver.MoveInstruction Instruction;
    }

    /// <summary>
    /// Local replacement for main.py's FastAPI routes + in-memory SESSION
    /// dict: the same state machine (scan all 6 faces -> validate -> solve
    /// -> step through instructions one at a time, with back/next/reset),
    /// just as plain method calls instead of HTTP endpoints, since the
    /// whole app now runs on-device with no server to call.
    /// </summary>
    public sealed class AppController : MonoBehaviour
    {
        public ScanController Scan;
        public SolveStepPresenter Presenter;

        List<Solver.MoveInstruction> _instructions = new List<Solver.MoveInstruction>();
        int _stepIndex;

        void Awake()
        {
            if (Scan != null) Scan.OnAllFacesScanned += OnAllFacesScanned;
        }

        void OnAllFacesScanned(Dictionary<char, List<string>> colorGrid)
        {
            var (state, result) = Validation.ValidateScan(colorGrid);
            if (!result.Ok)
            {
                Debug.LogWarning(
                    $"Scan invalid ({result.ErrorCode}): {result.Message} Re-scan the faces you're least sure about, starting over.");
                Scan.ResetScan();
                return;
            }

            try
            {
                var (moves, stageBounds) = Solver.Solve(state);
                _instructions = Solver.Enrich(moves, stageBounds);
                _stepIndex = 0;
                Presenter?.ShowStep(CurrentStep());
            }
            catch (SolverException e)
            {
                Debug.LogError($"Solver error: {e.Message}");
                Scan.ResetScan();
            }
        }

        public StepView CurrentStep()
        {
            if (_instructions.Count == 0) return null;
            if (_stepIndex >= _instructions.Count)
                return new StepView { Done = true, TotalSteps = _instructions.Count };
            return new StepView { Done = false, Instruction = _instructions[_stepIndex] };
        }

        public void NextStep()
        {
            _stepIndex = Mathf.Min(_stepIndex + 1, _instructions.Count);
            Presenter?.ShowStep(CurrentStep());
        }

        public void BackStep()
        {
            _stepIndex = Mathf.Max(_stepIndex - 1, 0);
            Presenter?.ShowStep(CurrentStep());
        }

        public void ResetAll()
        {
            _instructions = new List<Solver.MoveInstruction>();
            _stepIndex = 0;
            Scan?.ResetScan();
        }
    }
}
