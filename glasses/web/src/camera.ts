// The camera. On a laptop: the webcam facing the user. On the glasses: any
// camera the browser offers -- the list is shown so the user can pick the one
// on the glasses (if the browser can see it) or the device's rear camera.

import { glasses } from './mode';

const REMEMBER = 'cube-tutor-camera';
let stream: MediaStream | null = null;

export type CameraInfo = { id: string; label: string };

/** Cameras the browser offers (labels are only filled in after permission is granted). */
export async function listCameras(): Promise<CameraInfo[]> {
  const devices = await navigator.mediaDevices.enumerateDevices();
  return devices.filter((d) => d.kind === 'videoinput')
    .map((d, i) => ({ id: d.deviceId, label: d.label || `Camera ${i + 1}` }));
}

export function currentCameraId(): string | null {
  return stream?.getVideoTracks()[0]?.getSettings().deviceId ?? null;
}

/** Opens the camera: a specific one (deviceId), the remembered one, or the default for this mode. */
export async function startCamera(video: HTMLVideoElement, deviceId?: string): Promise<void> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('This browser cannot open the camera (the page must be opened over https or on localhost).');
  }
  let remembered: string | null = null;
  try { remembered = localStorage.getItem(REMEMBER); } catch { /* private window */ }
  const wanted = deviceId ?? remembered ?? undefined;
  const size = { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30 } };
  const open = (video: MediaTrackConstraints) => navigator.mediaDevices.getUserMedia({ video, audio: false });
  stream?.getTracks().forEach((t) => t.stop());
  try {
    stream = await open(wanted ? { ...size, deviceId: { exact: wanted } }
      : { ...size, facingMode: glasses ? 'environment' : 'user' });
  } catch (e) {
    if (!wanted) throw e;
    stream = await open({ ...size, facingMode: glasses ? 'environment' : 'user' });  // remembered camera is gone
  }
  if (deviceId) { try { localStorage.setItem(REMEMBER, deviceId); } catch { /* ignore */ } }
  video.srcObject = stream;
  await video.play();
  if (!video.videoWidth) await new Promise((r) => video.addEventListener('loadedmetadata', r, { once: true }));
}
