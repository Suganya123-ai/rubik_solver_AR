// Labelling tool: review YOLO's 7 corner points on saved frames, drag to fix,
// save. Labels are written next to each frame for retraining.

const FACE_CORNERS = { U: [2, 3, 0, 1], F: [1, 0, 5, 6], R: [0, 3, 4, 5] };
const FACE_COLORS = { U: '#ff4fa3', F: '#4f8cff', R: '#3ecf8e' };
const HIT_RADIUS = 18; // CSS pixels

const els = {};
let captures = [];
let index = 0;
let current = null;   // label payload from the server for the current frame
let points = null;    // 7 [x, y] in image pixels, or null
let modelGuess = null;
let dragging = -1;

document.addEventListener('DOMContentLoaded', async () => {
  for (const id of ['frame', 'overlay', 'status', 'progress', 'position', 'prev-btn', 'next-btn', 'next-todo-btn',
                    'save-btn', 'nocube-btn', 'reset-btn', 'place-btn', 'delete-btn', 'error-banner']) {
    els[id] = document.getElementById(id);
  }
  els['prev-btn'].onclick = () => go(index - 1);
  els['next-btn'].onclick = () => go(index + 1);
  els['next-todo-btn'].onclick = nextUnreviewed;
  els['save-btn'].onclick = save;
  els['nocube-btn'].onclick = noCube;
  els['reset-btn'].onclick = () => { points = modelGuess && modelGuess.map((p) => [...p]); draw(); };
  els['place-btn'].onclick = placeDefault;
  els['delete-btn'].onclick = remove;
  els.frame.onload = draw;
  window.addEventListener('resize', draw);
  document.addEventListener('keydown', onKey);
  const c = els.overlay;
  c.addEventListener('pointerdown', onDown);
  c.addEventListener('pointermove', onMove);
  c.addEventListener('pointerup', onUp);
  c.addEventListener('pointercancel', onUp);
  await refreshList();
  const firstTodo = captures.findIndex((c) => !c.reviewed);
  go(firstTodo >= 0 ? firstTodo : 0);
});

function showError(msg) { els['error-banner'].textContent = msg; els['error-banner'].classList.add('show'); }
function clearError() { els['error-banner'].classList.remove('show'); }

async function refreshList() {
  const res = await fetch('/api/captures');
  const data = await res.json();
  captures = data.captures;
  els.progress.textContent = captures.length
    ? `${data.reviewed} of ${captures.length} frames reviewed`
    : 'No saved frames yet. Use "Save frame" in the live view first.';
}

async function go(i) {
  if (!captures.length) { els.position.textContent = '–'; return; }
  index = Math.max(0, Math.min(captures.length - 1, i));
  els.position.textContent = `${index + 1} / ${captures.length}`;
  const id = captures[index].id;
  setStatus('Loading…', '');
  const res = await fetch(`/api/captures/${id}/label`);
  if (!res.ok) { showError('Could not load this frame.'); return; }
  current = await res.json();
  points = current.keypoints;
  modelGuess = current.source === 'model' || current.source === 'saved' ? current.keypoints : null;
  els.frame.src = `/api/captures/${id}/image`;
  const labels = { reviewed: 'Reviewed ✓', model: "YOLO's guess — check it", saved: 'Saved guess — check it',
                   none: 'YOLO found no cube — place points or mark "no cube"' };
  setStatus(current.reviewed && !points ? 'Reviewed: no cube' : labels[current.source],
            current.reviewed ? 'found' : (points ? 'unsure' : 'lost'));
}

function nextUnreviewed() {
  for (let k = 1; k <= captures.length; k++) {
    const j = (index + k) % captures.length;
    if (!captures[j].reviewed) return go(j);
  }
  setStatus('Every frame is reviewed', 'found');
}

function setStatus(text, cls) { els.status.textContent = text; els.status.className = 'live-status ' + cls; }

// --- geometry: image pixels <-> canvas pixels ---
function scale() { return els.overlay.width / (current ? current.width : 1); }
function toCanvas(p) { const s = scale(); return [p[0] * s, p[1] * s]; }
function fromEvent(e) {
  const r = els.overlay.getBoundingClientRect();
  const s = (current.width / r.width);
  return [(e.clientX - r.left) * s, (e.clientY - r.top) * s];
}

function draw() {
  const c = els.overlay;
  const r = els.frame.getBoundingClientRect();
  c.width = r.width * devicePixelRatio;
  c.height = r.height * devicePixelRatio;
  const ctx = c.getContext('2d');
  ctx.clearRect(0, 0, c.width, c.height);
  if (!points || !current) return;
  const pts = points.map(toCanvas);
  const px = devicePixelRatio;
  for (const face of Object.keys(FACE_CORNERS)) {
    const q = FACE_CORNERS[face].map((i) => pts[i]);
    ctx.beginPath();
    q.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    ctx.closePath();
    ctx.fillStyle = FACE_COLORS[face] + '22';
    ctx.fill();
    ctx.lineWidth = 2 * px;
    ctx.strokeStyle = FACE_COLORS[face];
    ctx.stroke();
  }
  pts.forEach(([x, y], i) => {
    ctx.beginPath();
    ctx.arc(x, y, (i === dragging ? 9 : 7) * px, 0, Math.PI * 2);
    ctx.fillStyle = '#e11d74';
    ctx.fill();
    ctx.lineWidth = 2 * px;
    ctx.strokeStyle = '#fff';
    ctx.stroke();
    ctx.font = `bold ${13 * px}px -apple-system, sans-serif`;
    ctx.fillStyle = '#fff';
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 3 * px;
    ctx.strokeText(String(i), x + 10 * px, y - 10 * px);
    ctx.fillText(String(i), x + 10 * px, y - 10 * px);
  });
}

function onDown(e) {
  if (!points) return;
  const p = fromEvent(e);
  const r = els.overlay.getBoundingClientRect();
  const limit = HIT_RADIUS * current.width / r.width;
  let best = -1, bestD = limit;
  points.forEach((q, i) => { const d = Math.hypot(q[0] - p[0], q[1] - p[1]); if (d < bestD) { best = i; bestD = d; } });
  if (best < 0) return;
  dragging = best;
  els.overlay.setPointerCapture(e.pointerId);
  els.overlay.classList.add('dragging');
  draw();
}

function onMove(e) {
  if (dragging < 0) return;
  const [x, y] = fromEvent(e);
  points[dragging] = [Math.max(0, Math.min(current.width, x)), Math.max(0, Math.min(current.height, y))];
  draw();
}

function onUp() { dragging = -1; els.overlay.classList.remove('dragging'); draw(); }

function placeDefault() {
  // A neutral corner-on hexagon in the middle of the frame to drag into place.
  const cx = current.width / 2, cy = current.height / 2, s = Math.min(current.width, current.height) * 0.28;
  const c30 = Math.cos(Math.PI / 6);
  points = [[cx, cy], [cx - s * c30, cy - s / 2], [cx, cy - s], [cx + s * c30, cy - s / 2],
            [cx + s * c30, cy + s / 2], [cx, cy + s], [cx - s * c30, cy + s / 2]];
  setStatus('Drag each point onto its corner, then save', 'unsure');
  draw();
}

async function post(keypoints) {
  clearError();
  const res = await fetch(`/api/captures/${captures[index].id}/label`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ keypoints }),
  });
  if (!res.ok) { showError('Save failed: ' + ((await res.json()).detail || res.status)); return false; }
  captures[index].reviewed = true;
  await refreshList();
  return true;
}

async function save() {
  if (!points) { showError('No points to save. Place points (P) or choose "No cube here" (N).'); return; }
  if (await post(points.map(([x, y]) => [Math.round(x * 10) / 10, Math.round(y * 10) / 10]))) nextUnreviewed();
}

async function noCube() { if (await post(null)) nextUnreviewed(); }

async function remove() {
  if (!confirm('Delete this frame and its label?')) return;
  await fetch(`/api/captures/${captures[index].id}`, { method: 'DELETE' });
  await refreshList();
  go(Math.min(index, captures.length - 1));
}

function onKey(e) {
  if (e.target.tagName === 'INPUT') return;
  const k = e.key.toLowerCase();
  if (k === 's') save();
  else if (k === 'n') noCube();
  else if (k === 'r') els['reset-btn'].click();
  else if (k === 'p') placeDefault();
  else if (k === 'd') remove();
  else if (e.key === 'ArrowLeft') go(index - 1);
  else if (e.key === 'ArrowRight') go(index + 1);
  else return;
  e.preventDefault();
}
