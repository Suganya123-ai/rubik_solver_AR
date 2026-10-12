// Cube Tutor AR on a laptop webcam: the mirrored full-screen camera, the hand
// mesh (MediaPipe in the browser, every frame), the cube box and move arrows
// (from the Python vision server's 7 corner points), the ghost cube, and the
// tutor flow (flow.ts): scan, solve, live guided moves with undo, solved.

import './style.css';
import { AppState } from './appState';
import { startCamera } from './camera';
import { CubeView } from './cubeView';
import { HandTracking } from './handTracking';
import { Flow } from './flow';
import { drawCubeBox } from './overlay/cubeBox';
import { Effects } from './overlay/effects';
import { drawMoveArrows } from './overlay/moveArrows';
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
const effects = new Effects();
const flow = new Flow(link, state, effects, document.getElementById('ui')!);
const ghostBox = document.getElementById('ghost')!;
const ghost = new window.CubeHologram(document.getElementById('ghost-canvas') as HTMLCanvasElement);
// Seen from the user's side: the webcam looks at the cube from the other side,
// so the ghost is turned round (green facing the user is in front) and not mirrored.
ghost.homeYaw = ghost.yaw = -0.68 + Math.PI;
let ghostPos: [number, number, number] | null = null;

const HINT_AFTER_MS = 800; // no confident cube for this long: show the "hold it steady" hint
let lastConfident = -Infinity;
let frames: number[] = [];

link.onFrame = (reply) => {
  const now = performance.now();
  cube.update(reply, now);
  if (reply.confident) lastConfident = now;
  flow.onFrame(reply);
  updateGhost();
};
link.onMessage = (msg) => { flow.onMessage(msg); updateGhost(); };

function updateGhost(): void {
  const t = flow.track;
  ghostBox.hidden = !t || !t.state;
  if (!t || !t.state) return;
  ghost.show(t.state, t.face_colors, t.phase === 'solved' ? null : t.move, { undo: t.phase === 'undo' });
  ghostBox.classList.toggle('warn', t.phase === 'undo');
}

/** The ghost cube floats beside the real cube (the roomier side), gliding as it moves. */
function placeGhost(corners: [number, number][] | null): void {
  if (ghostBox.hidden) return;
  let x: number, y: number, size: number;
  if (corners) {
    const xs = corners.map((p) => p[0]), ys = corners.map((p) => p[1]);
    const left = Math.min(...xs), right = Math.max(...xs), top = Math.min(...ys), bottom = Math.max(...ys);
    const gap = Math.max(24, (right - left) * 0.15);
    const roomRight = innerWidth - 16 - (right + gap), roomLeft = left - gap - 16;
    size = Math.max(160, Math.min(320, (bottom - top) * 1.0, Math.max(roomRight, roomLeft)));
    x = roomRight >= roomLeft ? right + gap : left - gap - size;
    y = (top + bottom) / 2 - size * 0.6;
  } else {
    size = 260; x = innerWidth - size - 24; y = innerHeight * 0.18;  // no cube: park top-right
  }
  // Keep clear of the readouts (top-left), the progress bars (left) and the instruction card (bottom).
  x = Math.max(110, Math.min(innerWidth - size - 16, x));
  y = Math.max(120, Math.min(innerHeight - size - 190, y));
  ghostPos = ghostPos ? ghostPos.map((v, i) => v + ([x, y, size][i] - v) * 0.15) as [number, number, number] : [x, y, size];
  ghostBox.style.transform = `translate(${ghostPos[0]}px, ${ghostPos[1]}px)`;
  ghostBox.style.width = ghostBox.style.height = `${ghostPos[2]}px`;
}
link.onConnection = (up) => hud.say(up ? '' : 'Connecting to the vision server…');

/** True when one side fills the view and another hardly shows (the cube is held face-on):
 *  the stickers on the thin sides can't be read well, so moves are missed. */
function faceOn(c: [number, number][]): boolean {
  const area = (q: number[]) => Math.abs(q.reduce((s, i, k) => {
    const j = q[(k + 1) % q.length];
    return s + c[i][0] * c[j][1] - c[j][0] * c[i][1];
  }, 0)) / 2;
  const sides = [area([2, 3, 0, 1]), area([1, 0, 5, 6]), area([0, 3, 4, 5])];
  return Math.min(...sides) < 0.5 * Math.max(...sides);  // real frames: good 0.6-0.8, missed moves 0.36-0.45
}

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
  let corners: [number, number][] | null = null;
  if (cube.keypoints && alpha > 0) {
    corners = cube.keypoints.map((p) => view.fromFrame(p, cube.frameW));
    drawCubeBox(ctx, corners, alpha * (flow.guide ? 0.5 : 1), `CUBE ${Math.round(cube.confidence * 100)}%`);
    if (flow.guide && alpha > 0.5) {
      drawMoveArrows(ctx, view, cube.keypoints, cube.frameW, flow.guide.move, flow.guide.undo, now);
    }
  }
  drawHands(ctx, hands.hands, view, video.videoHeight || 720, state.error);
  effects.draw(ctx, now, corners, innerWidth, innerHeight);
  placeGhost(alpha > 0.5 ? corners : null);

  frames.push(now);
  while (frames.length && now - frames[0] > 1000) frames.shift();
  hud.readouts({ fps: frames.length, handsFps: hands.fps, replies: link.repliesPerSecond, latency: link.latencyMs,
                 serverMs: link.serverMs, confidence: cube.confident ? cube.confidence : 0, connected: link.connected });
  const active = state.phase === 'camera' || state.phase === 'scan' || state.phase === 'guided' || state.phase === 'undo';
  const lostCube = active && link.connected && now - lastConfident > HINT_AFTER_MS;
  hud.showHint(lostCube, !lostCube && active && corners && faceOn(corners)
    ? 'Tilt the cube so you see three sides -- a corner pointing at the camera' : undefined);
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
  link.connect();  // (the flow already set the stage; the user may have pressed Start scan meanwhile)
  requestAnimationFrame(frame);
}

boot();
