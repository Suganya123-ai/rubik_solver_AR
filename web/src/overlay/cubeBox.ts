// A thin wireframe box around the cube, corner brackets, and a small label on
// a leader line -- the "data" look of the reference HUD.

import type { Pt } from '../view';
import { CYAN, MONO, glow } from './theme';

// The 7 visible corners (0 front-right-top, 1 FLT, 2 BLT, 3 BRT, 4 BRB, 5 FRB,
// 6 FLB) plus the hidden back-left-bottom, estimated as 2 + 6 - 1.
const EDGES = [[0, 1], [1, 2], [2, 3], [3, 0], [0, 5], [1, 6], [3, 4], [4, 5], [5, 6], [2, 7], [6, 7], [4, 7]];
const HIDDEN = new Set([9, 10, 11]); // edges to the hidden corner: drawn fainter

export function drawCubeBox(ctx: CanvasRenderingContext2D, corners: Pt[], alpha: number, label: string): void {
  const c = [...corners, [corners[2][0] + corners[6][0] - corners[1][0], corners[2][1] + corners[6][1] - corners[1][1]] as Pt];
  const xs = c.map((p) => p[0]), ys = c.map((p) => p[1]);
  const size = Math.max(...xs) - Math.min(...xs);
  ctx.save();
  ctx.globalAlpha = alpha;
  glow(ctx, CYAN, 6);
  ctx.strokeStyle = CYAN;
  EDGES.forEach(([a, b], i) => {
    ctx.globalAlpha = alpha * (HIDDEN.has(i) ? 0.25 : 0.7);
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(...c[a]); ctx.lineTo(...c[b]); ctx.stroke();
  });
  // Corner brackets on the screen-aligned bounding box, a little outside the cube.
  const pad = size * 0.08, L = size * 0.1;
  const x0 = Math.min(...xs) - pad, x1 = Math.max(...xs) + pad, y0 = Math.min(...ys) - pad, y1 = Math.max(...ys) + pad;
  ctx.globalAlpha = alpha * 0.9;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (const [x, y, dx, dy] of [[x0, y0, 1, 1], [x1, y0, -1, 1], [x1, y1, -1, -1], [x0, y1, 1, -1]]) {
    ctx.moveTo(x + dx * L, y); ctx.lineTo(x, y); ctx.lineTo(x, y + dy * L);
  }
  ctx.stroke();
  // Leader line to a label, up and to the right of the box.
  const lx = x1 + size * 0.25, ly = y0 - size * 0.12;
  ctx.globalAlpha = alpha * 0.8;
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(x1, y0); ctx.lineTo(lx, ly); ctx.lineTo(lx + 90, ly); ctx.stroke();
  ctx.fillStyle = CYAN;
  ctx.beginPath(); ctx.arc(x1, y0, 2.5, 0, Math.PI * 2); ctx.fill();
  ctx.shadowBlur = 0;
  ctx.font = `11px ${MONO}`;
  ctx.fillText(label, lx + 2, ly - 5);
  ctx.restore();
}
