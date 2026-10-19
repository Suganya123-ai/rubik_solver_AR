// Moves described from where the user sits. The webcam faces the user, so
// the camera's view is the user's view turned round: the camera's Front is the
// side facing away from the user, its Right is on the user's left. The server
// names moves in the camera's terms (U R F D L B); this turns them into "the
// green side (facing you): its top edge moves to your left".
//
// Cube axes (server convention): +x = camera's Right, +y = Up, +z = camera's
// Front (toward the camera). The user is at -z looking toward +z, so the
// user's right is -x.

import { glasses } from './mode';

// On the glasses the camera looks the wearer's way, so the camera's view IS the
// user's view: Front faces the user, Right is on the user's right.

type V = [number, number, number];
const LAYER: Record<string, [number, number]> = { U: [1, 1], D: [1, -1], F: [2, 1], B: [2, -1], R: [0, 1], L: [0, -1] };

/** Where each side is, from the user's seat. */
export const POSITION: Record<string, string> = glasses
  ? { U: 'on top', D: 'underneath', F: 'facing you', B: 'at the back', R: 'on your right', L: 'on your left' }
  : { U: 'on top', D: 'underneath', F: 'facing the camera', B: 'facing you', R: 'on your left', L: 'on your right' };

// For each side, a point on its layer the user can see, and what to call it.
const NEAR = glasses ? 1 : -1;  // which way along z is "nearest you"
const REFERENCE: Record<string, [V, string]> = {
  U: [[0, 1, NEAR], 'the edge nearest you'],
  D: [[0, -1, NEAR], 'the edge nearest you'],
  R: [[1, 0, NEAR], 'the edge nearest you'],
  L: [[-1, 0, NEAR], 'the edge nearest you'],
  F: [[0, 1, 1], 'its top edge'],
  B: [[0, 1, -1], 'its top edge'],
};

const cross = (a: V, b: V): V => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];

/** Which way a motion (cube axes) goes for the user. */
function direction(t: V): string {
  const right = glasses ? t[0] : -t[0], up = t[1], toward = glasses ? t[2] : -t[2];
  const best = [[Math.abs(right), right > 0 ? 'to your right' : 'to your left'],
    [Math.abs(up), up > 0 ? 'up' : 'down'],
    [Math.abs(toward), toward > 0 ? 'toward you' : 'away from you']] as [number, string][];
  return best.sort((a, b) => b[0] - a[0])[0][1];
}

export type MoveText = { colour: string; position: string; half: boolean; part: string; moves: string };

/** move: e.g. "B'", in the server's (camera's) terms. */
export function describe(move: string, faceColours: Record<string, string>): MoveText {
  const face = move[0];
  const turns = move.endsWith("'") ? -1 : move.endsWith('2') ? 2 : 1;
  const [axis, side] = LAYER[face];
  const angle = -side * turns;                 // sign of the turn about the +axis (clockwise seen from outside)
  const a: V = [0, 0, 0]; a[axis] = 1;
  const [p, part] = REFERENCE[face];
  const t = cross(a, p).map((v) => v * Math.sign(angle)) as V;  // how the reference point starts to move
  return { colour: faceColours[face] ?? face, position: POSITION[face], half: turns === 2, part,
           moves: direction(t) };
}

/** One line: "Turn the green side (facing you): its top edge moves to your left." */
export function sentence(move: string, faceColours: Record<string, string>): string {
  const d = describe(move, faceColours);
  if (d.half) return `Turn the ${d.colour} side (${d.position}) twice -- a half turn, either way.`;
  const part = d.part.startsWith('its') ? d.part : d.part;
  return `Turn the ${d.colour} side (${d.position}): ${part} moves ${d.moves}.`;
}

/** How to hold the cube, from the user's seat. */
export function holdHint(faceColours: Record<string, string>): string {
  const c = faceColours;
  return glasses
    ? `Hold it with ${c.U} on top, ${c.F} facing you and ${c.R} on your right.`
    : `Hold it with ${c.U} on top and ${c.F} facing the camera (${c.B} facing you, ${c.R} on your left).`;
}
