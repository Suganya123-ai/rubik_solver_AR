# Live protocol (`/ws/live`)

One WebSocket connection per device: the browser live view, or the XREAL
glasses app. Each connection has its own scan and tracking state on the server.

- URL: `ws://<laptop-ip>:8000/ws/live` (start the server with `--host 0.0.0.0` for other devices)
- Health check: `GET http://<laptop-ip>:8000/health` → `{"ok": true, "model": "cube_pose_v2.pt", "model_loaded": true}`

## Frames (client → server, binary)

`4-byte big-endian frame id` + `JPEG bytes`. Send 640 px wide (any aspect),
quality ~80, max 2 MB. **Send the next frame only after the reply to the
previous one**, so frames never pile up (~25–35 replies/s on a laptop GPU).

## Frame reply (server → client)

```json
{
  "type": "frame", "frame": 812, "width": 640, "height": 480, "ms": 17.9,
  "keypoints": [[x, y], ... 7 points] | null,
  "confidence": 0.94 | null, "confident": true,
  "faces": {"U": [[r, g, b] x 9], "F": [...], "R": [...]} | null,
  "hands": [{"points": [[x, y] x 21], "score": 0.97}],   // MediaPipe hand points (0 wrist, 4 thumb tip, 8 index tip, ...)
  "covered": {"U": [9 bools], "F": [...], "R": [...]} | null,  // stickers a hand covers (left out of scan/tracking)
  "hands_busy": false,    // hands turning the cube: nothing is judged until they stop
  "scan": {...},          // only while scanning
  "scan_result": {...},   // once, when the scan finishes
  "track": {...}          // only while solving
}
```

Keypoints are in the sent frame's pixels: 0 = corner nearest the camera
(Top-Front-Right), then 1 FLU, 2 BLU, 3 BRU, 4 BRD, 5 FRD, 6 FLD.
`confident` is false for guesses under 0.5 confidence (show them faded).

## Commands (client → server, JSON text)

| Command | Reply | Notes |
|---|---|---|
| `{"type": "scan_start"}` | `{"type": "scan", "scan": status}` | Then every frame reply carries `scan` until done |
| `{"type": "scan_cancel"}` | `{"type": "scan", ...}` | |
| `{"type": "scan_check", "locked": {"F0": "red"}}` | `{"type": "scan_result", "scan_result": result}` | Re-read with the user's confirmed stickers locked |
| `{"type": "scan_accept", "colors": {face: [9 names]}, "on_mistake": "undo" \| "replan"}` | `{"type": "track", "moves": [...], "track": status}` or `{"type": "error", ...}` | Validates, solves, starts tracking. `on_mistake` (default `undo`): after a wrong move, show how to undo it and keep the plan, or solve again from there |
| `{"type": "track_skip"}` | `{"type": "track", "track": status}` | "I did this move" fallback (also for undo moves) |
| `{"type": "track_replan"}` | `{"type": "track", "track": status}` | Stop undoing; solve again from where the cube is now |
| `{"type": "track_stop"}` | `{"type": "track", ...}` | |
| `{"type": "save"}` | `{"type": "saved", "saved": path, "count": n}` | Saves the last frame for retraining |
| `{"type": "ping"}` | `{"type": "pong"}` | |

Colour names: `white yellow red orange green blue`. Sticker names: face letter
+ index 0–8 in reading order (`U R F D L B`, each face viewed head-on).

### `scan` status

```json
{"phase": "view1" | "view2" | "done", "instruction": "Hold the cube corner-on...",
 "steady": 3, "needed": 5, "captured": [1], "message": "View 1 captured. Now flip the cube." | null,
 "event": null | "started" | "captured" | "done"}
```

### `scan_result`

```json
{"colors": {"U": ["white", ...], ...}, "doubtful": ["F2", "R7"], "valid": true, "centers": {"U": "white", ...}}
```

Show the cube; highlight `doubtful` stickers for the user to confirm or change,
then send `scan_check` with the locks. When `doubtful` is empty and `valid` is
true, send `scan_accept`.

### `track` status

```json
{"phase": "home" | "tracking" | "undo" | "solved", "step": 4, "total": 20, "move": "R'",
 "undo": ["U'"], "plan_move": "L",
 "description": "Turn the Right (R) face counter-clockwise ...",
 "steady": 2, "needed": 5,
 "event": null | "home" | "correct" | "wrong" | "unsure" | "lost" | "solved",
 "message": "You did U instead of L. New plan: 18 moves." | null,
 "state": "UUFRU...",
 "face_colors": {"U": "white", "R": "red", "F": "green", "D": "yellow", "L": "orange", "B": "blue"}}
```

- `state`: the cube as the server believes it is now, 54 face letters in the
  order U R F D L B (each face row by row, as seen from outside it).
  `face_colors` gives the real colour of each face letter, so a client can draw
  the user's cube (the browser shows it in 3D, playing `move`; see
  `static/cube3d.js`).

- `home`: waiting for the cube to be held in the first position (Top, Front, Right toward the camera).
- `correct`: the move was seen; `move` is now the next one.
- `wrong`: the user did something else; the message says what. With
  `on_mistake: "undo"` the phase becomes `undo`: `move` is the first move that
  reverses the mistake, `undo` all of them (in order), `plan_move` the plan's
  move to do afterwards. More than 3 moves to undo, or `on_mistake: "replan"`:
  the plan was rebuilt instead (`step` back to 1).
- `undone`: the mistake is reversed; back on the same plan (`move` = `plan_move`).
- `replanned`: a new plan after `track_replan`.
- `lost`: nothing recognisable for 3 s; ask the user to return to the first position or rescan.

## Errors

`{"type": "error", "code": "BAD_REQUEST" | "SERVER" | <validation code>, "message": "..."}`.
The connection stays open after an error.
