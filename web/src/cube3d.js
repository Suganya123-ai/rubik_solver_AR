// A 3D copy of the user's cube, in the scanned colours, that plays the next
// move: the layer to turn rotates in a loop with an arrow around it. Drawn on
// a plain canvas (no libraries): 27 small cubes, painted far to near.
//
// Geometry follows cube/moves.py exactly: axes +x = R, +y = U, +z = F;
// stickers in the server's 54-letter order (faces U R F D L B, rows top to
// bottom as seen from outside each face). Shown from the same corner the
// camera sees: Top up, Front on the left, Right on the right.

(function () {
  const FACES = ['U', 'R', 'F', 'D', 'L', 'B'];
  const DIR = { U: [0, 1, 0], D: [0, -1, 0], F: [0, 0, 1], B: [0, 0, -1], R: [1, 0, 0], L: [-1, 0, 0] };
  const LAYER = { U: [1, 1], D: [1, -1], F: [2, 1], B: [2, -1], R: [0, 1], L: [0, -1] };  // [axis, side]
  const COLOURS = {
    white: '#f4f4f0', yellow: '#ffd43b', red: '#e03131', orange: '#ff8a1f', green: '#2fb35a', blue: '#2a6fdb',
  };

  function gridPos(face, r, c) {
    switch (face) {
      case 'U': return [c - 1, 1, r - 1];
      case 'D': return [c - 1, -1, 1 - r];
      case 'F': return [c - 1, 1 - r, 1];
      case 'B': return [1 - c, 1 - r, -1];
      case 'R': return [1, 1 - r, 1 - c];
      case 'L': return [-1, 1 - r, c - 1];
    }
    throw new Error('bad face ' + face);
  }

  // Every sticker index -> [cubie position, direction it faces].
  const STICKERS = [];
  for (const face of FACES) for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) STICKERS.push([gridPos(face, r, c), DIR[face]]);

  function parseMove(move) {
    const face = move[0];
    const turns = move.endsWith("'") ? -1 : move.endsWith('2') ? 2 : 1;
    const [axis, side] = LAYER[face];
    // Clockwise as seen from outside the face = -90 deg about the face's outward axis.
    return { face, axis, side, angle: -side * turns * Math.PI / 2 };
  }

  function rotate(v, axis, a) {
    const c = Math.cos(a), s = Math.sin(a), [x, y, z] = v;
    if (axis === 0) return [x, y * c - z * s, y * s + z * c];
    if (axis === 1) return [x * c + z * s, y, -x * s + z * c];
    return [x * c - y * s, x * s + y * c, z];
  }

  // The state after a move, by turning the stickers in 3D (used by the tests
  // to prove the animation ends where the server's move engine does).
  function applyMove(state, move) {
    const m = parseMove(move);
    const key = (p, d) => p.map(Math.round).join(',') + '|' + d.map(Math.round).join(',');
    const index = new Map(STICKERS.map(([p, d], i) => [key(p, d), i]));
    const out = state.split('');
    STICKERS.forEach(([p, d], i) => {
      if (p[m.axis] !== m.side) return;
      out[index.get(key(rotate(p, m.axis, m.angle), rotate(d, m.axis, m.angle)))] = state[i];
    });
    return out.join('');
  }

  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const scale = (a, k) => [a[0] * k, a[1] * k, a[2] * k];
  const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
  const ease = (t) => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];

  // Points (3D) of an arrow arc around the turning layer, on the side that
  // faces `toward` (a direction to the viewer), pointing the way it turns.
  function arcPoints(m, toward, radius) {
    const axis = [0, 0, 0]; axis[m.axis] = 1;
    const u = m.axis === 1 ? [0, 0, 1] : [0, 1, 0];
    const v = cross(axis, u);  // a positive turn about the axis carries u toward v
    const mid = Math.atan2(dot(toward, v), dot(toward, u));
    const dir = Math.sign(m.angle);
    const sweep = Math.abs(m.angle) > Math.PI * 0.6 ? 3.6 : 2.0;
    const centre = scale(axis, m.side);
    const pts = [];
    for (let i = 0; i <= 40; i++) {
      const t = mid + dir * (i / 40 - 0.5) * sweep;
      pts.push(add(centre, add(scale(u, radius * Math.cos(t)), scale(v, radius * Math.sin(t)))));
    }
    return pts;
  }

  function strokeArrow(ctx, pts, colour, width, glow) {
    ctx.save();
    ctx.shadowColor = colour;
    ctx.shadowBlur = glow;
    ctx.strokeStyle = colour;
    ctx.lineWidth = width;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    ctx.stroke();
    if (pts.length > 4) {
      const [x1, y1] = pts[pts.length - 1], [x0, y0] = pts[pts.length - 4];
      const a = Math.atan2(y1 - y0, x1 - x0), L = width * 3.2;
      ctx.fillStyle = colour;
      ctx.beginPath();
      ctx.moveTo(x1 + Math.cos(a) * L * 0.6, y1 + Math.sin(a) * L * 0.6);
      ctx.lineTo(x1 + Math.cos(a + 2.4) * L, y1 + Math.sin(a + 2.4) * L);
      ctx.lineTo(x1 + Math.cos(a - 2.4) * L, y1 + Math.sin(a - 2.4) * L);
      ctx.closePath();
      ctx.fill();
    }
    ctx.restore();
  }

  const ARROW = '#3dff9a', UNDO = '#ff6a3d';  // green = do this, red-orange = undo (webcam app colours)

  const HALF = 0.47;     // small-cube half size (gaps between them)
  const STICKER = 0.39;  // sticker half size
  const CAMERA = 11;     // camera distance, for a little perspective
  // Loop timing (seconds): show the cube, turn the layer, hold, start again.
  const PAUSE = 0.7, TURN = 1.0, HOLD = 0.9;

  class CubeHologram {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.state = null;
      this.faceColours = {};
      this.move = null;
      this.homeYaw = -0.68;   // from the camera's corner: Front left, Right right
      this.homePitch = 0.5;   // (the webcam app turns this round to the user's side)
      this.yaw = this.homeYaw;
      this.pitch = this.homePitch;
      this.start = performance.now();
      this._drag(canvas);
      this._frame = this._frame.bind(this);
      requestAnimationFrame(this._frame);
    }

    // state: 54 face letters; faceColours: {letter: colour name}; move: e.g. "R'" or null.
    // opts.undo: the move undoes a mistake (drawn amber).
    show(state, faceColours, move, opts = {}) {
      this.undo = !!opts.undo;
      if (state === this.state && move === this.move) return;
      this.state = state;
      this.faceColours = faceColours || this.faceColours;
      this.move = move || null;
      this.start = performance.now();
    }

    _drag(canvas) {  // drag to look around the cube; double-click to go back
      let last = null;
      canvas.addEventListener('pointerdown', (e) => { last = [e.clientX, e.clientY]; canvas.setPointerCapture(e.pointerId); });
      canvas.addEventListener('pointermove', (e) => {
        if (!last) return;
        this.yaw += (e.clientX - last[0]) * 0.01;
        this.pitch = Math.max(-1.4, Math.min(1.4, this.pitch + (e.clientY - last[1]) * 0.01));
        last = [e.clientX, e.clientY];
      });
      canvas.addEventListener('pointerup', () => { last = null; });
      canvas.addEventListener('dblclick', () => { this.yaw = this.homeYaw; this.pitch = this.homePitch; });
    }

    // world -> view space (camera looks down -z from +z)
    _view(p) {
      const cy = Math.cos(this.yaw), sy = Math.sin(this.yaw), cp = Math.cos(this.pitch), sp = Math.sin(this.pitch);
      const x = p[0] * cy + p[2] * sy, z1 = -p[0] * sy + p[2] * cy;
      return [x, p[1] * cp - z1 * sp, p[1] * sp + z1 * cp];
    }

    _camera() {  // camera position in world space
      const cy = Math.cos(this.yaw), sy = Math.sin(this.yaw), cp = Math.cos(this.pitch), sp = Math.sin(this.pitch);
      const y = CAMERA * sp, z1 = CAMERA * cp;
      return [-z1 * sy, y, z1 * cy];
    }

    _project(p) {
      const v = this._view(p);
      const k = this.size * 0.19 * CAMERA / (CAMERA - v[2]);
      return [this.w / 2 + v[0] * k, this.h / 2 - v[1] * k];
    }

    _frame(now) {
      requestAnimationFrame(this._frame);
      const c = this.canvas;
      if (!this.state || !c.offsetParent) return;  // nothing to show, or hidden
      const dpr = window.devicePixelRatio || 1;
      const w = Math.round(c.clientWidth * dpr), h = Math.round(c.clientHeight * dpr);
      if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
      this.w = w; this.h = h; this.size = Math.min(w, h);

      let angle = 0, m = null;
      if (this.move) {
        m = parseMove(this.move);
        const t = ((now - this.start) / 1000) % (PAUSE + TURN + HOLD);
        angle = t < PAUSE ? 0 : t < PAUSE + TURN ? m.angle * ease((t - PAUSE) / TURN) : m.angle;
      }
      const ctx = this.ctx;
      ctx.clearRect(0, 0, w, h);
      this._base(ctx);
      this._cube(ctx, m, angle);
      if (m) this._arrow(ctx, m);
    }

    _base(ctx) {  // the projector glow under the cube
      const [x, y] = this._project([0, -2.3, 0]);
      const g = ctx.createRadialGradient(x, y, 0, x, y, this.size * 0.42);
      g.addColorStop(0, 'rgba(90, 220, 255, 0.35)');
      g.addColorStop(1, 'rgba(90, 220, 255, 0)');
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.ellipse(x, y, this.size * 0.42, this.size * 0.1, 0, 0, Math.PI * 2);
      ctx.fill();
    }

    _cube(ctx, m, angle) {
      const colourAt = new Map();
      STICKERS.forEach(([p, d], i) => colourAt.set(p.join(',') + '|' + d.join(','), COLOURS[this.faceColours[this.state[i]]] || '#888'));
      const camera = this._camera();
      const cubies = [];
      for (let x = -1; x <= 1; x++) for (let y = -1; y <= 1; y++) for (let z = -1; z <= 1; z++) {
        if (!x && !y && !z) continue;
        const pos = [x, y, z];
        const moving = m && pos[m.axis] === m.side;
        cubies.push({ pos, moving, depth: this._view(moving ? rotate(pos, m.axis, angle) : pos)[2] });
      }
      // The turning layer and the rest are split by a plane: draw the far group first.
      let groups = [cubies];
      if (m) {
        const n = [0, 0, 0]; n[m.axis] = m.side;
        const layerNear = dot(sub(camera, scale(n, 0.5)), n) > 0;
        const turning = cubies.filter((q) => q.moving), still = cubies.filter((q) => !q.moving);
        groups = layerNear ? [still, turning] : [turning, still];
      }
      for (const group of groups) {
        group.sort((a, b) => a.depth - b.depth);
        for (const q of group) this._cubie(ctx, q, m, angle, colourAt, camera);
      }
    }

    _cubie(ctx, q, m, angle, colourAt, camera) {
      const turn = (v) => (q.moving ? rotate(v, m.axis, angle) : v);
      const centre = turn(q.pos);
      for (const d of Object.values(DIR)) {
        const normal = turn(d);
        const faceCentre = add(centre, scale(normal, HALF));
        if (dot(normal, sub(camera, faceCentre)) <= 0) continue;  // facing away
        // Two in-plane axes for this face.
        const a = d[0] ? [0, 1, 0] : [1, 0, 0];
        const b = [d[1] * a[2] - d[2] * a[1], d[2] * a[0] - d[0] * a[2], d[0] * a[1] - d[1] * a[0]];
        const quad = (half, lift) => [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([i, j]) =>
          this._project(turn(add(add(q.pos, scale(d, HALF + lift)), add(scale(a, i * half), scale(b, j * half))))));
        this._poly(ctx, quad(HALF, 0), '#111418', q.moving ? 'rgba(110, 230, 255, 0.55)' : 'rgba(255,255,255,0.06)');
        const colour = colourAt.get(q.pos.join(',') + '|' + d.join(','));
        if (colour) this._poly(ctx, quad(STICKER, 0.002), colour, null, true);
      }
    }

    _poly(ctx, pts, fill, stroke, rounded) {
      ctx.beginPath();
      pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.fill();
      if (rounded) {  // soften sticker corners
        ctx.lineJoin = 'round';
        ctx.lineWidth = this.size * 0.012;
        ctx.strokeStyle = fill;
        ctx.stroke();
      }
      if (stroke) {
        ctx.lineWidth = Math.max(1, this.size * 0.004);
        ctx.strokeStyle = stroke;
        ctx.stroke();
      }
    }

    _arrow(ctx, m) {
      const pts = arcPoints(m, this._camera(), 2.05).map((p) => this._project(p));
      strokeArrow(ctx, pts, this.undo ? UNDO : ARROW, this.size * 0.022, this.size * 0.04);
    }
  }

  // ---------- the same move drawn on the camera picture ----------
  // The 7 corner points YOLO finds (FRU, FLU, BLU, BRU, BRD, FRD, FLD), in
  // cube units: small cubes are 1 apart, so the cube's corners are at +-1.5.
  const CORNERS_3D = [[1, 1, 1], [-1, 1, 1], [-1, 1, -1], [1, 1, -1], [1, -1, -1], [1, -1, 1], [-1, -1, 1]]
    .map((p) => scale(p, 1.5));

  function solveLinear(A, b) {  // Gaussian elimination with partial pivoting
    const n = b.length;
    A = A.map((r) => r.slice()); b = b.slice();
    for (let c = 0; c < n; c++) {
      let piv = c;
      for (let r = c + 1; r < n; r++) if (Math.abs(A[r][c]) > Math.abs(A[piv][c])) piv = r;
      if (Math.abs(A[piv][c]) < 1e-12) return null;
      [A[c], A[piv]] = [A[piv], A[c]]; [b[c], b[piv]] = [b[piv], b[c]];
      for (let r = 0; r < n; r++) {
        if (r === c) continue;
        const f = A[r][c] / A[c][c];
        for (let j = c; j < n; j++) A[r][j] -= f * A[c][j];
        b[r] -= f * b[c];
      }
    }
    return b.map((v, i) => v / A[i][i]);
  }

  function leastSquares(rows, rhs) {  // via the normal equations
    const n = rows[0].length;
    const A = [...Array(n)].map((_, i) => [...Array(n)].map((_, j) => rows.reduce((s, r) => s + r[i] * r[j], 0)));
    const b = [...Array(n)].map((_, i) => rows.reduce((s, r, k) => s + r[i] * rhs[k], 0));
    return solveLinear(A, b);
  }

  // A perspective camera (3x4, last entry fixed to 1) fitted to the 7 corners:
  // the cube is close to the camera, so perspective matters. Falls back to an
  // affine fit if that goes wrong. Returns {project(p), eye(p) -> direction
  // from p toward the camera}.
  function fitCamera(points2d) {
    const rows = [], rhs = [];
    CORNERS_3D.forEach(([X, Y, Z], i) => {
      const [u, v] = points2d[i];
      rows.push([X, Y, Z, 1, 0, 0, 0, 0, -u * X, -u * Y, -u * Z]); rhs.push(u);
      rows.push([0, 0, 0, 0, X, Y, Z, 1, -v * X, -v * Y, -v * Z]); rhs.push(v);
    });
    const p = leastSquares(rows, rhs);
    if (p) {
      const P = [p.slice(0, 4), p.slice(4, 8), [p[8], p[9], p[10], 1]];
      const project = (q) => {
        const w = P[2][0] * q[0] + P[2][1] * q[1] + P[2][2] * q[2] + P[2][3];
        return [0, 1].map((r) => (P[r][0] * q[0] + P[r][1] * q[1] + P[r][2] * q[2] + P[r][3]) / w);
      };
      const centre = solveLinear(P.map((r) => r.slice(0, 3)), P.map((r) => -r[3]));  // camera position
      const err = Math.max(...CORNERS_3D.map((q, i) => Math.hypot(project(q)[0] - points2d[i][0], project(q)[1] - points2d[i][1])));
      const size = Math.hypot(points2d[2][0] - points2d[5][0], points2d[2][1] - points2d[5][1]);
      if (centre && dot(centre, [1, 1, 1]) > 0 && Math.hypot(...centre) > 3 && err < 0.08 * size) {
        return { project, eye: (q) => sub(centre, q) };
      }
    }
    // Affine fallback: the viewing direction is the same everywhere.
    const rowsA = CORNERS_3D.map((q) => [q[0], q[1], q[2], 1]);
    const a = leastSquares(rowsA, points2d.map((q) => q[0])), b = leastSquares(rowsA, points2d.map((q) => q[1]));
    let toward = cross(a.slice(0, 3), b.slice(0, 3));
    if (dot(toward, [1, 1, 1]) < 0) toward = scale(toward, -1);  // the camera sees Top, Front, Right
    return {
      project: (q) => [a[0] * q[0] + a[1] * q[1] + a[2] * q[2] + a[3], b[0] * q[0] + b[1] * q[1] + b[2] * q[2] + b[3]],
      eye: () => toward,
    };
  }

  // Draws `move` on the camera picture: the stickers that will turn, and an
  // arrow around their layer (sweeping, so it reads as motion). keypoints:
  // the 7 corners in canvas pixels. undo: draw it as an undo step (amber).
  function drawMoveOnVideo(ctx, keypoints, move, opts = {}) {
    if (!move || !keypoints || keypoints.length !== 7) return;
    const m = parseMove(move);
    const cam = fitCamera(keypoints);
    const colour = opts.undo ? UNDO : ARROW;
    const size = Math.hypot(keypoints[2][0] - keypoints[5][0], keypoints[2][1] - keypoints[5][1]);  // top to bottom
    ctx.save();
    for (const [p, d] of STICKERS) {  // the turning layer's visible stickers
      if (p[m.axis] !== m.side || dot(d, cam.eye(add(p, scale(d, 0.5)))) <= 0) continue;
      const a = d[0] ? [0, 1, 0] : [1, 0, 0], b = cross(d, a);
      const quad = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([i, j]) =>
        cam.project(add(add(p, scale(d, 0.5)), add(scale(a, i * 0.42), scale(b, j * 0.42)))));
      ctx.beginPath();
      quad.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.closePath();
      ctx.fillStyle = opts.undo ? 'rgba(255, 106, 61, 0.18)' : 'rgba(61, 255, 154, 0.14)';
      ctx.fill();
      ctx.lineWidth = Math.max(2, size * 0.008);
      ctx.strokeStyle = colour;
      ctx.stroke();
    }
    ctx.restore();
    const centre = [0, 0, 0]; centre[m.axis] = m.side;
    const arc = arcPoints(m, cam.eye(centre), 2.2).map(cam.project);
    const t = ((opts.now || performance.now()) % 1400) / 1400;           // sweep, then show whole
    const shown = arc.slice(0, Math.max(3, Math.round(arc.length * Math.min(1, t * 1.6))));
    strokeArrow(ctx, shown, colour, Math.max(4, size * 0.03), size * 0.06);
  }

  if (typeof window !== 'undefined') { window.CubeHologram = CubeHologram; window.drawMoveOnVideo = drawMoveOnVideo; }
  if (typeof module !== 'undefined') module.exports = { applyMove, parseMove, STICKERS, fitCamera, arcPoints };
})();
