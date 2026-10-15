// Pyraminx Tutor AR on a laptop webcam (branch `pyraminx`): the mirrored full-screen camera, the hand
// mesh, the pyramid's outline and move arrows (from the Pyraminx vision server's 4 corner points),
// the ghost pyramid top right, and the tutor flow (flow.ts).

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
import { type Pt, fitCamera, geometry, loadGeometry, moveArc, strokeArrow, unit } from './geometry';
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
let corners: { pts: Pt[]; frameW: number; at: number; conf: number } | null = null;
const frames: number[] = [];

link.onFrame = (reply) => {
  const r = reply as unknown as { confident: boolean; confidence: number | null; keypoints: Pt[] | null; width: number };
  const now = performance.now();
  if (r.confident && r.keypoints) { lastConfident = now; corners = { pts: r.keypoints, frameW: r.width, at: now, conf: r.confidence ?? 0 }; }
  flow.onFrame(reply as never);
  updateGhost();
};
link.onMessage = (msg) => { flow.onMessage(msg); updateGhost(); };
link.onConnection = (up) => hud.say(up ? '' : 'Connecting to the vision server…');

function updateGhost(): void {
  const t = flow.track;
  ghostBox.hidden = !t || !t.state;
  if (!t || !t.state) return;
  ghost.show(t.state, t.colour_of, t.phase === 'solved' ? null : t.move, t.phase === 'undo', t.hold);
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

function drawOutline(pts: Pt[], alpha: number, label: string): void {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = '#5ee6ff';
  ctx.lineWidth = 2;
  for (const [a, b] of [[0, 1], [0, 2], [0, 3], [1, 2], [2, 3], [3, 1]]) {
    ctx.beginPath(); ctx.moveTo(pts[a][0], pts[a][1]); ctx.lineTo(pts[b][0], pts[b][1]); ctx.stroke();
  }
  ctx.fillStyle = '#5ee6ff';
  ctx.font = '11px "JetBrains Mono", monospace';
  const top = pts.reduce((m, p) => (p[1] < m[1] ? p : m), pts[0]);
  ctx.fillText(label, top[0] + 8, top[1] - 8);
  ctx.restore();
}

function frame(now: number): void {
  requestAnimationFrame(frame);
  view.update(video.videoWidth || 1280, video.videoHeight || 720, innerWidth, innerHeight);
  hands.update(video, now);
  link.pump(video);
  ctx.clearRect(0, 0, innerWidth, innerHeight);
  const fresh = corners && now - corners.at < 600;
  if (corners && fresh) {
    const screen = corners.pts.map((p) => view.fromFrame(p, corners!.frameW));
    drawOutline(screen, flow.guide ? 0.45 : 0.9, `PYRAMID ${Math.round(corners.conf * 100)}%`);
    const g = geometry(), t = flow.track;
    if (g && flow.guide && t?.hold) {   // the arrow on the real pyramid: an arc around the layer to turn
      const cam = fitCamera(g, corners.pts, t.hold);
      const arc = moveArc(g, flow.guide.move, unit(g.corners[t.hold[0]])).map((p) => view.fromFrame(cam(p), corners!.frameW));
      const sweep = Math.min(1, ((now % 1400) / 1400) * 1.6);
      const size = Math.hypot(screen[1][0] - screen[0][0], screen[1][1] - screen[0][1]);
      strokeArrow(ctx, arc.slice(0, Math.max(4, Math.round(arc.length * sweep))), flow.guide.undo ? '#ff6a3d' : '#3dff9a',
        Math.max(4, size * 0.05), 'x1');
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
    'Hold the pyramid steady inside the box, a corner pointing at the camera, so three faces show');
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
