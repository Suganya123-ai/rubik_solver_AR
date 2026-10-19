"""Where the self-improving loop reads from and writes to. Override with environment variables:
AUTOLEARN_APPS (folders whose saved demo frames are used, separated by ':'), AUTOLEARN_REPLAY_PYRA /
AUTOLEARN_REPLAY_CUBE (folders of the earlier training pictures, mixed in so nothing is forgotten)."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.dirname(ROOT)
MODELS = os.path.join(ROOT, 'models')
WORK = os.path.join(ROOT, 'data', 'autolearn')

# the app folders on this laptop: every demo's saved frames feed the loop (read only)
DEFAULT_APPS = ['rubik_solver_AR_webcam', 'rubik_solver_AR_anyside', 'rubik_solver_AR_glasses',
                'rubik_solver_AR_pyraminx', 'rubik_solver_AR_autolearn', 'rubik_solver_AR_laptop_voice',
                'rubik_solver_AR_assistant', os.path.basename(ROOT)]
# the earlier training pictures (images/<split> + labels/<split>), from the folders they were made in
_PYRA = os.path.join(HOME, 'rubik_solver_AR_pyraminx', 'bench', 'data')
_CUBE = os.path.join(HOME, 'rubik_solver_AR_anyside', 'bench', 'data')
REPLAY = {
    'pyra': [os.path.join(_PYRA, d) for d in ('pyra_v1_subset', 'pyra_hard', 'pyra_real_hands', 'pyra_edge', 'pyra_edge_hands')],
    # not real_pseudo: real frames from the same recordings the real test comes from
    'cube': [os.path.join(_CUBE, d) for d in ('yolo_v3', 'v2_subset')],
}
# the fixed drawn test pictures a new model must not get worse on
SYNTH_TEST = {
    'pyra': [os.path.join(_PYRA, d, 'images', 'val') for d in ('pyra_edge', 'pyra_v1', 'pyra_hard')],
    'cube': [os.path.join(_CUBE, 'yolo_v3', 'images', 'val')],
}
BASE_MODEL = {'pyra': 'pyra_pose_v3.pt', 'cube': 'cube_pose_v3.pt'}
# Sessions that are not real camera frames: test videos of drawn puzzles played to the apps during
# development. More can be listed, one '<app folder>/<sessions|pyra_sessions>/<day>/<time>' per line,
# in data/autolearn/exclude.txt.
EXCLUDE = {
    'rubik_solver_AR_webcam/sessions/2026-10-12/014119',
    'rubik_solver_AR_webcam/sessions/2026-10-12/014245',
    'rubik_solver_AR_webcam/sessions/2026-10-12/120130',
}


def excluded():
    out = set(EXCLUDE)
    path = os.path.join(WORK, 'exclude.txt')
    if os.path.exists(path):
        out |= {line.strip() for line in open(path) if line.strip() and not line.startswith('#')}
    return out


def apps():
    env = os.environ.get('AUTOLEARN_APPS')
    names = env.split(':') if env else DEFAULT_APPS
    paths = [n if os.path.isabs(n) else os.path.join(HOME, n) for n in names]
    return list(dict.fromkeys(p for p in paths if os.path.isdir(p)))   # (each folder once)


def replay(puzzle):
    env = os.environ.get(f'AUTOLEARN_REPLAY_{puzzle.upper()}')
    dirs = env.split(':') if env else REPLAY[puzzle]
    return [d for d in dirs if os.path.isdir(os.path.join(d, 'images', 'train'))]
