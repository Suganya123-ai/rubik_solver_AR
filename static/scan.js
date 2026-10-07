const FACE_ORDER = ['U', 'F', 'D', 'B', 'L', 'R'];
const FACE_INSTRUCTIONS = {
  U: "Hold the cube normally, then tilt it back so the TOP face points at the camera.",
  F: "Hold the cube normally and show the FRONT face (the one facing you) to the camera.",
  D: "Flip the cube upside down (keep the same face toward you) and show the BOTTOM face.",
  B: "Turn the cube around to show the BACK face to the camera.",
  L: "Turn the cube to show the LEFT face to the camera.",
  R: "Turn the cube to show the RIGHT face to the camera.",
};
const COLOR_NAMES = ['white', 'yellow', 'red', 'orange', 'green', 'blue'];

let faceIndex = 0;
let detectedColors = null;
let selectedStickerIndex = null;
let capturedDataUrl = null;

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
  });
  buildPalette();
  renderFaceProgress();
  updateInstructions();
  startCamera();
  els.captureBtn.addEventListener('click', onCapture);
  els.retakeBtn.addEventListener('click', onRetake);
  els.confirmBtn.addEventListener('click', onConfirmFace);
});

function showError(message) {
  els.errorBanner.textContent = message;
  els.errorBanner.classList.add('show');
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
  FACE_ORDER.forEach((f, i) => {
    const chip = document.createElement('span');
    chip.className = 'face-chip' + (i < faceIndex ? ' done' : i === faceIndex ? ' active' : '');
    chip.textContent = f;
    els.faceProgress.appendChild(chip);
  });
}

function updateInstructions() {
  const face = FACE_ORDER[faceIndex];
  els.scanInstructions.textContent = FACE_INSTRUCTIONS[face];
}

function currentFace() {
  return FACE_ORDER[faceIndex];
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
      body: JSON.stringify({ face: currentFace(), image: capturedDataUrl }),
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
}

function onRetake() {
  els.confirmPanel.style.display = 'none';
  els.cameraWrap.style.display = 'block';
  els.cameraWrap.parentElement.querySelector('.controls').style.display = 'flex';
  detectedColors = null;
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
      body: JSON.stringify({ face: currentFace(), colors: detectedColors }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'confirm failed');
  } catch (e) {
    showError('Could not confirm face: ' + e.message);
    return;
  }

  faceIndex += 1;
  els.confirmPanel.style.display = 'none';
  els.cameraWrap.style.display = 'block';
  els.cameraWrap.parentElement.querySelector('.controls').style.display = 'flex';
  detectedColors = null;

  if (faceIndex >= FACE_ORDER.length) {
    await finalizeScan();
  } else {
    renderFaceProgress();
    updateInstructions();
  }
}

async function finalizeScan() {
  try {
    const res = await fetch('/api/build-and-solve', { method: 'POST' });
    if (!res.ok) {
      const body = await res.json();
      const msg = (body.detail && body.detail.message) || body.detail || 'validation failed';
      throw new Error(msg);
    }
    const data = await res.json();
    document.getElementById('scan-screen').classList.remove('active');
    document.getElementById('solve-screen').classList.add('active');
    window.initGuide(data);
  } catch (e) {
    showError('Scan looks invalid: ' + e.message + '. Re-scan the faces you\'re least sure about, starting over.');
    faceIndex = 0;
    renderFaceProgress();
    updateInstructions();
    fetch('/api/reset', { method: 'POST' });
  }
}
