// The look of the reference video: neon green = correct, red = error,
// amber = warning, cyan = data. Thin lines, soft glow.
export const GREEN = '#3dff9a';
export const RED = '#ff4d5e';
export const AMBER = '#ffb547';
export const CYAN = '#5ee6ff';
export const MONO = '"JetBrains Mono", ui-monospace, Menlo, monospace';

export function glow(ctx: CanvasRenderingContext2D, colour: string, blur: number): void {
  // A blurred shadow is costly to draw: on a busy device (the Beam Pro) the lines go without it.
  if ((window as unknown as { lowPowerFps?: number }).lowPowerFps) return;
  ctx.shadowColor = colour;
  ctx.shadowBlur = blur;
}
