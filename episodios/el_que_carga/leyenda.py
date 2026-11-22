"""leyenda.py - El cartel fileteado de la leyenda: el Hombre-Tanque cargando
el laboratorio, en filete porteno. 2D puro (numpy + PIL), sin Blender: el
filete es dibujo plano y no necesita camara. Reusa las espirales y la hoja de
acanto de el_fileteador/filete.py.

    python episodios/el_que_carga/leyenda.py [salida.png]

Convenciones del filete que se respetan: fondo negro, cada forma con su
sombra corrida (azul petroleo), relleno, mitad oscura, contorno negro y un
brillo claro; cintas celeste y blanca; bolitas amarillas; simetria.
"""

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "el_fileteador"))
from filete import PALETA, _acanto, _bezier, _espiral  # noqa: E402

W, H, S = 1080, 1920, 2          # salida y supersampleo
P = dict(PALETA, fondo="#120e0c", celeste="#6fc3ea", blanco="#fbf6ea", oro="#f2c23a", oro_osc="#a8701c",
         roca="#2f1a3c", roca_brillo="#6b4a86", poncho="#efe2c4", poncho_osc="#c9b48e", metal="#7fa6a0",
         metal_osc="#3f5e62", visor="#7ff7ff")
SOMBRA = (10 * S, 12 * S)
LW = 5 * S                        # grosor del contorno


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class Lienzo:
    def __init__(self):
        self.im = Image.new("RGB", (W * S, H * S), rgb(P["fondo"]))
        self.d = ImageDraw.Draw(self.im)

    def forma(self, pts, fill, oscuro=None, brillo=None, sombra=True, borde=True):
        pts = [tuple(map(float, p)) for p in pts]
        if sombra:
            self.d.polygon([(x + SOMBRA[0], y + SOMBRA[1]) for x, y in pts], fill=rgb(P["sombra"]))
        self.d.polygon(pts, fill=rgb(fill))
        if oscuro is not None:
            self.d.polygon([tuple(map(float, p)) for p in oscuro], fill=rgb(fill_osc(fill)))
        if brillo is not None:
            self.trazo(brillo, 4 * S, 1.5 * S, P["blanco"])
        if borde:
            self.d.line(pts + [pts[0]], fill=rgb(P["linea"]), width=LW, joint="curve")

    def trazo(self, pts, w0, w1, col, sombra=False):
        """Pincelada de ancho w0 -> w1 (afinada en la punta)."""
        pts = np.asarray(pts, float)
        if len(pts) < 2:
            return
        d = np.gradient(pts, axis=0)
        n = np.c_[-d[:, 1], d[:, 0]]
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-9
        k = np.linspace(0, 1, len(pts))
        w = (w0 + (w1 - w0) * k)[:, None] / 2
        poly = np.r_[pts + n * w, (pts - n * w)[::-1]]
        if sombra:
            self.d.polygon([(x + SOMBRA[0], y + SOMBRA[1]) for x, y in poly], fill=rgb(P["sombra"]))
        self.d.polygon([tuple(p) for p in poly], fill=rgb(col))

    def bolita(self, c, r, col=None):
        x, y = c
        self.d.ellipse((x - r + SOMBRA[0] / 2, y - r + SOMBRA[1] / 2, x + r + SOMBRA[0] / 2, y + r + SOMBRA[1] / 2),
                       fill=rgb(P["sombra"]))
        self.d.ellipse((x - r, y - r, x + r, y + r), fill=rgb(col or P["bolita"]), outline=rgb(P["linea"]), width=2 * S)


def fill_osc(c):
    return {P["verde"]: P["verde_osc"], P["rojo"]: P["rojo_osc"], P["oro"]: P["oro_osc"],
            P["poncho"]: P["poncho_osc"], P["metal"]: P["metal_osc"], P["roca"]: "#1c0f26"}.get(c, c)


def mapa(pts, K, o, flip=(1, 1)):
    """De unidades del filete (y arriba) a pixeles (y abajo)."""
    pts = np.asarray(pts, float)
    return np.c_[o[0] + flip[0] * pts[:, 0] * K, o[1] - flip[1] * pts[:, 1] * K]


# ------------------------------------------------------------------ ornamentos

def hoja(L, o, K, flip):
    """Hoja de acanto que se enrosca en la punta (de filete.py)."""
    b = _bezier((0, 0), (0.12, 0.10), (0.26, 0.14), (0.34, 0.08), 90)
    r1 = 0.055
    c = b[-1] - np.array([0, r1])
    esp = _espiral(c, 0.012, r1, 1.1, math.pi / 2, sentido=-1)[::-1]
    eje = np.r_[b, esp[1:]]
    cont, osc, nerv, cortes, _ = _acanto(eje, [(0, 0.012), (0.25, 0.06), (0.6, 0.05), (0.85, 0.03), (1, 0.006)],
                                         [(0, 0.006), (0.5, 0.022), (1, 0.003)],
                                         [(0.06, 0.2), (0.2, 0.34), (0.34, 0.48), (0.48, 0.6)])
    L.forma(mapa(cont, K, o, flip), P["verde"], oscuro=mapa(osc, K, o, flip))
    for nv in nerv:
        L.trazo(mapa(nv, K, o, flip), 4 * S, 1 * S, P["brillo"])
    for ct in cortes:
        L.d.line([tuple(p) for p in mapa(ct, K, o, flip)], fill=rgb(P["linea"]), width=3 * S)


def voluta(L, o, K, flip, col="rojo"):
    """Banda que nace en espiral y corre derecha (la voluta del filete)."""
    esp = _espiral((0, 0), 0.012, 0.06, 1.6, -math.pi / 2, sentido=1)
    banda = np.r_[esp, _bezier(esp[-1], esp[-1] + (0.1, 0), (0.25, -0.06), (0.36, -0.06), 60)[1:]]
    pts = mapa(banda, K, o, flip)
    L.trazo(pts, 6 * S, 26 * S, P["linea"], sombra=True)
    L.trazo(pts, 3 * S, 19 * S, P[col])
    L.trazo(pts + np.array([0, -3 * S]), 1 * S, 5 * S, P[col + "_brillo"])
    return pts


def esquina(L, o, flip):
    K = 1150 * S
    voluta(L, o, K, flip)
    hoja(L, (o[0] + flip[0] * 24 * S, o[1] - flip[1] * 64 * S), K * 0.55, flip)
    for k in range(4):
        L.bolita((o[0] + flip[0] * (430 + 26 * k) * S, o[1] + flip[1] * (95 - 9 * k) * S), (9 - 1.5 * k) * S)


def marco(L):
    m = 46 * S
    for off, col, w in ((0, P["celeste"], 14 * S), (22 * S, P["blanco"], 6 * S)):
        r = (m + off, m + off, W * S - m - off, H * S - m - off)
        L.d.rectangle(r, outline=rgb(col), width=w)


def cinta(L, cx, cy, w, h):
    """Cinta celeste y blanca bajo el titulo, con las puntas cortadas en V."""
    x0, x1 = cx - w / 2, cx + w / 2
    for k, col in enumerate((P["celeste"], P["blanco"], P["celeste"])):
        y0 = cy - h / 2 + k * h / 3
        y1 = y0 + h / 3
        pts = [(x0, y0), (x1, y0), (x1 + h * 0.45, (y0 + y1) / 2 if k == 1 else y0 + (y1 - y0) * (0 if k == 0 else 1)),
               (x1, y1), (x0, y1), (x0 - h * 0.45, (y0 + y1) / 2 if k == 1 else y0 + (y1 - y0) * (0 if k == 0 else 1))]
        L.d.polygon([(x + SOMBRA[0], y + SOMBRA[1]) for x, y in pts], fill=rgb(P["sombra"]))
        L.d.polygon(pts, fill=rgb(col))
    L.d.rectangle((x0, cy - h / 2, x1, cy + h / 2), outline=rgb(P["linea"]), width=LW)


def titulo(L, texto, cy, size):
    f = ImageFont.truetype("C:/Windows/Fonts/georgiab.ttf", size * S)
    bb = L.d.textbbox((0, 0), texto, font=f)
    x = (W * S - (bb[2] - bb[0])) / 2
    # volumen del filete: sombra corrida, cuerpo, contorno y brillo
    L.d.text((x + 9 * S, cy + 11 * S), texto, font=f, fill=rgb(P["rojo_osc"]), stroke_width=4 * S,
             stroke_fill=rgb(P["linea"]))
    L.d.text((x, cy), texto, font=f, fill=rgb(P["oro"]), stroke_width=4 * S, stroke_fill=rgb(P["linea"]))


# ------------------------------------------------------------------ el icono

def icono(L, cx, cy, esc):
    s = esc * S

    def T(pts):
        return [(cx + x * s, cy + y * s) for x, y in pts]

    # la roca: triangulo invertido de borde irregular, laboratorio arriba
    rng = np.random.default_rng(4)
    borde = [(-260, -120)]
    for k in range(1, 12):
        t = k / 12
        borde.append((-260 + 520 * t, -120 + rng.uniform(-14, 14)))
    borde.append((260, -120))
    izq = [(-260 + 255 * t + rng.uniform(-10, 10), -120 + 300 * t) for t in np.linspace(0.1, 0.95, 8)]
    der = [(260 - 255 * t + rng.uniform(-10, 10), -120 + 300 * t) for t in np.linspace(0.1, 0.95, 8)]
    roca = borde + der + [(0, 190)] + izq[::-1]
    L.forma(T(roca), P["roca"], brillo=T([(-230, -100), (-20, -104), (200, -98)]))
    # laboratorio: torres con cupula y ventanas cian
    for x, h, w in ((-150, 120, 46), (-80, 190, 54), (0, 260, 60), (85, 170, 50), (160, 110, 44)):
        L.forma(T([(x - w / 2, -120), (x - w / 2, -120 - h), (x, -120 - h - w * 0.7), (x + w / 2, -120 - h),
                   (x + w / 2, -120)]), P["metal"], oscuro=T([(x, -120), (x, -120 - h - w * 0.7), (x + w / 2, -120 - h),
                                                               (x + w / 2, -120)]))
        for k in range(int(h // 50)):
            L.bolita(T([(x - w * 0.1, -150 - 45 * k)])[0], 6 * S, P["visor"])
    L.forma(T([(-230, -130), (230, -130), (240, -112), (-240, -112)]), P["verde"])   # pasto del borde
    # el Hombre-Tanque: brazos en alto bajo la punta
    for sg in (-1, 1):
        L.forma(T([(sg * 30, 200), (sg * 46, 200), (sg * 78, 300), (sg * 62, 306)]), P["metal"])   # antebrazo
        L.forma(T([(sg * 62, 300), (sg * 80, 296), (sg * 86, 380), (sg * 66, 384)]), P["metal"])   # brazo
        L.bolita(T([(sg * 72, 300)])[0], 14 * S, P["metal_osc"])
        L.forma(T([(sg * 18, 186), (sg * 52, 186), (sg * 52, 206), (sg * 18, 206)]), P["metal_osc"])  # mano
    # sombrero y cabeza
    L.forma(T([(-34, 300), (34, 300), (34, 352), (-34, 352)]), P["metal_osc"])
    L.d.rectangle(T([(-24, 318), (24, 328)]), fill=rgb(P["visor"]))
    L.forma(T([(-92, 300), (92, 300), (80, 288), (-80, 288)]), "#2b2026")
    L.forma(T([(-34, 290), (34, 290), (28, 252), (-28, 252)]), "#2b2026")
    # poncho con guarda
    pon = [(-50, 356), (50, 356), (140, 520), (0, 560), (-140, 520)]
    L.forma(T(pon), P["poncho"], oscuro=T([(0, 356), (50, 356), (140, 520), (0, 560)]))
    L.trazo(T([(-128, 500), (0, 536), (128, 500)]), 16 * S, 16 * S, P["rojo"])
    for x in np.linspace(-100, 100, 6):
        L.bolita(T([(x, 518 + 18 * (1 - abs(x) / 100))])[0], 5 * S, P["oro"])
    # piernas y botas, aceite que gotea
    for sg in (-1, 1):
        L.forma(T([(sg * 20, 556), (sg * 62, 548), (sg * 70, 660), (sg * 34, 664)]), P["metal"])
        L.bolita(T([(sg * 50, 612)])[0], 15 * S, P["metal_osc"])
        L.forma(T([(sg * 26, 660), (sg * 76, 660), (sg * 96, 690), (sg * 22, 690)]), P["metal_osc"])
        L.trazo(T([(sg * 58, 630), (sg * 58, 700), (sg * 60, 720)]), 6 * S, 2 * S, P["linea"])
    L.d.ellipse(T([(-120, 712), (120, 736)]), fill=rgb(P["linea"]))


def main(dst):
    L = Lienzo()
    marco(L)
    pad = 110 * S
    esquina(L, (pad, pad + 40 * S), (1, -1))
    esquina(L, (W * S - pad, pad + 40 * S), (-1, -1))
    esquina(L, (pad, H * S - pad - 40 * S), (1, 1))
    esquina(L, (W * S - pad, H * S - pad - 40 * S), (-1, 1))
    titulo(L, "EL QUE CARGA", 300 * S, 104)
    cinta(L, W * S / 2, 520 * S, 720 * S, 66 * S)
    f = ImageFont.truetype("C:/Windows/Fonts/georgiab.ttf", 30 * S)
    t = "LEYENDA DEL HOMBRE-TANQUE"
    bb = L.d.textbbox((0, 0), t, font=f)
    L.d.text(((W * S - (bb[2] - bb[0])) / 2, 520 * S - 22 * S), t, font=f, fill=rgb(P["linea"]))
    icono(L, W * S / 2, 1000 * S, 0.95)
    im = L.im.resize((W, H), Image.LANCZOS)
    # papel: el mismo soporte que el post de los planos 3D
    sys.path.insert(0, str(AQUI.parent.parent / "motor"))
    import post
    a = np.asarray(im, np.float32) / 255.0
    a = a * post.papel_textura(W, H, {"manchas": 0.08, "fibra": 0.035, "seed": 11})
    Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)).save(dst)
    print(dst)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else AQUI / "out" / "leyenda.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    main(out)
