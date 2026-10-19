"""The vision server plus the built glasses web app, in one program.

    uvicorn glasses_server:app --host 0.0.0.0 --port 5273 --ssl-keyfile ... --ssl-certfile ...

The Beam Pro opens https://<laptop>:5273/glasses/ . Serving the page from the
Python server (instead of the Node dev server) means one process, one address,
and it is the program macOS's firewall already allows to accept connections.
The web app is built into web/dist by `npm run build` (run_glasses.sh does it).

It also relays a camera that is not the browser's own. The glasses' add-on
camera can't be opened by a browser, so a small Android app (android_bridge/)
reads it and uploads the frames here; the tutor page then runs in "remote
camera" mode (`?camera=remote`), showing what the server makes of them:

    bridge app  --frames-->  /ws/feed  --> one shared session --> /ws/view  --results-->  tutor page(s)
                                                                  /feed.mjpg --picture-->
"""
import asyncio
import json
import logging
import os

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from main import app

log = logging.getLogger('rubik.relay')
DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web', 'dist')
if not os.path.isfile(os.path.join(DIST, 'index.html')):
    raise RuntimeError('web/dist is missing: run `npm run build` in web/ (or use ./run_glasses.sh)')


class Relay:
    """One shared tutor session fed by an external camera and watched by viewers."""

    def __init__(self):
        from vision.live_session import LiveClient
        self.session = LiveClient(name='glasses-camera')
        self.viewers = set()
        self.jpeg = None       # the newest frame, for the picture stream
        self.count = 0         # frames received (lets the picture stream wait for a new one)
        self.feeding = False

    async def broadcast(self, reply):
        for viewer in list(self.viewers):
            try:
                await viewer.send_json(reply)
            except Exception:  # a viewer that went away
                self.viewers.discard(viewer)

    async def handle(self, function, payload):
        """Runs a frame or command on the shared session; errors become replies."""
        from vision.live_session import ProtocolError
        try:
            return await run_in_threadpool(function, payload)
        except (ProtocolError, ValueError) as e:
            return {'type': 'error', 'code': 'BAD_REQUEST', 'message': str(e)}
        except Exception:
            log.exception('relay: error handling a message')
            return {'type': 'error', 'code': 'SERVER', 'message': 'internal error, see server log'}


_relay = None


def relay():
    global _relay
    if _relay is None:
        _relay = Relay()
    return _relay


@app.websocket('/ws/feed')
async def feed_socket(ws: WebSocket):
    """The camera uploader (the bridge app): binary frames as on /ws/live
    (4-byte id + JPEG). Each is answered with a short reply, so the uploader
    sends its next frame only when the last one is done; the full result goes
    to the viewers."""
    await ws.accept()
    r = relay()
    r.feeding = True
    log.info('camera feed connected from %s', ws.client.host if ws.client else '?')
    await r.broadcast({'type': 'feed', 'connected': True})
    try:
        while True:
            message = await ws.receive()
            if message['type'] == 'websocket.disconnect':
                break
            data = message.get('bytes')
            if data is None:
                continue
            reply = await r.handle(r.session.handle_frame, data)
            if reply.get('type') == 'frame':
                r.jpeg = data[4:]
                r.count += 1
            # Where the cube is in the frame that was sent (0..1), so the uploader can keep its
            # zoom window on the cube instead of only looking at the middle of the camera's view.
            short = {'type': reply.get('type'), 'frame': reply.get('frame'), 'ms': reply.get('ms'),
                     'found': bool(reply.get('keypoints')), 'message': reply.get('message')}
            if reply.get('keypoints'):
                xs = [p[0] for p in reply['keypoints']]
                ys = [p[1] for p in reply['keypoints']]
                short['cx'] = round((min(xs) + max(xs)) / 2 / reply['width'], 4)
                short['cy'] = round((min(ys) + max(ys)) / 2 / reply['height'], 4)
                short['size'] = round((max(xs) - min(xs)) / reply['width'], 4)
            await ws.send_json(short)
            await r.broadcast(reply)
    except WebSocketDisconnect:
        pass
    r.feeding = False
    await r.broadcast({'type': 'feed', 'connected': False})
    log.info('camera feed disconnected')


@app.websocket('/ws/view')
async def view_socket(ws: WebSocket):
    """A tutor page in remote-camera mode: receives every frame reply, and its
    commands (scan_start, scan_accept, track_skip...) act on the shared session."""
    await ws.accept()
    r = relay()
    r.viewers.add(ws)
    await ws.send_json({'type': 'feed', 'connected': r.feeding})
    try:
        while True:
            message = await ws.receive()
            if message['type'] == 'websocket.disconnect':
                break
            if message.get('text'):
                await r.broadcast(await r.handle(r.session.handle_command, json.loads(message['text'])))
    except WebSocketDisconnect:
        pass
    r.viewers.discard(ws)


@app.get('/feed.mjpg', include_in_schema=False)
async def feed_picture():
    """The camera picture the server is receiving, as a stream an <img> can show."""
    r = relay()

    async def frames():
        sent = -1
        while True:
            if r.jpeg is not None and r.count != sent:
                sent = r.count
                yield (b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ' + str(len(r.jpeg)).encode()
                       + b'\r\n\r\n' + r.jpeg + b'\r\n')
            await asyncio.sleep(0.02)

    return StreamingResponse(frames(), media_type='multipart/x-mixed-replace; boundary=frame')


@app.get('/glasses', include_in_schema=False)
def _glasses_slash():
    return RedirectResponse('/glasses/')  # relative asset paths need the trailing slash


app.mount('/glasses', StaticFiles(directory=DIST, html=True), name='glasses')
