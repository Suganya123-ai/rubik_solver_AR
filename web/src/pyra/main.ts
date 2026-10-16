// Pyraminx Tutor AR on a laptop webcam (branch `pyraminx`): the mirrored full-screen camera, the hand
// mesh, the sticker grid on the real pyramid (from the Pyraminx vision server's 4 corner points; while
// scanning, filled with the colours read), the move guide on it (the part that turns, highlighted and
// shown turning, and an arrow), the ghost pyramid top right, and the tutor flow (flow.ts).

import '../style.css';
import './pyra.css';
import { AppState } from '../appState';
import { startCamera } from '../camera';
import { HandTracking } from '../handTracking';
import { Effects } from '../overlay/effects';
import { drawHands } from '../overlay/handMesh';
import { Hud } from '../overlay/hud';
import { ServerLink } from '../serverLink';
import { View } from '../view';
import { PyraFlow } from './flow';
import { type Geo, type Pt, type V3, type ViewKind, add, cross, dot, fitCamera, geometry, loadGeometry, moveAngle, moveArc,
  rotate, scale, stickerGrid, strokeArrow, sub, towardCamera, turningStickers, unit } from './geometry';
import { GhostPyramid } from './ghost';

const video = document.getElementById('video') as HTMLVideoElement;
const canvas = document.getElementById('overlay') as HTMLCanvasElement;
const ctx = canvas.getContext('2d')!;
const hud = new Hud(document.getElementById('hud')!);
const state = new AppState();
const view = new View();
const hands = new HandTracking();
const link = new ServerLink();
const effects = new Effects();
const flow = new PyraFlow(link, state, effects, document.getElementById('ui')!);
const ghostBox = document.getElementById('ghost')!;
const ghost = new GhostPyramid(document.getElementById('ghost-canvas') as HTMLCanvasElement, geometry);

let lastConfident = -Infinity;
type RGB = [number, number, number];
let corners: { pts: Pt[]; frameW: number; at: number; conf: number; kind: ViewKind; stickers: (RGB | null)[] | null } | null = null;
const frames: number[] = [];

link.onFrame = (reply) => {
  const r = reply as unknown as { confident: boolean; confidence: number | null; keypoints: Pt[] | null; width: number;
    view: ViewKind | null; stickers: (RGB | null)[] | null };
  const now = performance.now();
  if (r.confident && r.keypoints) {
    lastConfident = now;
    corners = { pts: r.keypoints, frameW: r.width, at: now, conf: r.confidence ?? 0, kind: r.view ?? 'corner', stickers: r.stickers };
  }
  flow.onFrame(reply as never);
  updateGhost();
};
link.onMessage = (msg) => { flow.onMessage(msg); updateGhost(); };
link.onConnection = (up) => hud.say(up ? '' : 'Connecting to the vision server…');

function updateGhost(): void {
  const t = flow.track;
  ghostBox.hidden = !t || !t.state;
  if (!t || !t.state) return;
  ghost.show(t.state, t.colour_of, t.phase === 'solved' ? null : t.move, t.phase === 'undo', t.hold, t.view);
  ghostBox.classList.toggle('warn', t.phase === 'undo');
  const size = Math.max(160, Math.min(240, Math.min(innerWidth, innerHeight) * 0.3));
  ghostBox.style.transform = `translate(${innerWidth - size - 16}px, 60px)`;
  ghostBox.style.width = ghostBox.style.height = `${size}px`;
}

function resize(): void {
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(innerWidth * dpr);
  canvas.height = Math.round(innerHeight * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function path(pts: Pt[]): void {
  ctx.beginPath();
  pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
  ctx.closePath();
}

function shrink(pts: Pt[], f: number): Pt[] {
  const c = pts.reduce((m, p) => [m[0] + p[0] / pts.length, m[1] + p[1] / pts.length], [0, 0]);
  return pts.map((p) => [c[0] + (p[0] - c[0]) * f, c[1] + (p[1] - c[1]) * f] as Pt);
}

/** The sticker grid on the real pyramid; while scanning, each sticker filled with the colour read there. */
function drawGrid(screen: Pt[][], alpha: number, colours: (RGB | null)[] | null, label: string, labelAt: Pt): void {
  ctx.save();
  if (colours) {
    screen.forEach((tri, i) => {
      const c = colours[i];
      if (!c) return;
      path(shrink(tri, 0.45));
      ctx.fillStyle = `rgb(${c[0] | 0},${c[1] | 0},${c[2] | 0})`;
      ctx.globalAlpha = 0.95;
      ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.9)';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    });
  }
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 1.2;
  for (const tri of screen) { path(tri); ctx.stroke(); }
  ctx.fillStyle = '#5ee6ff';
  ctx.globalAlpha = 0.9;
  ctx.font = '11px "JetBrains Mono", monospace';
  ctx.fillText(label, labelAt[0] + 8, labelAt[1] - 8);
  ctx.restore();
}

/** A sticker's outward normal (the puzzle is centred on 0). */
function normalOf(tri: V3[]): V3 {
  const n = unit(cross(sub(tri[1], tri[0]), sub(tri[2], tri[0])));
  const c = scale(add(add(tri[0], tri[1]), tri[2]), 1 / 3);
  return dot(n, c) < 0 ? scale(n, -1) : n;
}

const PAUSE = 0.5, TURN = 1.1, HOLD = 0.7;

/** On the real pyramid: the part that turns (highlighted where it is), the same part turning in a loop,
 *  and the arrow (x1). Returns the arrow's direction on screen, in words. */
function drawMove(g: Geo, move: string, undo: boolean, hold: string[], kind: ViewKind, now: number): string {
  const c = corners!;
  const toward = towardCamera(g, hold, kind);
  const cam = fitCamera(g, c.pts, hold, toward);
  const toScreen = (p: V3): Pt => view.fromFrame(cam(p), c.frameW);
  const colour = undo ? '#ff6a3d' : '#3dff9a';
  const turning = turningStickers(g, move);
  const corner = move[0].toUpperCase(), axis = g.corners[corner];
  const facing = (tri: V3[]) => dot(normalOf(tri), cam.dir) > 0.08;
  ctx.save();
  // 1. the part that turns, where it is now
  for (const i of turning) {
    const tri = g.stickers[i].tri;
    if (!facing(tri)) continue;
    path(tri.map(toScreen));
    ctx.globalAlpha = 0.3; ctx.fillStyle = colour; ctx.fill();
    ctx.globalAlpha = 0.95; ctx.strokeStyle = colour; ctx.lineWidth = 2.5; ctx.stroke();
  }
  // 2. the same part turning: the outline sweeps through the turn, then holds, then starts again
  const t = (now / 1000) % (PAUSE + TURN + HOLD);
  const p = t < PAUSE ? 0 : t < PAUSE + TURN ? (t - PAUSE) / TURN : 1;
  const ease = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
  if (p > 0) {
    const angle = moveAngle(move) * ease;
    ctx.globalAlpha = p < 1 ? 0.95 : 0.6;
    ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 2; ctx.setLineDash([6, 4]);
    for (const i of turning) {
      const tri = g.stickers[i].tri.map((q) => rotate(q, axis, angle));
      if (!facing(tri)) continue;
      path(tri.map(toScreen)); ctx.stroke();
    }
    ctx.setLineDash([]);
  }
  ctx.restore();
  // 3. the arrow, around the front of the layer
  const nearCorner = kind === 'corner' && hold[0] === corner;
  const arc = moveArc(g, move, toward, nearCorner ? 230 : 170, 1.3).map(toScreen);
  const k = c.pts.map((q) => view.fromFrame(q, c.frameW));
  const size = Math.max(...k.map((q) => Math.hypot(q[0] - k[0][0], q[1] - k[0][1])));
  strokeArrow(ctx, arc, colour, Math.max(4, size * 0.04), 'x1');
  // its direction in words, as seen on screen
  if (nearCorner) {
    let area = 0;
    for (let i = 0; i + 1 < arc.length; i++) area += arc[i][0] * arc[i + 1][1] - arc[i + 1][0] * arc[i][1];
    return area > 0 ? 'clockwise' : 'anticlockwise';
  }
  const dx = arc[arc.length - 1][0] - arc[0][0], dy = arc[arc.length - 1][1] - arc[0][1];
  return Math.abs(dx) >= Math.abs(dy) ? (dx > 0 ? 'to the right' : 'to the left') : (dy > 0 ? 'down' : 'up');
}

function frame(now: number): void {
  requestAnimationFrame(frame);
  view.update(video.videoWidth || 1280, video.videoHeight || 720, innerWidth, innerHeight);
  hands.update(video, now);
  link.pump(video);
  ctx.clearRect(0, 0, innerWidth, innerHeight);
  const fresh = corners && now - corners.at < 600;
  if (corners && fresh) {
    const c = corners;
    const grid = stickerGrid(c.pts, c.kind).map((tri) => tri.map((p) => view.fromFrame(p, c.frameW)));
    const top = c.pts.map((p) => view.fromFrame(p, c.frameW)).reduce((m, p) => (p[1] < m[1] ? p : m));
    drawGrid(grid, flow.guide ? 0.35 : 0.7, state.phase === 'scan' ? c.stickers : null,
      `PYRAMID ${Math.round(c.conf * 100)}%`, top);
    const g = geometry(), t = flow.track;
    if (g && flow.guide && t?.hold && t.view === c.kind) {
      flow.arrowWord = drawMove(g, flow.guide.move, flow.guide.undo, t.hold, t.view, now);
      flow.arrowFor = flow.guide.move;
    }
  }
  drawHands(ctx, hands.hands, view, video.videoHeight || 720, state.error);
  effects.draw(ctx, now, null, innerWidth, innerHeight);
  frames.push(now);
  while (frames.length && now - frames[0] > 1000) frames.shift();
  hud.readouts({ fps: frames.length, handsFps: hands.fps, replies: link.repliesPerSecond, latency: link.latencyMs,
    serverMs: link.serverMs, confidence: corners && fresh ? corners.conf : 0, connected: link.connected });
  const active = ['camera', 'scan', 'guided', 'undo'].includes(state.phase);
  hud.showHint(active && link.connected && now - lastConfident > 800 ? true : false,
    'Hold the pyramid steady, tip up, with an edge pointing at the camera so two faces show');
}

async function boot(): Promise<void> {
  resize();
  addEventListener('resize', resize);
  hud.say('Loading…');
  await loadGeometry();
  hud.say('Starting the camera…');
  try {
    await startCamera(video);
  } catch (e) {
    hud.say(`Couldn't open the camera: ${(e as Error).message}`);
    return;
  }
  try { await hands.init(new URLSearchParams(location.search).get('hands') ?? 'gpu'); } catch (e) { console.error(e); }
  hud.say('');
  link.connect();
  requestAnimationFrame(frame);
}

boot();
