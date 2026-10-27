// The camera: the laptop webcam by default, or another one (e.g. the Living Lab's Lumens cameras).
// Which one: ?camera=N (1 = first in the list) or ?camera=<part of its name>, else the last one
// chosen (remembered in this browser by the camera's own id: the Living Lab's four Lumens cameras
// all have the same name and send no serial number), else the default camera.

const KEY = 'cubeTutor.camera';

function remembered(): string | null {
  try { return localStorage.getItem(KEY); } catch { return null; }
}

function remember(deviceId: string): void {
  try { localStorage.setItem(KEY, deviceId); } catch { /* private window: not remembered */ }
}

/** The cameras, in the browser's order (names only after camera permission was given). */
export async function listCameras(): Promise<MediaDeviceInfo[]> {
  return (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'videoinput');
}

function pick(cams: MediaDeviceInfo[], want: string | null): MediaDeviceInfo | undefined {
  if (!want) return undefined;
  const n = Number(want);
  if (Number.isInteger(n) && n >= 1 && n <= cams.length) return cams[n - 1];
  return cams.find((c) => c.deviceId === want) ?? cams.find((c) => c.label === want) ??
    cams.find((c) => c.label.toLowerCase().includes(want.toLowerCase()));
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
    const asked = new URLSearchParams(location.search).get('camera');
    // a camera chosen before wins over a name in the link (?camera=lumens picks the first of four)
    id = (pick(cams, remembered()) && (!asked || Number.isNaN(Number(asked))) ? pick(cams, remembered()) : pick(cams, asked))?.deviceId;
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
  remember(next.deviceId);
  return `${label} (${(i + 1) % cams.length + 1} of ${cams.length})`;
}

/** A screen with every camera's live picture: click one to use it (remembered). Resolves with its name,
 *  or null if closed without choosing. */
export async function chooseCamera(video: HTMLVideoElement): Promise<string | null> {
  const cams = await listCameras();
  const now = (video.srcObject as MediaStream | null)?.getVideoTracks()[0]?.getSettings().deviceId;
  const box = document.createElement('div');
  box.id = 'cam-choose';
  box.innerHTML = '<div class="cam-choose-title">Choose the camera: click its picture</div><div class="cam-grid"></div>' +
    '<button class="cam-close">Close</button>';
  document.body.appendChild(box);
  const grid = box.querySelector('.cam-grid')!;
  const streams: MediaStream[] = [];
  const done = (): void => { streams.forEach((st) => st.getTracks().forEach((t) => t.stop())); box.remove(); };
  return new Promise((resolve) => {
    box.querySelector('.cam-close')!.addEventListener('click', () => { done(); resolve(null); });
    cams.forEach(async (cam, i) => {
      const tile = document.createElement('button');
      tile.className = 'cam-tile' + (cam.deviceId === now ? ' current' : '');
      tile.innerHTML = `<video muted playsinline></video><span>${i + 1}. ${cam.label || 'Camera'}${cam.deviceId === now ? ' (in use)' : ''}</span>`;
      grid.appendChild(tile);
      const v = tile.querySelector('video')!;
      if (cam.deviceId === now) { v.srcObject = video.srcObject; void v.play(); }
      else {
        try {
          const st = await navigator.mediaDevices.getUserMedia({ video: { deviceId: { exact: cam.deviceId }, width: 320, height: 180 } });
          streams.push(st); v.srcObject = st; void v.play();
        } catch { tile.querySelector('span')!.textContent += ' (busy)'; }
      }
      tile.addEventListener('click', async () => {
        done();
        const label = cam.deviceId === now ? cam.label : await startCamera(video, cam.deviceId);
        remember(cam.deviceId);
        resolve(`${label} (${i + 1} of ${cams.length})`);
      });
    });
  });
}
