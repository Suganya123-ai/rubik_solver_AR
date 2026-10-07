import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

from cube.color_detect import COLOR_NAMES, classify_hsv, detect_face_colors

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
