// The text parts of the HUD (DOM, crisp at any size): live readouts top-left,
// connection state, and the "hold the cube steady" hint with a target box.

export type Readouts = { fps: number; handsFps: number; replies: number; latency: number; serverMs: number;
  confidence: number; connected: boolean };

export class Hud {
  private stats: HTMLElement;
  private hint: HTMLElement;
  private target: HTMLElement;
  private message: HTMLElement;

  constructor(root: HTMLElement) {
    root.innerHTML = `
      <div class="hud-stats" id="hud-stats"></div>
      <div class="hud-target" id="hud-target"></div>
      <div class="hud-hint" id="hud-hint">Hold the cube steady inside the box, corner-on, so three sides show</div>
      <div class="hud-message" id="hud-message"></div>`;
    this.stats = root.querySelector('#hud-stats')!;
    this.hint = root.querySelector('#hud-hint')!;
    this.target = root.querySelector('#hud-target')!;
    this.message = root.querySelector('#hud-message')!;
  }

  readouts(r: Readouts): void {
    const row = (k: string, v: string) => `<div><span>${k}</span><b>${v}</b></div>`;
    this.stats.innerHTML =
      row('RENDER', `${r.fps} fps`) + row('HANDS', `${r.handsFps} fps`) +
      row('VISION', r.connected ? `${r.replies}/s · ${Math.round(r.latency)} ms` : 'offline') +
      row('CUBE', r.confidence ? `${Math.round(r.confidence * 100)}%` : '—');
  }

  /** Show the hint and target box when the cube isn't being found reliably;
   *  or (target box off) another hint, e.g. "tilt the cube". */
  showHint(on: boolean, text?: string): void {
    this.hint.textContent = text ?? 'Hold the cube steady inside the box, corner-on, so three sides show';
    this.hint.classList.toggle('on', on || !!text);
    this.target.classList.toggle('on', on);
  }

  say(text: string): void {
    this.message.textContent = text;
    this.message.classList.toggle('on', !!text);
  }
}
