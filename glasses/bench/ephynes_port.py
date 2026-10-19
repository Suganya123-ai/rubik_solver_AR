"""Faithful Python port of ephynes/AR-Optimal-Rubiks-Cube-solver's face
detection (VideoCapture.ProcessImage, Rhombus, TileLayoutAlgorithm,
RubikFace.ProcessRhombuses) and per-face colour recognition
(ColorRecognition.Face). Same thresholds; the C# runs on 1280x720 frames, so
frames are scaled to 1280 px wide first and results scaled back."""
import math

import cv2
import numpy as np

WORK_W = 1280
# ColorTileEnum.rubikColor (RGB), in values() order.
RUBIK_RGB = {'red': (220, 20, 30), 'orange': (240, 80, 0), 'yellow': (230, 230, 20),
             'green': (0, 140, 60), 'blue': (0, 60, 220), 'white': (225, 225, 225)}


class Rhombus:
    def __init__(self, poly):
        self.poly = [tuple(map(int, p)) for p in poly.reshape(-1, 2)]
        self.status = 'NOT_PROCESSED'

    def qualify(self):
        xs = sum(p[0] for p in self.poly)
        ys = sum(p[1] for p in self.poly)
        self.center = (int(xs) // len(self.poly), int(ys) // len(self.poly))
        if len(self.poly) != 4:
            self.status = 'NOT_4_POINTS'
            return
        if not cv2.isContourConvex(np.array(self.poly, np.int32).reshape(-1, 1, 2)):
            self.status = 'NOT_CONVEX'
            return
        self.area = area_quad(self.poly)
        if self.area < 1000 or self.area > 10000:
            self.status = 'AREA'
            return
        if self.adjust():
            self.status = 'CLOCKWISE'
            return
        p = self.poly
        self.alpha = 180 / math.pi * math.atan2((p[1][1] - p[0][1]) + (p[2][1] - p[3][1]), (p[1][0] - p[0][0]) + (p[2][0] - p[3][0]))
        self.beta = 180 / math.pi * math.atan2((p[2][1] - p[1][1]) + (p[3][1] - p[0][1]), (p[2][0] - p[1][0]) + (p[3][0] - p[0][0]))
        al = (dist(p[0], p[1]) + dist(p[3], p[2])) / 2
        bl = (dist(p[0], p[3]) + dist(p[1], p[2])) / 2
        self.gamma = bl / al
        self.status = 'VALID'

    def adjust(self):
        index = min(range(4), key=lambda i: (self.poly[i][1], i))  # first minimum y
        for _ in range(index):
            self.poly = self.poly[1:] + self.poly[:1]
        return self.poly[1][0] < self.poly[3][0]


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def tri(a, b, c):
    v = (a + b - c) * (a - b + c) * (-a + b + c) * (a + b + c)
    return math.sqrt(v) / 4 if v > 0 else (float('nan') if v < 0 else 0.0)


def area_quad(q):
    return tri(dist(q[0], q[1]), dist(q[1], q[2]), dist(q[2], q[0])) + tri(dist(q[0], q[3]), dist(q[3], q[2]), dist(q[2], q[0]))


def remove_outliers(rl):
    if len(rl) < 3:
        return
    mid = len(rl) // 2
    rl.sort(key=lambda r: r.alpha)
    med_a = rl[mid].alpha
    rl.sort(key=lambda r: r.beta)
    med_b = rl[mid].beta
    i = 0
    while i < len(rl):  # C# removes while iterating with i++, skipping the next element
        r = rl[i]
        if abs(r.alpha - med_a) > 10 or abs(r.beta - med_b) > 10:
            rl.remove(r)
        i += 1


def initial_layout(rl, alpha, beta):
    ga = lambda r: int(r.center[0] * math.cos(alpha) + r.center[1] * math.sin(alpha))
    gb = lambda r: int(r.center[0] * math.cos(beta) + r.center[1] * math.sin(beta))

    def sets(key):
        s = sorted(rl, key=key)
        n = len(s)
        best, bp, bq = float('inf'), 0, 0
        sse = lambda sub: sum((key(sub[i]) - key(sub[j])) ** 2 for i in range(len(sub) - 1) for j in range(i + 1, len(sub)))
        for p in range(1, n - 1):
            for q in range(p + 1, n):
                e = sse(s[0:p]) + sse(s[p:q]) + sse(s[q:n])
                if e < best:
                    best, bp, bq = e, p, q
        return [s[0:bp], s[bp:bq], s[bq:n]]

    a_sets, b_sets = sets(ga), sets(gb)
    arr = [[None] * 3 for _ in range(3)]
    for n in range(3):
        for m in range(3):
            common = [r for r in a_sets[n] if r in b_sets[m]]
            arr[n][m] = common[0] if common else None
    for n in range(3):
        if all(arr[n][m] is None for m in range(3)):
            return None
    for m in range(3):
        if all(arr[n][m] is None for n in range(3)):
            return None
    return arr


def lms(arr, alpha, beta, gamma):
    A, Y = [], []
    for n in range(3):
        for m in range(3):
            r = arr[n][m]
            if r is not None:
                A.append([1.0, 0.0, n * math.cos(alpha) + gamma * m * math.cos(beta)]); Y.append(r.center[0])
                A.append([0.0, 1.0, n * math.sin(alpha) + gamma * m * math.sin(beta)]); Y.append(r.center[1])
    A, Y = np.array(A), np.array(Y, float)
    try:
        X = np.linalg.solve(A.T @ A, A.T @ Y)  # Cv2.Solve(..., DecompTypes.Normal)
    except np.linalg.LinAlgError:
        return None
    sigma = float(np.sqrt(((Y - A @ X) ** 2).sum()))
    if np.isnan(X).any() or np.isnan(sigma):
        return None
    return X[0], X[1], X[2], sigma


def detect_face(frame, work_w=WORK_W):
    """Returns (9 tile centres in raster order, 9 colour names) or None."""
    scale = work_w / frame.shape[1]
    img = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR) if scale != 1 else frame
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(g, (7, 7), 0)
    g = cv2.Canny(g, 100, 100)
    g = cv2.dilate(g, cv2.getStructuringElement(cv2.MORPH_RECT, (10, 10)))
    contours, _ = cv2.findContours(g, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    rl = []
    for c in contours:
        a = cv2.contourArea(c, True)
        if a < 0 or a < 100:
            continue
        poly = cv2.approxPolyDP(c.astype(np.float32), 30, True).astype(np.int32)
        r = Rhombus(poly)
        r.qualify()
        if r.status == 'VALID':
            rl.append(r)
    remove_outliers(rl)
    if len(rl) < 3:
        return None
    alpha = sum(r.alpha for r in rl) / len(rl) * math.pi / 180
    beta = sum(r.beta for r in rl) / len(rl) * math.pi / 180
    gamma = sum(r.gamma for r in rl) / len(rl)
    arr = initial_layout(rl, alpha, beta)
    if arr is None:
        return None
    fit = lms(arr, alpha, beta, gamma)
    if fit is None:
        return None
    moves = 0
    while fit[3] > 35:
        if moves > 5:
            return None
        ox, oy, al, _ = fit
        bl = gamma * al
        worst, wn, wm, werr = None, 0, 0, -1
        for n in range(3):
            for m in range(3):
                r = arr[n][m]
                if r is not None:
                    tx = ox + n * al * math.cos(alpha) + m * bl * math.cos(beta)
                    ty = oy + n * al * math.sin(alpha) + m * bl * math.sin(beta)
                    e = math.hypot(r.center[0] - tx, r.center[1] - ty)
                    if e > werr:
                        worst, wn, wm, werr = r, n, m, e
        ex = worst.center[0] - (ox + wn * al * math.cos(alpha) + wm * bl * math.cos(beta))
        ey = worst.center[1] - (oy + wn * al * math.sin(alpha) + wm * bl * math.sin(beta))
        dn = round((ex * math.cos(alpha) + ey * math.sin(alpha)) / al)
        dm = round((ex * math.cos(beta) + ey * math.sin(beta)) / bl)
        nn, nm = min(max(wn + dn, 0), 2), min(max(wm + dm, 0), 2)
        if (nn, nm) == (wn, wm):
            return None
        arr[nn][nm], arr[wn][wm] = arr[wn][wm], arr[nn][nm]
        moves += 1
        fit = lms(arr, alpha, beta, gamma)
        if fit is None:
            return None
    ox, oy, al, _ = fit
    bl = gamma * al
    centres, colours = [], []
    H, Wd = img.shape[:2]
    for m in range(3):          # beta direction ~ rows
        for n in range(3):      # alpha direction ~ columns
            x = ox + n * al * math.cos(alpha) + m * bl * math.cos(beta)
            y = oy + n * al * math.sin(alpha) + m * bl * math.sin(beta)
            centres.append((x / scale, y / scale))
            if x < 10 or x > Wd - 10 or y < 10 or y > H - 10:
                rgb = (0.0, 0.0, 0.0)
            else:
                b, gg, r = img[int(y) - 10:int(y) + 10, int(x) - 10:int(x) + 10].reshape(-1, 3).mean(axis=0)
                rgb = (r, gg, b)
            colours.append(rgb)
    return centres, face_colours(colours)


def yuv(rgb):
    r, g, b = rgb[:3]
    return (0.229 * r + 0.587 * g + 0.114 * b, -0.147 * r - 0.289 * g + 0.436 * b, 0.615 * r - 0.515 * g - 0.100 * b)


def face_colours(rgbs):
    """ColorRecognition.Face: nearest expected colour on U,V; then a luminosity
    offset from the non-red/orange tiles and a second pass on Y,U,V."""
    cand = {k: yuv(v) for k, v in RUBIK_RGB.items()}
    first = []
    for rgb in rgbs:
        _, u, v = yuv(rgb)
        first.append(min(cand, key=lambda k: (cand[k][1] - u) ** 2 + (cand[k][2] - v) ** 2))
    offs = [cand[c][0] - yuv(rgb)[0] for c, rgb in zip(first, rgbs) if c not in ('red', 'orange')]
    lum = sum(offs) / len(offs) if offs else 0.0
    out = []
    for rgb in rgbs:
        y, u, v = yuv(rgb)
        out.append(min(cand, key=lambda k: (cand[k][0] - (y + lum)) ** 2 + (cand[k][1] - u) ** 2 + (cand[k][2] - v) ** 2))
    return out


def ephynes_detect(frame):
    out = detect_face(frame)
    return None if out is None else out[0]


def ephynes_multiscale_detect(frame):
    """Our tweak: its sticker-area window (1000-10000 px at 1280 wide) only
    fits one cube distance, so also try smaller working sizes."""
    for w in (1280, 960, 640, 480):
        out = detect_face(frame, work_w=w)
        if out is not None:
            return out[0]
    return None
