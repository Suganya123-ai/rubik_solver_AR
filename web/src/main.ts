// Cube Tutor AR on a laptop webcam -- Milestone 1: the mirrored full-screen
// camera, the hand mesh (MediaPipe in the browser, every frame) and the cube
// box (from the Python vision server's 7 corner points).

import './style.css';
import { AppState } from './appState';
import { startCamera } from './camera';
import { CubeView } from './cubeView';
import { HandTracking } from './handTracking';
import { drawCubeBox } from './overlay/cubeBox';
import { drawHands } from './overlay/handMesh';
import { Hud } from './overlay/hud';
import { ServerLink } from './serverLink';
import { View } from './view';

const video = document.getElementById('video') as HTMLVideoElement;
const canvas = document.getElementById('overlay') as HTMLCanvasElement;
const ctx = canvas.getContext('2d')!;
const hud = new Hud(document.getElementById('hud')!);
const state = new AppState();
const view = new View();
const hands = new HandTracking();
const cube = new CubeView();
const link = new ServerLink();

const HINT_AFTER_MS = 800; // no confident cube for this long: show the "hold it steady" hint
let lastConfident = -Infinity;
let frames: number[] = [];

link.onFrame = (reply) => {
  const now = performance.now();
  cube.update(reply, now);
  if (reply.confident) lastConfident = now;
};
link.onConnection = (up) => hud.say(up ? '' : 'Connecting to the vision server…');

function resize(): void {
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(innerWidth * dpr);
  canvas.height = Math.round(innerHeight * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function frame(now: number): void {
  requestAnimationFrame(frame);
  view.update(video.videoWidth || 1280, video.videoHeight || 720, innerWidth, innerHeight);
  hands.update(video, now);
  link.pump(video);

  ctx.clearRect(0, 0, innerWidth, innerHeight);
  const alpha = cube.step(now);
  if (cube.keypoints && alpha > 0) {
    const corners = cube.keypoints.map((p) => view.fromFrame(p, cube.frameW));
    drawCubeBox(ctx, corners, alpha, `CUBE ${Math.round(cube.confidence * 100)}%`);
  }
  drawHands(ctx, hands.hands, view, video.videoHeight || 720, state.error);

  frames.push(now);
  while (frames.length && now - frames[0] > 1000) frames.shift();
  hud.readouts({ fps: frames.length, handsFps: hands.fps, replies: link.repliesPerSecond, latency: link.latencyMs,
                 serverMs: link.serverMs, confidence: cube.confident ? cube.confidence : 0, connected: link.connected });
  hud.showHint(state.phase === 'camera' && link.connected && now - lastConfident > HINT_AFTER_MS);
}

async function boot(): Promise<void> {
  resize();
  addEventListener('resize', resize);
  hud.say('Starting the camera…');
  try {
    await startCamera(video);
  } catch (e) {
    hud.say(`Couldn't open the camera: ${(e as Error).message}`);
    return;
  }
  hud.say('Loading hand tracking…');
  try {
    await hands.init(new URLSearchParams(location.search).get('hands') ?? 'gpu');
  } catch (e) {
    console.error(e);
    hud.say('Hand tracking unavailable in this browser; carrying on without it.');
  }
  hud.say('');
  link.connect();
  state.set('camera');
  requestAnimationFrame(frame);
}

boot();
