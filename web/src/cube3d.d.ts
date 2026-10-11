// Types for cube3d.js (copied from the demo's static/cube3d.js: the 3D cube
// that plays a move, and the move drawn on the camera picture).
declare global {
  interface Window {
    CubeHologram: new (canvas: HTMLCanvasElement) => {
      show(state: string, faceColours: Record<string, string>, move: string | null, opts?: { undo?: boolean }): void;
      yaw: number;
      pitch: number;
    };
    drawMoveOnVideo(ctx: CanvasRenderingContext2D, keypoints: [number, number][], move: string,
                    opts?: { undo?: boolean; now?: number }): void;
  }
}
export {};
