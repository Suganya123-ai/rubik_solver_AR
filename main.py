import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from cube.color_detect import COLOR_NAMES, detect_face_colors_from_base64
from cube.cube_state import FACES
from cube.solver import SolverError, enrich, solve
from cube.validation import validate_scan

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = FastAPI(title="Rubik's Cube Solver")
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')

# Single-user, in-memory session -- this is a local personal tool, no auth
# or multi-user support needed.
SESSION = {
    'confirmed': {},   # face letter -> list of 9 color names
    'instructions': [],  # enriched MoveInstruction dicts, once solved
    'step_index': 0,
}


class ScanFaceRequest(BaseModel):
    face: str
    image: str


class ConfirmFaceRequest(BaseModel):
    face: str
    colors: list[str]


def _require_face(face):
    if face not in FACES:
        raise HTTPException(400, f"Unknown face '{face}', expected one of {FACES}")


@app.get('/')
def index():
    return FileResponse(os.path.join(STATIC_DIR, 'index.html'))


@app.post('/api/scan-face')
def scan_face(req: ScanFaceRequest):
    _require_face(req.face)
    try:
        colors = detect_face_colors_from_base64(req.image)
    except Exception as e:
        raise HTTPException(400, f"Couldn't read that image: {e}")
    return {'face': req.face, 'colors': colors}


@app.post('/api/confirm-face')
def confirm_face(req: ConfirmFaceRequest):
    _require_face(req.face)
    if len(req.colors) != 9:
        raise HTTPException(400, f"Expected 9 colors, got {len(req.colors)}")
    for c in req.colors:
        if c not in COLOR_NAMES:
            raise HTTPException(400, f"Unknown color '{c}', expected one of {COLOR_NAMES}")
    SESSION['confirmed'][req.face] = req.colors
    remaining = [f for f in FACES if f not in SESSION['confirmed']]
    return {'ok': True, 'confirmed_faces': list(SESSION['confirmed'].keys()), 'remaining_faces': remaining}


@app.post('/api/build-and-solve')
def build_and_solve():
    missing = [f for f in FACES if f not in SESSION['confirmed']]
    if missing:
        raise HTTPException(400, f"Still need to scan: {missing}")

    state, result = validate_scan(SESSION['confirmed'])
    if not result.ok:
        raise HTTPException(422, {'error_code': result.error_code, 'message': result.message})

    try:
        moves, stage_bounds = solve(state)
    except SolverError as e:
        raise HTTPException(500, f"Solver error: {e}")

    instructions = enrich(moves, stage_bounds)
    SESSION['instructions'] = [instr.__dict__ for instr in instructions]
    SESSION['step_index'] = 0
    return {'total_steps': len(instructions), 'step': _current_step()}


def _current_step():
    instructions = SESSION['instructions']
    index = SESSION['step_index']
    if not instructions:
        return None
    if index >= len(instructions):
        return {'done': True, 'total_steps': len(instructions)}
    return {'done': False, **instructions[index]}


@app.get('/api/step')
def get_step():
    if not SESSION['instructions']:
        raise HTTPException(400, "No solution yet -- call /api/build-and-solve first")
    return _current_step()


@app.post('/api/step/next')
def next_step():
    if not SESSION['instructions']:
        raise HTTPException(400, "No solution yet -- call /api/build-and-solve first")
    SESSION['step_index'] = min(SESSION['step_index'] + 1, len(SESSION['instructions']))
    return _current_step()


@app.post('/api/step/back')
def back_step():
    if not SESSION['instructions']:
        raise HTTPException(400, "No solution yet -- call /api/build-and-solve first")
    SESSION['step_index'] = max(SESSION['step_index'] - 1, 0)
    return _current_step()


@app.post('/api/reset')
def reset():
    SESSION['confirmed'] = {}
    SESSION['instructions'] = []
    SESSION['step_index'] = 0
    return {'ok': True}
