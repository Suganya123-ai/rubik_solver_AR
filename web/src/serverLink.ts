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
  /** How the cube is held (corner, top_front, front_right, face) and which of the 7 corners the camera
   *  really sees (the others in keypoints are estimates); null with an older, corner-only model. */
  hold?: string | null;
  seen?: boolean[] | null;
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
// On a slow link (e.g. a forwarded port) smaller frames get through more often.
const SLOW_MS = 180;
const SLOW_WIDTH = 480;
const SLOW_QUALITY = 0.65;
const REPLY_TIMEOUT_MS = 2000;
// Frames out at once: on a slow link (a forwarded port: ~200 ms there and back) the next frame is
// already on its way while the server works on one, so it gets twice as many (the server answers
// them in order, so nothing builds up beyond this).
const MAX_IN_FLIGHT = 2;

/** The part of the video sent: a crop that follows the cube (a wide camera such as the Living Lab's
 *  makes the cube small), turned half round when the camera is upside down to the person. */
type Region = { x: number; y: number; w: number; h: number };
const FOLLOW_MARGIN = 2.4;      // crop side = cube size times this
const MIN_CROP = 360;           // video pixels: never zoom in further than this
const FORGET_CROP_MS = 1200;    // no cube this long: back to the whole picture

export class ServerLink {
  /** The camera is upside down to the person (it looks at them from the far side of a table). */
  rotated = false;
  /** Follow the cube with a crop (wide cameras). */
  follow = false;
  private regions = new Map<number, Region>();  // the crop sent with each frame in flight, by frame id
  private region: Region | null = null;     // ...the one of the reply being read
  private focus: Region | null = null;      // where the cube is (video pixels)
  private focusSeen = 0;
  private videoW = 1;
  private videoH = 1;
  connected = false;
  latencyMs = 0;
  serverMs = 0;
  repliesPerSecond = 0;
  onFrame: (reply: FrameReply) => void = () => {};
  onMessage: (msg: Message) => void = () => {};
  onConnection: (up: boolean) => void = () => {};

  private ws: WebSocket | null = null;
  private inFlight = 0;
  private sentTimes = new Map<number, number>();
  private encoding = false;
  private encodeStart = 0;
  private sentAt = 0;
  private frameId = 0;
  private replies: number[] = [];
  private canvas = document.createElement('canvas');
  private queue: string[] = [];  // commands sent before the connection opened

  connect(): void {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/ws/live`);
    ws.binaryType = 'arraybuffer';
    ws.onopen = () => {
      this.connected = true;
      this.inFlight = 0;
      for (const command of this.queue.splice(0)) ws.send(command);
      this.onConnection(true);
    };
    ws.onclose = () => {
      this.connected = false;
      this.inFlight = 0;
      this.onConnection(false);
      setTimeout(() => this.connect(), 1500);
    };
    ws.onmessage = (event) => this.receive(JSON.parse(event.data as string) as Message);
    this.ws = ws;
  }

  /** Call every animation frame: sends the current video frame if the server is free. */
  pump(video: HTMLVideoElement): void {
    if (!this.connected || !video.videoWidth) return;
    const now = performance.now();
    if (this.encoding && now - this.encodeStart < REPLY_TIMEOUT_MS) return;
    // one frame at a time while the server answers quickly (on this computer: ~40 ms), two on a slow link
    const allowed = this.latencyMs < SLOW_MS / 2 ? 1 : MAX_IN_FLIGHT;
    if (this.inFlight >= allowed) {
      if (now - this.sentAt < REPLY_TIMEOUT_MS) return;
      // no reply for 2 s (lost on a stalled link): stop waiting for it, or sending would stop for good
      this.inFlight = 0; this.sentTimes.clear(); this.regions.clear();
    }
    this.encoding = true;
    this.encodeStart = now;
    const slow = this.latencyMs > SLOW_MS;
    const width = slow ? SLOW_WIDTH : SEND_WIDTH;
    this.videoW = video.videoWidth; this.videoH = video.videoHeight;
    const r = this.cropRegion();
    this.canvas.width = width;
    this.canvas.height = Math.round((width * r.h) / r.w);
    const g = this.canvas.getContext('2d')!;
    g.setTransform(1, 0, 0, 1, 0, 0);
    if (this.rotated) g.setTransform(-1, 0, 0, -1, this.canvas.width, this.canvas.height);
    g.drawImage(video, r.x, r.y, r.w, r.h, 0, 0, this.canvas.width, this.canvas.height);
    this.canvas.toBlob(async (blob) => {
      this.encoding = false;
      if (!blob || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;
      const jpeg = new Uint8Array(await blob.arrayBuffer());
      const msg = new Uint8Array(4 + jpeg.length);
      const id = ++this.frameId;
      new DataView(msg.buffer).setUint32(0, id);
      msg.set(jpeg, 4);
      this.sentAt = performance.now();
      this.sentTimes.set(id, this.sentAt);
      this.regions.set(id, r);
      this.inFlight++;
      this.ws.send(msg);
    }, 'image/jpeg', slow ? SLOW_QUALITY : JPEG_QUALITY);
  }

  send(command: Record<string, unknown>): void {
    const text = JSON.stringify(command);
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(text);
    else this.queue.push(text);  // delivered as soon as the connection opens
  }

  /** The region of the video to send: all of it, or a 4:3 crop around where the cube was. */
  private cropRegion(): Region {
    const W = this.videoW, H = this.videoH;
    const all = { x: 0, y: 0, w: W, h: H };
    if (!this.follow || !this.focus || performance.now() - this.focusSeen > FORGET_CROP_MS) return all;
    const f = this.focus;
    let h = Math.min(H, Math.max(MIN_CROP, Math.max(f.w, f.h) * FOLLOW_MARGIN));
    let w = Math.min(W, h * 4 / 3);
    h = Math.min(h, w * 3 / 4);
    const cx = f.x + f.w / 2, cy = f.y + f.h / 2;
    const x = Math.min(Math.max(cx - w / 2, 0), W - w), y = Math.min(Math.max(cy - h / 2, 0), H - h);
    return { x, y, w, h };
  }

  /** Points in the sent picture -> video pixels (undoing the crop and the half turn). */
  private toVideo(p: [number, number], frameW: number, frameH: number): [number, number] {
    const r = this.region ?? { x: 0, y: 0, w: this.videoW, h: this.videoH };
    let [u, v] = p;
    if (this.rotated) { u = frameW - u; v = frameH - v; }
    return [r.x + u * r.w / frameW, r.y + v * r.h / frameH];
  }

  private receive(msg: Message): void {
    if (msg.type === 'frame') {
      const reply = msg as FrameReply;
      this.region = this.regions.get(reply.frame) ?? null;
      this.regions.delete(reply.frame);
      // The overlays work in video pixels: the reply's points are mapped back from the crop, and its
      // size becomes the video's (CubeView scales by width only).
      if (reply.keypoints) {
        reply.keypoints = reply.keypoints.map((p) => this.toVideo(p, reply.width, reply.height));
        const seen = reply.keypoints.filter((_, i) => !reply.seen || reply.seen[i]);
        const xs = seen.map((p) => p[0]), ys = seen.map((p) => p[1]);
        const box = { x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) };
        const old = this.focus;
        // move the crop only when the cube nears its edge or changes size a lot (a still crop: steadier)
        const keep = old && Math.abs(box.x + box.w / 2 - (old.x + old.w / 2)) < old.w * 0.35 &&
          Math.abs(box.y + box.h / 2 - (old.y + old.h / 2)) < old.h * 0.35 &&
          Math.abs(Math.max(box.w, box.h) / Math.max(old.w, old.h) - 1) < 0.25;
        if (!keep) this.focus = box;
        this.focusSeen = performance.now();
      }
      reply.width = this.videoW; reply.height = this.videoH;
    }
    if (msg.type === 'frame') {
      const now = performance.now();
      const reply = msg as FrameReply;
      this.inFlight = Math.max(0, this.inFlight - 1);
      this.latencyMs = now - (this.sentTimes.get(reply.frame) ?? this.sentAt);
      this.sentTimes.delete(reply.frame);
      this.serverMs = (msg as FrameReply).ms;
      this.replies.push(now);
      while (this.replies.length && now - this.replies[0] > 1000) this.replies.shift();
      this.repliesPerSecond = this.replies.length;
      this.onFrame(msg as FrameReply);
    } else {
      if (msg.type === 'error') this.inFlight = Math.max(0, this.inFlight - 1);
      this.onMessage(msg);
    }
  }
}
