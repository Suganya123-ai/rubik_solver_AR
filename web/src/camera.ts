// The laptop webcam: 1280x720 if available.

export async function startCamera(video: HTMLVideoElement): Promise<void> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('This browser cannot open the camera (needs https or localhost).');
  }
  const stream = await navigator.mediaDevices.getUserMedia({
    video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30 }, facingMode: 'user' },
    audio: false,
  });
  video.srcObject = stream;
  await video.play();
  if (!video.videoWidth) await new Promise((r) => video.addEventListener('loadedmetadata', r, { once: true }));
}
