// Live cube view: streams webcam frames to /ws/live and draws what the
// server finds (7 corner points, the three visible sides, sticker colours).

const SEND_WIDTH = 640;   // frames are downscaled to this width before sending
const JPEG_QUALITY = 0.8;
const FACES = ['U', 'F', 'R'];
const FACE_LABELS = { U: 'Top', F: 'Front', R: 'Right' };
// Keypoint indices of each side's corners: top-left, top-right, bottom-right, bottom-left.
const FACE_CORNERS = { U: [2, 3, 0, 1], F: [1, 0, 5, 6], R: [0, 3, 4, 5] };
const FACE_COLORS = { U: '#ff4fa3', F: '#4f8cff', R: '#3ecf8e' };

const els = {};
let ws = null;
let frameId = 0;
let sentAt = 0;
let inFlight = false;
let replyTimes = [];
const sendCanvas = document.createElement('canvas');

document.addEventListener('DOMContentLoaded', () => {
  for (const id of ['video', 'overlay', 'live-status', 'stat-fps', 'stat-latency', 'stat-server', 'stat-conf',
                    'save-btn', 'save-count', 'live-faces', 'error-banner', 'live-stage', 'ar-btn', 'ar-exit-btn',
                    'ar-holo', 'hands-chip']) {
    els[id] = document.getElementById(id);
  }
  els['save-btn'].addEventListener('click', () => ws && ws.send(JSON.stringify({ type: 'save' })));
  els['ar-btn'].addEventListener('click', () => setGlassesView(true));
  els['ar-exit-btn'].addEventListener('click', () => setGlassesView(false));
  document.addEventListener('keydown', (e) => {
    if (e.target.closest && e.target.closest('input, textarea')) return;
    if (e.key === 'Escape') setGlassesView(false);
    else if (e.key === 'g' || e.key === 'G') setGlassesView(!window.glassesView);
  });
  renderFaces(null);
  startCamera();
});

function showError(message) {
  els['error-banner'].textContent = message;
  els['error-banner'].classList.add('show');
}

async function startCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'environment' },
    });
    els.video.srcObject = stream;
    await els.video.play();
    connect();
  } catch (e) {
    showError("Couldn't access the camera: " + e.message + '. Check browser permissions.');
  }
}

function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/live`);
  ws.binaryType = 'arraybuffer';
  ws.onopen = () => {
    setStatus('Loading the cube detector…', '');
    sendFrame();
  };
  ws.onmessage = (event) => handleMessage(JSON.parse(event.data));
  ws.onclose = () => {
    setStatus('Disconnected — retrying…', 'lost');
    els['save-btn'].disabled = true;
    inFlight = false;
    setTimeout(connect, 1500);
  };
}

function sendFrame() {
  if (!ws || ws.readyState !== WebSocket.OPEN || inFlight) return;
  const v = els.video;
  if (!v.videoWidth) { setTimeout(sendFrame, 100); return; }
  sendCanvas.width = SEND_WIDTH;
  sendCanvas.height = Math.round(SEND_WIDTH * v.videoHeight / v.videoWidth);
  sendCanvas.getContext('2d').drawImage(v, 0, 0, sendCanvas.width, sendCanvas.height);
  inFlight = true;
  sendCanvas.toBlob(async (blob) => {
    const jpeg = new Uint8Array(await blob.arrayBuffer());
    const msg = new Uint8Array(4 + jpeg.length);
    new DataView(msg.buffer).setUint32(0, ++frameId);
    msg.set(jpeg, 4);
    sentAt = performance.now();
    ws.send(msg);
  }, 'image/jpeg', JPEG_QUALITY);
}

// Lets scan_ui.js send commands ({type: 'scan_start'} etc.) over the live socket.
window.sendLiveCommand = (command) => ws && ws.readyState === WebSocket.OPEN && ws.send(JSON.stringify(command));

function handleMessage(msg) {
  if (msg.type === 'scan' || msg.type === 'track' || msg.type === 'scan_result' ||
      (msg.type === 'error' && msg.code !== 'BAD_REQUEST' && window.scanAwaitingReply)) {
    if (window.onScanMessage) window.onScanMessage(msg);
    return;
  }
  if (msg.type === 'frame' && (msg.scan || msg.scan_result || msg.track) && window.onScanMessage) window.onScanMessage(msg);
  if (msg.type === 'saved') {
    els['save-count'].textContent = `${msg.count} frame${msg.count === 1 ? '' : 's'} saved` +
      (msg.prelabelled ? '' : ' (last one had no cube found)');
    return;
  }
  if (msg.type === 'error') {
    setStatus(msg.message, 'lost');
  } else if (msg.type === 'frame') {
    const now = performance.now();
    replyTimes.push(now);
    replyTimes = replyTimes.filter((t) => now - t < 1000);
    els['stat-fps'].textContent = replyTimes.length;
    els['stat-latency'].textContent = Math.round(now - sentAt);
    els['stat-server'].textContent = msg.ms;
    els['stat-conf'].textContent = msg.confidence === null ? '–' : msg.confidence.toFixed(2);
    els['save-btn'].disabled = false;
    if (msg.keypoints && msg.confident) setStatus('Cube found', 'found');
    else if (msg.keypoints) setStatus('Unsure — low confidence guess (save this frame!)', 'unsure');
    else setStatus('No cube found — hold it corner-on to the camera', 'lost');
    drawOverlay(msg);
    renderFaces(msg.faces);
  }
  inFlight = false;
  requestAnimationFrame(sendFrame);
}

// Glasses view: the camera picture full screen with the heads-up display,
// as the wearer will see it through the XREAL glasses.
window.setGlassesView = setGlassesView;
function setGlassesView(on) {
  window.glassesView = !!on;
  els['live-stage'].classList.toggle('ar', window.glassesView);
  if (window.onGlassesView) window.onGlassesView(window.glassesView);
}

function setStatus(text, cls) {
  els['live-status'].textContent = text;
  els['live-status'].className = 'live-status ' + cls;
}

function drawOverlay(msg) {
  const canvas = els.overlay;
  const stage = canvas.getBoundingClientRect();
  canvas.width = stage.width * devicePixelRatio;
  canvas.height = stage.height * devicePixelRatio;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // The video is letterboxed (object-fit: contain): map frame pixels to canvas pixels.
  const scale = Math.min(canvas.width / msg.width, canvas.height / msg.height);
  const ox = (canvas.width - msg.width * scale) / 2;
  const oy = (canvas.height - msg.height * scale) / 2;
  const P = (p) => [ox + p[0] * scale, oy + p[1] * scale];
  const px = devicePixelRatio;
  drawHands(ctx, msg.hands, P, px, msg.hands_busy);
  els['hands-chip'].hidden = !(msg.hands_busy && window.cubeTaskActive);
  if (!msg.keypoints) return;
  const pts = msg.keypoints.map(P);
  const guide = window.liveGuide;  // set by scan_ui.js while solving: {move, undo}
  const guiding = guide && guide.move && msg.confident;
  ctx.globalAlpha = guiding ? 0.3 : (msg.confident ? 1 : 0.55);  // while guiding, the move is what matters

  for (const face of FACES) {
    const corners = FACE_CORNERS[face].map((i) => pts[i]);
    ctx.beginPath();
    corners.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    ctx.closePath();
    ctx.lineWidth = 2.5 * px;
    ctx.strokeStyle = FACE_COLORS[face];
    ctx.stroke();
    // 3x3 grid lines inside the side (bilinear is close enough for drawing).
    ctx.lineWidth = 1 * px;
    for (let t = 1; t < 3; t++) {
      const f = t / 3;
      line(ctx, lerp(corners[0], corners[1], f), lerp(corners[3], corners[2], f));
      line(ctx, lerp(corners[0], corners[3], f), lerp(corners[1], corners[2], f));
    }
  }
  pts.forEach(([x, y], i) => {
    ctx.beginPath();
    ctx.arc(x, y, 6 * px, 0, Math.PI * 2);
    ctx.fillStyle = msg.confident ? '#e11d74' : '#f59e0b';
    ctx.fill();
    ctx.lineWidth = 2 * px;
    ctx.strokeStyle = '#fff';
    ctx.stroke();
    ctx.font = `bold ${12 * px}px -apple-system, sans-serif`;
    ctx.fillStyle = '#fff';
    ctx.fillText(String(i), x + 8 * px, y - 8 * px);
  });
  ctx.globalAlpha = 1;
  drawCovered(ctx, pts, msg.covered, px);
  if (guiding && window.drawMoveOnVideo) window.drawMoveOnVideo(ctx, pts, guide.move, { undo: guide.undo });
  if (window.glassesView) placeHologram(pts, canvas);
}

// Stickers a finger is covering: the camera can't read them, so they are left out.
function drawCovered(ctx, pts, covered, px) {
  if (!covered) return;
  ctx.save();
  ctx.setLineDash([5 * px, 4 * px]);
  ctx.lineWidth = 2 * px;
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.85)';
  for (const face of FACES) {
    const c = FACE_CORNERS[face].map((i) => pts[i]);
    covered[face].forEach((hidden, k) => {
      if (!hidden) return;
      const r = Math.floor(k / 3), col = k % 3;
      const at = (u, v) => lerp(lerp(c[0], c[1], u), lerp(c[3], c[2], u), v);  // bilinear on the side
      const q = [at(col / 3, r / 3), at((col + 1) / 3, r / 3), at((col + 1) / 3, (r + 1) / 3), at(col / 3, (r + 1) / 3)];
      ctx.beginPath();
      q.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.closePath();
      ctx.stroke();
    });
  }
  ctx.restore();
}

const HAND_BONES = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11], [11, 12],
                    [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [0, 17], [17, 18], [18, 19], [19, 20]];

function drawHands(ctx, hands, P, px, busy) {
  if (!hands || !hands.length) return;
  ctx.save();
  ctx.lineCap = 'round';
  ctx.shadowColor = busy ? 'rgba(255, 255, 255, 0.9)' : 'rgba(127, 232, 255, 0.8)';
  ctx.shadowBlur = 8 * px;
  for (const hand of hands) {
    const p = hand.points.map(P);
    ctx.strokeStyle = busy ? 'rgba(255, 255, 255, 0.9)' : 'rgba(127, 232, 255, 0.75)';
    ctx.lineWidth = 3 * px;
    for (const [a, b] of HAND_BONES) line(ctx, p[a], p[b]);
    ctx.fillStyle = '#fff';
    for (const i of [4, 8, 12, 16, 20]) { ctx.beginPath(); ctx.arc(p[i][0], p[i][1], 4.5 * px, 0, Math.PI * 2); ctx.fill(); }
  }
  ctx.restore();
}

// The floating 3D cube sits beside the real cube (right if there's room, else left), gliding as it moves.
let holoPos = null;
function placeHologram(pts, canvas) {
  const box = els['ar-holo'];
  if (box.hidden) return;
  const k = 1 / devicePixelRatio;
  const xs = pts.map((p) => p[0] * k), ys = pts.map((p) => p[1] * k);
  const left = Math.min(...xs), right = Math.max(...xs), top = Math.min(...ys), bottom = Math.max(...ys);
  const W = canvas.width * k, H = canvas.height * k;
  const gap = Math.max(16, (right - left) * 0.12);
  const roomRight = W - 10 - (right + gap), roomLeft = left - gap - 10;
  // As big as the real cube, but never covering it: shrink to the roomier side.
  const size = Math.max(150, Math.min(340, (bottom - top) * 1.1, Math.max(roomRight, roomLeft)));
  let x = roomRight >= roomLeft ? right + gap : left - gap - size;
  x = Math.max(10, Math.min(W - size - 10, x));
  const y = Math.max(70, Math.min(H - size - 130, (top + bottom) / 2 - size / 2));
  holoPos = holoPos ? holoPos.map((v, i) => v + ([x, y, size][i] - v) * 0.35) : [x, y, size];
  box.style.transform = `translate(${holoPos[0]}px, ${holoPos[1]}px)`;
  box.style.width = box.style.height = `${holoPos[2]}px`;
}

function lerp(a, b, f) { return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]; }
function line(ctx, a, b) { ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); }

function renderFaces(faces) {
  els['live-faces'].innerHTML = '';
  for (const face of FACES) {
    const wrap = document.createElement('div');
    wrap.className = 'live-face';
    const grid = document.createElement('div');
    grid.className = 'mini-grid';
    for (let k = 0; k < 9; k++) {
      const cell = document.createElement('div');
      const rgb = faces && faces[face] && faces[face][k];
      if (rgb) cell.style.background = `rgb(${rgb.map(Math.round).join(',')})`;
      else cell.className = 'empty';
      grid.appendChild(cell);
    }
    const label = document.createElement('span');
    label.textContent = `${FACE_LABELS[face]} (${face})`;
    label.style.color = FACE_COLORS[face];
    wrap.append(grid, label);
    els['live-faces'].appendChild(wrap);
  }
}
