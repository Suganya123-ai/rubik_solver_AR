import os
import sys

import cv2
import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from vision.reader import FACE_CORNERS, read_three_faces  # noqa: E402

COLORS = [(230, 230, 225), (250, 210, 30), (200, 30, 45), (250, 110, 25), (0, 155, 80), (0, 80, 190)]
# A hexagon like a cube seen corner-on (keypoint order from vision/detector.py).
KPTS = np.float32([[320, 250], [200, 180], [320, 110], [440, 180], [440, 330], [320, 400], [200, 330]])


def _draw_cube():
    """Paints each sticker of the three faces a known colour through the same
    face corners the reader uses, with black gaps between stickers."""
    img = np.zeros((480, 640, 3), np.uint8)
    unit = np.float32([[0, 0], [1, 0], [1, 1], [0, 1]])
    expected = {}
    for n, (face, idx) in enumerate(FACE_CORNERS.items()):
        hom = cv2.getPerspectiveTransform(unit, np.float32([KPTS[i] for i in idx]))
        expected[face] = []
        for k in range(9):
            r, c = divmod(k, 3)
            rgb = COLORS[(k + 2 * n) % 6]
            expected[face].append(rgb)
            g = 0.08
            cell = np.float32([[[(c + g) / 3, (r + g) / 3], [(c + 1 - g) / 3, (r + g) / 3],
                                [(c + 1 - g) / 3, (r + 1 - g) / 3], [(c + g) / 3, (r + 1 - g) / 3]]])
            quad = cv2.perspectiveTransform(cell, hom)[0]
            cv2.fillConvexPoly(img, np.round(quad).astype(np.int32), rgb[::-1])
    return img, expected


def test_reader_reads_each_sticker_through_the_corner_points():
    img, expected = _draw_cube()
    got = read_three_faces(img, KPTS)
    for face in FACE_CORNERS:
        for (r, g, b), (er, eg, eb) in zip(got[face], expected[face]):
            assert max(abs(r - er), abs(g - eg), abs(b - eb)) <= 2


def test_reader_marks_off_frame_stickers_as_missing():
    img, _ = _draw_cube()
    got = read_three_faces(img, KPTS + np.float32([2000, 0]))
    assert all(c is None for face in got.values() for c in face)


MODEL = os.path.join(ROOT, 'models', 'cube_pose_synthetic.pt')
SAMPLE = os.path.join(ROOT, 'docs', 'test_images', 'tracking_normal', 'trial1_before.jpg')
needs_model = pytest.mark.skipif(not (os.path.exists(MODEL) and os.path.exists(SAMPLE)),
                                 reason='needs the trained model and a sample frame')


@needs_model
def test_live_socket_finds_cube_and_saves_frame(tmp_path, monkeypatch):
    pytest.importorskip('ultralytics')
    from fastapi.testclient import TestClient

    import main
    import vision.live

    monkeypatch.setattr(vision.live, 'CAPTURE_DIR', str(tmp_path / 'captures'))
    jpeg = open(SAMPLE, 'rb').read()
    with TestClient(main.app).websocket_connect('/ws/live') as ws:
        ws.send_bytes((7).to_bytes(4, 'big') + jpeg)
        reply = ws.receive_json()
        assert reply['type'] == 'frame' and reply['frame'] == 7
        assert len(reply['keypoints']) == 7 and reply['confidence'] > 0.5
        assert all(len(reply['faces'][f]) == 9 for f in 'UFR')

        ws.send_text('{"type": "save"}')
        saved = ws.receive_json()
        assert saved['type'] == 'saved' and saved['count'] == 1 and saved['prelabelled']
    day_dirs = list((tmp_path / 'captures').iterdir())
    files = sorted(p.suffix for p in day_dirs[0].iterdir())
    assert files == ['.jpg', '.txt']
    label = (day_dirs[0] / next(p.name for p in day_dirs[0].iterdir() if p.suffix == '.txt')).read_text().split()
    assert len(label) == 5 + 7 * 3  # YOLO pose format: class, box, 7 x (x, y, visible)


@needs_model
def test_live_socket_reports_bad_image():
    pytest.importorskip('ultralytics')
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app).websocket_connect('/ws/live') as ws:
        ws.send_bytes((1).to_bytes(4, 'big') + b'not a jpeg')
        assert ws.receive_json()['type'] == 'error'


def test_server_has_websocket_support():
    # uvicorn without a WebSocket library answers /ws/live with 404; the test
    # client above bypasses uvicorn, so check the dependency directly.
    import importlib.util
    assert importlib.util.find_spec('websockets') or importlib.util.find_spec('wsproto')


def _make_capture(tmp_path, stem='120000_000001'):
    day = tmp_path / 'captures' / '2026-01-01'
    day.mkdir(parents=True, exist_ok=True)
    img, _ = _draw_cube()
    cv2.imwrite(str(day / f'{stem}.jpg'), img)
    return f'2026-01-01/{stem}'


def test_label_round_trip_and_review_state(tmp_path, monkeypatch):
    import vision.captures as caps
    monkeypatch.setattr(caps, 'CAPTURE_DIR', str(tmp_path / 'captures'))
    cid = _make_capture(tmp_path)
    assert caps.list_captures() == [{'id': cid, 'reviewed': False}]
    guess = caps.read_label(cid, predict=lambda frame: (KPTS + 3, 0.9))
    assert guess['source'] == 'model' and not guess['reviewed'] and guess['width'] == 640

    caps.write_label(cid, KPTS.tolist())
    back = caps.read_label(cid, predict=lambda frame: None)
    assert back['reviewed'] and back['source'] == 'reviewed'
    assert np.abs(np.float32(back['keypoints']) - KPTS).max() < 0.01
    assert caps.list_captures()[0]['reviewed']


def test_no_cube_label_and_delete(tmp_path, monkeypatch):
    import vision.captures as caps
    monkeypatch.setattr(caps, 'CAPTURE_DIR', str(tmp_path / 'captures'))
    cid = _make_capture(tmp_path)
    caps.write_label(cid, None)
    label = caps.read_label(cid, predict=lambda frame: (KPTS, 0.9))
    assert label['reviewed'] and label['keypoints'] is None  # a reviewed "no cube" isn't overridden by the model
    caps.delete_capture(cid)
    assert caps.list_captures() == []


def test_capture_ids_cannot_escape_the_folder(tmp_path, monkeypatch):
    import vision.captures as caps
    monkeypatch.setattr(caps, 'CAPTURE_DIR', str(tmp_path / 'captures'))
    with pytest.raises((ValueError, FileNotFoundError)):
        caps.read_label('../../etc/passwd')


@needs_model
def test_socket_survives_bad_messages():
    pytest.importorskip('ultralytics')
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app).websocket_connect('/ws/live') as ws:
        ws.send_text('not json')
        assert ws.receive_json()['type'] == 'error'
        ws.send_text('{"type": "unknown"}')
        assert ws.receive_json()['code'] == 'BAD_REQUEST'
        ws.send_text('{"type": "ping"}')
        assert ws.receive_json() == {'type': 'pong'}           # still connected


def test_health_endpoint():
    from fastapi.testclient import TestClient

    import main

    body = TestClient(main.app).get('/health').json()
    assert body['ok'] and body['model'].endswith('.pt')
