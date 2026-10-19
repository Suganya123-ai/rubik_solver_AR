// The next move drawn on the real cube in the (mirrored) picture: the
// stickers that turn, outlined, and a curved arrow around their layer.
// cube3d.js draws in the server frame's pixels; a canvas transform maps that
// onto the mirrored full-screen picture, so arrows mirror with the video.

import '../cube3d.js';
import type { Pt, View } from '../view';

export function drawMoveArrows(ctx: CanvasRenderingContext2D, view: View, keypoints: Pt[], frameW: number,
                               move: string, undo: boolean, now: number): void {
  const o = view.fromFrame([0, 0], frameW);
  const ex = view.fromFrame([1, 0], frameW);   // where +1 frame pixel in x lands
  const ey = view.fromFrame([0, 1], frameW);
  ctx.save();
  ctx.transform(ex[0] - o[0], ex[1] - o[1], ey[0] - o[0], ey[1] - o[1], o[0], o[1]);
  window.drawMoveOnVideo(ctx, keypoints, move, { undo, now });
  ctx.restore();
}
