// Voice: the tutor says its instructions out loud and listens for a few spoken commands, so the
// hands can stay on the cube.
//
// Two ways to speak and listen:
//   - the glasses app (android_phone/): Android's own text-to-speech and speech recognition, offered
//     to the page as window.TutorVoice (Android's web view has neither); what is heard comes back
//     through window.tutorHeard(text);
//   - a browser (the laptop app): the Web Speech API (speechSynthesis, SpeechRecognition).
// While the tutor is talking it doesn't listen, so it never takes its own "next move" as a command.

export type Command = 'next' | 'repeat' | 'scan' | 'solve' | 'plan' | 'stop' | 'quiet' | 'speak' | 'help';

/** What can be said, in the words people use (checked in this order: the first that matches wins). */
const WORDS: [Command, RegExp][] = [
  ['quiet', /\b(quiet|mute|silence|be quiet|stop talking)\b/],
  ['speak', /\b(speak|unmute|talk|voice on)\b/],
  ['help', /\b(help|commands|what can i say)\b/],
  ['plan', /\b(new plan|replan|re plan)\b/],
  ['repeat', /\b(repeat|again|say that again|what|pardon)\b/],
  ['next', /\b(next|done|did it|i did it|finished|okay next|ok next)\b/],
  ['solve', /\b(solve|go|ready|confirm)\b/],
  ['scan', /\b(scan|start)\b/],
  ['stop', /\b(stop|cancel)\b/],
];

export const HELP = 'You can say: next, when you have done the move. Repeat, to hear it again. ' +
  'Scan, solve, new plan, or stop. Quiet, to turn the voice off, and speak, to turn it back on.';

/** A question for the assistant ("why this move?", "what did I do wrong?"), rather than a command:
 *  starts with a question word and has a few words ("what" alone is "repeat"). */
export function isQuestion(heard: string): boolean {
  const words = heard.toLowerCase().replace(/[^a-z' ]/g, ' ').trim().split(/\s+/).filter(Boolean);
  return words.length >= 3 && /^(why|what|what's|how|which|where|when|who|is|are|can|could|should|do|does|did|will|would|tell|explain)$/.test(words[0]);
}

export function parseCommand(heard: string): Command | null {
  const text = ` ${heard.toLowerCase().replace(/[^a-z ]/g, ' ')} `;
  for (const [cmd, re] of WORDS) if (re.test(text)) return cmd;
  return null;
}

/** Screen text into something good to hear: no key hints, symbols or brackets. */
export function forSpeech(text: string): string {
  return text
    .replace(/\s*\((?:→|Esc|S|N|Enter|[A-Z])\)/g, '')       // key hints like "(→)"
    .replace(/[✓✋🎉⚠↶!]+/gu, '')
    .replace(/\s*·\s*/g, ', ')
    .replace(/\s*--\s*/g, ', ')
    .replace(/\s*\(([^)]*)\)/g, ', $1')                     // "(facing you)" -> ", facing you"
    .replace(/\s+/g, ' ')
    .replace(/\s+([.,])/g, '$1')
    .replace(/([.,]){2,}/g, '$1')
    .trim();
}

type Bridge = { say(text: string): void; listen(on: boolean): void };
type Recognition = { continuous: boolean; interimResults: boolean; lang: string; start(): void; stop(): void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }>; resultIndex: number }) => void) | null;
  onend: (() => void) | null; onerror: ((e: { error: string }) => void) | null };

declare global {
  interface Window {
    TutorVoice?: Bridge;
    tutorHeard?: (text: string) => void;
    tutorSpoke?: () => void;          // the app's text-to-speech finished a sentence
    SpeechRecognition?: new () => Recognition;
    webkitSpeechRecognition?: new () => Recognition;
  }
}

export class Voice {
  /** Speaking on (the user can say "quiet" / "speak"). */
  on = true;
  /** The last instruction (what "repeat" says again; help and other replies don't replace it). */
  last = '';
  /** Everything said, newest last (tests read it). */
  readonly said: string[] = [];
  private talkUntil = 0;              // not listening until then: the tutor is talking
  private waiting: string | null = null;   // a routine update said once the current sentence ends
  private listening = false;
  private bridge: Bridge | null = window.TutorVoice ?? null;

  constructor(private onCommand: (cmd: Command, heard: string) => void, private onQuestion?: (question: string) => void) {
    window.tutorHeard = (text: string) => this.heard(text);
    window.tutorSpoke = () => { this.talkUntil = performance.now() + 300; this.next(); };
    setInterval(() => { if (performance.now() >= this.talkUntil) this.next(); }, 250);   // (no 'done' from the engine)
  }

  /** Starts listening for commands (after a click or key press in a browser: microphones need one). */
  listen(): void {
    if (this.listening) return;
    this.listening = true;
    if (this.bridge) { this.bridge.listen(true); return; }
    const Rec = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!Rec) return;
    const rec = new Rec();
    rec.continuous = true;
    rec.interimResults = false;
    rec.lang = 'en-US';
    rec.onresult = (e) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) this.heard(e.results[i][0].transcript);
      }
    };
    rec.onend = () => { if (this.listening) setTimeout(() => { try { rec.start(); } catch { /* already on */ } }, 300); };
    rec.onerror = () => { /* onend follows and starts it again */ };
    try { rec.start(); } catch { this.listening = false; }
  }

  /** Says a sentence when it is new (the screen updates many times a second: only changes are said),
   *  or again when `force` ("repeat"). `urgent` (an event: correct, wrong, captured, solved) cuts in;
   *  anything else waits for the current sentence to end, and only the newest of those is said. */
  say(text: string, force = false, urgent = force): void {
    const t = forSpeech(text);
    if (!t || (!force && (t === this.last || t === this.waiting))) return;
    if (!force) this.last = t;                        // an instruction (a reply to "help" etc. is not one)
    if (!urgent && performance.now() < this.talkUntil) { this.waiting = t; return; }
    this.waiting = null;
    this.speakNow(t, force);
  }

  private next(): void {
    if (this.waiting) { const t = this.waiting; this.waiting = null; this.speakNow(t, false); }
  }

  private speakNow(t: string, force: boolean): void {
    this.said.push(t);
    if (!this.on && !force) return;
    // deaf while talking: until the speech says it has finished, or a generous guess of its length
    this.talkUntil = performance.now() + 1000 + t.length * 75;
    if (this.bridge) { this.bridge.say(t); return; }
    const synth = window.speechSynthesis;
    if (!synth) { this.talkUntil = 0; return; }
    synth.cancel();                                   // the newest instruction is the one that matters
    const u = new SpeechSynthesisUtterance(t);
    u.rate = 1.05;
    u.onend = u.onerror = () => { this.talkUntil = performance.now() + 300; };
    synth.speak(u);
  }

  private heard(text: string): void {
    if (performance.now() < this.talkUntil) return;   // its own voice
    const best = text.split(' | ')[0];                  // the app sends every guess, best first
    if (this.onQuestion && isQuestion(best)) { this.onQuestion(best); return; }
    const cmd = parseCommand(text);
    if (!cmd) return;
    if (cmd === 'quiet') { this.on = false; window.speechSynthesis?.cancel(); return; }
    if (cmd === 'speak') { this.on = true; this.say(this.last || 'Voice on.', true); return; }
    if (cmd === 'repeat') { this.say(this.last, true); return; }
    if (cmd === 'help') { this.say(HELP, true); return; }
    this.onCommand(cmd, text);
  }
}
