// The Pyraminx layout, loaded from the server (pyra/geometry.py is the one source of truth),
// and the 3D helpers the ghost pyramid and the arrows on the real pyramid share.

export type V3 = [number, number, number];
export type Pt = [number, number];
export type Geo = {
  corners: Record<string, V3>;
  faces: string[];
  face_corners: Record<string, string[]>;
  colours: Record<string, string>;
  stickers: { face: string; k: number; tri: V3[] }[];
  moves: Record<string, number[]>;
};

export const SWATCH: Record<string, string> = { green: '#2fb35a', blue: '#2a6fdb', red: '#e03131', yellow: '#ffd43b' };

let geo: Geo | null = null;
export async function loadGeometry(): Promise<Geo> {
  if (!geo) geo = (await (await fetch('/api/pyra/geometry')).json()) as Geo;
  return geo;
}
export function geometry(): Geo | null { return geo; }

export const sub = (a: V3, b: V3): V3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
export const add = (a: V3, b: V3): V3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
export const scale = (a: V3, k: number): V3 => [a[0] * k, a[1] * k, a[2] * k];
export const dot = (a: V3, b: V3): number => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
export const cross = (a: V3, b: V3): V3 => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
export const norm = (a: V3): number => Math.hypot(a[0], a[1], a[2]);
export const unit = (a: V3): V3 => scale(a, 1 / (norm(a) || 1));

export function rotate(p: V3, axis: V3, angle: number): V3 {   // Rodrigues, right-handed
  const k = unit(axis), c = Math.cos(angle), s = Math.sin(angle);
  return add(add(scale(p, c), scale(cross(k, p), s)), scale(k, dot(k, p) * (1 - c)));
}

/** Stickers turned by a move (layer: 2 for U/L/R/B, 1 for a tip u/l/r/b), as in geometry.py. */
export function turningStickers(g: Geo, move: string): number[] {
  const corner = move[0].toUpperCase(), layers = move[0] === corner ? 2 : 1;
  const v = g.corners[corner], a = unit(v), height = norm(v) * 4 / 3;
  return g.stickers.map((s, i) => {
    const c = scale(add(add(s.tri[0], s.tri[1]), s.tri[2]), 1 / 3);
    return dot(sub(v, c), a) / height < layers / 3 - 1e-6 ? i : -1;
  }).filter((i) => i >= 0);
}

/** Clockwise (seen from outside the corner) = a negative turn about the corner's axis; ' = the other way. */
export function moveAngle(move: string): number { return (move.endsWith("'") ? 1 : -1) * (2 * Math.PI / 3); }

/** 3D points of an arc around the layer a move turns, sweeping the way it turns, centred toward `toward`. */
export function moveArc(g: Geo, move: string, toward: V3, sweepDeg = 230): V3[] {
  const corner = move[0].toUpperCase(), layers = move[0] === corner ? 2 : 1;
  const v = g.corners[corner], a = unit(v), height = norm(v) * 4 / 3;
  const depth = (layers === 2 ? 0.5 : 0.2) * height;
  const centre = sub(v, scale(a, depth));
  const edge = norm(sub(g.corners.U, g.corners.L));
  const radius = 1.15 * (depth / height) * edge / Math.sqrt(3);
  let e1 = sub(toward, scale(a, dot(toward, a)));
  if (norm(e1) < 0.2) e1 = cross(a, [0.3, 1, 0.2]);
  e1 = unit(e1);
  const e2 = cross(a, e1);
  const dir = Math.sign(moveAngle(move));     // positive = anticlockwise from outside
  const sweep = (sweepDeg * Math.PI) / 180;
  const pts: V3[] = [];
  for (let i = 0; i <= 40; i++) {
    const t = dir * (i / 40 - 0.5) * sweep;
    pts.push(add(centre, add(scale(e1, radius * Math.cos(t)), scale(e2, radius * Math.sin(t)))));
  }
  return pts;
}

/** An affine camera from the 4 corner points: hold[i] is the corner seen at keypoint i. */
export function fitCamera(g: Geo, keypoints: Pt[], hold: string[]): (p: V3) => Pt {
  const rows = hold.map((c) => [...g.corners[c], 1]);
  const solve = (rhs: number[]): number[] => {   // 4x4 Gaussian elimination
    const A = rows.map((r, i) => [...r, rhs[i]]);
    for (let c = 0; c < 4; c++) {
      let p = c;
      for (let r = c + 1; r < 4; r++) if (Math.abs(A[r][c]) > Math.abs(A[p][c])) p = r;
      [A[c], A[p]] = [A[p], A[c]];
      for (let r = 0; r < 4; r++) {
        if (r === c || Math.abs(A[c][c]) < 1e-12) continue;
        const f = A[r][c] / A[c][c];
        for (let k = c; k < 5; k++) A[r][k] -= f * A[c][k];
      }
    }
    return A.map((r, i) => r[4] / (r[i] || 1e-12));
  };
  const mx = solve(keypoints.map((p) => p[0])), my = solve(keypoints.map((p) => p[1]));
  return (p: V3) => [mx[0] * p[0] + mx[1] * p[1] + mx[2] * p[2] + mx[3], my[0] * p[0] + my[1] * p[1] + my[2] * p[2] + my[3]];
}

export function strokeArrow(ctx: CanvasRenderingContext2D, pts: Pt[], colour: string, width: number, label?: string): void {
  if (pts.length < 4) return;
  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.globalAlpha = 0.25;
  ctx.strokeStyle = colour;
  ctx.lineWidth = width * 2.6;
  ctx.beginPath();
  pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
  ctx.stroke();
  ctx.globalAlpha = 1;
  ctx.lineWidth = width;
  ctx.stroke();
  const [x1, y1] = pts[pts.length - 1], [x0, y0] = pts[pts.length - 4];
  const ang = Math.atan2(y1 - y0, x1 - x0), L = width * 3.2;
  ctx.fillStyle = colour;
  ctx.beginPath();
  ctx.moveTo(x1 + Math.cos(ang) * L * 0.6, y1 + Math.sin(ang) * L * 0.6);
  ctx.lineTo(x1 + Math.cos(ang + 2.4) * L, y1 + Math.sin(ang + 2.4) * L);
  ctx.lineTo(x1 + Math.cos(ang - 2.4) * L, y1 + Math.sin(ang - 2.4) * L);
  ctx.closePath();
  ctx.fill();
  if (label) {
    const px = Math.max(13, width * 4);
    const tx = x1 + Math.cos(ang) * width * 5, ty = y1 + Math.sin(ang) * width * 5;
    ctx.font = `800 ${Math.round(px)}px Inter, system-ui, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.lineWidth = Math.max(3, px * 0.22);
    ctx.strokeStyle = 'rgba(0,0,0,0.85)';
    ctx.strokeText(label, tx, ty);
    ctx.fillText(label, tx, ty);
  }
  ctx.restore();
}
