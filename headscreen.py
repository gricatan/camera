"""HeadScreen : remplace ta tête par un cube-écran 3D suivi en temps réel
(caméra virtuelle OBS). Les gestes des mains changent l'expression.
Touches (fenêtre d'aperçu) : 1 visage | 2 texte | 3 matrix | 4 image perso (dossier avatars/)
                             n style suivant | a image suivante | c calibrer | b bezel
                             q quitter
Gestes : pouce levé=content | main ouverte=HELLO | V=coeurs | poing=colère | main devant le visage=?
"""
import argparse
import math
import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

CW, CH = 560, 480           # canvas de la face écran
BEZEL = 26
MATRIX_GREEN = (80, 255, 90)

# Styles d'avatar (touche N) : couleur (BGR), forme des yeux, effet de rendu
THEMES = [
    {"name": "Neon",      "color": (255, 240, 40),  "eyes": "rect",  "post": None},
    {"name": "Pixel LED", "color": (0, 180, 255),   "eyes": "rect",  "post": "dots"},
    {"name": "Retro CRT", "color": (80, 255, 90),   "eyes": "round", "post": "crt"},
    {"name": "Robot",     "color": (60, 60, 255),   "eyes": "visor", "post": None},
    {"name": "Mignon",    "color": (220, 120, 255), "eyes": "cute",  "post": None},
]
THEME = THEMES[0]
ACCENT = THEME["color"]
AVATAR_DIR = Path(__file__).parent / "avatars"   # tes images perso (ignorées par git)


def clamp(v, a, b):
    return max(a, min(b, v))


def lerp(a, b, t):
    return a + (b - a) * t


# ================================================================ tracking visage
class Tracker:
    def __init__(self):
        self.fm = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1, refine_landmarks=True,
            min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.state = None
        self.neutral_pitch = 0.42
        self.last_ratio = 0.42
        self.last_seen = 0.0

    def calibrate(self):
        self.neutral_pitch = self.last_ratio

    def update(self, frame):
        h, w = frame.shape[:2]
        res = self.fm.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if not res.multi_face_landmarks:
            return None if time.time() - self.last_seen > 0.6 else self.state
        self.last_seen = time.time()
        p = np.array([[l.x * w, l.y * h] for l in res.multi_face_landmarks[0].landmark])

        top, chin = p[10], p[152]
        size = float(np.linalg.norm(chin - top))
        face_w = float(np.linalg.norm(p[454] - p[234]))
        center = (top + chin) / 2 + np.array([0, -0.06 * size])

        v = p[263] - p[33]
        roll = math.atan2(v[1], v[0])
        yaw = clamp((p[1][0] - (p[234][0] + p[454][0]) / 2) / (face_w / 2), -1, 1) * 1.15
        ratio = (p[1][1] - p[168][1]) / max(1.0, chin[1] - p[168][1])
        self.last_ratio = ratio
        pitch = clamp((ratio - self.neutral_pitch) * 3.0, -0.7, 0.7)

        def gaze(iris, outer, inner, up, low):
            gx = (p[iris][0] - p[outer][0]) / (p[inner][0] - p[outer][0] + 1e-6) - 0.5
            gy = (p[iris][1] - p[up][1]) / (p[low][1] - p[up][1] + 1e-6) - 0.5
            return gx, gy

        lx, ly = gaze(468, 33, 133, 159, 145)
        rx, ry = gaze(473, 362, 263, 386, 374)
        gx, gy = clamp((lx + rx), -0.6, 0.6), clamp((ly + ry), -0.6, 0.6)

        blink_l = clamp((abs(p[159][1] - p[145][1]) / (abs(p[133][0] - p[33][0]) + 1e-6)) / 0.28, 0, 1)
        blink_r = clamp((abs(p[386][1] - p[374][1]) / (abs(p[263][0] - p[362][0]) + 1e-6)) / 0.28, 0, 1)
        mouth = clamp(abs(p[14][1] - p[13][1]) / (abs(p[291][0] - p[61][0]) + 1e-6) / 0.6, 0, 1)
        smile = clamp((((p[61][1] + p[291][1]) / 2) - p[13][1]) / (size * 0.12), -1, 1)

        new = dict(cx=center[0], cy=center[1], size=size, roll=roll, yaw=yaw, pitch=pitch,
                   gx=gx, gy=gy, bl=blink_l, br=blink_r, mouth=mouth, smile=smile)
        if self.state is None:
            self.state = new
        else:
            for k, val in new.items():
                self.state[k] = lerp(self.state[k], val, 0.55)
        return self.state


# ---------------------------------------------------------------- mains
class HandTracker:
    def __init__(self):
        self.h = mp.solutions.hands.Hands(max_num_hands=2, model_complexity=0,
                                          min_detection_confidence=0.6, min_tracking_confidence=0.5)
        self.cand, self.count, self.stable = None, 0, None
        self.stable_hands = None

    @staticmethod
    def classify(p):
        d = lambda a, b: float(np.linalg.norm(p[a] - p[b]))
        ext = [d(t, 0) > d(pip, 0) * 1.05 for t, pip in ((8, 6), (12, 10), (16, 14), (20, 18))]
        thumb = d(4, 17) > d(3, 17) * 1.08 and d(4, 5) > d(2, 5) * 0.9
        thumb_up = thumb and p[4][1] < min(p[i][1] for i in (5, 9, 13, 17)) - 0.05 * d(0, 9)
        if thumb_up and not any(ext):
            return "happy"
        if all(ext) and thumb:
            return "hello"
        if ext[0] and ext[1] and not ext[2] and not ext[3]:
            return "heart"
        if not any(ext):
            return "angry"
        return None

    def update(self, frame, face_state, frame_i=0):
        if frame_i % 2 and self.stable_hands is not None:
            return self.stable, self.stable_hands
        h, w = frame.shape[:2]
        res = self.h.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        hands, gesture, near = [], None, False
        if res.multi_hand_landmarks:
            for hl in res.multi_hand_landmarks:
                pts = np.array([[l.x, l.y] for l in hl.landmark])
                hands.append(pts * [w, h])
                gesture = gesture or self.classify(pts)
                if face_state is not None:
                    c = np.array([face_state["cx"], face_state["cy"]])
                    if np.linalg.norm(pts[9] * [w, h] - c) < face_state["size"] * 0.9:
                        near = True
        emote = gesture or ("question" if near else None)
        if emote == self.cand:
            self.count += 1
        else:
            self.cand, self.count = emote, 1
        if self.count >= 4:
            self.stable = self.cand
        self.stable_hands = hands
        return self.stable, hands


# ================================================================ écran (face avant du cube)
def glow(img, k=21, strength=1.0):
    return cv2.addWeighted(img, 1.0, cv2.GaussianBlur(img, (k, k), 0), strength, 0)


def _heart(layer, cx, cy, r, color):
    cv2.circle(layer, (cx - r // 2, cy - r // 4), r // 2 + 2, color, -1)
    cv2.circle(layer, (cx + r // 2, cy - r // 4), r // 2 + 2, color, -1)
    cv2.fillPoly(layer, [np.array([[cx - r, cy - r // 6], [cx + r, cy - r // 6], [cx, cy + r]], np.int32)], color)


def draw_emote(screen, s, t, emote):
    h, w = screen.shape[:2]
    layer = np.zeros_like(screen)
    cx, cy = w // 2, h // 2

    def big(txt, sc, th):
        (tw, tth), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, sc, th)
        cv2.putText(layer, txt, (cx - tw // 2, cy + tth // 2), cv2.FONT_HERSHEY_DUPLEX, sc, ACCENT, th, cv2.LINE_AA)

    if emote == "hello":
        big("HELLO", 3.6, 8)
    elif emote == "question":
        big("?", 9.0, 16)
    elif emote == "heart":
        for side in (-1, 1):
            beat = 1 + 0.08 * math.sin(t * 8)
            _heart(layer, int(cx + side * 120), cy - 40, int(55 * beat), (120, 60, 255))
        cv2.ellipse(layer, (cx, cy + 90), (70, 45), 0, 0, 180, (120, 60, 255), 10, cv2.LINE_AA)
    elif emote == "happy":
        for side in (-1, 1):
            cv2.ellipse(layer, (cx + side * 120, cy - 20), (55, 50), 0, 180, 360, ACCENT, 14, cv2.LINE_AA)
        cv2.ellipse(layer, (cx, cy + 40), (110, 90), 0, 0, 180, ACCENT, -1, cv2.LINE_AA)
    elif emote == "angry":
        red = (60, 60, 255)
        for side in (-1, 1):
            x = cx + side * 120
            pts = np.array([[x - 55, cy - 80 + (30 if side < 0 else 0)], [x + 55, cy - 80 + (0 if side < 0 else 30)],
                            [x + 55, cy + 10 + (0 if side < 0 else 30)], [x - 55, cy + 10 + (30 if side < 0 else 0)]], np.int32)
            cv2.fillPoly(layer, [pts], red)
        zz = np.array([[cx - 100 + i * 20, cy + 110 + (12 if i % 2 else -12)] for i in range(11)], np.int32)
        cv2.polylines(layer, [zz.reshape(-1, 1, 2)], False, red, 9, cv2.LINE_AA)
    screen[:] = glow(layer, 31, 1.2)


def _draw_idle(screen, s, t):
    h, w = screen.shape[:2]
    layer = np.zeros_like(screen)
    cx, cy = w // 2, h // 2
    style = THEME["eyes"]
    ex, ey, ew, eh = 120, -45, 70, 120
    gx, gy = int(cx + s["gx"] * 60), int(cy + ey + s["gy"] * 45)
    if style == "visor":
        oh = int(14 + 70 * clamp((s["bl"] + s["br"]) / 2 * 1.25, 0, 1))
        cv2.rectangle(layer, (gx - 170, gy - oh // 2), (gx + 170, gy + oh // 2), ACCENT, -1)
        cv2.circle(layer, (gx - 170, gy), oh // 2, ACCENT, -1)
        cv2.circle(layer, (gx + 170, gy), oh // 2, ACCENT, -1)
    else:
        for side, bl in ((-1, s["bl"]), (1, s["br"])):
            oh = int(max(6, eh * clamp(bl * 1.25, 0, 1)))
            x, y = gx + side * ex, gy
            if style == "rect":
                cv2.rectangle(layer, (x - ew // 2, y - oh // 2), (x + ew // 2, y + oh // 2), ACCENT, -1)
            else:                                   # round / cute
                cv2.ellipse(layer, (x, y), (48, max(5, oh // 2 - 8)), 0, 0, 360, ACCENT, -1, cv2.LINE_AA)
                if style == "cute" and bl > 0.4:
                    cv2.circle(layer, (x - 16, y - 18), 11, (255, 255, 255), -1, cv2.LINE_AA)
                    cv2.circle(layer, (x + 14, y + 16), 5, (255, 255, 255), -1, cv2.LINE_AA)
    mw, my = 130, cy + 110
    if style == "visor":                            # bouche = haut-parleur
        for i in range(9):
            bh = int(8 + s["mouth"] * 80 * (1 - abs(i - 4) / 5))
            x = cx - 100 + i * 25
            cv2.rectangle(layer, (x - 7, my - bh // 2), (x + 7, my + bh // 2), ACCENT, -1)
    else:
        mo = int(s["mouth"] * 70)
        curve = int(s["smile"] * 22)
        pts = np.array([[cx - mw + i * 2 * mw // 20, my - int(curve * (1 - ((i - 10) / 10) ** 2))] for i in range(21)], np.int32)
        if mo > 8:
            cv2.ellipse(layer, (cx, my + mo // 2), (mw // 2, mo // 2 + 6), 0, 0, 360, ACCENT, -1)
        else:
            cv2.polylines(layer, [pts.reshape(-1, 1, 2)], False, ACCENT, 9, cv2.LINE_AA)
    screen[:] = glow(layer, 31, 1.2)


def _post(screen, t):
    h, w = screen.shape[:2]
    post = THEME["post"]
    if post == "dots":                              # matrice de LED
        c = 12
        gh, gw = h // c, w // c
        small = cv2.resize(screen, (gw, gh), interpolation=cv2.INTER_AREA)
        big = cv2.resize(cv2.convertScaleAbs(small, alpha=1.6), (gw * c, gh * c), interpolation=cv2.INTER_NEAREST)
        tile = np.zeros((c, c), np.uint8)
        cv2.circle(tile, (c // 2, c // 2), c // 2 - 2, 255, -1, cv2.LINE_AA)
        m = np.tile(tile, (gh, gw))[..., None].astype(np.float32) / 255
        out = np.zeros_like(screen)
        out[:gh * c, :gw * c] = (big * m).astype(np.uint8)
        screen[:] = glow(out, 15, 0.8)
    elif post == "crt":                             # vieux moniteur : scintillement + barre qui défile
        screen[:] = (screen * (0.88 + 0.12 * math.sin(t * 45))).astype(np.uint8)
        y = int((t * 90) % (h + 40)) - 40
        y0, y1 = max(0, y), min(h, y + 40)
        if y1 > y0:
            screen[y0:y1] = (screen[y0:y1] * 0.7).astype(np.uint8)


def draw_face(screen, s, t):
    if s.get("emote"):
        draw_emote(screen, s, t, s["emote"])
    else:
        _draw_idle(screen, s, t)
    _post(screen, t)


class AvatarImages:
    """Images perso dans avatars/ (ignorées par git) -> mode 4, touche A pour changer."""
    def __init__(self):
        self.files = sorted(p for p in AVATAR_DIR.glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".webp"))
        self.i = 0
        self.cache = {}

    def next(self):
        if self.files:
            self.i = (self.i + 1) % len(self.files)

    def draw(self, screen, s, t, _):
        h, w = screen.shape[:2]
        if not self.files:
            for k, line in enumerate(("Mets une image", "dans le dossier", "avatars/")):
                cv2.putText(screen, line, (30, h // 2 - 50 + k * 60), cv2.FONT_HERSHEY_DUPLEX, 1.4, ACCENT, 3, cv2.LINE_AA)
            return
        f = self.files[self.i]
        if f not in self.cache:
            img = cv2.imdecode(np.fromfile(str(f), np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                img = np.zeros((10, 10, 3), np.uint8)
            sc = min(w / img.shape[1], h / img.shape[0])
            img = cv2.resize(img, (max(1, int(img.shape[1] * sc)), max(1, int(img.shape[0] * sc))))
            canvas = np.zeros((h, w, 3), np.uint8)
            y0, x0 = (h - img.shape[0]) // 2, (w - img.shape[1]) // 2
            canvas[y0:y0 + img.shape[0], x0:x0 + img.shape[1]] = img
            self.cache[f] = canvas
        screen[:] = self.cache[f]


def draw_text(screen, s, t, text):
    scale = 3.2
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, scale, 6)
    span = tw + screen.shape[1]
    x = int(screen.shape[1] - (t * 220) % span)
    layer = np.zeros_like(screen)
    cv2.putText(layer, text, (x, screen.shape[0] // 2 + th // 2), cv2.FONT_HERSHEY_DUPLEX, scale, ACCENT, 6, cv2.LINE_AA)
    screen[:] = glow(layer, 25, 1.0)


class Matrix:
    def __init__(self, w, h, cell=18):
        self.cell = cell
        self.cols, self.rows = w // cell, h // cell
        self.heads = np.random.randint(0, self.rows, self.cols).astype(float)
        self.speed = np.random.uniform(0.3, 0.9, self.cols)
        self.buf = np.zeros((h, w, 3), np.uint8)

    def draw(self, screen, s, t, _):
        self.buf = (self.buf * 0.86).astype(np.uint8)
        for c in range(self.cols):
            self.heads[c] = (self.heads[c] + self.speed[c]) % self.rows
            ch = chr(np.random.randint(0x30, 0x5A))
            cv2.putText(self.buf, ch, (c * self.cell, int(self.heads[c]) * self.cell),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, MATRIX_GREEN, 1, cv2.LINE_AA)
        screen[:] = glow(self.buf, 9, 0.8)


def build_canvas(s, t, mode, text, matrix, bezel, avatars=None):
    canvas = np.zeros((CH, CW, 3), np.uint8)
    inner = np.zeros((CH - 2 * BEZEL, CW - 2 * BEZEL, 3), np.uint8)
    inner[:] = (22, 18, 12)
    if mode == 0:
        draw_face(inner, s, t)
    elif mode == 1:
        draw_text(inner, s, t, text)
    elif mode == 2:
        matrix.draw(inner, s, t, None)
    else:
        avatars.draw(inner, s, t, None)
    inner[::3] = (inner[::3] * 0.72).astype(np.uint8)
    canvas[:] = (45, 45, 50)
    canvas[BEZEL:CH - BEZEL, BEZEL:CW - BEZEL] = inner
    if bezel:
        cv2.rectangle(canvas, (BEZEL - 3, BEZEL - 3), (CW - BEZEL + 2, CH - BEZEL + 2), (15, 15, 15), 3)
    return canvas


# ================================================================ cube 3D
def _panel(w, h, kind):
    """Texture métallique statique d'une face non-écran."""
    img = np.full((h, w, 3), (78, 76, 72), np.uint8)
    cv2.rectangle(img, (0, 0), (w - 1, h - 1), (110, 108, 104), 8)
    cv2.rectangle(img, (14, 14), (w - 15, h - 15), (58, 56, 54), 2)
    if kind in ("side", "back"):
        for y in range(int(h * 0.28), int(h * 0.74), 14):          # grille d'aération
            cv2.line(img, (int(w * 0.22), y), (int(w * 0.78), y), (40, 38, 36), 5)
        cv2.circle(img, (int(w * 0.5), int(h * 0.18)), 6, ACCENT, -1, cv2.LINE_AA)
        cv2.circle(img, (int(w * 0.5), int(h * 0.18)), 12, ACCENT, 2, cv2.LINE_AA)
    else:                                                          # dessus / dessous
        for x in range(int(w * 0.2), int(w * 0.82), 18):
            cv2.line(img, (x, int(h * 0.25)), (x, int(h * 0.75)), (40, 38, 36), 6)
    return img


_TEX = {k: _panel(320, 320, k) for k in ("side", "back", "tb")}


def set_theme(i):
    global THEME, ACCENT, _TEX
    THEME = THEMES[i % len(THEMES)]
    ACCENT = THEME["color"]
    _TEX = {k: _panel(320, 320, k) for k in ("side", "back", "tb")}
# face : (nom, texture, normale, 4 coins (haut-g, haut-d, bas-d, bas-g))
_FACES = [
    ("front", None, (0, 0, -1), ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1))),
    ("back", "back", (0, 0, 1), ((1, -1, 1), (-1, -1, 1), (-1, 1, 1), (1, 1, 1))),
    ("right", "side", (1, 0, 0), ((1, -1, -1), (1, -1, 1), (1, 1, 1), (1, 1, -1))),
    ("left", "side", (-1, 0, 0), ((-1, -1, 1), (-1, -1, -1), (-1, 1, -1), (-1, 1, 1))),
    ("top", "tb", (0, -1, 0), ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1))),
    ("bottom", "tb", (0, 1, 0), ((-1, 1, 1), (1, 1, 1), (1, 1, -1), (-1, 1, -1))),
]
_LIGHT = np.array([-0.3, -0.6, -0.7]) / np.linalg.norm([-0.3, -0.6, -0.7])


def _rot(yaw, pitch, roll):
    cy, sy, cp, sp, cr, sr = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch), math.cos(roll), math.sin(roll)
    ry = np.array([[cy, 0, -sy], [0, 1, 0], [sy, 0, cy]])
    rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    rz = np.array([[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]])
    return rz @ rx @ ry


def _warp_blend(frame, tex, quad, shade=1.0):
    fh, fw = frame.shape[:2]
    x0, y0 = np.floor(quad.min(0)).astype(int) - 2
    x1, y1 = np.ceil(quad.max(0)).astype(int) + 2
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(fw, x1), min(fh, y1)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return
    th, tw = tex.shape[:2]
    src = np.float32([[0, 0], [tw, 0], [tw, th], [0, th]])
    M = cv2.getPerspectiveTransform(src, (quad - [x0, y0]).astype(np.float32))
    size = (x1 - x0, y1 - y0)
    warped = cv2.warpPerspective(tex, M, size, flags=cv2.INTER_LINEAR)
    m = cv2.warpPerspective(np.full((th, tw), 255, np.uint8), M, size, flags=cv2.INTER_LINEAR)
    a = (m.astype(np.float32) / 255)[..., None]
    roi = frame[y0:y1, x0:x1].astype(np.float32)
    frame[y0:y1, x0:x1] = (roi * (1 - a) + warped.astype(np.float32) * shade * a).clip(0, 255).astype(np.uint8)


def draw_cube(frame, screen_tex, s):
    hh = s["size"] * 0.82
    hw = hh * CW / CH
    hd = hw * 0.85
    dims = np.array([hw, hh, hd])
    R = _rot(s["yaw"], s["pitch"], s["roll"])
    F = s["size"] * 7.0
    cam = np.array([0, 0, -F])
    center = np.array([s["cx"], s["cy"]])

    def proj(v3):
        r = R @ v3
        return center + r[:2] * F / (F + r[2])

    vis = []
    for name, tex, n, corners in _FACES:
        n_cam = R @ np.array(n, float)
        fc = R @ (np.array(n, float) * dims)
        if np.dot(n_cam, cam - fc) > 0:
            vis.append((fc[2], name, tex, n_cam, corners))
    # ombre portée douce
    shadow = np.zeros(frame.shape[:2], np.uint8)
    allq = [proj(np.array(c, float) * dims) for _, _, _, _, cs in vis for c in cs]
    if allq:
        pts = cv2.convexHull(np.array(allq, np.float32)).astype(np.int32)
        cv2.fillConvexPoly(shadow, pts + [0, int(s["size"] * 0.06)], 255)
        sh = cv2.GaussianBlur(shadow, (61, 61), 0).astype(np.float32)[..., None] / 255 * 0.4
        frame[:] = (frame.astype(np.float32) * (1 - sh)).astype(np.uint8)
    for _, name, tex, n_cam, corners in sorted(vis, key=lambda v: -v[0]):
        quad = np.array([proj(np.array(c, float) * dims) for c in corners], np.float32)
        if name == "front":
            _warp_blend(frame, screen_tex, quad, 1.0)
        else:
            _warp_blend(frame, _TEX[tex], quad, 0.4 + 0.6 * clamp(float(np.dot(n_cam, -_LIGHT)), 0, 1))
        cv2.polylines(frame, [quad.astype(np.int32)], True, (150, 148, 145), 2, cv2.LINE_AA)
    return frame


# ================================================================ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--text", default="HELLO WORLD  ")
    ap.add_argument("--mirror", action="store_true", help="effet miroir")
    ap.add_argument("--no-vcam", action="store_true", help="aperçu seulement")
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--no-hands", action="store_true", help="désactive le suivi des mains")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS, args.fps)
    if not cap.isOpened():
        raise SystemExit("Impossible d'ouvrir la webcam (index %d)." % args.camera)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    vcam = None
    if not args.no_vcam:
        try:
            import pyvirtualcam
            vcam = pyvirtualcam.Camera(W, H, args.fps, fmt=pyvirtualcam.PixelFormat.BGR)
            print("Caméra virtuelle active :", vcam.device)
        except Exception as e:
            print("Caméra virtuelle indisponible (%s)\n-> installe OBS Studio puis relance. Aperçu seul." % e)

    tracker = Tracker()
    hand_tr = None if args.no_hands else HandTracker()
    matrix = Matrix(CW - 2 * BEZEL, CH - 2 * BEZEL)
    avatars = AvatarImages()
    theme_i = 0
    mode, bezel, t0, warned, frame_i = 0, True, time.time(), False, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            print("Plus d'image de la webcam : elle est probablement utilisée par une autre app (Discord ?).")
            break
        if frame.mean() < 2 and not warned:
            warned = True
            print("Image noire : la webcam est sans doute déjà utilisée par Discord/Teams/etc. "
                  "Coupe-la dans cette app ou choisis 'OBS Virtual Camera' comme caméra.")
        if args.mirror:
            frame = cv2.flip(frame, 1)
        t = time.time() - t0
        frame_i += 1
        s = tracker.update(frame)
        emote = None if hand_tr is None else hand_tr.update(frame, s, frame_i)[0]

        out = frame.copy()
        if s is not None:
            out = draw_cube(out, build_canvas(dict(s, emote=emote), t, mode, args.text, matrix, bezel, avatars), s)

        if vcam:
            vcam.send(out)
            vcam.sleep_until_next_frame()
        if not args.no_preview:
            prev = out.copy()                       # le HUD n'apparait que dans l'aperçu
            hud = "[N] style: %s | [1-4] mode | [A] image | [C] calibrer | [Q] quitter" % THEME["name"]
            cv2.putText(prev, hud, (10, prev.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(prev, hud, (10, prev.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.imshow("HeadScreen", prev)
            k = cv2.waitKey(1) & 0xFF
            if k == ord("q") or k == 27:
                break
            elif k in (ord("1"), ord("2"), ord("3"), ord("4")):
                mode = k - ord("1")
            elif k == ord("n"):
                theme_i += 1
                set_theme(theme_i)
            elif k == ord("a"):
                avatars.next()
                mode = 3
            elif k == ord("c"):
                tracker.calibrate()
            elif k == ord("b"):
                bezel = not bezel
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
