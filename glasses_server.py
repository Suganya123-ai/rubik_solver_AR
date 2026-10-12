"""The vision server plus the built glasses web app, in one program.

    uvicorn glasses_server:app --host 0.0.0.0 --port 5273 --ssl-keyfile ... --ssl-certfile ...

The Beam Pro opens https://<laptop>:5273/glasses/ . Serving the page from the
Python server (instead of the Node dev server) means one process, one address,
and it is the program macOS's firewall already allows to accept connections.
The web app is built into web/dist by `npm run build` (run_glasses.sh does it).
"""
import os

from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from main import app

DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web', 'dist')
if not os.path.isfile(os.path.join(DIST, 'index.html')):
    raise RuntimeError('web/dist is missing: run `npm run build` in web/ (or use ./run_glasses.sh)')


@app.get('/glasses', include_in_schema=False)
def _glasses_slash():
    return RedirectResponse('/glasses/')  # relative asset paths need the trailing slash


app.mount('/glasses', StaticFiles(directory=DIST, html=True), name='glasses')
