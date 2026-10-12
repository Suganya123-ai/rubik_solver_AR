// The hand mesh: MediaPipe Hand Landmarker in the browser (21 points per
// hand), run on the live video so the mesh keeps up with the camera.

import { FilesetResolver, HandLandmarker } from '@mediapipe/tasks-vision';

export type Hand = { points: [number, number][] }; // normalized 0..1 of the video

const FRAME_BUDGET_MS = 12; // hand detection slower than this: run it on every 2nd/3rd frame instead

export class HandTracking {
  hands: Hand[] = [];
  fps = 0;
  /** Milliseconds the last detection took. */
  costMs = 0;
  private landmarker: HandLandmarker | null = null;
  private lastVideoTime = -1;
  private times: number[] = [];
  private skip = 0;

  /** mode: 'gpu' (default, falls back to CPU), 'cpu', or 'off' (URL ?hands=...). */
  async init(mode: string = 'gpu'): Promise<void> {
    if (mode === 'off') return;
    const fileset = await FilesetResolver.forVisionTasks(`${import.meta.env.BASE_URL}mediapipe/wasm`);
    const make = (delegate: 'GPU' | 'CPU') =>
      HandLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: `${import.meta.env.BASE_URL}models/hand_landmarker.task`, delegate },
        runningMode: 'VIDEO',
        numHands: 2,
        minHandDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5,
      });
    if (mode === 'cpu') { this.landmarker = await make('CPU'); return; }
    try {
      this.landmarker = await make('GPU');
    } catch {
      this.landmarker = await make('CPU'); // no WebGL2 GPU: slower but works
    }
  }

  /** Runs on the newest video frame (once per frame). */
  update(video: HTMLVideoElement, now: number): void {
    if (!this.landmarker || video.currentTime === this.lastVideoTime) return;
    if (this.skip > 0) { this.skip--; return; }     // keep the render loop smooth on slow machines
    this.lastVideoTime = video.currentTime;
    const t0 = performance.now();
    const result = this.landmarker.detectForVideo(video, now);
    this.costMs = performance.now() - t0;
    this.skip = Math.min(3, Math.floor(this.costMs / FRAME_BUDGET_MS));
    this.hands = result.landmarks.map((lm) => ({ points: lm.map((p) => [p.x, p.y] as [number, number]) }));
    this.times.push(now);
    while (this.times.length && now - this.times[0] > 1000) this.times.shift();
    this.fps = this.times.length;
  }
}
