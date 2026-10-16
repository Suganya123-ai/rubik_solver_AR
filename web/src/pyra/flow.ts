// The Pyraminx tutor flow (same look as the cube app): start -> scan (two views, each with an edge
// toward the camera: two faces, then the other two) -> check colours -> solve -> live guided moves (wrong move: undo it,
// then the same plan carries on) -> solved (confetti + stats).

import type { AppState } from '../appState';
import type { Effects } from '../overlay/effects';
import type { Message, ServerLink } from '../serverLink';
import { type Geo, SWATCH, geometry } from './geometry';

type Scan = { phase: string; steady: number; needed: number; message: string | null; faces_done: number;
  instruction: string | null; event: string | null; refused?: string };
type ScanResult = { state: string; valid: boolean; doubtful: number[]; colour_of: Record<string, string>; colours: string[] };
export type Track = { phase: string; step: number; total: number; move: string | null; undo: string[]; state: string;
  hold: string[] | null; view: 'corner' | 'edge' | null; fix?: boolean; event: string | null; message: string | null;
  colour_of: Record<string, string> };
type Frame = { confident?: boolean; confidence?: number | null; keypoints?: [number, number][] | null;
  scan?: Scan; scan_result?: ScanResult; track?: Track };

const LETTERS = ['F', 'R', 'L', 'D'];

export class PyraFlow {
  guide: { move: string; undo: boolean } | null = null;
  /** The arrow's direction on screen in words ("to the right", "clockwise"), set by main.ts as it draws it. */
  arrowWord = '';
  arrowFor = '';   // the move that arrowWord was worked out for
  track: Track | null = null;
  keypoints: [number, number][] | null = null;
  private review: ScanResult | null = null;
  private locked: Record<string, string> = {};
  private holdUntil = 0;
  private stats = { start: 0, mistakes: 0, moves: 0 };
  private audio: AudioContext | null = null;
  private el: Record<string, HTMLElement> = {};

  constructor(private link: ServerLink, private state: AppState, private effects: Effects, root: HTMLElement) {
    root.innerHTML = `
      <div class="card" id="card">
        <div class="card-label" id="card-label"></div>
        <div class="card-main"><span id="card-title"></span></div>
        <div class="card-text" id="card-text"></div>
        <div class="steady" id="card-steady"><div></div></div>
        <div class="card-buttons" id="card-buttons"></div>
      </div>
      <div class="review" id="review" hidden>
        <div class="review-title" id="review-title"></div>
        <svg id="net" class="pyra-net" viewBox="0 0 440 210"></svg>
        <div class="card-buttons" id="review-buttons"></div>
      </div>
      <div class="popup" id="popup" hidden>
        <div class="popup-head"><span id="popup-title">⚠ Undo the step</span><button id="popup-close" aria-label="Close">✕</button></div>
        <div class="popup-body"><div class="popup-icon">↶</div><div><b id="popup-move"></b><div id="popup-text"></div></div></div>
      </div>
      <div class="progress" id="progress" hidden>
        <div class="bars"><div class="bar"><div id="bar-progress"></div></div><div class="bar"><div id="bar-cube"></div></div></div>
        <div class="bar-labels"><span>PLAN</span><span>PUZZLE</span></div>
        <div class="percent" id="percent"></div>
      </div>
      <div class="stats" id="stats" hidden></div>`;
    for (const id of ['card', 'card-label', 'card-title', 'card-text', 'card-steady', 'card-buttons', 'review', 'review-title',
      'net', 'review-buttons', 'popup', 'popup-title', 'popup-move', 'popup-text', 'popup-close', 'progress', 'bar-progress', 'bar-cube',
      'percent', 'stats']) {
      this.el[id] = root.querySelector('#' + id)!;
    }
    this.el['popup-close'].onclick = () => (this.el.popup.hidden = true);
    addEventListener('keydown', (e) => this.key(e));
    this.idle();
  }

  // ---------- server messages ----------
  onFrame(reply: Frame): void {
    this.keypoints = reply.keypoints ?? null;
    this.el['bar-cube'].style.height = `${Math.round((reply.confident ? reply.confidence ?? 0 : 0) * 100)}%`;
    if (reply.scan_result) { this.showReview(reply.scan_result, true); return; }
    if (reply.scan) this.showScan(reply.scan);
    if (reply.track) this.showTrack(reply.track);
  }

  onMessage(msg: Message): void {
    if (msg.type === 'scan_result') this.showReview(msg.scan_result as ScanResult, false);
    else if (msg.type === 'track') this.showTrack(msg.track as Track);
    else if (msg.type === 'scan' && (msg.scan as Scan).phase === 'off') this.idle();
    else if (msg.type === 'error' && this.state.phase === 'review') {
      this.el['review-title'].textContent = String(msg.message ?? 'Check the highlighted stickers.');
    }
  }

  // ---------- stages ----------
  private idle(): void {
    this.state.set('camera');
    this.guide = null; this.track = null;
    this.el.review.hidden = true; this.el.popup.hidden = true; this.el.progress.hidden = true;
    this.card('READY', 'Hold your pyramid up to the camera',
      'Tip up, with an edge pointing at the camera, so two faces show. Then start the scan: two views in all.',
      [['Start scan  (S)', () => this.startScan(), 'primary']]);
    this.steady(0);
  }

  private startScan(): void {
    this.ensureAudio();
    this.link.send({ type: 'scan_start' });
    this.review = null; this.locked = {};
    this.el.review.hidden = true; this.el.stats.hidden = true; this.el.popup.hidden = true;
    this.guide = null; this.track = null;
    this.state.set('scan');
    this.card('Scan · 0 of 4 faces', 'Hold still', '', [['Cancel  (Esc)', () => this.cancel(), '']]);
  }

  private cancel(): void {
    this.link.send({ type: this.state.phase === 'scan' ? 'scan_cancel' : 'track_stop' });
    this.idle();
  }

  private showScan(s: Scan): void {
    if (this.state.phase !== 'scan' || s.phase === 'done') return;
    this.steady(s.steady / s.needed);
    const cancel: [string, () => void, string][] = [['Cancel  (Esc)', () => this.cancel(), '']];
    const label = `Scan · ${s.faces_done} of 4 faces`;
    if (s.event === 'captured') {
      this.beep(1);
      this.effects.check(performance.now());
      this.card(`✓ ${s.faces_done} of 4 faces scanned`, 'Now turn it around',
        'Show the other two faces: tip up again, an edge toward the camera.', cancel, 'good');
      this.holdUntil = performance.now() + 3000;
      return;
    }
    if (performance.now() < this.holdUntil) return;
    if (s.message) {
      this.card(label, s.refused === 'nothing new' ? 'Those faces are already scanned'
        : s.refused === 'corner' ? 'Hold it edge-on' : 'Hold it still, edge-on',
        s.message, cancel, 'warn');
      this.holdUntil = performance.now() + 2500;
      return;
    }
    this.card(label, s.steady ? 'Hold still…' : (s.faces_done ? 'Turn it around: the other two faces' : 'Show two faces, tip up'),
      s.instruction ?? '', cancel);
  }

  private showReview(r: ScanResult, fresh: boolean): void {
    this.review = r;
    if (fresh) { this.beep(2); this.locked = {}; }
    this.state.set('review');
    this.el.card.hidden = true;
    this.el.review.hidden = false;
    const doubtful = r.doubtful.filter((i) => !(String(i) in this.locked));
    this.el['review-title'].textContent = !r.valid ? 'Those colours are not a possible Pyraminx: tap the highlighted stickers to fix them.'
      : doubtful.length ? `Check the ${doubtful.length} highlighted stickers: tap one to change its colour, or confirm they look right.`
        : 'Every sticker read clearly. Ready to solve.';
    this.drawNet(r, new Set(doubtful));
    const buttons: [string, () => void, string][] = [];
    if (r.valid) buttons.push([doubtful.length ? 'They look right  (Enter)' : 'Solve  (Enter)', () => this.solve(), 'primary']);
    buttons.push(['Scan again  (S)', () => this.startScan(), '']);
    this.buttons(this.el['review-buttons'], buttons);
  }

  /** The 4 faces as triangles side by side; each sticker can be tapped to cycle its colour. */
  private drawNet(r: ScanResult, doubtful: Set<number>): void {
    const g = geometry();
    const svg = this.el.net;
    if (!g) return;
    svg.innerHTML = '';
    const layout = layoutTriangles();
    const colourOf = r.colour_of;
    g.faces.forEach((face, fi) => {
      const ox = 10 + fi * 107, side = 100, h = side * Math.sqrt(3) / 2;
      const corners: [number, number][] = [[ox + side / 2, 20], [ox, 20 + h], [ox + side, 20 + h]];
      for (let k = 0; k < 9; k++) {
        const i = fi * 9 + k;
        const pts = layout[k].map((w) => [w[0] * corners[0][0] + w[1] * corners[1][0] + w[2] * corners[2][0],
          w[0] * corners[0][1] + w[1] * corners[1][1] + w[2] * corners[2][1]]);
        const c = pts.reduce((a, p) => [a[0] + p[0] / 3, a[1] + p[1] / 3], [0, 0]);
        const shrunk = pts.map((p) => [c[0] + (p[0] - c[0]) * 0.86, c[1] + (p[1] - c[1]) * 0.86]);
        const letter = this.locked[String(i)] ?? r.state[i];
        const poly = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
        poly.setAttribute('points', shrunk.map((p) => p.join(',')).join(' '));
        poly.setAttribute('fill', SWATCH[colourOf[letter] ?? g.colours[letter]] ?? '#888');
        poly.setAttribute('class', doubtful.has(i) ? 'doubtful' : '');
        poly.addEventListener('click', () => this.cycle(i));
        svg.appendChild(poly);
      }
      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      label.setAttribute('x', String(ox + side / 2)); label.setAttribute('y', String(20 + h + 22));
      label.setAttribute('text-anchor', 'middle'); label.setAttribute('class', 'net-label');
      label.textContent = `${colourOf[face] ?? ''} face`;
      svg.appendChild(label);
    });
  }

  private cycle(i: number): void {
    if (!this.review) return;
    const now = this.locked[String(i)] ?? this.review.state[i];
    this.locked[String(i)] = LETTERS[(LETTERS.indexOf(now) + 1) % 4];
    this.link.send({ type: 'scan_check', locked: this.locked });
  }

  private solve(): void {
    this.link.send({ type: 'scan_accept', locked: this.locked });
    this.stats = { start: performance.now(), mistakes: 0, moves: 0 };
  }

  private showTrack(t: Track): void {
    if (t.phase === 'off') { this.idle(); return; }
    this.track = t;
    this.el.review.hidden = true;
    this.el.progress.hidden = false;
    const done = t.total ? t.step / t.total : 1;
    this.el['bar-progress'].style.height = `${Math.round(done * 100)}%`;
    this.el.percent.textContent = `${Math.round(done * 100)}%`;
    if (t.event === 'correct') { this.stats.moves++; this.beep(1); this.effects.check(performance.now()); }
    if (t.event === 'wrong' || t.event === 'replan') { this.stats.mistakes++; this.beepLow(); }
    if (t.phase === 'solved') {
      this.state.set('solved');
      this.guide = null;
      this.el.popup.hidden = true;
      if (t.event === 'solved') { this.beep(3); this.effects.celebrate(performance.now(), innerWidth, innerHeight); this.showStats(); }
      this.card('SOLVED!', '🎉 Pyramid solved', 'Well done.', [['Scan another  (S)', () => this.startScan(), 'primary']], 'good');
      return;
    }
    const undo = t.phase === 'undo';
    this.state.set(undo ? 'undo' : 'guided');
    this.state.error = undo;
    this.guide = t.move ? { move: t.move, undo } : null;
    const words = t.move ? this.moveWords(t.move, t.hold, t.view) : { title: '', how: '' };
    const buttons: [string, () => void, string][] = [['I did it  (→)', () => this.link.send({ type: 'track_skip' }), ''],
      ['Stop  (Esc)', () => this.cancel(), '']];
    if (undo) {
      buttons.splice(1, 0, ['New plan instead  (N)', () => this.link.send({ type: 'track_replan' }), '']);
      this.el.popup.hidden = false;
      this.el['popup-title'].textContent = t.fix ? '⚠ Wrong way' : '⚠ Undo the step';
      this.el['popup-move'].textContent = words.title;
      this.el['popup-text'].textContent = (t.message ?? '') + ' Then the same plan carries on.';
      this.card(t.fix ? 'WRONG WAY: ONCE MORE THE SAME WAY' : 'UNDO THE STEP', words.title,
        t.fix ? 'You turned the right part the other way: keep going the way you turned it, one more third. The arrow shows it.'
          : words.how, buttons, 'bad');
    } else {
      this.el.popup.hidden = true;
      this.card(`MOVE ${t.step + 1} OF ${t.total}`, words.title, words.how + (t.event === 'correct' ? '  ✓ Correct.' : ''),
        buttons, t.event === 'correct' ? 'good' : '');
    }
  }

  /** "Turn the top corner to the right" / "Twist the tip of the left corner up": where the corner is in the
   *  picture, and which way the arrow goes on screen. */
  private lastWhere: Record<string, string> = {};

  private moveWords(move: string, hold: string[] | null, kind: 'corner' | 'edge' | null): { title: string; how: string } {
    const corner = move[0].toUpperCase(), tip = move[0] !== corner;
    // where that corner is in the (mirrored) picture; while the pyramid is out of view, the last place it was seen
    let where = this.lastWhere[move] ?? 'the marked corner';
    if (hold && this.keypoints) {
      const i = hold.indexOf(corner);
      if (i === 0 && kind !== 'edge') where = 'the corner pointing at the camera';
      else if (i >= 0) {
        const k = this.keypoints, cx = (k[0][0] + k[1][0] + k[2][0] + k[3][0]) / 4, cy = (k[0][1] + k[1][1] + k[2][1] + k[3][1]) / 4;
        const dx = -(k[i][0] - cx), dy = k[i][1] - cy;   // the picture is mirrored
        where = `the ${Math.abs(dy) > Math.abs(dx) ? (dy < 0 ? 'top' : 'bottom') : (dx < 0 ? 'left' : 'right')} corner`;
        if (kind === 'edge' && i === 1) where = 'the bottom corner (nearest you)';
      }
      this.lastWhere = { [move]: where };
    }
    const way = this.arrowWord && this.arrowFor === move ? ` ${this.arrowWord}` : '';
    const title = tip ? `Twist the tip of ${where}${way}` : `Turn ${where}${way}`;
    const how = `${tip ? 'Only the small tip (it lights up).' : 'The lit-up part: the tip and the layer under it, one third of a turn.'} Follow the arrow (x1), then hold the pyramid still.`;
    return { title, how };
  }

  private showStats(): void {
    const secs = Math.round((performance.now() - this.stats.start) / 1000);
    this.el.stats.hidden = false;
    this.el.stats.innerHTML = `<div class="stats-title">Solved</div>
      <div class="stats-row"><span>TIME</span><b>${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}</b></div>
      <div class="stats-row"><span>MOVES</span><b>${this.stats.moves}</b></div>
      <div class="stats-row"><span>MISTAKES</span><b>${this.stats.mistakes}</b></div>`;
  }

  // ---------- UI helpers (as in the cube app) ----------
  private card(label: string, title: string, text: string, buttons: [string, () => void, string][], tone = ''): void {
    this.el.card.hidden = false;
    this.el.card.className = 'card ' + tone;
    this.el['card-label'].textContent = label;
    this.el['card-title'].textContent = title;
    this.el['card-text'].textContent = text;
    this.buttons(this.el['card-buttons'], buttons);
  }

  private buttons(box: HTMLElement, list: [string, () => void, string][]): void {
    const key = list.map((b) => b[0]).join('|');
    if (box.dataset.key === key) return;
    box.dataset.key = key;
    box.innerHTML = '';
    for (const [label, action, cls] of list) {
      const b = document.createElement('button');
      b.textContent = label;
      b.className = cls;
      b.onclick = action;
      box.appendChild(b);
    }
  }

  private steady(f: number): void {
    (this.el['card-steady'].firstElementChild as HTMLElement).style.width = `${Math.round(Math.min(1, f) * 100)}%`;
  }

  private key(e: KeyboardEvent): void {
    const p = this.state.phase;
    if ((e.key === 's' || e.key === 'S') && (p === 'camera' || p === 'solved' || p === 'review')) this.startScan();
    else if (e.key === 'Escape' && (p === 'scan' || p === 'guided' || p === 'undo')) this.cancel();
    else if (e.key === 'Enter' && p === 'review' && this.review?.valid) this.solve();
    else if ((e.key === 'ArrowRight' || e.key === ' ') && (p === 'guided' || p === 'undo')) {
      e.preventDefault();
      this.link.send({ type: 'track_skip' });
    } else if ((e.key === 'n' || e.key === 'N') && p === 'undo') this.link.send({ type: 'track_replan' });
  }

  private ensureAudio(): void { try { this.audio = this.audio ?? new AudioContext(); } catch { this.audio = null; } }
  private tone(freq: number, at: number, length = 0.14): void {
    if (!this.audio) return;
    const t = this.audio.currentTime + at, osc = this.audio.createOscillator(), gain = this.audio.createGain();
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(0.2, t + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + length);
    osc.connect(gain).connect(this.audio.destination);
    osc.start(t); osc.stop(t + length + 0.02);
  }
  private beep(n: number): void { for (let i = 0; i < n; i++) this.tone(880 + 220 * i, i * 0.16); }
  private beepLow(): void { this.tone(300, 0, 0.25); this.tone(220, 0.22, 0.3); }
}

/** A face's 9 sticker triangles in barycentric weights over its 3 corners (as in pyra/view.py). */
function layoutTriangles(): number[][][] {
  const up = (i: number, j: number, k: number) => [[i + 1, j, k], [i, j + 1, k], [i, j, k + 1]];
  const down = (i: number, j: number, k: number) => [[i, j + 1, k + 1], [i + 1, j, k + 1], [i + 1, j + 1, k]];
  return [up(2, 0, 0), up(0, 2, 0), up(0, 0, 2), down(1, 0, 0), down(0, 1, 0), down(0, 0, 1), up(1, 1, 0), up(0, 1, 1),
    up(1, 0, 1)].map((t) => t.map((w) => w.map((x) => x / 3)));
}

export type { Geo };
