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
                    'save-btn', 'save-count', 'live-faces', 'error-banner']) {
    els[id] = document.getElementById(id);
  }
  els['save-btn'].addEventListener('click', () => ws && ws.send(JSON.stringify({ type: 'save' })));
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
  if (!msg.keypoints) return;

  // The video is letterboxed (object-fit: contain): map frame pixels to canvas pixels.
  const scale = Math.min(canvas.width / msg.width, canvas.height / msg.height);
  const ox = (canvas.width - msg.width * scale) / 2;
  const oy = (canvas.height - msg.height * scale) / 2;
  const P = (p) => [ox + p[0] * scale, oy + p[1] * scale];
  const pts = msg.keypoints.map(P);
  const px = devicePixelRatio;
  ctx.globalAlpha = msg.confident ? 1 : 0.55;  // unsure guesses are drawn faded

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
