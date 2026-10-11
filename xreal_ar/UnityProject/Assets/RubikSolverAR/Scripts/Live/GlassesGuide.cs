using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.UI;

namespace RubikSolverAR.Live
{
    /// <summary>
    /// What the wearer sees in the glasses: scan instructions, then the move
    /// to make, a ✓ when the camera sees it, and a clear message after a wrong
    /// move. Put it on a world-space Canvas a little below eye level; wire the
    /// buttons (on the Beam Pro screen / controller) to StartScan, SkipMove and
    /// Rescan.
    ///
    /// Scanning in the glasses: stickers can't easily be tapped to fix, so if
    /// a scan has doubtful stickers it simply scans again (up to
    /// maxAutoRescans times); after that it accepts the best reading, and the
    /// move tracking will report "lost" if that reading was wrong.
    /// </summary>
    public sealed class GlassesGuide : MonoBehaviour
    {
        public LiveServerClient client;

        [Header("Text")]
        public Text titleText;        // "Scan the cube" / "Move 4 of 20"
        public Text moveText;         // big: R'
        public Text detailText;       // instruction or move description
        public Text bannerText;       // ✓ Correct / You did U instead of L ...
        public Image bannerBackground;
        public Image steadyFill;      // Image Type = Filled, Horizontal
        public Text statusText;       // connection + speed, small
        public Text handsText;        // optional: "Turning…" while the hands are turning the cube

        [Header("Behaviour")]
        public int maxAutoRescans = 2;

        static readonly Color Good = new Color(0.24f, 0.81f, 0.56f, 0.9f);
        static readonly Color Warn = new Color(0.96f, 0.71f, 0.27f, 0.9f);
        static readonly Color Bad = new Color(1f, 0.42f, 0.42f, 0.9f);
        static readonly Color Info = new Color(0.31f, 0.55f, 1f, 0.9f);

        int rescans;
        float bannerUntil;

        void OnEnable()
        {
            client.FrameReceived += OnFrame;
            client.MessageReceived += OnMessage;
            client.ConnectionChanged += OnConnection;
            ShowIdle("Connecting to the laptop…");
        }

        void OnDisable()
        {
            client.FrameReceived -= OnFrame;
            client.MessageReceived -= OnMessage;
            client.ConnectionChanged -= OnConnection;
        }

        void Update()
        {
            if (bannerUntil > 0 && Time.time > bannerUntil) Banner("", Info, 0);
            if (statusText != null)
                statusText.text = client.Connected ? $"Connected · {client.RoundTripMs:0} ms" : "Not connected";
        }

        // ---------- buttons ----------
        public void StartScan()
        {
            rescans = 0;
            client.StartScan();
        }

        public void Rescan() => StartScan();
        public void SkipMove() => client.SkipMove();
        /// <summary>While undoing a mistake: give up on undoing and solve again from here.</summary>
        public void NewPlan() => client.NewPlan();

        // ---------- server messages ----------
        void OnConnection(bool up)
        {
            if (up) ShowIdle("Connected. Press Start to scan the cube.");
            else ShowIdle("Lost the connection to the laptop. Reconnecting…");
        }

        void OnFrame(JObject msg)
        {
            // The server tracks the hands too: while they're turning the cube nothing is judged.
            if (handsText) handsText.text = (bool?)msg["hands_busy"] == true ? "Turning… hold still when you're done" : "";
            if (msg["scan"] is JObject scan) ShowScan(scan);
            if (msg["scan_result"] is JObject result) HandleScanResult(result);
            if (msg["track"] is JObject track) ShowTrack(track);
        }

        void OnMessage(JObject msg)
        {
            switch ((string)msg["type"])
            {
                case "scan": ShowScan((JObject)msg["scan"]); break;
                case "scan_result": HandleScanResult((JObject)msg["scan_result"]); break;
                case "track": ShowTrack((JObject)msg["track"]); break;
                case "error": Banner((string)msg["message"] ?? "Something went wrong", Bad, 5); break;
            }
        }

        void ShowIdle(string text)
        {
            Set("Rubik's Cube Solver", "", text);
            Steady(0);
        }

        void ShowScan(JObject scan)
        {
            string p = (string)scan["phase"];
            if (p == "off" || p == "done") return;
            Set(p == "view1" ? "Scan 1 of 2" : "Scan 2 of 2", "", (string)scan["instruction"] ?? "");
            Steady((float?)scan["steady"] ?? 0, (float?)scan["needed"] ?? 5);
            string message = (string)scan["message"];
            if (!string.IsNullOrEmpty(message)) Banner(message, (string)scan["event"] == "captured" ? Good : Warn, 3);
        }

        void HandleScanResult(JObject result)
        {
            bool valid = (bool?)result["valid"] ?? false;
            var doubtful = result["doubtful"] as JArray;
            int unclear = doubtful?.Count ?? 0;
            if (valid && unclear == 0)
            {
                Banner("Scan complete", Good, 2);
                client.AcceptScan(result["colors"]);
            }
            else if (rescans < maxAutoRescans)
            {
                rescans++;
                Banner(unclear > 0 ? $"{unclear} sticker(s) were unclear. Scanning again…" : "That didn't read as a real cube. Scanning again…", Warn, 4);
                client.StartScan();
            }
            else if (valid)
            {
                // Out of retries: accept the best reading; tracking will say "lost" if it's wrong.
                Banner("Using the best reading. If moves aren't recognised, press Rescan.", Warn, 5);
                client.AcceptScan(result["colors"]);
            }
            else
            {
                Banner("The scan doesn't read as a real cube. Check the lighting and press Start again.", Bad, 8);
                ShowIdle("Press Start to scan again.");
            }
        }

        void ShowTrack(JObject t)
        {
            string p = (string)t["phase"];
            if (p == "off") { ShowIdle("Press Start to scan a new cube."); return; }
            string ev = (string)t["event"];
            string message = (string)t["message"];
            if (p == "solved")
            {
                Set("Solved!", "🎉", message ?? "Well done.");
                Banner("Solved!", Good, 0);
                Steady(0);
                return;
            }
            if (p == "undo")
            {
                // A wrong move: show how to turn it back, then the same plan carries on.
                var undo = t["undo"] as JArray;
                string then = undo != null && undo.Count == 1 && t["plan_move"] != null ? $" Then carry on with {t["plan_move"]}." : "";
                Set(undo != null && undo.Count > 1 ? $"Undo the mistake ({undo.Count} moves)" : "Undo the mistake",
                    (string)t["move"] ?? "", ((string)t["description"] ?? "") + then);
                if (moveText) moveText.color = Warn;
            }
            else
            {
                Set($"Move {t["step"]} of {t["total"]}", (string)t["move"] ?? "", (string)t["description"] ?? "");
                if (moveText) moveText.color = Color.white;
            }
            Steady((float?)t["steady"] ?? 0, (float?)t["needed"] ?? 5);
            switch (ev)
            {
                case "correct": Banner(message ?? "✓ Correct", Good, 1.5f); break;
                case "undone": Banner(message ?? "Undone -- back on track", Good, 3); break;
                case "replanned": Banner(message, Info, 3); break;
                case "wrong": Banner(message, Warn, 6); break;
                case "lost": Banner(message, Bad, 6); break;
                case "home": Banner(message, Good, 3); break;
                default:
                    if (p == "home" && message != null) Banner(message, Info, 0);
                    break;
            }
        }

        // ---------- UI helpers ----------
        void Set(string title, string move, string detail)
        {
            if (titleText) titleText.text = title;
            if (moveText) moveText.text = move;
            if (detailText) detailText.text = detail;
        }

        void Steady(float steady, float needed = 5)
        {
            if (steadyFill) steadyFill.fillAmount = needed > 0 ? Mathf.Clamp01(steady / needed) : 0;
        }

        void Banner(string text, Color color, float seconds)
        {
            if (bannerText) bannerText.text = text ?? "";
            if (bannerBackground)
            {
                bannerBackground.enabled = !string.IsNullOrEmpty(text);
                bannerBackground.color = color;
            }
            bannerUntil = seconds > 0 ? Time.time + seconds : 0;
        }
    }
}
