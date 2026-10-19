import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def _face(center, fill='red'):
    colors = [fill] * 9
    colors[4] = center
    return colors


def test_confirming_same_side_twice_is_rejected():
    client.post('/api/reset')
    assert client.post('/api/confirm-face', json={'face': 'U', 'colors': _face('white')}).status_code == 200
    res = client.post('/api/confirm-face', json={'face': 'F', 'colors': _face('white')})
    assert res.status_code == 409
    assert 'Top (U)' in res.json()['detail']
    assert 'F' not in client.post('/api/confirm-face', json={'face': 'R', 'colors': _face('blue')}).json()['confirmed_faces']


def test_rescanning_the_same_slot_is_allowed():
    client.post('/api/reset')
    assert client.post('/api/confirm-face', json={'face': 'U', 'colors': _face('white')}).status_code == 200
    assert client.post('/api/confirm-face', json={'face': 'U', 'colors': _face('white', 'blue')}).status_code == 200


def test_state_returns_captured_sides_for_restore():
    client.post('/api/reset')
    client.post('/api/confirm-face', json={'face': 'U', 'colors': _face('white')})
    assert client.get('/api/state').json() == {'confirmed': {'U': _face('white')}}
    client.post('/api/reset')
    assert client.get('/api/state').json() == {'confirmed': {}}


def test_resolver_rescues_scan_when_rebalance_cannot(monkeypatch):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
    from test_color_detect import BAD_LIGHTING, _scrambled_scan

    truth, rgbs = _scrambled_scan(BAD_LIGHTING)
    client.post('/api/reset')
    for f in truth:
        wrong = list(truth[f])
        wrong[0], wrong[8] = wrong[8], wrong[0]  # corrupt two stickers so validation fails...
        if wrong == truth[f]:
            wrong[1], wrong[7] = wrong[7], wrong[1]
        main.SESSION['scans'][f] = {'colors': wrong, 'rgbs': rgbs[f]}
        main.SESSION['confirmed'][f] = wrong
    monkeypatch.setattr(main, 'rebalance_colors', lambda *a, **k: None)  # ...and rebalance gives up
    res = client.post('/api/build-and-solve')
    assert res.status_code == 200, res.json()
    assert main.SESSION['confirmed'] == truth
    assert res.json()['total_steps'] <= 22
