"""The Pyraminx tutor's vision server (branch `pyraminx`): the camera link and the puzzle layout.

    uvicorn main_pyra:app --port 8102        (run_pyra.sh starts it with the web app)
"""
import json
import logging
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
log = logging.getLogger('rubik.pyra')
app = FastAPI(title='Pyraminx Tutor')


@app.websocket('/ws/live')
async def live_socket(ws: WebSocket):
    from pyra.live import ProtocolError, PyraClient
    await ws.accept()
    client = PyraClient(name=f'{ws.client.host}:{ws.client.port}' if ws.client else 'client')
    log.info('%s connected', client.name)
    try:
        while True:
            message = await ws.receive()
            if message['type'] == 'websocket.disconnect':
                break
            try:
                if message.get('bytes') is not None:
                    reply = await run_in_threadpool(client.handle_frame, message['bytes'])
                elif message.get('text'):
                    reply = await run_in_threadpool(client.handle_command, json.loads(message['text']))
                else:
                    continue
            except (ProtocolError, ValueError) as e:
                reply = {'type': 'error', 'code': 'BAD_REQUEST', 'message': str(e)}
            except Exception:
                log.exception('%s: error handling a message', client.name)
                reply = {'type': 'error', 'code': 'SERVER', 'message': 'internal error, see server log'}
            await ws.send_json(reply)
    except WebSocketDisconnect:
        pass
    log.info('%s disconnected', client.name)


@app.get('/api/pyra/geometry')
def geometry():
    from pyra.live import geometry_json
    return geometry_json()


@app.get('/health')
def health():
    from pyra import live
    return {'ok': True, 'model': os.path.basename(live.MODEL_PATH), 'model_loaded': live._detector is not None,
            'model_exists': os.path.exists(live.MODEL_PATH)}
