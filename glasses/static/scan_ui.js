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
                    'guide-desc', 'guide-rescan-btn', 'track-banner', 'track-steady', 'track-skip-btn',
                    'track-replan-btn']) {
    scanEls[id] = document.getElementById(id);
  }
  scanEls['scan-start-btn'].onclick = startScan;
  scanEls['rescan-btn'].onclick = startScan;
  scanEls['guide-rescan-btn'].onclick = startScan;
  scanEls['scan-cancel-btn'].onclick = () => { window.sendLiveCommand({ type: 'scan_cancel' }); show('scan-idle'); };
  scanEls['review-confirm-btn'].onclick = confirmHighlighted;
  scanEls['solve-btn'].onclick = solve;
  scanEls['track-skip-btn'].onclick = () => window.sendLiveCommand({ type: 'track_skip' });
  scanEls['track-replan-btn'].onclick = () => window.sendLiveCommand({ type: 'track_replan' });
  // The same controls in the glasses view's heads-up display.
  document.getElementById('ar-start-btn').onclick = startScan;
  document.getElementById('ar-skip-btn').onclick = () => window.sendLiveCommand({ type: 'track_skip' });
  document.getElementById('ar-replan-btn').onclick = () => window.sendLiveCommand({ type: 'track_replan' });
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
  // Heads-up display: what applies in this stage.
  window.cubeTaskActive = section === 'scan-running' || section === 'scan-guide';
  document.getElementById('ar-start-btn').hidden = section !== 'scan-idle' && section !== 'scan-review';
  document.getElementById('ar-progress').hidden = section !== 'scan-guide';
  document.getElementById('ar-holo').hidden = section !== 'scan-guide';
  if (section !== 'scan-guide') {
    document.getElementById('ar-skip-btn').hidden = true;
    document.getElementById('ar-replan-btn').hidden = true;
  }
}

function startScan() {
  review = null; locked = {}; selected = null;
  ensureAudio();
  setVideoGuide(null);
  window.sendLiveCommand({ type: 'scan_start' });
  show('scan-running');
}

// ---------- "side captured" feedback: a beep, a green flash and a message that stays up ----------
let audio = null, scanMessageHold = 0;

function ensureAudio() {  // browsers only allow sound after a click, so this is set up on "Start scan"
  try { audio = audio || new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { audio = null; }
}

function beep(times) {
  if (!audio) return;
  for (let i = 0; i < times; i++) {
    const t = audio.currentTime + i * 0.18, osc = audio.createOscillator(), gain = audio.createGain();
    osc.frequency.value = 880 + i * 220;
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(0.25, t + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.15);
    osc.connect(gain).connect(audio.destination);
    osc.start(t); osc.stop(t + 0.16);
  }
}

function sideCaptured(side, nextText) {
  beep(side);
  const stage = document.getElementById('live-stage');
  stage.classList.remove('flash-good'); void stage.offsetWidth; stage.classList.add('flash-good');
  setVideoGuide({ label: `✓ Side ${side} of 2 captured`, move: '✓', text: nextText, cls: 'good' }, 3);
  scanEls['scan-message'].textContent = `✓ Side ${side} captured! ${nextText}`;
  scanEls['scan-message'].classList.add('scan-success');
  scanMessageHold = performance.now() + 3000;
}

window.onScanMessage = (msg) => {
  window.scanAwaitingReply = false;
  if (msg.type === 'error') { scanEls['review-text'].textContent = msg.message || 'Could not solve this cube.'; return; }
  if (msg.track) { renderTrack(msg.track); return; }
  if (msg.scan_result) {
    if (msg.type === 'frame') sideCaptured(2, 'Both sides read. Check the colours.');
    showReview(msg.scan_result);
    return;
  }
  const st = msg.scan;
  if (!st || st.phase === 'off' || st.phase === 'done') return;
  show('scan-running');
  scanEls['scan-instruction'].textContent = st.instruction || '';
  scanEls['steady-fill'].style.width = `${100 * st.steady / st.needed}%`;
  scanEls['step-v1'].className = st.captured.includes(1) ? 'done' : (st.phase === 'view1' ? 'active' : '');
  scanEls['step-v2'].className = st.captured.includes(2) ? 'done' : (st.phase === 'view2' ? 'active' : '');
  if (st.event === 'captured') { sideCaptured(1, 'Now flip the cube: ' + (st.instruction || '')); return; }
  if (performance.now() < scanMessageHold) return;  // keep "captured" (or a warning) up for a moment
  scanEls['scan-message'].classList.remove('scan-success');
  if (st.message) {  // e.g. "That looks like the first view again": show it long enough to read
    setVideoGuide({ label: `Scan ${st.phase === 'view2' ? 2 : 1} of 2`, move: '!', text: st.message, cls: 'undo' }, 2.5);
    scanEls['scan-message'].textContent = st.message;
    scanMessageHold = performance.now() + 2500;
    return;
  }
  setVideoGuide({ label: `Scan ${st.phase === 'view2' ? 2 : 1} of 2`, move: '',
                  text: (st.message || st.instruction || '') + (st.steady ? ` (hold still ${'●'.repeat(st.steady)}${'○'.repeat(Math.max(0, st.needed - st.steady))})` : '') });
  if (st.message) scanEls['scan-message'].textContent = st.message;
  else if (msg.type === 'frame') {
    scanEls['scan-message'].textContent = msg.keypoints && msg.confident
      ? (st.steady ? 'Hold still…' : 'Cube found — hold it still') : 'Hold the cube corner-on to the camera';
  }
};

let backToGlasses = false;

function showReview(result) {
  review = result;
  show('scan-review');
  setVideoGuide(null);
  if (window.glassesView) {  // checking the colours needs the cube net beside the video
    backToGlasses = true;
    window.setGlassesView(false);
  }
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
  if (backToGlasses) { backToGlasses = false; window.setGlassesView(true); }
  const undo = document.getElementById('undo-mistakes');
  window.sendLiveCommand({ type: 'scan_accept', colors: review.colors, on_mistake: undo && !undo.checked ? 'replan' : 'undo' });
}

let bannerUntil = 0;
function banner(text, cls, seconds) {
  scanEls['track-banner'].textContent = text;
  scanEls['track-banner'].className = 'track-banner ' + cls;
  bannerUntil = seconds ? performance.now() + seconds * 1000 : 0;
}

let hologram = null, arHologram = null;

function renderTrack(t) {
  if (t.phase === 'off') { setVideoGuide(null); show('scan-idle'); return; }
  show('scan-guide');
  const undoing = t.phase === 'undo';
  // What the camera picture draws on the cube (live.js): only once the cube is in the first position.
  window.liveGuide = (t.phase === 'tracking' || undoing) ? { move: t.move, undo: undoing } : null;
  if (t.state && window.CubeHologram) {
    hologram = hologram || new window.CubeHologram(document.getElementById('hologram'));
    arHologram = arHologram || new window.CubeHologram(document.getElementById('ar-holo-canvas'));
    for (const h of [hologram, arHologram]) h.show(t.state, t.face_colors, t.phase === 'solved' ? null : t.move, { undo: undoing });
  }
  document.getElementById('ar-step').textContent = t.phase === 'solved' ? 'Solved!'
    : undoing ? `Undo the mistake · then move ${t.step} of ${t.total}` : t.phase === 'home' ? 'Get ready' : `Move ${t.step} of ${t.total}`;
  document.getElementById('ar-bar-fill').style.width = `${100 * (t.phase === 'solved' ? 1 : (t.step - 1) / Math.max(1, t.total))}%`;
  document.getElementById('ar-skip-btn').hidden = t.phase === 'solved';
  document.getElementById('ar-replan-btn').hidden = !undoing;
  scanEls['track-steady'].style.width = `${100 * (t.steady || 0) / (t.needed || 1)}%`;
  scanEls['track-replan-btn'].hidden = !undoing;
  if (t.phase === 'solved') {
    scanEls['guide-count'].textContent = '';
    scanEls['guide-move'].textContent = '🎉';
    scanEls['guide-move'].classList.remove('undo');
    scanEls['guide-desc'].textContent = 'Cube solved!';
    banner(t.message || 'Solved!', 'correct');
    scanEls['track-skip-btn'].hidden = true;
    setVideoGuide({ label: 'Solved!', move: '🎉', text: t.message || 'Well done.', cls: 'good' });
    return;
  }
  scanEls['track-skip-btn'].hidden = false;
  scanEls['guide-move'].textContent = t.move || '';
  scanEls['guide-move'].classList.toggle('undo', undoing);
  const then = t.plan_move ? ` Then carry on with ${t.plan_move}.` : '';
  if (undoing) {
    const n = (t.undo || []).length;
    scanEls['guide-count'].textContent = n > 1 ? `Undo the mistake: ${n} moves left` : 'Undo the mistake';
    scanEls['guide-desc'].textContent = (t.description || '') + (n > 1 ? '' : then);
  } else {
    scanEls['guide-count'].textContent = `Move ${t.step} of ${t.total}`;
    scanEls['guide-desc'].textContent = t.description || '';
  }
  if (t.event === 'wrong') banner(t.message, 'wrong', 8);
  else if (t.event === 'correct') banner(t.message || '✓ Correct', 'correct', 2);
  else if (t.event === 'undone') banner(t.message, 'correct', 4);
  else if (t.event === 'replanned') banner(t.message, 'correct', 4);
  else if (t.event === 'lost') banner(t.message, 'lost', 6);
  else if (t.phase === 'home') banner(t.message || 'Turn the cube back to the first position: Top, Front and Right toward the camera.', 'home');
  else if (t.event === 'home') banner(t.message, 'correct', 3);
  else if (bannerUntil && performance.now() > bannerUntil) banner('', '');

  // The same instruction over the camera picture.
  if (t.phase === 'home') {
    setVideoGuide({ label: 'Get ready', move: '', text: t.message || 'Hold the cube in the first position.' });
  } else if (t.event === 'wrong') {
    setVideoGuide({ label: undoing ? 'Not that one -- undo it' : 'New plan', move: t.move || '', text: t.message, cls: undoing ? 'undo' : '' }, 6);
  } else if (t.event === 'correct' || t.event === 'undone') {
    setVideoGuide({ label: t.event === 'undone' ? '✓ Undone -- back on track' : '✓ Correct', move: t.move || '',
                    text: t.description || '', cls: 'good' }, 1.5);
  } else if (performance.now() > videoGuideHold) {
    setVideoGuide(undoing
      ? { label: 'Undo the mistake', move: t.move || '', text: (t.description || '') + ((t.undo || []).length > 1 ? '' : then), cls: 'undo' }
      : { label: `Move ${t.step} of ${t.total}`, move: t.move || '', text: t.description || '' });
  }
}

let videoGuideHold = 0;  // keep an event message up for a moment before the next status replaces it

function setVideoGuide(g, holdSeconds) {
  const box = document.getElementById('video-guide');
  if (!box) return;
  if (!g) { box.hidden = true; window.liveGuide = null; return; }
  box.hidden = false;
  box.className = 'video-guide ' + (g.cls || '');
  document.getElementById('video-guide-label').textContent = g.label;
  document.getElementById('video-guide-move').textContent = g.move;
  document.getElementById('video-guide-text').textContent = g.text;
  videoGuideHold = holdSeconds ? performance.now() + holdSeconds * 1000 : 0;
}
