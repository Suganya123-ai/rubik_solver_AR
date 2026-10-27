// The camera: the laptop webcam by default, or another one (e.g. the Living Lab's Lumens cameras).
// Which one: ?camera=N (1 = first in the list) or ?camera=<part of its name>, else the last one
// chosen with the C key (remembered in this browser), else the default camera.

const KEY = 'cubeTutor.camera';

function remembered(): string | null {
  try { return localStorage.getItem(KEY); } catch { return null; }
}

function remember(label: string): void {
  try { localStorage.setItem(KEY, label); } catch { /* private window: not remembered */ }
}

/** The cameras, in the browser's order (names only after camera permission was given). */
export async function listCameras(): Promise<MediaDeviceInfo[]> {
  return (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'videoinput');
}

function pick(cams: MediaDeviceInfo[], want: string | null): MediaDeviceInfo | undefined {
  if (!want) return undefined;
  const n = Number(want);
  if (Number.isInteger(n) && n >= 1 && n <= cams.length) return cams[n - 1];
  return cams.find((c) => c.label === want) ?? cams.find((c) => c.label.toLowerCase().includes(want.toLowerCase()));
}

/** Opens a camera (deviceId, or the choice described above). Returns its name. */
export async function startCamera(video: HTMLVideoElement, deviceId?: string): Promise<string> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('This browser cannot open the camera (needs https or localhost).');
  }
  const size = { width: { ideal: 1920 }, height: { ideal: 1080 }, frameRate: { ideal: 30 } };
  let id = deviceId;
  if (!id) {
    let cams = await listCameras();
    if (cams.some((c) => !c.label)) {   // names come once permission is given: ask with the default camera first
      (await navigator.mediaDevices.getUserMedia({ video: true })).getTracks().forEach((t) => t.stop());
      cams = await listCameras();
    }
    id = pick(cams, new URLSearchParams(location.search).get('camera') ?? remembered())?.deviceId;
  }
  (video.srcObject as MediaStream | null)?.getTracks().forEach((t) => t.stop());
  const stream = await navigator.mediaDevices.getUserMedia({
    video: id ? { ...size, deviceId: { exact: id } } : { ...size, facingMode: 'user' }, audio: false,
  });
  video.srcObject = stream;
  await video.play();
  if (!video.videoWidth) await new Promise((r) => video.addEventListener('loadedmetadata', r, { once: true }));
  const label = stream.getVideoTracks()[0]?.label ?? 'camera';
  return label;
}

/** The next camera in the list (the C key); remembered for next time. Returns its name. */
export async function nextCamera(video: HTMLVideoElement): Promise<string> {
  const cams = await listCameras();
  const now = (video.srcObject as MediaStream | null)?.getVideoTracks()[0]?.getSettings().deviceId;
  const i = cams.findIndex((c) => c.deviceId === now);
  const next = cams[(i + 1) % cams.length];
  const label = await startCamera(video, next.deviceId);
  remember(next.label);
  return `${label} (${(i + 1) % cams.length + 1} of ${cams.length})`;
}
