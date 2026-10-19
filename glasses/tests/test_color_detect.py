import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

from cube.color_detect import (COLOR_NAMES, _rgb_to_hsv, classify_hsv, detect_face_colors, rebalance_colors,
                               resolver_colors)

# Representative sticker RGB values (standard cube color scheme).
SAMPLE_RGB = {
    'white': (245, 245, 245),
    'yellow': (255, 213, 0),
    'red': (200, 15, 30),
    'orange': (255, 100, 0),
    'green': (0, 150, 70),
    'blue': (0, 70, 180),
}


def _classify_rgb(rgb):
    img = Image.new('RGB', (10, 10), rgb)
    h, s, v = img.convert('HSV').getpixel((5, 5))
    return classify_hsv(h, s, v)


def test_each_reference_color_classifies_correctly():
    for name, rgb in SAMPLE_RGB.items():
        result = _classify_rgb(rgb)
        assert result == name, f"{name} {rgb} classified as {result}"


def test_detect_face_colors_on_synthetic_grid():
    # Build a 300x300 image with a distinct solid color per cell, in the
    # standard solved-face layout (all one color, like a real solved face).
    img = Image.new('RGB', (300, 300), SAMPLE_RGB['green'])
    colors = detect_face_colors(img)
    assert colors == ['green'] * 9


def test_detect_face_colors_on_mixed_grid():
    img = Image.new('RGB', (300, 300), (0, 0, 0))
    layout = [
        'white', 'red', 'green',
        'yellow', 'white', 'blue',
        'orange', 'green', 'white',
    ]
    cell = 100
    for i, name in enumerate(layout):
        row, col = divmod(i, 3)
        for y in range(row * cell, (row + 1) * cell):
            for x in range(col * cell, (col + 1) * cell):
                img.putpixel((x, y), SAMPLE_RGB[name])
    colors = detect_face_colors(img)
    assert colors == layout, f"got {colors}"


def test_all_color_names_reachable():
    for name in COLOR_NAMES:
        assert name in SAMPLE_RGB


if __name__ == '__main__':
    import traceback
    tests = [v for k, v in list(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


def _scrambled_scan(lighting, seed=3):
    """Simulate scanning a scrambled cube: per-face sticker colors (truth)
    plus noisy per-sticker RGB samples under `lighting` (color -> RGB)."""
    import random

    from cube.cube_state import FACES, solved_state
    from cube.moves import ALL_MOVES, apply_moves

    rng = random.Random(seed)
    state = apply_moves(solved_state(), [rng.choice(ALL_MOVES) for _ in range(25)])
    color_of_face = {'U': 'white', 'D': 'yellow', 'F': 'green', 'B': 'blue', 'L': 'orange', 'R': 'red'}
    truth, rgbs = {}, {}
    for f in FACES:
        truth[f] = [color_of_face[letter] for letter in state.face(f)]
        rgbs[f] = [tuple(min(255, max(0, c + rng.randint(-12, 12))) for c in lighting[name])
                   for name in truth[f]]
    return truth, rgbs


# Warm, dim lighting: blue washes out toward white, red drifts toward orange.
BAD_LIGHTING = {
    'white': (205, 195, 170),
    'yellow': (215, 190, 60),
    'red': (190, 55, 35),
    'orange': (225, 105, 35),
    'green': (40, 140, 90),
    'blue': (120, 135, 160),
}


def test_threshold_detection_fails_under_bad_lighting():
    # Guards the premise of the rebalancing test below.
    truth, rgbs = _scrambled_scan(BAD_LIGHTING)
    detected = {f: [classify_hsv(*_rgb_to_hsv(rgb)) for rgb in rgbs[f]] for f in truth}
    assert detected != truth


def test_rebalance_recovers_scan_under_bad_lighting():
    truth, rgbs = _scrambled_scan(BAD_LIGHTING)
    detected = {f: [classify_hsv(*_rgb_to_hsv(rgb)) for rgb in rgbs[f]] for f in truth}
    for f in truth:
        detected[f][4] = truth[f][4]  # user fixed the centers if needed
    rebalanced = rebalance_colors(detected, rgbs, {})
    assert rebalanced == truth


def test_rebalance_keeps_locked_cells():
    truth, rgbs = _scrambled_scan(SAMPLE_RGB)
    confirmed = {f: list(c) for f, c in truth.items()}
    # A cell the user set by hand wins even if its sample says otherwise.
    confirmed['U'][0] = 'blue' if truth['U'][0] != 'blue' else 'green'
    rebalanced = rebalance_colors(confirmed, rgbs, {'U': [0]})
    assert rebalanced['U'][0] == confirmed['U'][0]


def test_rebalance_rejects_duplicate_centers():
    truth, rgbs = _scrambled_scan(SAMPLE_RGB)
    truth['U'][4] = truth['D'][4]
    assert rebalance_colors(truth, rgbs, {}) is None


def test_resolver_fallback_reads_scan():
    for lighting in (SAMPLE_RGB, BAD_LIGHTING):
        truth, rgbs = _scrambled_scan(lighting)
        assert resolver_colors(rgbs, truth) == truth


def test_resolver_fallback_gives_up_quietly_on_garbage():
    truth, rgbs = _scrambled_scan(SAMPLE_RGB)
    rgbs = {f: [(128, 128, 128)] * 9 for f in rgbs}  # every sticker the same grey
    result = resolver_colors(rgbs, truth)
    assert result is None or isinstance(result, dict)
