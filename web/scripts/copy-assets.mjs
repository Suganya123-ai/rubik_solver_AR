// Copies what the browser loads at runtime into public/, so the app works offline:
// MediaPipe's WebAssembly files and the hand model (shared with the Python server).
import { cpSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const wasm = join(root, 'node_modules/@mediapipe/tasks-vision/wasm');
const model = join(root, '../models/hand_landmarker.task');
mkdirSync(join(root, 'public/mediapipe'), { recursive: true });
mkdirSync(join(root, 'public/models'), { recursive: true });
if (existsSync(wasm)) cpSync(wasm, join(root, 'public/mediapipe/wasm'), { recursive: true });
else console.warn('copy-assets: MediaPipe wasm not found (run npm install)');
if (existsSync(model)) cpSync(model, join(root, 'public/models/hand_landmarker.task'));
else console.warn('copy-assets: ../models/hand_landmarker.task not found');
console.log('copy-assets: MediaPipe wasm + hand model copied to public/');
