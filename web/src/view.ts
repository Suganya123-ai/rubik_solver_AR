// Where things in the camera picture land on screen. The video fills the
// screen (cropped, like object-fit: cover) and is mirrored, so the picture
// moves like a mirror. Everything drawn on top goes through these mappings.

export type Pt = [number, number];

export class View {
  /** Screen size in CSS pixels. */
  w = 1;
  h = 1;
  private scale = 1;
  private ox = 0;
  private oy = 0;
  private vw = 1;
  /** Shown like a mirror (a camera facing the person); off for a camera looking at the table. */
  mirrored = true;

  update(videoW: number, videoH: number, screenW: number, screenH: number): void {
    this.w = screenW;
    this.h = screenH;
    this.vw = videoW;
    this.scale = Math.max(screenW / videoW, screenH / videoH);
    this.ox = (screenW - videoW * this.scale) / 2;
    this.oy = (screenH - videoH * this.scale) / 2;
  }

  /** A point in video pixels -> screen (mirrored). */
  fromVideo([x, y]: Pt): Pt {
    return [this.ox + (this.mirrored ? this.vw - x : x) * this.scale, this.oy + y * this.scale];
  }

  /** A MediaPipe point (0..1 of the video) -> screen. */
  fromNormalized(nx: number, ny: number, videoH: number): Pt {
    return this.fromVideo([nx * this.vw, ny * videoH]);
  }

  /** A point in a downscaled copy of the video (what the server saw) -> screen. */
  fromFrame([x, y]: Pt, frameW: number): Pt {
    const k = this.vw / frameW;
    return this.fromVideo([x * k, y * k]);
  }
}
