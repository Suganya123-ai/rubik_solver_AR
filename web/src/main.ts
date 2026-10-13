// Cube Tutor AR on a laptop webcam: the mirrored full-screen camera, the hand
// mesh (MediaPipe in the browser, every frame), the cube box and move arrows
// (from the Python vision server's 7 corner points), the ghost cube, and the
// tutor flow (flow.ts): scan, solve, live guided moves with undo, solved.

import './style.css';
import { AppState } from './appState';
import { currentCameraId, listCameras, startCamera } from './camera';
import { CubeView } from './cubeView';
import { HandTracking } from './handTracking';
import { Flow } from './flow';
import { drawCubeBox } from './overlay/cubeBox';
import { Effects } from './overlay/effects';
import { drawMoveArrows } from './overlay/moveArrows';
import { drawHands } from './overlay/handMesh';
import { Hud } from './overlay/hud';
import { displayOnly, glasses, handsMode, hudOnly, remoteCamera, setHudOnly } from './mode';
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
// Laptop: the webcam looks at the cube from the other side, so the ghost is turned
// round to the user's side. Glasses: the camera looks the wearer's way, so no turn.
ghost.homeYaw = ghost.yaw = glasses ? -0.68 : -0.68 + Math.PI;
view.mirror = !glasses;
document.body.classList.toggle('glasses', glasses);
document.body.classList.toggle('display-only', displayOnly);
let ghostPos: [number, number, number] | null = null;
// The size of the camera picture: the video's, or (remote camera) the frames the server received.
let srcW = 1280, srcH = 720;
let feedOn = false;

const HINT_AFTER_MS = 800; // no confident cube for this long: show the "hold it steady" hint
let lastConfident = -Infinity;
let frames: number[] = [];

link.onFrame = (reply) => {
  const now = performance.now();
  cube.update(reply, now);
  if (reply.confident) lastConfident = now;
  if (remoteCamera) { srcW = reply.width; srcH = reply.height; feedOn = true; }
  if ((handsMode === 'off' || remoteCamera) && reply.hands) {  // draw the server's hand points instead
    hands.hands = reply.hands.map((h) => ({ points: h.points.map(([x, y]) => [x / reply.width, y / reply.height] as [number, number]) }));
  }
  flow.onFrame(reply);
  updateGhost();
};
link.onMessage = (msg) => {
  if (msg.type === 'feed') {  // remote camera: the bridge app connected / went away
    feedOn = !!msg.connected;
    hud.say(feedOn ? '' : "Waiting for the glasses' camera -- start the Cube Tutor Bridge app on the Beam Pro");
    return;
  }
  flow.onMessage(msg);
  updateGhost();
};

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
  if (glasses) {
    // On the glasses the ghost cube stays put, small, in the top-right corner (it doesn't follow the cube).
    size = Math.max(110, Math.min(200, Math.min(innerWidth, innerHeight) * 0.24));
    x = innerWidth - size - (displayOnly ? 28 : 12);
    y = displayOnly ? 28 : 64;   // (below the phone page's own top button)
    ghostPos = [x, y, size];
    ghostBox.style.transform = `translate(${x}px, ${y}px)`;
    ghostBox.style.width = ghostBox.style.height = `${size}px`;
    return;
  }
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

// ---------- glasses controls: which camera, and camera picture vs floating HUD ----------
async function setupControls(withCameras = true): Promise<void> {
  const box = document.getElementById('controls')!;
  const select = document.getElementById('camera-select') as HTMLSelectElement;
  const toggle = document.getElementById('hud-toggle') as HTMLButtonElement;
  if (!withCameras) (select.parentElement as HTMLElement).hidden = true;
  const fill = async () => {
    if (!withCameras) { box.hidden = false; return; }
    const cameras = await listCameras();
    select.innerHTML = '';
    for (const c of cameras) {
      const o = document.createElement('option');
      o.value = c.id; o.textContent = c.label;
      o.selected = c.id === currentCameraId();
      select.appendChild(o);
    }
    box.hidden = false;
  };
  select.onchange = async () => {
    try { await startCamera(video, select.value); } catch (e) { hud.say(`Couldn't open that camera: ${(e as Error).message}`); }
    await fill();
  };
  const applyHud = () => {
    document.body.classList.toggle('hud-only', hudOnly);
    if (remoteCamera) {
      // The camera picture is only downloaded while it is shown (in the floating view it is invisible).
      const picture = document.getElementById('remote-picture') as HTMLImageElement;
      picture.hidden = hudOnly;
      if (hudOnly) picture.removeAttribute('src');
      else if (!picture.getAttribute('src')) picture.src = '/feed.mjpg';
    }
    toggle.textContent = hudOnly ? 'Show camera picture' : 'Floating display only';
  };
  toggle.onclick = () => { setHudOnly(!hudOnly); applyHud(); };
  applyHud();
  navigator.mediaDevices.addEventListener?.('devicechange', fill);
  await fill();
}

function resize(): void {
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(innerWidth * dpr);
  canvas.height = Math.round(innerHeight * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

// Remote camera (the Beam Pro, which is also decoding the camera video and drawing up to three
// copies of this page): redraw 15 times a second, not 60. The picture only changes a few
// times a second anyway.
const MIN_FRAME_MS = remoteCamera ? 66 : 0;
let lastDraw = 0;

function frame(now: number): void {
  requestAnimationFrame(frame);
  if (now - lastDraw < MIN_FRAME_MS) return;
  lastDraw = now;
  if (!remoteCamera) { srcW = video.videoWidth || 1280; srcH = video.videoHeight || 720; }
  view.update(srcW, srcH, innerWidth, innerHeight);
  if (!remoteCamera) { hands.update(video, now); link.pump(video); }

  ctx.clearRect(0, 0, innerWidth, innerHeight);
  const alpha = cube.step(now);
  let corners: [number, number][] | null = null;
  if (cube.keypoints && alpha > 0) {
    corners = cube.keypoints.map((p) => view.fromFrame(p, cube.frameW));
    // HUD-only: there is no camera picture to draw on, so nothing is drawn on the cube.
    if (!hudOnly) drawCubeBox(ctx, corners, alpha * (flow.guide ? 0.5 : 1), `CUBE ${Math.round(cube.confidence * 100)}%`);
    if (!hudOnly && flow.guide && alpha > 0.5) {
      drawMoveArrows(ctx, view, cube.keypoints, cube.frameW, flow.guide.move, flow.guide.undo, now);
    }
  }
  if (!hudOnly) drawHands(ctx, hands.hands, view, srcH, state.error);
  effects.draw(ctx, now, hudOnly ? null : corners, innerWidth, innerHeight);
  placeGhost(!hudOnly && alpha > 0.5 ? corners : null);

  frames.push(now);
  while (frames.length && now - frames[0] > 1000) frames.shift();
  hud.readouts({ fps: frames.length, handsFps: hands.fps, replies: link.repliesPerSecond, latency: link.latencyMs,
                 serverMs: link.serverMs, confidence: cube.confident ? cube.confidence : 0, connected: link.connected });
  const active = state.phase === 'camera' || state.phase === 'scan' || state.phase === 'guided' || state.phase === 'undo';
  const lostCube = active && link.connected && (!remoteCamera || feedOn) && now - lastConfident > HINT_AFTER_MS;
  hud.showHint(lostCube, !lostCube && active && corners && faceOn(corners)
    ? 'Tilt the cube so you see three sides -- a corner pointing at the camera' : undefined);
}

async function boot(): Promise<void> {
  resize();
  addEventListener('resize', resize);
  if (remoteCamera) {  // the frames come from the bridge app: no camera or hand tracking in this page
    document.body.classList.add('remote');
    (window as unknown as { lowPowerFps: number }).lowPowerFps = 15;  // the ghost cube animates at this rate too
    cube.forgetMs = 2500;   // frames arrive a few times a second: keep the cube's overlays between them
    link.path = '/ws/view';
    setupControls(false);
    link.connect();
    requestAnimationFrame(frame);
    return;
  }
  hud.say('Starting the camera…');
  try {
    await startCamera(video);
  } catch (e) {
    hud.say(`Couldn't open the camera: ${(e as Error).message}`);
    return;
  }
  hud.say('Loading hand tracking…');
  try {
    await hands.init(handsMode);
  } catch (e) {
    console.error(e);
    hud.say('Hand tracking unavailable in this browser; carrying on without it.');
  }
  hud.say('');
  setupControls();
  link.connect();  // (the flow already set the stage; the user may have pressed Start scan meanwhile)
  requestAnimationFrame(frame);
}

boot();
