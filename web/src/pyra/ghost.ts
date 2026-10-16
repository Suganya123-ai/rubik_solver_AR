// The ghost pyramid: the puzzle as it is now, held the way you hold it (the near corner or the near
// edge toward you, mirrored like the camera picture), playing the next move in a loop with an arrow and "x1".

import { type Geo, type Pt, type V3, type ViewKind, SWATCH, add, cross, dot, moveAngle, moveArc, rotate, scale,
  strokeArrow, sub, towardCamera, turningStickers, unit } from './geometry';

const ARROW = '#3dff9a', UNDO = '#ff6a3d';
const PAUSE = 0.7, TURN = 1.0, HOLD = 0.9;

export class GhostPyramid {
  state: string | null = null;
  colourOf: Record<string, string> = {};
  move: string | null = null;
  undo = false;
  hold: string[] = ['U', 'L', 'B', 'R'];
  kind: ViewKind = 'edge';
  private start = performance.now();
  private ctx: CanvasRenderingContext2D;

  constructor(private canvas: HTMLCanvasElement, private geo: () => Geo | null) {
    this.ctx = canvas.getContext('2d')!;
    requestAnimationFrame(this.frame);
  }

  show(state: string, colourOf: Record<string, string>, move: string | null, undo: boolean, hold: string[] | null,
    kind: ViewKind | null): void {
    if (state !== this.state || move !== this.move) this.start = performance.now();
    this.state = state; this.colourOf = colourOf; this.move = move; this.undo = undo;
    if (hold) { this.hold = hold; this.kind = kind ?? 'corner'; }
  }

  /** Model -> view: the near corner (or edge) toward the viewer, up as in the picture (corner-on: the
   *  corner at keypoint 1; edge-on: the near edge's top end), mirrored left-right, tilted a little. */
  private viewBasis(g: Geo): (p: V3) => V3 {
    const z = towardCamera(g, this.hold, this.kind);
    const up = this.kind === 'edge' ? sub(g.corners[this.hold[0]], g.corners[this.hold[1]]) : g.corners[this.hold[1]];
    const y = unit(sub(up, scale(z, dot(up, z))));
    const x = cross(y, z);
    const tilt = this.kind === 'edge' ? 0.35 : 0.45;
    return (p: V3) => {
      const v: V3 = [-dot(p, x), dot(p, y), dot(p, z)];          // mirrored like the picture
      const c = Math.cos(tilt), s = Math.sin(tilt);
      return [v[0], v[1] * c - v[2] * s, v[1] * s + v[2] * c];  // tilt so it doesn't look flat
    };
  }

  private frame = (now: number): void => {
    requestAnimationFrame(this.frame);
    const g = this.geo();
    const c = this.canvas, ctx = this.ctx;
    const dpr = window.devicePixelRatio || 1;
    const w = Math.round(c.clientWidth * dpr), h = Math.round(c.clientHeight * dpr);
    if (!w || !h) return;
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
    ctx.clearRect(0, 0, w, h);
    if (!g || !this.state) return;
    const view = this.viewBasis(g);
    const size = Math.min(w, h) * 0.36;
    const project = (p: V3): Pt => {
      const v = view(p), f = 6 / (6 - v[2]);
      return [w / 2 + v[0] * size * f, h * 0.52 - v[1] * size * f];
    };
    // the move: turn its layer through the turn, then hold, then start again
    const t = ((now - this.start) / 1000) % (PAUSE + TURN + HOLD);
    const p = t < PAUSE ? 0 : t < PAUSE + TURN ? (t - PAUSE) / TURN : 1;
    const ease = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
    const turning = new Set(this.move ? turningStickers(g, this.move) : []);
    const axis = this.move ? g.corners[this.move[0].toUpperCase()] : ([0, 1, 0] as V3);
    const angle = this.move ? moveAngle(this.move) * ease : 0;
    const polys = g.stickers.map((s, i) => {
      let tri = s.tri;
      if (turning.has(i)) tri = tri.map((q) => rotate(q, axis, angle));
      const centre = scale(add(add(tri[0], tri[1]), tri[2]), 1 / 3);
      let normal = unit(cross(sub(tri[1], tri[0]), sub(tri[2], tri[0])));
      if (dot(normal, centre) < 0) normal = scale(normal, -1);          // outward (the puzzle is centred on 0)
      const shrink = tri.map((q) => add(centre, scale(sub(q, centre), 0.86)));
      return { i, depth: view(centre)[2], facing: view(normal)[2], tri, shrink };   // view is linear: no offset
    });
    polys.filter((q) => q.facing > 0).sort((a, b) => a.depth - b.depth).forEach((q) => {
      ctx.beginPath();
      q.tri.map(project).forEach(([x, y], k) => (k ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.closePath();
      ctx.fillStyle = '#111418';
      ctx.fill();
      ctx.beginPath();
      q.shrink.map(project).forEach(([x, y], k) => (k ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.closePath();
      const letter = this.state![q.i];
      ctx.fillStyle = SWATCH[this.colourOf[letter] ?? g.colours[letter]] ?? '#888';
      ctx.globalAlpha = 0.6 + 0.4 * Math.min(1, q.facing * 3);
      ctx.fill();
      ctx.globalAlpha = 1;
    });
    if (this.move) {
      const toward = towardCamera(g, this.hold, this.kind);
      const near = this.kind === 'corner' && this.hold[0] === this.move[0].toUpperCase();
      const arc = moveArc(g, this.move, toward, near ? 230 : 170, 1.3).map(project);
      strokeArrow(ctx, arc, this.undo ? UNDO : ARROW, size * 0.04, 'x1');
    }
  };
}
