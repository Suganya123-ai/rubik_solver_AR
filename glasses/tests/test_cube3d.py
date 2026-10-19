"""The 3D cube in the browser (static/cube3d.js) turns layers with its own
geometry; this checks every move ends exactly where the move engine says.
Needs Node.js; skipped without it."""
import json
import os
import random
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cube.cube_state import CubeState, solved_state  # noqa: E402
from cube.moves import ALL_MOVES, apply_moves  # noqa: E402


@pytest.mark.skipif(shutil.which('node') is None, reason='needs Node.js')
def test_3d_cube_moves_match_the_move_engine():
    rng = random.Random(3)
    cases = []
    for i in range(3 * len(ALL_MOVES)):
        state = apply_moves(solved_state(), [rng.choice(ALL_MOVES) for _ in range(20)])
        move = ALL_MOVES[i % len(ALL_MOVES)]
        cases.append([''.join(state.arr), move, ''.join(apply_moves(CubeState(state.arr.copy()), [move]).arr)])
    script = ("const {applyMove} = require('./static/cube3d.js');"
              f"const cases = {json.dumps(cases)};"
              "console.log(JSON.stringify(cases.filter(([s, m, e]) => applyMove(s, m) !== e).map(c => c[1])));")
    out = subprocess.run(['node', '-e', script], capture_output=True, text=True, cwd=ROOT, check=True)
    assert json.loads(out.stdout) == []
