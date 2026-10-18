"""
post.py - Composicion anime sobre los frames crudos de Blender.

    python motor/post.py episodios/nodo_404 02_calle              # todos los frames + mp4
    python motor/post.py episodios/nodo_404 02_calle --frames 1 3 # solo esos (pruebas de look)
    python motor/post.py episodios/nodo_404 02_calle --draft      # sobre render/_draft_02_calle

El render 3D es lo unico caro. Todo lo de aca tarda segundos, asi que probar
brillo, lluvia o grano NUNCA requiere volver a renderizar.

Orden: ondas -> datamosh -> brillo (solo lo que emite) -> lluvia -> lineas de velocidad ->
glitch -> aberracion -> vineta -> textos ("textos", ver textos.py) -> grano.
Nada aleatorio por frame: la lluvia es una lista fija de gotas que se mueve
con el tiempo, y el grano cicla entre 3 patrones fijos.
"""

import argparse
import math
import subprocess
from pathlib import Path

import cv2
import numpy as np

from plano import load_shot, merge


DEFAULTS = {
    "glow": {"threshold": 0.55, "radii": [5, 18, 55], "weights": [0.7, 0.55, 0.4], "strength": 1.5},
    "rain": {
        "angle_deg": 8, "color": "#cfe8ff",
        "layers": [
            {"count": 900, "length": [18, 34], "width": 1, "speed": 2600, "alpha": 0.22},
            {"count": 260, "length": [50, 90], "width": 2, "speed": 3800, "alpha": 0.32},
            {"count": 45, "length": [160, 260], "width": 3, "speed": 5600, "alpha": 0.40},
        ],
    },
    "aberration": 0.0022,
    "vignette": 0.28,
    "grain": 0.008,
    "fps_unique": 12,
    "fps_out": 24,
}


def hex_rgb(c):
    c = c.lstrip("#")
    return np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255.0


# ------------------------------------------------------------------ efectos

def glow(img, g):
    """Bloom de compositing anime: solo lo que supera el umbral (neon,
    ventanas), en varias escalas. Se suma en modo screen."""
    lum = img.max(axis=2, keepdims=True)
    mask = np.clip((lum - g["threshold"]) / (1 - g["threshold"]), 0, 1)
    src = img * mask
    h, w = img.shape[:2]
    acc = np.zeros_like(img)
    scale = w / 1080.0
    for r, wt in zip(g["radii"], g["weights"]):
        # blur sobre una version reducida: mismo resultado, 10x mas rapido
        k = max(1, int(r * scale / 4))
        small = cv2.resize(src, (w // 4, h // 4), interpolation=cv2.INTER_AREA)
        small = cv2.GaussianBlur(small, (0, 0), k)
        acc += wt * cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
    acc *= g["strength"]
    return 1 - (1 - img) * (1 - np.clip(acc, 0, 1))


def resplandor(img, R):
    """El aire que se tine alrededor de una fuente de color: toma solo lo que
    tiene ese color dominante (por defecto rojo: r por encima de g y b), lo
    difumina en radios muy grandes y lo suma (screen) tenido. El halo sigue la
    forma real de la fuente y no tiene borde: no es una forma pegada al cielo.
    R: {"radios": [60, 160, 320], "pesos": [...], "fuerza": 1.0, "tinte": "#ff2a3a",
    "umbral": 0.12}"""
    h, w = img.shape[:2]
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    dom = r - np.maximum(g, b) * R.get("cruce", 0.85)
    mask = np.clip((dom - R.get("umbral", 0.12)) / 0.5, 0, 1)[..., None]
    src = mask * hex_rgb(R.get("tinte", "#ff2a3a"))
    acc = np.zeros_like(img)
    scale = w / 1080.0
    small = cv2.resize(src, (w // 8, h // 8), interpolation=cv2.INTER_AREA)
    for rad, wt in zip(R.get("radios", [60, 160, 320]), R.get("pesos", [0.5, 0.45, 0.35])):
        k = max(1, int(rad * scale / 8))
        acc += wt * cv2.resize(cv2.GaussianBlur(small, (0, 0), k), (w, h), interpolation=cv2.INTER_LINEAR)
    acc *= R.get("fuerza", 1.0)
    return 1 - (1 - img) * (1 - np.clip(acc, 0, 1))


def estelas(img, E):
    """Piso mojado o pulido pintado: lo que brilla deja hacia abajo una estela
    vertical que se desvanece, como en los fondos de anime. Solo en la parte de
    abajo del cuadro (donde esta el piso). E: {"umbral": 0.55, "largo": 0.14,
    "fuerza": 0.55, "desde": 0.45}"""
    h, w = img.shape[:2]
    lum = img.max(axis=2)
    th = E.get("umbral", 0.55)
    src = img * np.clip((lum - th) / (1 - th), 0, 1)[..., None]
    q = 4
    small = cv2.resize(src, (w // q, h // q), interpolation=cv2.INTER_AREA)
    L = max(2, int(E.get("largo", 0.14) * h / q))
    wts = np.exp(-np.arange(L + 1) / (L / 3.0)).astype(np.float32)
    # correlacion con ancla abajo: el pixel y recibe de y-k (lo que esta arriba)
    k = wts[::-1].reshape(-1, 1) / wts.sum() * 3.0
    acc = cv2.filter2D(small, -1, k, anchor=(0, L), borderType=cv2.BORDER_CONSTANT)
    acc = cv2.GaussianBlur(acc, (0, 0), sigmaX=1.2, sigmaY=0.1)
    acc = cv2.resize(acc, (w, h), interpolation=cv2.INTER_LINEAR)
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    ramp = np.clip((y - E.get("desde", 0.45)) / 0.15, 0, 1)
    acc = np.clip(acc * ramp * E.get("fuerza", 0.55), 0, 1)
    return 1 - (1 - img) * (1 - acc)


class Rain:
    """Gotas con posicion y velocidad fijas: el frame t es una funcion pura
    de t. Repetir un frame da exactamente la misma lluvia."""

    def __init__(self, r, w, h, seed=404):
        rnd = np.random.default_rng(seed)
        self.r, self.w, self.h = r, w, h
        self.color = hex_rgb(r["color"])
        ang = np.radians(r["angle_deg"])
        self.dir = np.array([np.sin(ang), np.cos(ang)])
        self.layers = []
        for L in r["layers"]:
            n = L["count"]
            self.layers.append({
                **L,
                "x": rnd.uniform(-0.2 * w, 1.1 * w, n),
                "y": rnd.uniform(0, h, n),
                "len": rnd.uniform(*L["length"], n),
                "spd": L["speed"] * rnd.uniform(0.85, 1.15, n),
            })

    def draw(self, img, t, dim=1.0):
        h, w = self.h, self.w
        for L in self.layers:
            layer = np.zeros((h, w), np.float32)
            travel = L["spd"] * t
            y = (L["y"] + travel * self.dir[1]) % (h + 300) - 150
            x = L["x"] + travel * self.dir[0]
            x = (x + 0.2 * w) % (1.3 * w) - 0.2 * w
            x2 = x - L["len"] * self.dir[0]
            y2 = y - L["len"] * self.dir[1]
            for a, b, c, d in zip(x, y, x2, y2):
                cv2.line(layer, (int(a), int(b)), (int(c), int(d)), 1.0, L["width"], cv2.LINE_AA)
            a = (layer * L["alpha"] * dim)[..., None]
            img = img * (1 - a) + self.color * a
        return img


def keyed(keys, f, default=1.0):
    """Interpola linealmente una lista [[frame, valor], ...]."""
    if not keys:
        return default
    fs, vs = zip(*keys)
    return float(np.interp(f, fs, vs))


def glitch(img, f, amt, seed=404):
    """Bandas horizontales desplazadas + separacion RGB. Determinista por
    frame: el mismo frame da siempre el mismo glitch."""
    rnd = np.random.default_rng(seed + f)
    h, w = img.shape[:2]
    out = img.copy()
    for _ in range(int(6 + 10 * amt)):
        y0 = int(rnd.integers(0, h - 20))
        bh = int(rnd.integers(6, int(20 + 120 * amt)))
        dx = int(rnd.integers(-1, 2) * rnd.integers(10, int(20 + 140 * amt)))
        out[y0:y0 + bh] = np.roll(img[y0:y0 + bh], dx, axis=1)
    sh = int(4 + 10 * amt)
    out[..., 0] = np.roll(out[..., 0], sh, axis=1)
    out[..., 2] = np.roll(out[..., 2], -sh, axis=1)
    return out


def datamosh(img, i, raw_dir, D, w, h):
    """Datamosh: como un video al que se le perdio el cuadro clave. La imagen
    vieja (el cuadro anterior a f0) se arrastra con el movimiento del cuadro
    actual, en macrobloques; algunos bloques "sangran" hacia abajo. Los bloques
    se van resolviendo (llega el cuadro clave) hacia el final del tramo.
    D: [f0, f1, amt]. Sin estado: cada frame lee el cuadro clave del disco."""
    f0, f1, amt = D
    key_path = raw_dir / f"f_{max(1, f0 - 1):04d}.png"
    key = cv2.imread(str(key_path))
    if key is None:
        return img
    if key.shape[1] != w:
        key = cv2.resize(key, (w, h), interpolation=cv2.INTER_LANCZOS4)
    key = cv2.cvtColor(key, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    B = int(24 * w / 1080)
    s = 4
    g_cur = cv2.cvtColor((img * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)[::s, ::s]
    g_key = cv2.cvtColor((key * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)[::s, ::s]
    flow = cv2.calcOpticalFlowFarneback(g_cur, g_key, None, 0.5, 3, 15, 3, 5, 1.2, 0) * s
    bw, bh = w // B, h // B
    blk = cv2.resize(flow, (bw, bh), interpolation=cv2.INTER_AREA) * (1 + 2 * amt)
    rnd = np.random.default_rng(404 + f0)
    resolve = rnd.random((bh, bw))
    bleed = (rnd.random((bh, bw)) < 0.12 * amt) * rnd.uniform(4, 14, (bh, bw)) * (i - f0 + 1) * w / 1080
    blk[..., 1] -= bleed
    big = cv2.resize(blk, (bw * B, bh * B), interpolation=cv2.INTER_NEAREST)
    big = cv2.copyMakeBorder(big, 0, h - bh * B, 0, w - bw * B, cv2.BORDER_REPLICATE)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    warped = cv2.remap(key, xx + big[..., 0], yy + big[..., 1], cv2.INTER_NEAREST,
                       borderMode=cv2.BORDER_REFLECT)
    # cuanto del cuadro sigue "moshed": todo al principio, nada al final
    p = amt * (1 - (i - f0) / max(1, f1 - f0 + 1)) ** 0.6
    m = cv2.resize((resolve < p).astype(np.float32), (bw * B, bh * B), interpolation=cv2.INTER_NEAREST)
    m = cv2.copyMakeBorder(m, 0, h - bh * B, 0, w - bw * B, cv2.BORDER_REPLICATE)[..., None]
    return img * (1 - m) + warped * m


def anclas(raw_dir, i, w, h):
    """Rectangulos en pixeles de los personajes ancla en el frame i (los
    escribe escena.py en render/<plano>/anclas.json)."""
    cache = _W.setdefault("anclas", {})
    if raw_dir not in cache:
        import json
        p = raw_dir / "anclas.json"
        cache[raw_dir] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return [(max(0, int(x0 * w)), max(0, int(y0 * h)), min(w, int(x1 * w)), min(h, int(y1 * h)))
            for x0, y0, x1, y1 in cache[raw_dir].get(str(i), [])]


def mascara(raw_dir, i, w, h):
    """Alfa de los anclas (m_####.png, de escena.py con "mascara_anclas"), un
    poco dilatado para que entre la tinta del contorno. None si no hay."""
    path = raw_dir / f"m_{i:04d}.png"
    if not path.exists():
        return None
    m = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if m is None or m.ndim < 3 or m.shape[2] < 4:
        return None
    a = m[..., 3]
    if a.shape[1] != w:
        a = cv2.resize(a, (w, h), interpolation=cv2.INTER_LINEAR)
    k = max(3, int(5 * w / 1080)) | 1
    a = cv2.dilate(a, np.ones((k, k), np.uint8))
    return (a.astype(np.float32) / 255.0)[..., None]


def keep(img, clean, rects, mask=None):
    """El glitch no toca a los anclas: se restaura su mascara exacta si la hay
    y si no, su rectangulo."""
    if mask is not None:
        return img * (1 - mask) + clean * mask
    for x0, y0, x1, y1 in rects:
        img[y0:y1, x0:x1] = clean[y0:y1, x0:x1]
    return img


def congelar(img, a, tint):
    """El tiempo detenido: el mundo pierde el color, se enfria y baja un poco."""
    lum = img @ np.array([0.299, 0.587, 0.114], np.float32)
    cold = lum[..., None] * np.array(tint, np.float32) * 0.85
    return img * (1 - a) + cold * a


def impacto(img, i, I, w, h):
    """Impact frames de anime: el cuadro pasa a dos tonos (la tinta = lo
    oscuro de la imagen) con fondo de color, alternando cada dos cuadros
    rojo/negro, negro/rojo y blanco/negro, mas lineas de foco radiales hacia
    "centro". I: {"frames": [f0, f1], "modos": [...], "centro": [x, y],
    "umbral": 0.35, "lineas": 90, "cada": 2}. Determinista por frame."""
    f0, f1 = I["frames"]
    modos = I.get("modos", ["rojo", "negro", "blanco"])
    m = modos[((i - f0) // I.get("cada", 2)) % len(modos)]
    pal = {"rojo": ("#e0142a", "#0a0608"), "negro": ("#0a0608", "#ff2a3a"), "blanco": ("#f4efe6", "#0a0608")}
    fondo, tinta = (hex_rgb(c) for c in pal[m])
    lum = img @ np.array([0.299, 0.587, 0.114], np.float32)
    ink = (lum < I.get("umbral", 0.35)).astype(np.float32)
    # lo que brilla (el duende) va en tinta invertida: es el centro del golpe
    ink = np.where(lum > I.get("brillo", 0.75), 0.0, ink)
    out = fondo * (1 - ink[..., None]) + tinta * ink[..., None]
    # lineas de foco: triangulos finos desde el borde hacia un radio interior
    rnd = np.random.default_rng(1000 + i)
    cx, cy = I.get("centro", [0.5, 0.35])
    cx, cy = cx * w, cy * h
    capa = np.zeros((h, w), np.uint8)
    R = math.hypot(w, h)
    for _ in range(I.get("lineas", 90)):
        a = rnd.uniform(0, 2 * math.pi)
        r_in = rnd.uniform(0.28, 0.5) * min(w, h)
        anc = rnd.uniform(0.004, 0.014)
        p0 = (cx + math.cos(a) * r_in, cy + math.sin(a) * r_in)
        pa = (cx + math.cos(a - anc) * R, cy + math.sin(a - anc) * R)
        pb = (cx + math.cos(a + anc) * R, cy + math.sin(a + anc) * R)
        cv2.fillPoly(capa, [np.array([p0, pa, pb], np.int32)], 255)
    L = (capa > 0)[..., None]
    return np.where(L, tinta, out)


class Ripples:
    """Gota + ondas en un charco visto en perspectiva. Las ondas son elipses
    (el circulo en el piso se aplasta por el angulo de camara: 'aspect') que
    (1) desplazan la imagen -el reflejo tiembla- y (2) se dibujan como aros
    claros, como en el anime. La lluvia fina pica el charco con aros chicos.
    Todo es funcion pura del frame."""

    def __init__(self, R, w, h):
        self.R, self.w, self.h = R, w, h
        self.k = w / 1080.0
        self.color = hex_rgb(R.get("color", "#e8f4ff"))
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        self.xx, self.yy = xx, yy
        rnd = np.random.default_rng(R.get("seed", 1))
        x0, y0, x1, y1 = R.get("region", [0, 0, 1, 1])
        self.rain = []
        for f in range(1, R.get("frames", 200) + 1):
            for _ in range(R.get("rain_per_frame", 0)):
                self.rain.append((f, rnd.uniform(x0, x1) * w, rnd.uniform(y0, y1) * h))

    def _events(self, f):
        R = self.R
        m = R.get("main")
        if m:
            yield m["frame"], m["x"] * self.w, m["y"] * self.h, m
        small = {"speed": R.get("rain_speed", 9), "life": R.get("rain_life", 5),
                 "amp": R.get("rain_amp", 1.5), "rings": 1, "spacing": 0, "alpha": 0.35, "width": 1}
        for (f0, x, y) in self.rain:
            if 0 <= f - f0 < small["life"] * 2:
                yield f0, x, y, small

    def apply(self, img, f):
        R = self.R
        asp = R.get("aspect", 0.6)
        h, w = self.h, self.w
        dx = np.zeros((h, w), np.float32)
        dy = np.zeros((h, w), np.float32)
        rings = []
        for f0, cx, cy, ev in self._events(f):
            age = f - f0
            if age < 0:
                continue
            decay = np.exp(-age / ev["life"])
            if decay < 0.04:
                continue
            bw = 14 * self.k * ev.get("width", 2)
            r_max = ev["speed"] * self.k * age + 3 * bw
            # solo la caja que ocupa la onda: con ~25 gotitas activas por frame,
            # calcular cada una sobre la imagen entera multiplicaba el tiempo x20
            x0, x1 = max(0, int(cx - r_max)), min(w, int(cx + r_max) + 1)
            y0, y1 = max(0, int(cy - r_max * asp)), min(h, int(cy + r_max * asp) + 1)
            if x0 >= x1 or y0 >= y1:
                continue
            ex = self.xx[y0:y1, x0:x1] - cx
            ey = (self.yy[y0:y1, x0:x1] - cy) / asp
            d = np.sqrt(ex * ex + ey * ey) + 1e-3
            for j in range(ev.get("rings", 3)):
                r = ev["speed"] * self.k * age - j * ev.get("spacing", 30) * self.k
                if r <= 0:
                    continue
                wave = ev["amp"] * self.k * decay * np.exp(-((d - r) / bw) ** 2)
                dx[y0:y1, x0:x1] += wave * ex / d
                dy[y0:y1, x0:x1] += wave * ey / d * asp
                rings.append((cx, cy, r, decay * ev.get("alpha", 0.6), ev.get("width", 2)))
        y_min = int(R.get("region", [0, 0, 1, 1])[1] * h)
        dx[:y_min] = 0
        dy[:y_min] = 0
        out = cv2.remap(img, self.xx + dx, self.yy + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        layer = np.zeros((h, w), np.float32)
        for cx, cy, r, a, wd in rings:
            cv2.ellipse(layer, (int(cx), int(cy)), (int(r), int(r * asp)), 0, 0, 360,
                        float(a), max(1, int(wd * self.k)), cv2.LINE_AA)
        layer[:y_min] = 0
        a = layer[..., None]
        out = out * (1 - a) + self.color * a
        return self._drop(out, f)

    def _drop(self, img, f):
        """La gota que cae y la corona de salpicadura al tocar el agua."""
        m = self.R.get("main")
        if not m:
            return img
        f_imp = m["frame"]
        f_start = f_imp - m.get("fall_frames", 5)
        cx, cy = m["x"] * self.w, m["y"] * self.h
        layer = np.zeros((self.h, self.w), np.float32)
        if f_start <= f < f_imp:
            t = (f - f_start) / (f_imp - f_start)
            y = cy * t
            L = 90 * self.k
            cv2.line(layer, (int(cx), int(y - L)), (int(cx), int(y)), 0.9, max(2, int(5 * self.k)), cv2.LINE_AA)
            cv2.circle(layer, (int(cx), int(y)), max(3, int(7 * self.k)), 1.0, -1, cv2.LINE_AA)
        elif f_imp <= f < f_imp + 3:
            age = f - f_imp
            for k in range(9):
                ang = np.pi * (0.1 + 0.8 * k / 8)
                r0 = (10 + 25 * age) * self.k
                r1 = r0 + (40 - 10 * age) * self.k
                p0 = (int(cx + r0 * np.cos(ang)), int(cy - r0 * np.sin(ang) * 1.4))
                p1 = (int(cx + r1 * np.cos(ang)), int(cy - r1 * np.sin(ang) * 1.4))
                cv2.line(layer, p0, p1, 0.9 - 0.25 * age, max(2, int(4 * self.k)), cv2.LINE_AA)
        a = layer[..., None]
        return img * (1 - a) + self.color * a


def speedlines(img, f, S, w, h):
    """Lineas de velocidad de anime: trazos horizontales finos que cambian en
    cada frame (azar fijado por frame). Mas densos en la banda del sujeto."""
    if not (S["frames"][0] <= f <= S["frames"][1]):
        return img
    rnd = np.random.default_rng(S.get("seed", 7) * 1000 + f)
    layer = np.zeros((h, w), np.float32)
    b0, b1 = S.get("band", [0.0, 1.0])
    k = w / 1080.0
    for _ in range(S.get("count", 40)):
        y = int(rnd.uniform(b0, b1) * h)
        L = rnd.uniform(0.25, 0.9) * w
        x = rnd.uniform(-0.2 * w, w)
        th = max(1, int(rnd.choice([1, 1, 2, 3]) * k))
        cv2.line(layer, (int(x), y), (int(x + L), y), float(rnd.uniform(0.4, 1.0)), th, cv2.LINE_AA)
    a = (layer * S.get("alpha", 0.3))[..., None]
    return img * (1 - a) + hex_rgb(S.get("color", "#f4f8ff")) * a


def aberration(img, k):
    """Aberracion cromatica radial: R se agranda, B se achica."""
    if k <= 0:
        return img
    h, w = img.shape[:2]
    out = img.copy()
    for ch, s in ((0, 1 + k), (2, 1 - k)):
        M = cv2.getRotationMatrix2D((w / 2, h / 2), 0, s)
        out[..., ch] = cv2.warpAffine(img[..., ch], M, (w, h), flags=cv2.INTER_LINEAR,
                                      borderMode=cv2.BORDER_REFLECT)
    return out


def vignette_mask(w, h, amt):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r2 = ((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2
    return (1 - amt * np.clip(r2 / 2, 0, 1))[..., None]


def grain_patterns(w, h, amt, n=3, seed=7):
    rnd = np.random.default_rng(seed)
    pats = []
    for _ in range(n):
        g = rnd.normal(0, 1, (h // 2, w // 2)).astype(np.float32)
        g = cv2.resize(g, (w, h), interpolation=cv2.INTER_LINEAR)
        pats.append((g * amt)[..., None])
    return pats


# ------------------------------------------------------------------ main

_W = {}   # estado por proceso (lluvia, vineta, grano): se arma una vez por worker


def _init(P, w, h, dst):
    _W.update(P=P, w=w, h=h, dst=dst,
              rain=Rain(P["rain"], w, h) if P.get("rain") else None,
              vig=vignette_mask(w, h, P["vignette"]),
              grains=grain_patterns(w, h, P["grain"]),
              ripples=Ripples(P["ripples"], w, h) if P.get("ripples") else None)


def _frame(f):
    P, w, h = _W["P"], _W["w"], _W["h"]
    i = int(f.stem[2:])
    t = (i - 1) / P["fps_unique"]
    img = cv2.imread(str(f))
    if img.shape[1] != w:
        # frame de borrador (--draft): se reescala ANTES de los efectos, asi
        # lluvia, grano y glitch salen a resolucion final
        img = cv2.resize(img, (w, h), interpolation=cv2.INTER_LANCZOS4)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    if _W["ripples"]:
        # antes del brillo: la onda deforma el reflejo y su halo la acompana
        img = _W["ripples"].apply(img, i)
    rects = anclas(f.parent, i, w, h)
    mask = mascara(f.parent, i, w, h)
    for D in P.get("datamosh", []):
        if D[0] <= i <= D[1]:
            img = keep(datamosh(img, i, f.parent, D, w, h), img, rects, mask)
    img = glow(img, P["glow"])
    if P.get("resplandor"):
        img = resplandor(img, P["resplandor"])
    if P.get("estelas"):
        img = estelas(img, P["estelas"])
    C = P.get("congelar")
    if C:
        # [[frame, intensidad], ...]: el mundo detenido; los anclas, a color
        a = keyed(C["keys"], i, 0.0)
        if a > 0:
            img = keep(congelar(img, a, hex_rgb(C.get("tint", "#b4c6e8"))), img, rects, mask)
    if _W["rain"]:
        img = _W["rain"].draw(img, t, keyed(P.get("rain_dim"), i))
    if P.get("speedlines"):
        img = speedlines(img, i, P["speedlines"], w, h)
    for g0, g1, ga in P.get("glitch", []):
        if g0 <= i <= g1:
            img = keep(glitch(img, i, ga), img, rects, mask)
    I = P.get("impacto")
    if I and I["frames"][0] <= i <= I["frames"][1]:
        img = impacto(img, i, I, w, h)
    img = aberration(img, P["aberration"])
    img = img * _W["vig"]
    if P.get("textos"):
        # titulos del plano: despues de brillo y vineta (nitidos), antes del grano
        import textos
        img = textos.compose(img, [dict(t, alpha=textos.fade_alpha(i, t["frames"], t.get("fade")))
                                   for t in P["textos"]])
    img = img + _W["grains"][i % len(_W["grains"])]
    out = (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
    cv2.imwrite(str(_W["dst"] / f"p_{i:04d}.png"), cv2.cvtColor(out, cv2.COLOR_RGB2BGR))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode", type=Path, help="carpeta del episodio (episodios/<nombre>)")
    ap.add_argument("shot")
    ap.add_argument("--frames", nargs=2, type=int)
    ap.add_argument("--no-video", action="store_true")
    ap.add_argument("--draft", action="store_true", help="lee render/_draft_<plano>, escribe out/_draft_<plano>")
    ap.add_argument("--jobs", type=int, default=4, help="procesos en paralelo (uno por nucleo)")
    args = ap.parse_args()

    ROOT = args.episode.resolve()
    cfg = load_shot(ROOT / "shots" / f"{args.shot}.json")
    P = merge(DEFAULTS, cfg.get("post", {}))
    name = f"_draft_{args.shot}" if args.draft else args.shot
    src = ROOT / "render" / name
    dst = ROOT / "out" / name
    dst.mkdir(parents=True, exist_ok=True)

    files = sorted(src.glob("f_*.png"))
    if args.frames:
        a, b = args.frames
        files = [f for f in files if a <= int(f.stem[2:]) <= b]
    if not files:
        raise SystemExit(f"No hay frames en {src}")

    if not args.frames:
        # un render anterior mas largo deja frames viejos que el montaje pegaria
        for f in dst.glob("p_*.png"):
            if not (src / f"f_{f.stem[2:]}.png").exists():
                f.unlink()

    # resolucion final = la del JSON, aunque los frames vengan de un borrador
    w, h = cfg["width"], cfg["height"]
    # cada worker procesa frames independientes (todo es funcion pura del frame)
    cv2.setNumThreads(1)
    if args.jobs > 1 and len(files) > 1:
        from multiprocessing import Pool
        with Pool(args.jobs, initializer=_init, initargs=(P, w, h, dst)) as pool:
            pool.map(_frame, files, chunksize=4)
    else:
        _init(P, w, h, dst)
        for f in files:
            _frame(f)
    print(f"{len(files)} frames -> {dst}")

    if args.no_video or args.frames:
        return
    mp4 = ROOT / "out" / f"{name}.mp4"
    # entrada a 12 fps, salida a 24: ffmpeg duplica cada frame -> animado en doses
    # un plano con render_frames no empieza en 1 (contraplanos de la misma accion)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(P["fps_unique"]),
           "-start_number", files[0].stem[2:], "-i", str(dst / "p_%04d.png"), "-r", str(P["fps_out"]),
           "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", str(mp4)]
    subprocess.run(cmd, check=True)
    print(f"-> {mp4}")


if __name__ == "__main__":
    main()
