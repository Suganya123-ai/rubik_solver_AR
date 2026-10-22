// The cube as the overlays see it: the server's 7 corner points (picture
// pixels of the frame it was sent), eased toward each new reply so the
// overlays glide at screen rate between server replies.

import type { FrameReply } from './serverLink';

export type Pt = [number, number];
const EASE = 0.45;          // per animation frame
const FORGET_MS = 600;      // no cube for this long: overlays fade out

export class CubeView {
  /** Smoothed corner points in the server frame's pixels, or null. */
  keypoints: Pt[] | null = null;
  frameW = 640;
  confidence = 0;
  confident = false;
  /** How the cube is held and which corners are really seen (null: an older model, corner-on only). */
  hold: string | null = null;
  seen: boolean[] | null = null;
  lastSeen = -Infinity;
  private target: Pt[] | null = null;

  update(reply: FrameReply, now: number): void {
    this.frameW = reply.width;
    this.confidence = reply.confidence ?? 0;
    this.confident = reply.confident;
    if (reply.keypoints) {
      this.target = reply.keypoints;
      this.hold = reply.hold ?? null;
      this.seen = reply.seen ?? null;
      this.lastSeen = now;
      if (!this.keypoints) this.keypoints = reply.keypoints.map((p) => [p[0], p[1]] as Pt);
    }
  }

  /** Call every animation frame. Returns how visible the overlays should be (0..1). */
  step(now: number): number {
    if (this.keypoints && this.target) {
      this.keypoints = this.keypoints.map((p, i) => [
        p[0] + (this.target![i][0] - p[0]) * EASE,
        p[1] + (this.target![i][1] - p[1]) * EASE,
      ] as Pt);
    }
    const age = now - this.lastSeen;
    if (age > FORGET_MS * 2) { this.keypoints = null; this.target = null; return 0; }
    return age < FORGET_MS ? 1 : 1 - (age - FORGET_MS) / FORGET_MS;
  }
}
