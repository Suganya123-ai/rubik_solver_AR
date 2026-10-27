// Cube Tutor AR on a laptop webcam: the mirrored full-screen camera, the hand
// mesh (MediaPipe in the browser, every frame), the cube box and move arrows
// (from the Python vision server's 7 corner points), the ghost cube, and the
// tutor flow (flow.ts): scan, solve, live guided moves with undo, solved.

import './style.css';
import { AppState } from './appState';
import { nextCamera, startCamera } from './camera';
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
function placeGhost(_corners: [number, number][] | null): void {
  // Fixed in the top-right corner (below the "turning" badge), not following the cube.
  if (ghostBox.hidden) return;
  const size = Math.max(160, Math.min(240, Math.min(innerWidth, innerHeight) * 0.3));
  const x = innerWidth - size - 16, y = 60;
  ghostBox.style.transform = `translate(${x}px, ${y}px)`;
  ghostBox.style.width = ghostBox.style.height = `${size}px`;
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
    drawCubeBox(ctx, corners, alpha * (flow.guide ? 0.5 : 1), `CUBE ${Math.round(cube.confidence * 100)}%`, cube.seen);
    if (flow.guide && alpha > 0.5) {
      drawMoveArrows(ctx, view, cube.keypoints, cube.frameW, flow.guide.move, flow.guide.undo, now, cube.seen);
    }
  }
  drawHands(ctx, hands.hands, view, video.videoHeight || 720, state.error);
  effects.draw(ctx, now, corners, innerWidth, innerHeight, cube.seen);
  placeGhost(alpha > 0.5 ? corners : null);

  frames.push(now);
  while (frames.length && now - frames[0] > 1000) frames.shift();
  hud.readouts({ fps: frames.length, handsFps: hands.fps, replies: link.repliesPerSecond, latency: link.latencyMs,
                 serverMs: link.serverMs, confidence: cube.confident ? cube.confidence : 0, connected: link.connected });
  const active = state.phase === 'camera' || state.phase === 'scan' || state.phase === 'guided' || state.phase === 'undo';
  const lostCube = active && link.connected && now - lastConfident > HINT_AFTER_MS;
  // Three sides needed: always with an older, corner-only model; with the any-hold model (which
  // follows the cube held any way while solving) only for the scan.
  const needCorner = cube.hold ? state.phase === 'scan' && cube.hold !== 'corner' : corners !== null && faceOn(corners);
  hud.showHint(lostCube, !lostCube && active && corners && needCorner
    ? 'Tilt the cube so you see three sides -- a corner pointing at the camera' : undefined);
}

// Mirroring: like a mirror (?mirror=0/1 or the M key).
// The Lumens cameras on the Living Lab stand look down at the person from across the table: the
// picture is turned half round (?rotate=0/1 or the R key) and the crop follows the cube (wide lens).
function setMirror(lumens: boolean): void {
  // Turned half round, the stand's camera looks at the person like a webcam from above: mirrored like one.
  const q = new URLSearchParams(location.search);
  view.mirrored = q.get('mirror') !== null ? q.get('mirror') !== '0' : true;
  setRotated(q.get('rotate') !== null ? q.get('rotate') !== '0' : lumens);
  link.follow = q.get('follow') !== null ? q.get('follow') !== '0' : lumens;
}

function setRotated(on: boolean): void {
  view.rotated = on;
  link.rotated = on;
  applyVideoTransform();
}

function applyVideoTransform(): void {
  const sx = view.mirrored !== view.rotated ? -1 : 1, sy = view.rotated ? -1 : 1;
  video.style.transform = `scale(${sx}, ${sy})`;
}

let noteTimer = 0;
function note(text: string): void {     // a few seconds on screen
  hud.say(text);
  clearTimeout(noteTimer);
  noteTimer = window.setTimeout(() => hud.say(''), 4000);
}

addEventListener('keydown', async (e) => {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
  if (e.key === 'c' || e.key === 'C') {
    try {
      const name = await nextCamera(video);
      setMirror(/lumens/i.test(name));
      note(`Camera: ${name}`);
    } catch (err) { note(`Couldn't switch camera: ${(err as Error).message}`); }
  } else if (e.key === 'm' || e.key === 'M') {
    view.mirrored = !view.mirrored;
    applyVideoTransform();
    note(view.mirrored ? 'Mirrored' : 'Not mirrored');
  } else if (e.key === 'r' || e.key === 'R') {
    setRotated(!view.rotated);
    note(view.rotated ? 'Turned half round' : 'Upright');
  } else if (e.key === 'f' || e.key === 'F') {
    link.follow = !link.follow;
    note(link.follow ? 'Zooming in on the cube' : 'Whole picture');
  }
});

async function boot(): Promise<void> {
  resize();
  addEventListener('resize', resize);
  hud.say('Starting the camera…');
  try {
    const name = await startCamera(video);
    setMirror(/lumens/i.test(name));
    note(`Camera: ${name}. C: next camera, R: turn round, M: mirror, F: zoom on the cube.`);
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
  link.connect();  // (the flow already set the stage; the user may have pressed Start scan meanwhile)
  requestAnimationFrame(frame);
}

boot();
