const FACE_ORDER = ['U', 'F', 'D', 'B', 'L', 'R'];
const FACE_INSTRUCTIONS = {
  U: "Hold the cube normally, then tilt it back so the TOP face points at the camera.",
  F: "Hold the cube normally and show the FRONT face (the one facing you) to the camera.",
  D: "Flip the cube upside down (keep the same face toward you) and show the BOTTOM face.",
  B: "Turn the cube around to show the BACK face to the camera.",
  L: "Turn the cube to show the LEFT face to the camera.",
  R: "Turn the cube to show the RIGHT face to the camera.",
};
const FACE_LABELS = { U: 'Top', F: 'Front', D: 'Bottom', B: 'Back', L: 'Left', R: 'Right' };
const COLOR_NAMES = ['white', 'yellow', 'red', 'orange', 'green', 'blue'];

let activeFace = 'U';  // side being scanned, or null once all 6 are captured
let detectedColors = null;
let selectedStickerIndex = null;
let capturedDataUrl = null;
const capturedFaces = {};  // face letter -> 9 confirmed color names

const els = {};
document.addEventListener('DOMContentLoaded', () => {
  Object.assign(els, {
    faceProgress: document.getElementById('face-progress'),
    scanInstructions: document.getElementById('scan-instructions'),
    video: document.getElementById('video'),
    cameraWrap: document.getElementById('camera-wrap'),
    captureCanvas: document.getElementById('capture-canvas'),
    captureBtn: document.getElementById('capture-btn'),
    confirmPanel: document.getElementById('confirm-panel'),
    capturedPhoto: document.getElementById('captured-photo'),
    gridPreview: document.getElementById('grid-preview'),
    palette: document.getElementById('palette'),
    retakeBtn: document.getElementById('retake-btn'),
    confirmBtn: document.getElementById('confirm-btn'),
    errorBanner: document.getElementById('error-banner'),
    duplicateWarning: document.getElementById('duplicate-warning'),
    capturedFaces: document.getElementById('captured-faces'),
    capturedCount: document.getElementById('captured-count'),
    capturedHint: document.getElementById('captured-hint'),
    solveBtn: document.getElementById('solve-btn'),
    startOverBtn: document.getElementById('start-over-btn'),
  });
  buildPalette();
  startCamera();
  els.captureBtn.addEventListener('click', onCapture);
  els.retakeBtn.addEventListener('click', onRetake);
  els.confirmBtn.addEventListener('click', onConfirmFace);
  els.solveBtn.addEventListener('click', finalizeScan);
  els.startOverBtn.addEventListener('click', startOver);
  restoreCapturedFaces();
});

// The server keeps the confirmed sides, so a reload picks up where you left off.
async function restoreCapturedFaces() {
  try {
    const res = await fetch('/api/state');
    if (res.ok) Object.assign(capturedFaces, (await res.json()).confirmed);
  } catch (e) {
    // Nothing to restore -- start fresh.
  }
  activeFace = nextUncapturedFace();
  render();
}

function nextUncapturedFace() {
  return FACE_ORDER.find((f) => !capturedFaces[f]) || null;
}

function render() {
  renderFaceProgress();
  renderCapturedFaces();
  updateInstructions();
}

function showError(message, extra) {
  els.errorBanner.textContent = message;
  if (extra) els.errorBanner.appendChild(extra);
  els.errorBanner.classList.add('show');
}

// One chip per color showing how many stickers of it were captured, with
// the ones that aren't exactly 9 flagged so it's clear which to look for.
function buildColorCounts() {
  const counts = Object.fromEntries(COLOR_NAMES.map((c) => [c, 0]));
  FACE_ORDER.forEach((f) => (capturedFaces[f] || []).forEach((c) => { counts[c] += 1; }));
  const wrap = document.createElement('div');
  wrap.className = 'color-counts';
  COLOR_NAMES.forEach((color) => {
    const diff = counts[color] - 9;
    const chip = document.createElement('div');
    chip.className = 'color-count' + (diff ? ' off' : '');
    const swatch = document.createElement('span');
    swatch.className = 'swatch color-' + color;
    const text = document.createElement('span');
    text.textContent = color + ': ' + counts[color] +
      (diff > 0 ? ' (' + diff + ' too many)' : diff < 0 ? ' (' + -diff + ' missing)' : ' \u2713');
    chip.append(swatch, text);
    wrap.appendChild(chip);
  });
  return wrap;
}

function clearError() {
  els.errorBanner.classList.remove('show');
}

async function startCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
    els.video.srcObject = stream;
  } catch (e) {
    showError("Couldn't access the camera: " + e.message + ". Check browser permissions.");
  }
}

function renderFaceProgress() {
  els.faceProgress.innerHTML = '';
  FACE_ORDER.forEach((f) => {
    const chip = document.createElement('span');
    chip.className = 'face-chip' + (f === activeFace ? ' active' : capturedFaces[f] ? ' done' : '');
    chip.textContent = f;
    els.faceProgress.appendChild(chip);
  });
}

function renderCapturedFaces() {
  els.capturedFaces.innerHTML = '';
  FACE_ORDER.forEach((f) => {
    const colors = capturedFaces[f];
    const tile = document.createElement('button');
    tile.type = 'button';
    tile.className = 'captured-face' + (colors ? ' done' : '') + (f === activeFace ? ' active' : '');
    tile.title = (colors ? 'Redo the ' : 'Scan the ') + FACE_LABELS[f] + ' side';
    tile.addEventListener('click', () => selectFace(f));
    const grid = document.createElement('div');
    grid.className = 'mini-grid';
    (colors || Array(9).fill(null)).forEach((color) => {
      const cell = document.createElement('div');
      if (color) cell.className = 'color-' + color;
      grid.appendChild(cell);
    });
    const label = document.createElement('span');
    label.textContent = FACE_LABELS[f] + ' (' + f + ')';
    tile.append(grid, label);
    els.capturedFaces.appendChild(tile);
  });
  const count = Object.keys(capturedFaces).length;
  els.capturedCount.textContent = count + ' / ' + FACE_ORDER.length;
  els.capturedHint.textContent = count ? '· tap a side to redo it' : '';
  els.solveBtn.style.display = count === FACE_ORDER.length ? '' : 'none';
  els.startOverBtn.style.display = count ? '' : 'none';
}

function selectFace(face) {
  activeFace = face;
  clearError();
  showCamera();
  render();
}

async function startOver() {
  await fetch('/api/reset', { method: 'POST' });
  FACE_ORDER.forEach((f) => delete capturedFaces[f]);
  clearError();
  showCamera();
  activeFace = nextUncapturedFace();
  render();
}

// Every side has a unique center color, so a center already seen on another
// captured side means the same side was shown twice.
function duplicateOf(face, colors) {
  return FACE_ORDER.find((f) => f !== face && capturedFaces[f] && capturedFaces[f][4] === colors[4]) || null;
}

function updateDuplicateWarning() {
  const face = activeFace;
  const dup = duplicateOf(face, detectedColors);
  if (dup) {
    els.duplicateWarning.textContent =
      'This looks like the ' + FACE_LABELS[dup] + ' (' + dup + ') side you already captured -- both have a ' +
      detectedColors[4] + ' center. Retake and show the ' + FACE_LABELS[face] + ' (' + face + ') side. ' +
      "If the center isn't actually " + detectedColors[4] + ', tap it and correct it.';
    els.duplicateWarning.classList.add('show');
  } else {
    els.duplicateWarning.classList.remove('show');
  }
  els.confirmBtn.disabled = !!dup;
}

function updateInstructions() {
  const face = activeFace;
  els.cameraWrap.style.display = face ? 'block' : 'none';
  els.captureBtn.style.display = face ? '' : 'none';
  if (!face) {
    els.scanInstructions.textContent = 'All 6 sides captured. Tap Solve below, or tap a side to redo it.';
  } else if (capturedFaces[face]) {
    els.scanInstructions.textContent = 'Redoing the ' + FACE_LABELS[face] + ' side. ' + FACE_INSTRUCTIONS[face];
  } else {
    els.scanInstructions.textContent = FACE_INSTRUCTIONS[face];
  }
}

function captureCroppedSquare() {
  const video = els.video;
  const vw = video.videoWidth, vh = video.videoHeight;
  const side = Math.min(vw, vh);
  const sx = (vw - side) / 2, sy = (vh - side) / 2;
  const inset = side * 0.08;
  const gridSide = side - inset * 2;
  const canvas = els.captureCanvas;
  canvas.width = gridSide;
  canvas.height = gridSide;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, sx + inset, sy + inset, gridSide, gridSide, 0, 0, gridSide, gridSide);
  return canvas.toDataURL('image/jpeg', 0.92);
}

async function onCapture() {
  clearError();
  capturedDataUrl = captureCroppedSquare();
  try {
    const res = await fetch('/api/scan-face', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ face: activeFace, image: capturedDataUrl }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'scan failed');
    const data = await res.json();
    detectedColors = data.colors;
    showConfirmPanel();
  } catch (e) {
    showError('Could not detect colors: ' + e.message);
  }
}

function showConfirmPanel() {
  els.cameraWrap.parentElement.querySelector('.controls').style.display = 'none';
  els.cameraWrap.style.display = 'none';
  els.confirmPanel.style.display = 'block';
  els.capturedPhoto.src = capturedDataUrl;
  selectedStickerIndex = null;
  renderGridPreview();
  updateDuplicateWarning();
}

function showCamera() {
  els.confirmPanel.style.display = 'none';
  els.cameraWrap.style.display = 'block';
  els.cameraWrap.parentElement.querySelector('.controls').style.display = 'flex';
  detectedColors = null;
}

function onRetake() {
  showCamera();
}

function renderGridPreview() {
  els.gridPreview.innerHTML = '';
  detectedColors.forEach((color, i) => {
    const div = document.createElement('div');
    div.className = 'sticker color-' + color + (i === selectedStickerIndex ? ' selected' : '');
    div.addEventListener('click', () => {
      selectedStickerIndex = i;
      renderGridPreview();
    });
    els.gridPreview.appendChild(div);
  });
}

function buildPalette() {
  els.palette.innerHTML = '';
  COLOR_NAMES.forEach((color) => {
    const btn = document.createElement('button');
    btn.className = 'color-' + color;
    btn.title = color;
    btn.addEventListener('click', () => {
      if (selectedStickerIndex === null) return;
      detectedColors[selectedStickerIndex] = color;
      renderGridPreview();
      updateDuplicateWarning();
    });
    els.palette.appendChild(btn);
  });
}

async function onConfirmFace() {
  clearError();
  try {
    const res = await fetch('/api/confirm-face', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ face: activeFace, colors: detectedColors }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'confirm failed');
  } catch (e) {
    showError('Could not confirm face: ' + e.message);
    return;
  }

  capturedFaces[activeFace] = detectedColors.slice();
  showCamera();
  activeFace = nextUncapturedFace();
  render();
  if (!activeFace) await finalizeScan();
}

async function finalizeScan() {
  try {
    const res = await fetch('/api/build-and-solve', { method: 'POST' });
    if (!res.ok) {
      const body = await res.json();
      if (body.detail && body.detail.error_code === 'ERROR_COLOR_COUNT') {
        showError('Scan looks invalid: each color should appear exactly 9 times, but it counted:',
                  buildColorCounts());
        els.errorBanner.append('Tap the side(s) below with the wrong colors to redo them.');
        return;
      }
      const msg = (body.detail && body.detail.message) || body.detail || 'validation failed';
      throw new Error(msg);
    }
    const data = await res.json();
    document.getElementById('scan-screen').classList.remove('active');
    document.getElementById('solve-screen').classList.add('active');
    window.initGuide(data);
  } catch (e) {
    // Keep the captured sides so only the doubtful ones need redoing.
    showError('Scan looks invalid: ' + e.message + ' Tap the side(s) below that look off to redo them.');
  }
}
