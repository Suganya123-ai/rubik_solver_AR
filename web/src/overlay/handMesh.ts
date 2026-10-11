// The wireframe hand mesh: bones, a web of cross-links between neighbouring
// fingers (the "mesh" look), and a dot on every joint.

import type { Hand } from '../handTracking';
import type { View } from '../view';
import { CYAN, RED, glow } from './theme';

const BONES = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [0, 17], [17, 18], [18, 19], [19, 20]];
// Thin links across the palm and between neighbouring fingers.
const WEB = [[0, 9], [0, 13], [1, 5], [2, 5], [6, 10], [10, 14], [14, 18], [7, 11], [11, 15], [15, 19],
  [8, 12], [12, 16], [16, 20], [3, 6], [2, 6]];

export function drawHands(ctx: CanvasRenderingContext2D, hands: Hand[], view: View, videoH: number,
                          error: boolean): void {
  const colour = error ? RED : CYAN;
  ctx.save();
  ctx.lineCap = 'round';
  for (const hand of hands) {
    const p = hand.points.map(([x, y]) => view.fromNormalized(x, y, videoH));
    const size = Math.hypot(p[0][0] - p[9][0], p[0][1] - p[9][1]);  // wrist to middle knuckle
    glow(ctx, colour, Math.min(14, size * 0.06));
    ctx.strokeStyle = colour;
    ctx.globalAlpha = 0.35;
    ctx.lineWidth = Math.max(0.6, size * 0.004);
    ctx.beginPath();
    for (const [a, b] of WEB) { ctx.moveTo(...p[a]); ctx.lineTo(...p[b]); }
    ctx.stroke();
    ctx.globalAlpha = 0.85;
    ctx.lineWidth = Math.max(0.9, size * 0.007);
    ctx.beginPath();
    for (const [a, b] of BONES) { ctx.moveTo(...p[a]); ctx.lineTo(...p[b]); }
    ctx.stroke();
    ctx.globalAlpha = 1;
    ctx.fillStyle = colour;
    const r = Math.max(1.5, size * 0.012);
    for (const [x, y] of p) { ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); }
  }
  ctx.restore();
}
