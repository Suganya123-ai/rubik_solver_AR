// "Scan & solve" panel: two automatic captures, a check of any doubtful
// stickers on a flat cube net, then the move-by-move guide.

const NET_LAYOUT = { U: [1, 0], L: [0, 1], F: [1, 1], R: [2, 1], B: [3, 1], D: [1, 2] }; // [col, row]
const PALETTE = ['white', 'yellow', 'red', 'orange', 'green', 'blue'];
const scanEls = {};
let review = null;      // latest scan result from the server
let locked = {};        // "F0" -> colour, stickers the user confirmed or changed
let selected = null;    // sticker picked for changing

document.addEventListener('DOMContentLoaded', () => {
  for (const id of ['scan-idle', 'scan-running', 'scan-review', 'scan-guide', 'scan-start-btn', 'scan-cancel-btn',
                    'scan-instruction', 'steady-fill', 'scan-message', 'step-v1', 'step-v2', 'review-text', 'cube-net',
                    'net-palette', 'review-confirm-btn', 'solve-btn', 'rescan-btn', 'guide-count', 'guide-move',
                    'guide-desc', 'guide-rescan-btn', 'track-banner', 'track-steady', 'track-skip-btn']) {
    scanEls[id] = document.getElementById(id);
  }
  scanEls['scan-start-btn'].onclick = startScan;
  scanEls['rescan-btn'].onclick = startScan;
  scanEls['guide-rescan-btn'].onclick = startScan;
  scanEls['scan-cancel-btn'].onclick = () => { window.sendLiveCommand({ type: 'scan_cancel' }); show('scan-idle'); };
  scanEls['review-confirm-btn'].onclick = confirmHighlighted;
  scanEls['solve-btn'].onclick = solve;
  scanEls['track-skip-btn'].onclick = () => window.sendLiveCommand({ type: 'track_skip' });
  for (const color of PALETTE) {
    const b = document.createElement('button');
    b.className = 'color-' + color;
    b.title = color;
    b.onclick = () => changeSelected(color);
    scanEls['net-palette'].appendChild(b);
  }
});

function show(section) {
  for (const s of ['scan-idle', 'scan-running', 'scan-review', 'scan-guide']) scanEls[s].hidden = s !== section;
}

function startScan() {
  review = null; locked = {}; selected = null;
  window.sendLiveCommand({ type: 'scan_start' });
  show('scan-running');
}

window.onScanMessage = (msg) => {
  window.scanAwaitingReply = false;
  if (msg.type === 'error') { scanEls['review-text'].textContent = msg.message || 'Could not solve this cube.'; return; }
  if (msg.track) { renderTrack(msg.track); return; }
  if (msg.scan_result) { showReview(msg.scan_result); return; }
  const st = msg.scan;
  if (!st || st.phase === 'off' || st.phase === 'done') return;
  show('scan-running');
  scanEls['scan-instruction'].textContent = st.instruction || '';
  scanEls['steady-fill'].style.width = `${100 * st.steady / st.needed}%`;
  if (st.message) scanEls['scan-message'].textContent = st.message;
  else if (msg.type === 'frame') {
    scanEls['scan-message'].textContent = msg.keypoints && msg.confident
      ? (st.steady ? 'Hold still…' : 'Cube found — hold it still') : 'Hold the cube corner-on to the camera';
  }
  scanEls['step-v1'].className = st.captured.includes(1) ? 'done' : (st.phase === 'view1' ? 'active' : '');
  scanEls['step-v2'].className = st.captured.includes(2) ? 'done' : (st.phase === 'view2' ? 'active' : '');
};

function showReview(result) {
  review = result;
  show('scan-review');
  const n = result.doubtful.length;
  scanEls['review-text'].textContent = !result.valid
    ? "This doesn't read as a real cube. Tap any wrong sticker to fix it, or scan again."
    : n ? `Please check the ${n} highlighted sticker${n > 1 ? 's' : ''}. Tap one to change its colour; if they all look right, confirm.`
      : 'Scan complete. Every sticker read clearly.';
  scanEls['review-confirm-btn'].hidden = !(n && result.valid);
  scanEls['solve-btn'].hidden = !(result.valid && !n);
  renderNet();
}

function renderNet() {
  const net = scanEls['cube-net'];
  net.innerHTML = '';
  for (const [face, [col, row]] of Object.entries(NET_LAYOUT)) {
    const box = document.createElement('div');
    box.className = 'net-face';
    box.style.gridColumn = col + 1;
    box.style.gridRow = row + 1;
    review.colors[face].forEach((color, k) => {
      const cell = document.createElement('span');
      const name = face + k;
      cell.className = `color-${color}` + (review.doubtful.includes(name) ? ' doubtful' : '') + (selected === name ? ' selected' : '');
      cell.title = `${face}${k}: ${color}`;
      cell.onclick = () => { selected = name; scanEls['net-palette'].hidden = false; renderNet(); };
      box.appendChild(cell);
    });
    net.appendChild(box);
  }
}

function recheck() {
  window.sendLiveCommand({ type: 'scan_check', locked });  // reply: {type: 'scan_result'}
}

function changeSelected(color) {
  if (!selected) return;
  locked[selected] = color;
  selected = null;
  scanEls['net-palette'].hidden = true;
  recheck();
}

function confirmHighlighted() {
  for (const name of review.doubtful) locked[name] = review.colors[name[0]][Number(name[1])];
  recheck();
}

function solve() {
  // The server checks the colours, solves, and starts checking every move (reply: {type: 'track'}).
  window.scanAwaitingReply = true;
  window.sendLiveCommand({ type: 'scan_accept', colors: review.colors });
}

let bannerUntil = 0;
function banner(text, cls, seconds) {
  scanEls['track-banner'].textContent = text;
  scanEls['track-banner'].className = 'track-banner ' + cls;
  bannerUntil = seconds ? performance.now() + seconds * 1000 : 0;
}

let hologram = null;

function renderTrack(t) {
  show('scan-guide');
  if (t.state && window.CubeHologram) {
    hologram = hologram || new window.CubeHologram(document.getElementById('hologram'));
    hologram.show(t.state, t.face_colors, t.phase === 'solved' ? null : t.move);
  }
  scanEls['track-steady'].style.width = `${100 * (t.steady || 0) / (t.needed || 1)}%`;
  if (t.phase === 'solved') {
    scanEls['guide-count'].textContent = '';
    scanEls['guide-move'].textContent = '🎉';
    scanEls['guide-desc'].textContent = 'Cube solved!';
    banner(t.message || 'Solved!', 'correct');
    scanEls['track-skip-btn'].hidden = true;
    return;
  }
  scanEls['track-skip-btn'].hidden = false;
  scanEls['guide-count'].textContent = `Move ${t.step} of ${t.total}`;
  scanEls['guide-move'].textContent = t.move || '';
  scanEls['guide-desc'].textContent = t.description || '';
  if (t.event === 'wrong') banner(t.message, 'wrong', 6);
  else if (t.event === 'correct') banner('✓ Correct', 'correct', 1.5);
  else if (t.event === 'lost') banner(t.message, 'lost', 6);
  else if (t.phase === 'home') banner(t.message || 'Turn the cube back to the first position: Top, Front and Right toward the camera.', 'home');
  else if (t.event === 'home') banner(t.message, 'correct', 3);
  else if (bannerUntil && performance.now() > bannerUntil) banner('', '');
}
