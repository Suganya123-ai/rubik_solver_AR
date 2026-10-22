// The whole tutor flow on top of the vision server (protocol: ../docs/PROTOCOL.md):
// start -> scan (2 views) -> check colours -> solve -> live guided moves
// (correct: next move; wrong: "Undo the step", then the same plan carries on)
// -> solved (confetti + stats).
//
// Instructions name sides by their centre colour ("turn the green side"):
// the webcam faces you, so the camera's "Front" is the side facing away from
// you -- colours mean the same thing from every side.

import type { AppState } from './appState';
import type { Effects } from './overlay/effects';
import { POSITION, describe } from './moveText';
import { type Command, Voice } from './voice';
import type { FrameReply, Message, ServerLink } from './serverLink';

type ScanStatus = { phase: string; instruction: string | null; steady: number; needed: number;
  scanned_centres?: [number, number, number][]; sides_done?: number; refused?: string;
  message: string | null; captured: number[]; event: string | null };
type ScanResult = { colors: Record<string, string[]>; doubtful: string[]; valid: boolean; centers: Record<string, string> };
export type Track = { phase: string; step: number; total: number; move: string | null; undo: string[];
  plan_move: string | null; event: string | null; message: string | null; state: string;
  face_colors: Record<string, string>; steady: number; needed: number;
  /** The right side turned by the wrong amount: [what was done, what was asked]; the move shown is the one-turn fix. */
  fix?: [string, string] | null;
  /** The cube held any way round: the sides the camera sees (of U, F, R, named from the camera), whether
   *  it shows too little to tell which way round it is, and whether the move's side can't be seen. */
  sides?: string; hold_unsure?: boolean; move_hidden?: boolean };

const ANY_HOLD = 'Any way round: a corner, an edge or one side toward the camera. Two or three sides showing works best.';

/** A line to add when the camera can't follow the move from how the cube is held. */
function holdTip(t: Track): string {
  if (t.move_hidden) return ' The camera can\'t see that side from here: tilt the cube so it sees the top as well.';
  if (t.hold_unsure) return ' Tilt the cube a little so the camera sees two sides.';
  return '';
}

const FACES = ['U', 'R', 'F', 'D', 'L', 'B'];
const NET: Record<string, [number, number]> = { U: [1, 0], L: [0, 1], F: [1, 1], R: [2, 1], B: [3, 1], D: [1, 2] };
const PALETTE = ['white', 'yellow', 'red', 'orange', 'green', 'blue'];
const SWATCH: Record<string, string> = { white: '#f4f4f0', yellow: '#ffd43b', red: '#e03131', orange: '#ff8a1f',
  green: '#2fb35a', blue: '#2a6fdb' };

function forSpeechLine(s: string): string {
  return s.replace(/\s+/g, ' ').replace(/\s*\((?:→|Esc|S|N|Enter)\)/g, '').trim().slice(0, 500);
}

/** What the voice says for a card: its label when it is news ("Move 3 of 18", "Correct"), the
 *  title and the text, without what only makes sense on screen. */
function spoken(label: string, title: string, text: string): string {
  const news = /^(Move|✓|Not that|Almost|Undo|Lost|Solved|Get ready|Got it|New plan|Scan|Ready)/.test(label) ? `${label}. ` : '';
  const body = text.replace(/\s*Then hold the cube still\.?/g, '').replace(/\(move (\d+) of (\d+)\)/, 'Next is move $1 of $2.');
  return `${news}${title}. ${body}`;
}

/** A move from the user's seat: a title ("Turn the green side (facing you)") and how ("its top edge moves to your left"). */
function moveWords(move: string, colours: Record<string, string>): { colour: string; title: string; how: string } {
  const d = describe(move, colours);
  const how = d.half ? 'Twice -- a half turn, either way.' : `${d.part[0].toUpperCase()}${d.part.slice(1)} moves ${d.moves}.`;
  return { colour: d.colour, title: `Turn the ${d.colour} side (${d.position})`, how };
}

export class Flow {
  /** What the overlays draw on the cube right now. */
  guide: { move: string; undo: boolean } | null = null;
  track: Track | null = null;
  private review: ScanResult | null = null;
  private locked: Record<string, string> = {};
  private selected: string | null = null;
  private holdUntil = 0;
  private stats = { start: 0, mistakes: 0, moves: 0 };
  private audio: AudioContext | null = null;
  private el: Record<string, HTMLElement> = {};
  /** Says each instruction as it changes; listens for "next", "repeat", "solve"... (voice.ts). */
  readonly voice = new Voice((cmd) => this.command(cmd), (q) => this.ask(q));
  /** What the card shows now (sent with a question, so the assistant knows the instruction). */
  private shown = '';
  private reported = false;

  constructor(private link: ServerLink, private state: AppState, private effects: Effects, root: HTMLElement) {
    root.innerHTML = `
      <div class="card" id="card">
        <div class="card-label" id="card-label"></div>
        <div class="card-main"><span class="chip" id="card-chip"></span><span id="card-title"></span></div>
        <div class="card-text" id="card-text"></div>
        <div class="steady" id="card-steady"><div></div></div>
        <div class="card-buttons" id="card-buttons"></div>
      </div>
      <div class="review" id="review" hidden>
        <div class="review-title" id="review-title"></div>
        <div class="net" id="net"></div>
        <div class="palette" id="palette" hidden></div>
        <div class="card-buttons" id="review-buttons"></div>
      </div>
      <div class="popup" id="popup" hidden>
        <div class="popup-head"><span>⚠ Undo the step</span><button id="popup-close" aria-label="Close">✕</button></div>
        <div class="popup-body"><div class="popup-icon">↶</div><div><b id="popup-move"></b><div id="popup-text"></div></div></div>
      </div>
      <div class="progress" id="progress" hidden>
        <div class="bars"><div class="bar"><div id="bar-progress"></div></div><div class="bar"><div id="bar-cube"></div></div></div>
        <div class="bar-labels"><span>PLAN</span><span>CUBE</span></div>
        <div class="percent" id="percent"></div>
      </div>
      <div class="turning" id="turning" hidden>✋ Turning… hold still when you're done</div>
      <div class="stats" id="stats" hidden></div>
      <div class="mic" id="mic"></div>
      <div class="assistant" id="assistant" hidden><div class="assistant-q" id="assistant-q"></div><div id="assistant-a"></div></div>`;
    for (const id of ['card', 'card-label', 'card-chip', 'card-title', 'card-text', 'card-steady', 'card-buttons',
      'review', 'review-title', 'net', 'palette', 'review-buttons', 'popup', 'popup-move', 'popup-text', 'popup-close',
      'progress', 'bar-progress', 'bar-cube', 'percent', 'turning', 'stats', 'assistant', 'assistant-q', 'assistant-a', 'mic']) {
      this.el[id] = root.querySelector('#' + id)!;
    }
    this.el['popup-close'].onclick = () => (this.el.popup.hidden = true);
    // The microphone: on at once if the browser allows it, else after the first click or key press.
    this.voice.onMic = (m) => this.showMic(m);
    this.voice.onHeard = (heard, understood) => this.showMic(this.voice.mic, heard, understood);
    this.showMic('off');
    this.voice.listen();
    for (const ev of ['pointerdown', 'keydown'] as const) addEventListener(ev, () => this.voice.listen());
    for (const colour of PALETTE) {
      const b = document.createElement('button');
      b.style.background = SWATCH[colour];
      b.title = colour;
      b.onclick = () => this.fixSticker(colour);
      this.el.palette.appendChild(b);
    }
    addEventListener('keydown', (e) => this.key(e));
    this.idle();
  }

  // ---------- server messages ----------
  onFrame(reply: FrameReply): void {
    this.el.turning.hidden = !(reply.hands_busy && (this.state.phase === 'scan' || this.state.phase === 'guided' || this.state.phase === 'undo'));
    this.el['bar-cube'].style.height = `${Math.round((reply.confident ? reply.confidence ?? 0 : 0) * 100)}%`;
    if (reply.scan_result) { this.showReview(reply.scan_result as unknown as ScanResult, true); return; }
    if (reply.scan) {
      const scan = reply.scan as unknown as ScanStatus;
      if (this.state.phase !== 'scan' && (scan.phase === 'view1' || scan.phase === 'view2')) this.enterScan();
      this.showScan(scan);
    }
    if (reply.track) this.showTrack(reply.track as unknown as Track);
  }

  onMessage(msg: Message): void {
    if (msg.type === 'answer') {
      const text = String(msg.text ?? '');
      this.showAssistant(String(msg.question ?? ''), text);
      this.voice.say(text, true, true);
      return;
    }
    if (msg.type === 'report') {
      if (msg.text) {
        this.voice.say(String(msg.text), true, true);
        this.el.stats.insertAdjacentHTML('beforeend', '<div class="stats-report"></div>');
        (this.el.stats.lastElementChild as HTMLElement).textContent = String(msg.text);
      }
      return;
    }
    if (msg.type === 'scan_result') this.showReview(msg.scan_result as ScanResult, false);
    else if (msg.type === 'track') this.showTrack(msg.track as Track);
    else if (msg.type === 'scan' && (msg.scan as ScanStatus).phase === 'off') this.idle();
    else if (msg.type === 'scan') this.enterScan();  // a scan was started (here, or on another screen of this session)
    else if (msg.type === 'error' && this.state.phase === 'review') {
      this.el['review-title'].textContent = String(msg.message ?? 'That cube cannot be solved -- check the colours.');
    }
  }

  // ---------- stages ----------
  private idle(): void {
    this.state.set('camera');
    this.state.error = false;
    this.guide = null;
    this.track = null;
    this.el.review.hidden = true;
    this.el.popup.hidden = true;
    this.el.progress.hidden = true;
    this.el.stats.hidden = true;
    this.card('Ready', '', 'Hold your cube up to the camera', 'Corner-on, so the camera sees three sides. Then start the scan.',
      [['Start scan  (S)', () => this.startScan(), 'primary']]);
  }

  /** A spoken question: to the assistant (on the server, vision/assistant.py), with what the tutor shows now
   *  and where each side is from the person's seat; the answer is said and shown (onMessage 'answer'). */
  private ask(question: string): void {
    const colours = this.track?.face_colors;
    const sides = colours ? Object.fromEntries(Object.entries(POSITION).map(([f, p]) => [colours[f] ?? f, p])) : undefined;
    this.link.send({ type: 'ask', text: question, context: this.shown, sides });
    this.showAssistant(question, 'Thinking…');
    this.tone(660, 0, 0.08);
  }

  /** The microphone indicator: listening or not, and what was last heard (for a few seconds). */
  private showMic(state: string, heard?: string, understood?: string | null): void {
    const el = this.el.mic;
    const base: Record<string, string> = { listening: '🎤 Listening: say “scan”, “next”, “repeat”, or ask a question',
      'needs-click': '🎤 Click anywhere to turn on the voice', blocked: '🎤 Microphone blocked: allow it in the address bar',
      unsupported: '🎤 Voice commands need Chrome', off: '🎤 Voice starting…' };
    el.className = 'mic ' + state;
    el.textContent = heard ? `🎤 Heard “${heard}”${understood ? ` → ${understood}` : ' (not a command)'}` : (base[state] ?? '');
    clearTimeout(this.micTimer);
    if (heard) this.micTimer = window.setTimeout(() => this.showMic(this.voice.mic), 4000);
  }
  private micTimer = 0;

  private showAssistant(question: string, answer: string): void {
    this.el.assistant.hidden = false;
    this.el['assistant-q'].textContent = `“${question}”`;
    this.el['assistant-a'].textContent = answer;
    clearTimeout(this.assistantTimer);
    this.assistantTimer = window.setTimeout(() => (this.el.assistant.hidden = true), 15000);
  }
  private assistantTimer = 0;

  /** A spoken command: the same as the button or key for it, where that applies now. */
  private command(cmd: Command): void {
    const p = this.state.phase;
    if (cmd === 'scan' && (p === 'camera' || p === 'solved' || p === 'review')) this.startScan();
    else if (cmd === 'solve' && p === 'review' && this.review?.valid) {
      if (this.review.doubtful.length) this.confirmHighlighted(); else this.solve();
    } else if (cmd === 'next' && (p === 'guided' || p === 'undo')) this.link.send({ type: 'track_skip' });
    else if (cmd === 'plan' && p === 'undo') this.link.send({ type: 'track_replan' });
    else if (cmd === 'stop' && (p === 'scan' || p === 'guided' || p === 'undo')) this.cancel();
    else this.voice.say(this.voice.last || 'Say help to hear what you can say.', true);   // not now: say where we are
  }

  private startScan(): void {
    this.voice.listen();
    this.reported = false;
    this.ensureAudio();
    this.link.send({ type: 'scan_start' });
    this.enterScan();
  }

  /** Shows the scanning stage. Also used when another screen of the same session started the scan. */
  private enterScan(): void {
    if (this.state.phase === 'scan') return;
    this.review = null; this.locked = {}; this.selected = null;
    this.el.review.hidden = true;
    this.el.stats.hidden = true;
    this.el.popup.hidden = true;
    this.guide = null;
    this.track = null;
    this.state.set('scan');
    this.card('Scan 1 of 2', '', 'Hold the cube still', '', [['Cancel  (Esc)', () => this.cancel(), '']]);
  }

  private cancel(): void {
    this.link.send({ type: this.state.phase === 'scan' ? 'scan_cancel' : 'track_stop' });
    this.idle();
  }

  private showScan(s: ScanStatus): void {
    if (this.state.phase !== 'scan' || s.phase === 'off' || s.phase === 'done') return;
    const sides = s.sides_done ?? 0;
    this.steady(s.steady / s.needed);
    // Centre colours of the sides scanned so far.
    const done = (s.scanned_centres ?? []).map(([r, g, b]) => `<i style="background:rgb(${r},${g},${b})"></i>`).join('');
    const cancel: [string, () => void, string][] = [['Cancel  (Esc)', () => this.cancel(), '']];
    const label = `Scan · ${sides} of 6 sides`;
    if (s.event === 'captured') {
      this.beep(1);
      this.effects.check(performance.now());
      const left = 6 - sides;
      this.card(`✓ ${sides} of 6 sides scanned`, done, left === 1 ? 'Now show the last side' : 'Now show the other sides',
        'Turn the cube any way you like, a corner toward the camera. ' +
        (left === 1 ? 'The side still missing is usually the underside.' : 'Sides already scanned may show again.'), cancel, 'good');
      this.holdUntil = performance.now() + 3000;
      return;
    }
    if (performance.now() < this.holdUntil) return;
    if (s.message) {
      this.card(label, done || '!', s.refused === 'nothing new' ? 'Those sides are already scanned' : 'Hold the cube corner-on',
        s.message, cancel, 'warn');
      this.holdUntil = performance.now() + 2500;
      return;
    }
    if (sides > 0) {
      this.card(label, done, s.steady ? 'Hold still…' : 'Show the sides not scanned yet', s.instruction ?? '', cancel);
      return;
    }
    this.card(label, '', s.steady ? 'Hold still…' : 'Show the cube corner-on', s.instruction ?? '', cancel);
  }

  private showReview(r: ScanResult, fresh: boolean): void {
    if (fresh) { this.beep(2); this.effects.check(performance.now()); }
    this.review = r;
    this.state.set('review');
    this.el.card.hidden = true;
    this.el.review.hidden = false;
    const n = r.doubtful.length;
    this.el['review-title'].textContent = !r.valid
      ? "This doesn't read as a real cube. Tap any wrong sticker to fix it, or scan again."
      : n ? `Check the ${n} highlighted sticker${n > 1 ? 's' : ''}: tap one to change it, or confirm they look right.`
        : 'Every sticker read clearly. Ready to solve.';
    this.voice.say(!r.valid ? "All sides scanned, but the colours don't make a real cube. Fix the wrong sticker, or say scan to scan again."
      : n ? `All six sides scanned. Check the ${n} highlighted sticker${n > 1 ? 's' : ''} on screen. If they look right, say solve.`
        : 'All six sides scanned, every sticker read clearly. Say solve when you are ready.');
    const buttons: [string, () => void, string][] = [];
    if (r.valid && n) buttons.push(['They look right  (Enter)', () => this.confirmHighlighted(), 'primary']);
    if (r.valid && !n) buttons.push(['Solve  (Enter)', () => this.solve(), 'primary']);
    buttons.push(['Scan again', () => this.startScan(), '']);
    this.buttons(this.el['review-buttons'], buttons);
    this.renderNet();
  }

  private renderNet(): void {
    const r = this.review!;
    this.el.net.innerHTML = '';
    for (const face of FACES) {
      const box = document.createElement('div');
      box.className = 'net-face';
      box.style.gridColumn = String(NET[face][0] + 1);
      box.style.gridRow = String(NET[face][1] + 1);
      r.colors[face].forEach((colour, k) => {
        const cell = document.createElement('button');
        const name = face + k;
        cell.style.background = SWATCH[colour];
        cell.className = (r.doubtful.includes(name) ? 'doubtful' : '') + (this.selected === name ? ' selected' : '');
        cell.title = `${colour}`;
        cell.onclick = () => { this.selected = name; this.el.palette.hidden = false; this.renderNet(); };
        box.appendChild(cell);
      });
      this.el.net.appendChild(box);
    }
  }

  private fixSticker(colour: string): void {
    if (!this.selected) return;
    this.locked[this.selected] = colour;
    this.selected = null;
    this.el.palette.hidden = true;
    this.link.send({ type: 'scan_check', locked: this.locked });
  }

  private confirmHighlighted(): void {
    const r = this.review!;
    for (const name of r.doubtful) this.locked[name] = r.colors[name[0]][Number(name[1])];
    this.link.send({ type: 'scan_check', locked: this.locked });
  }

  private solve(): void {
    this.link.send({ type: 'scan_accept', colors: this.review!.colors, on_mistake: 'undo' });
    this.stats = { start: performance.now(), mistakes: 0, moves: 0 };
  }

  private showTrack(t: Track): void {
    if (t.phase === 'off') { this.idle(); return; }
    this.track = t;
    this.el.review.hidden = true;
    this.el.card.hidden = false;
    this.el.progress.hidden = false;
    const done = t.phase === 'solved' ? 1 : (t.step - 1) / Math.max(1, t.total);
    this.el['bar-progress'].style.height = `${Math.round(done * 100)}%`;
    this.el.percent.textContent = `${Math.round(done * 100)}%`;
    this.steady(t.steady / Math.max(1, t.needed));
    const now = performance.now();

    if (t.event === 'correct' || t.event === 'undone') { this.stats.moves++; this.effects.check(now); this.beep(1); }
    if (t.event === 'wrong') { this.stats.mistakes++; this.stats.moves++; this.beepLow(); }

    if (t.phase === 'solved') {
      if (this.state.phase !== 'solved') {
        this.effects.celebrate(now, innerWidth, innerHeight); this.beep(3); this.showStats();
        if (!this.reported) { this.reported = true; this.link.send({ type: 'report' }); }   // the assistant's few words
      }
      this.state.set('solved');
      this.state.error = false;
      this.guide = null;
      this.el.popup.hidden = true;
      this.card('Solved!', '🎉', 'Cube solved', t.message ?? 'Well done.', [['Scan another cube  (S)', () => this.startScan(), 'primary']], 'good');
      return;
    }
    const undoing = t.phase === 'undo';
    this.state.set(t.phase === 'home' ? 'guided' : undoing ? 'undo' : 'guided');
    this.state.error = undoing;
    this.guide = t.move && t.phase !== 'home' ? { move: t.move, undo: undoing } : null;
    const buttons: [string, () => void, string][] = [['I did it  (→)', () => this.link.send({ type: 'track_skip' }), '']];
    if (undoing) buttons.push(['New plan instead  (N)', () => this.link.send({ type: 'track_replan' }), '']);
    buttons.push(['Stop  (Esc)', () => this.cancel(), '']);

    if (t.phase === 'home' && t.event === 'reoriented') {
      this.card('Got it', '', 'Following the cube the way you are holding it', 'Hold it still for a moment.', buttons, 'good');
      return;
    }
    if (t.phase === 'home') {
      this.el.popup.hidden = true;
      this.card('Get ready', '', 'Hold the cube up to the camera', `${ANY_HOLD} Then hold it still for a moment.`, buttons);
      return;
    }
    const m = moveWords(t.move ?? '', t.face_colors);
    const chip = `<i style="background:${SWATCH[m.colour] ?? '#888'}"></i>`;
    if (undoing && t.fix) {
      // The right side, the wrong amount: one turn of that side puts it back on the plan (no undo, no redo).
      const [did, asked] = t.fix;
      const amount = (mv: string) => mv.endsWith('2') ? 'twice' : mv.endsWith("'") ? 'once the other way' : 'once';
      const side = describe(asked, t.face_colors).colour;
      const why = `You turned the ${side} side ${amount(did)}; it needed ${amount(asked)}.`;
      this.el.popup.hidden = false;
      this.el['popup-move'].innerHTML = `${chip} ${m.title}`;
      this.el['popup-text'].textContent = `${why} ${m.how} Then the plan carries on.`;
      if (t.event === 'wrong' || now > this.holdUntil) {
        this.card('Almost -- fix the turn', chip, m.title, `${why} ${m.how}`, buttons, 'bad');
        if (t.event === 'wrong') this.holdUntil = now + 4000;
      }
      return;
    }
    if (undoing) {
      const left = t.undo.length;
      this.el.popup.hidden = false;
      this.el['popup-move'].innerHTML = `${chip} ${m.title}`;
      this.el['popup-text'].textContent = m.how + (left > 1 ? ` (${left} turns to undo, then the plan carries on.)`
        : ' That undoes it; then the plan carries on.');
      if (t.event === 'wrong' || now > this.holdUntil) {
        this.card(t.event === 'wrong' ? 'Not that one -- undo it' : 'Undo the mistake', chip, m.title,
          t.event === 'wrong' ? `${this.friendly(t.message, t.face_colors)} To undo: ${m.how}` : `${m.how} Then hold still.`,
          buttons, 'bad');
        if (t.event === 'wrong') this.holdUntil = now + 4000;
      }
      return;
    }
    this.el.popup.hidden = true;
    if (t.event === 'reoriented') {
      this.holdUntil = now + 2500;
      this.card('Got it', chip, m.title, `Following the cube the way you're holding it. ${m.how}${holdTip(t)}`, buttons, 'good');
      return;
    }
    if (t.event === 'correct' || t.event === 'undone' || t.event === 'replanned') {
      this.holdUntil = now + 1200;
      this.card(t.event === 'undone' ? '✓ Undone -- back on track' : t.event === 'replanned' ? 'New plan' : '✓ Correct',
        chip, m.title, `${m.how}${holdTip(t)} (move ${t.step} of ${t.total})`, buttons, 'good');
      return;
    }
    if (t.event === 'lost') {
      this.card('Lost the cube', '!', 'Bring the cube back into view', ANY_HOLD, buttons, 'warn');
      this.holdUntil = now + 3000;
      return;
    }
    if (now < this.holdUntil) return;
    this.card(`Move ${t.step} of ${t.total}`, chip, m.title, `${m.how}${holdTip(t)} Then hold the cube still.`, buttons);
  }

  /** The server's "You did U instead of L" in colours. */
  private friendly(message: string | null, colours: Record<string, string>): string {
    const did = /You did (.+?) instead of (\S+?)\./.exec(message ?? '');
    if (!did) return message ?? '';
    const name = (mv: string) => describe(mv, colours).colour;
    return `You turned the ${did[1].split(' then ').map(name).join(' side, then the ')} side -- the move was the ${name(did[2])} side.`;
  }

  private showStats(): void {
    const secs = Math.round((performance.now() - this.stats.start) / 1000);
    this.el.stats.hidden = false;
    this.el.stats.innerHTML = `<div class="stats-title">Solved</div>
      <div class="stats-row"><span>TIME</span><b>${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}</b></div>
      <div class="stats-row"><span>MOVES</span><b>${this.stats.moves}</b></div>
      <div class="stats-row"><span>MISTAKES</span><b>${this.stats.mistakes}</b></div>`;
  }

  // ---------- UI helpers ----------
  private card(label: string, chip: string, title: string, text: string, buttons: [string, () => void, string][],
               tone = ''): void {
    // "Hold still…" comes and goes as the cube moves: not said. News (correct, wrong, captured, solved) cuts in.
    if (!/^Hold still/.test(title)) this.voice.say(spoken(label, title, text), false, /^(✓|Not that|Almost|Solved|Lost|New plan)/.test(label));
    this.shown = forSpeechLine(`${label}. ${title}. ${text}`);
    this.el.card.hidden = false;
    this.el.card.className = 'card ' + tone;
    this.el['card-label'].textContent = label;
    this.el['card-chip'].innerHTML = chip;
    this.el['card-chip'].hidden = !chip;
    this.el['card-title'].textContent = title;
    this.el['card-text'].textContent = text;
    this.buttons(this.el['card-buttons'], buttons);
  }

  private buttons(box: HTMLElement, list: [string, () => void, string][]): void {
    const key = list.map((b) => b[0]).join('|');
    if (box.dataset.key === key) return;  // don't rebuild (keeps clicks working at 20 updates/s)
    box.dataset.key = key;
    box.innerHTML = '';
    const touch = matchMedia('(pointer: coarse)').matches;  // no keyboard: drop the key hints like "(Esc)"
    for (const [label, action, cls] of list) {
      const b = document.createElement('button');
      b.textContent = touch ? label.replace(/\s*\([^)]*\)\s*$/, '') : label;
      b.className = cls;
      b.onclick = action;
      box.appendChild(b);
    }
  }

  private steady(f: number): void {
    (this.el['card-steady'].firstElementChild as HTMLElement).style.width = `${Math.round(Math.min(1, f) * 100)}%`;
  }

  private key(e: KeyboardEvent): void {
    if (e.target instanceof HTMLInputElement) return;
    const p = this.state.phase;
    if ((e.key === 's' || e.key === 'S') && (p === 'camera' || p === 'solved' || p === 'review')) this.startScan();
    else if (e.key === 'Escape' && (p === 'scan' || p === 'guided' || p === 'undo')) this.cancel();
    else if (e.key === 'Enter' && p === 'review' && this.review?.valid) {
      if (this.review.doubtful.length) this.confirmHighlighted(); else this.solve();
    } else if ((e.key === 'ArrowRight' || e.key === ' ') && (p === 'guided' || p === 'undo')) {
      e.preventDefault();
      this.link.send({ type: 'track_skip' });
    } else if ((e.key === 'n' || e.key === 'N') && p === 'undo') this.link.send({ type: 'track_replan' });
  }

  private ensureAudio(): void {
    try { this.audio = this.audio ?? new AudioContext(); } catch { this.audio = null; }
  }

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

  private beep(times: number): void { for (let i = 0; i < times; i++) this.tone(880 + 220 * i, i * 0.16); }
  private beepLow(): void { this.tone(300, 0, 0.25); this.tone(220, 0.22, 0.3); }
}
