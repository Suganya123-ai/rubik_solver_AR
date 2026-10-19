// Short celebratory effects: a green check + grid outline when a move is
// right, and the heartbeat line + confetti when the cube is solved.

import type { Pt } from '../view';
import { GREEN, glow } from './theme';

// The visible sides as corner indices (top, front-left, front-right in the picture).
const SIDES = [[2, 3, 0, 1], [1, 0, 5, 6], [0, 3, 4, 5]];

type Piece = { x: number; y: number; vx: number; vy: number; rot: number; vr: number; colour: string; w: number; h: number };

export class Effects {
  private checkUntil = 0;
  private checkStart = 0;
  private confetti: Piece[] = [];
  private heartbeatStart = -Infinity;

  check(now: number): void { this.checkStart = now; this.checkUntil = now + 900; }

  celebrate(now: number, w: number, h: number): void {
    this.heartbeatStart = now;
    const colours = ['#3dff9a', '#5ee6ff', '#ffb547', '#ff4d5e', '#b07cff', '#ffffff', '#ffd43b'];
    for (let i = 0; i < 160; i++) {
      this.confetti.push({ x: w / 2 + (Math.random() - 0.5) * w * 0.3, y: h * 0.45, vx: (Math.random() - 0.5) * 14,
        vy: -Math.random() * 15 - 4, rot: Math.random() * 6, vr: (Math.random() - 0.5) * 0.4,
        colour: colours[i % colours.length], w: 6 + Math.random() * 6, h: 3 + Math.random() * 4 });
    }
  }

  get busy(): boolean { return this.confetti.length > 0; }

  /** corners: the cube's 7 corners on screen (or null). */
  draw(ctx: CanvasRenderingContext2D, now: number, corners: Pt[] | null, w: number, h: number): void {
    if (corners && now < this.checkUntil) this.drawCheck(ctx, now, corners);
    if (now - this.heartbeatStart < 2200) this.drawHeartbeat(ctx, now - this.heartbeatStart, w, h);
    if (this.confetti.length) this.drawConfetti(ctx, h);
  }

  private drawCheck(ctx: CanvasRenderingContext2D, now: number, c: Pt[]): void {
    const t = (now - this.checkStart) / 900;
    const alpha = t < 0.7 ? 1 : 1 - (t - 0.7) / 0.3;
    ctx.save();
    ctx.globalAlpha = alpha;
    glow(ctx, GREEN, 12);
    ctx.strokeStyle = GREEN;
    ctx.lineWidth = 2;
    for (const side of SIDES) {  // 3x3 grid on each visible side
      const q = side.map((i) => c[i]);
      const at = (u: number, v: number): Pt => {
        const top = [q[0][0] + (q[1][0] - q[0][0]) * u, q[0][1] + (q[1][1] - q[0][1]) * u];
        const bot = [q[3][0] + (q[2][0] - q[3][0]) * u, q[3][1] + (q[2][1] - q[3][1]) * u];
        return [top[0] + (bot[0] - top[0]) * v, top[1] + (bot[1] - top[1]) * v];
      };
      ctx.beginPath();
      for (let k = 0; k <= 3; k++) {
        ctx.moveTo(...at(k / 3, 0)); ctx.lineTo(...at(k / 3, 1));
        ctx.moveTo(...at(0, k / 3)); ctx.lineTo(...at(1, k / 3));
      }
      ctx.stroke();
    }
    // The check mark above the cube, drawn on as it appears.
    const top = c.reduce((a, p) => (p[1] < a[1] ? p : a));
    const size = Math.max(...c.map((p) => p[0])) - Math.min(...c.map((p) => p[0]));
    const s = size * 0.16, x = top[0], y = top[1] - s * 1.1;
    const pts: Pt[] = [[x - s * 0.55, y], [x - s * 0.15, y + s * 0.4], [x + s * 0.6, y - s * 0.45]];
    const grow = Math.min(1, t / 0.35);
    ctx.lineWidth = Math.max(5, s * 0.22);
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.beginPath();
    ctx.moveTo(...pts[0]);
    if (grow < 0.4) ctx.lineTo(pts[0][0] + (pts[1][0] - pts[0][0]) * grow / 0.4, pts[0][1] + (pts[1][1] - pts[0][1]) * grow / 0.4);
    else {
      const g = (grow - 0.4) / 0.6;
      ctx.lineTo(...pts[1]);
      ctx.lineTo(pts[1][0] + (pts[2][0] - pts[1][0]) * g, pts[1][1] + (pts[2][1] - pts[1][1]) * g);
    }
    ctx.stroke();
    ctx.restore();
  }

  private drawHeartbeat(ctx: CanvasRenderingContext2D, t: number, w: number, h: number): void {
    const y0 = h * 0.5, progress = Math.min(1, t / 1200), fade = t < 1600 ? 1 : 1 - (t - 1600) / 600;
    ctx.save();
    ctx.globalAlpha = fade;
    glow(ctx, GREEN, 18);
    ctx.strokeStyle = GREEN;
    ctx.lineWidth = 3;
    ctx.lineJoin = 'round';
    ctx.beginPath();
    const n = 120;
    for (let i = 0; i <= n * progress; i++) {
      const x = (i / n) * w, u = i / n;
      // flat, then one heartbeat spike in the middle
      const d = u - 0.5;
      const y = Math.abs(d) < 0.06 ? y0 - Math.sin((d + 0.06) / 0.12 * Math.PI * 2) * h * 0.12 * (1 - Math.abs(d) / 0.06) : y0;
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    }
    ctx.stroke();
    ctx.restore();
  }

  private drawConfetti(ctx: CanvasRenderingContext2D, h: number): void {
    ctx.save();
    for (const p of this.confetti) {
      p.vy += 0.35; p.vx *= 0.99; p.x += p.vx; p.y += p.vy; p.rot += p.vr;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.fillStyle = p.colour;
      ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
      ctx.restore();
    }
    ctx.restore();
    this.confetti = this.confetti.filter((p) => p.y < h + 40);
  }
}
