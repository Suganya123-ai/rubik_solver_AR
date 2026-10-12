// How the app is being used. On this branch the default is the glasses:
// the camera looks the same way the wearer does (XREAL Eye, or the Beam Pro's
// own camera), so nothing is mirrored and instructions are from the camera's
// point of view. `?mode=laptop` gives the webcam behaviour back (camera facing
// the user: mirrored picture, instructions turned round to the user's seat).

const params = new URLSearchParams(location.search);

/** True when the camera sees what the user sees (glasses / rear camera). */
export const glasses = params.get('mode') !== 'laptop';

/** Heads-up display only: no camera picture, black background. On see-through
 *  glasses black is invisible, so the ghost cube and text float in view. */
export let hudOnly = params.get('hud') === '1';
export function setHudOnly(on: boolean): void { hudOnly = on; }

/** Hand tracking mode from the URL (gpu | cpu | off). The Beam Pro is a phone-class
 *  device, so the glasses default to the server's hand tracking only ("off" here). */
export const handsMode = params.get('hands') ?? (glasses ? 'off' : 'gpu');
