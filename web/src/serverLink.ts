// The WebSocket link to the Python vision server (/ws/live, protocol in
// ../docs/PROTOCOL.md). Sends a downscaled JPEG of the newest video frame
// whenever the reply to the previous one is back, so nothing queues up.

export type FrameReply = {
  type: 'frame';
  frame: number;
  width: number;
  height: number;
  ms: number;
  keypoints: [number, number][] | null;
  confidence: number | null;
  confident: boolean;
  faces: Record<'U' | 'F' | 'R', [number, number, number][]> | null;
  covered: Record<'U' | 'F' | 'R', boolean[]> | null;
  hands_busy?: boolean;
  scan?: Record<string, unknown>;
  scan_result?: Record<string, unknown>;
  track?: Record<string, unknown>;
};

export type Message = FrameReply | ({ type: string } & Record<string, unknown>);

const SEND_WIDTH = 640;
const JPEG_QUALITY = 0.8;
const REPLY_TIMEOUT_MS = 2000;

export class ServerLink {
  connected = false;
  latencyMs = 0;
  serverMs = 0;
  repliesPerSecond = 0;
  onFrame: (reply: FrameReply) => void = () => {};
  onMessage: (msg: Message) => void = () => {};
  onConnection: (up: boolean) => void = () => {};

  private ws: WebSocket | null = null;
  private inFlight = false;
  private sentAt = 0;
  private frameId = 0;
  private replies: number[] = [];
  private canvas = document.createElement('canvas');

  connect(): void {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/ws/live`);
    ws.binaryType = 'arraybuffer';
    ws.onopen = () => { this.connected = true; this.inFlight = false; this.onConnection(true); };
    ws.onclose = () => {
      this.connected = false;
      this.inFlight = false;
      this.onConnection(false);
      setTimeout(() => this.connect(), 1500);
    };
    ws.onmessage = (event) => this.receive(JSON.parse(event.data as string) as Message);
    this.ws = ws;
  }

  /** Call every animation frame: sends the current video frame if the server is free. */
  pump(video: HTMLVideoElement): void {
    if (!this.connected || !video.videoWidth) return;
    if (this.inFlight && performance.now() - this.sentAt < REPLY_TIMEOUT_MS) return;
    this.inFlight = true;
    this.canvas.width = SEND_WIDTH;
    this.canvas.height = Math.round((SEND_WIDTH * video.videoHeight) / video.videoWidth);
    this.canvas.getContext('2d')!.drawImage(video, 0, 0, this.canvas.width, this.canvas.height);
    this.canvas.toBlob(async (blob) => {
      if (!blob || !this.ws || this.ws.readyState !== WebSocket.OPEN) { this.inFlight = false; return; }
      const jpeg = new Uint8Array(await blob.arrayBuffer());
      const msg = new Uint8Array(4 + jpeg.length);
      new DataView(msg.buffer).setUint32(0, ++this.frameId);
      msg.set(jpeg, 4);
      this.sentAt = performance.now();
      this.ws.send(msg);
    }, 'image/jpeg', JPEG_QUALITY);
  }

  send(command: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(command));
  }

  private receive(msg: Message): void {
    if (msg.type === 'frame') {
      const now = performance.now();
      this.inFlight = false;
      this.latencyMs = now - this.sentAt;
      this.serverMs = (msg as FrameReply).ms;
      this.replies.push(now);
      while (this.replies.length && now - this.replies[0] > 1000) this.replies.shift();
      this.repliesPerSecond = this.replies.length;
      this.onFrame(msg as FrameReply);
    } else {
      if (msg.type === 'error') this.inFlight = false;
      this.onMessage(msg);
    }
  }
}
