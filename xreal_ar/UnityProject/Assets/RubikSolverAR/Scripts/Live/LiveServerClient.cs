using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace RubikSolverAR.Live
{
    /// <summary>
    /// Streams camera frames to the laptop server (/ws/live) and raises the
    /// replies as events on the main thread. Protocol: docs/PROTOCOL.md.
    ///
    /// One frame is in flight at a time: the next frame is sent only after the
    /// reply to the previous one, so nothing queues up on a slow network.
    /// Reconnects automatically if the connection drops.
    /// Needs the Newtonsoft JSON package (com.unity.nuget.newtonsoft-json).
    /// </summary>
    public sealed class LiveServerClient : MonoBehaviour
    {
        [Tooltip("ws://<laptop-ip>:8000/ws/live -- printed by ./run.sh --lan on the laptop")]
        public string serverUrl = "ws://192.168.1.10:8000/ws/live";
        [Tooltip("A component implementing ILiveFrameSource (WebCamFrameSource or XrealEyeFrameSource).")]
        public MonoBehaviour frameSource;
        public bool streamFrames = true;
        [Tooltip("Give up on a reply after this long and send a fresh frame.")]
        public float replyTimeoutSeconds = 2f;

        /// <summary>Every frame reply ("type": "frame"), including scan / track status.</summary>
        public event Action<JObject> FrameReceived;
        /// <summary>Replies to commands: scan, scan_result, track, saved, error, pong.</summary>
        public event Action<JObject> MessageReceived;
        public event Action<bool> ConnectionChanged;

        public bool Connected => socket != null && socket.State == WebSocketState.Open;
        public float RoundTripMs { get; private set; }

        ILiveFrameSource source;
        ClientWebSocket socket;
        CancellationTokenSource cts;
        readonly SemaphoreSlim sendLock = new SemaphoreSlim(1, 1);
        readonly ConcurrentQueue<JObject> inbox = new ConcurrentQueue<JObject>();
        readonly ConcurrentQueue<bool> connectionEvents = new ConcurrentQueue<bool>();
        uint frameId;
        bool inFlight;
        float sentAt;

        void Awake()
        {
            source = frameSource as ILiveFrameSource;
            if (source == null) Debug.LogError("LiveServerClient: frameSource must implement ILiveFrameSource.");
        }

        void OnEnable()
        {
            cts = new CancellationTokenSource();
            _ = ConnectLoop(cts.Token);
        }

        void OnDisable()
        {
            cts?.Cancel();
            try { socket?.Abort(); } catch (Exception) { /* closing anyway */ }
        }

        void Update()
        {
            while (connectionEvents.TryDequeue(out bool up))
            {
                if (!up) inFlight = false;
                ConnectionChanged?.Invoke(up);
            }
            while (inbox.TryDequeue(out JObject msg))
            {
                if ((string)msg["type"] == "frame")
                {
                    inFlight = false;
                    RoundTripMs = (Time.realtimeSinceStartup - sentAt) * 1000f;
                    FrameReceived?.Invoke(msg);
                }
                else
                {
                    if ((string)msg["type"] == "error") inFlight = false;  // a failed frame also ends the wait
                    MessageReceived?.Invoke(msg);
                }
            }

            if (inFlight && Time.realtimeSinceStartup - sentAt > replyTimeoutSeconds) inFlight = false;
            if (!streamFrames || !Connected || inFlight || source == null || !source.IsReady) return;
            if (!source.TryGetJpeg(out byte[] jpeg)) return;

            var data = new byte[4 + jpeg.Length];
            frameId++;
            data[0] = (byte)(frameId >> 24); data[1] = (byte)(frameId >> 16);
            data[2] = (byte)(frameId >> 8); data[3] = (byte)frameId;
            Buffer.BlockCopy(jpeg, 0, data, 4, jpeg.Length);
            inFlight = true;
            sentAt = Time.realtimeSinceStartup;
            _ = SendAsync(data, WebSocketMessageType.Binary);
        }

        // ---------- commands (see docs/PROTOCOL.md) ----------
        public void StartScan() => SendCommand(new { type = "scan_start" });
        public void CancelScan() => SendCommand(new { type = "scan_cancel" });
        public void CheckScan(Dictionary<string, string> locked) => SendCommand(new { type = "scan_check", locked });
        public void AcceptScan(JToken colors) => SendCommand(new { type = "scan_accept", colors });
        public void SkipMove() => SendCommand(new { type = "track_skip" });
        public void StopTracking() => SendCommand(new { type = "track_stop" });
        public void SaveFrame() => SendCommand(new { type = "save" });

        public void SendCommand(object command)
        {
            if (!Connected) { Debug.LogWarning("LiveServerClient: not connected, command dropped."); return; }
            _ = SendAsync(Encoding.UTF8.GetBytes(JsonConvert.SerializeObject(command)), WebSocketMessageType.Text);
        }

        // ---------- connection ----------
        async Task ConnectLoop(CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                try
                {
                    socket = new ClientWebSocket();
                    await socket.ConnectAsync(new Uri(serverUrl), token);
                    connectionEvents.Enqueue(true);
                    await ReceiveLoop(token);
                }
                catch (Exception e) when (!token.IsCancellationRequested)
                {
                    Debug.LogWarning($"LiveServerClient: {e.Message} -- retrying");
                }
                await sendLock.WaitAsync();  // don't dispose while a send is using the socket
                try { socket?.Dispose(); } finally { sendLock.Release(); }
                connectionEvents.Enqueue(false);
                try { await Task.Delay(2000, token); } catch (TaskCanceledException) { return; }
            }
        }

        async Task ReceiveLoop(CancellationToken token)
        {
            var buffer = new byte[64 * 1024];
            var message = new List<byte>();
            while (socket.State == WebSocketState.Open && !token.IsCancellationRequested)
            {
                WebSocketReceiveResult result = await socket.ReceiveAsync(new ArraySegment<byte>(buffer), token);
                if (result.MessageType == WebSocketMessageType.Close) return;
                message.AddRange(new ArraySegment<byte>(buffer, 0, result.Count));
                if (!result.EndOfMessage) continue;
                try
                {
                    inbox.Enqueue(JObject.Parse(Encoding.UTF8.GetString(message.ToArray())));
                }
                catch (JsonException e)
                {
                    Debug.LogWarning($"LiveServerClient: bad message from server: {e.Message}");
                }
                message.Clear();
            }
        }

        async Task SendAsync(byte[] data, WebSocketMessageType type)
        {
            await sendLock.WaitAsync();
            try
            {
                if (Connected)
                    await socket.SendAsync(new ArraySegment<byte>(data), type, true, cts.Token);
            }
            catch (Exception e)
            {
                Debug.LogWarning($"LiveServerClient: send failed: {e.Message}");
            }
            finally
            {
                sendLock.Release();
            }
        }
    }
}
