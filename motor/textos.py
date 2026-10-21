"""
textos.py - Texto 2D sobre los frames: titulos por plano (post.py) y
subtitulos sobre el corte entero (montaje.py). Python puro + PIL.

Un texto es un dict:
    {"text": "...", "font": "C:/Windows/Fonts/YuGothB.ttc", "size": 52,
     "color": "#5ec5e2", "pos": [0.5, 0.72],      # centro x, borde de arriba y (0..1)
     "align": "center", "max_w": 0.84,            # ancho maximo antes de cortar linea
     "tracking": 0, "outline": 6, "outline_color": "#05070f", "glow": 0.5, "alpha": 1.0}

Se rasteriza una vez por contenido (cache) y se compone con alfa, sin
desenfoque por frame: el mismo frame da siempre el mismo texto.
"""

from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = {
    "texto": "C:/Windows/Fonts/YuGothB.ttc",     # latino y japones en la misma letra
    "mono": "C:/Windows/Fonts/consolab.ttf",     # la voz de la maquina, como en la app
    "mono_r": "C:/Windows/Fonts/consola.ttf",
}


def hex_rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


@lru_cache(maxsize=64)
def _font(path, size):
    return ImageFont.truetype(FONTS.get(path, path), size)


def _wrap(draw, text, font, max_px, tracking):
    """Corta por palabras; si no hay espacios (japones), por caracteres."""
    def width(s):
        return draw.textlength(s, font=font) + tracking * max(0, len(s) - 1)

    lines = []
    for para in text.split("\n"):
        tokens = para.split(" ") if " " in para else list(para)
        sep = " " if " " in para else ""
        cur = ""
        for tok in tokens:
            cand = (cur + sep + tok) if cur else tok
            # kinsoku: en japones un renglon no empieza con puntuacion de cierre;
            # se queda pegada al renglon anterior aunque lo pase un poco
            if width(cand) <= max_px or not cur or (not sep and tok in "。、．，！？!?)）」』…ー"):
                cur = cand
            else:
                lines.append(cur)
                cur = tok
        lines.append(cur)
    return lines


@lru_cache(maxsize=256)
def _raster(text, font, size, color, outline, outline_color, glow, tracking, max_px, line_gap,
            align="center"):
    """RGBA (float 0..1) recortado al texto, con contorno y halo."""
    f = _font(font, size)
    tmp = ImageDraw.Draw(Image.new("L", (8, 8)))
    lines = _wrap(tmp, text, f, max_px, tracking)
    asc, desc = f.getmetrics()
    lh = int((asc + desc) * line_gap)
    widths = [tmp.textlength(ln, font=f) + tracking * max(0, len(ln) - 1) for ln in lines]
    pad = outline + int(size * 0.6 * (glow > 0))
    W = int(max(widths or [1]) + 2 * pad + 2)
    H = int(lh * len(lines) + 2 * pad + 2)
    mask = Image.new("L", (W, H), 0)
    edge = Image.new("L", (W, H), 0)
    dm, de = ImageDraw.Draw(mask), ImageDraw.Draw(edge)
    for k, (ln, wd) in enumerate(zip(lines, widths)):
        # cada renglon se alinea como el bloque (antes, siempre centrado)
        x = pad + {"left": 0, "right": max(widths) - wd}.get(align, (max(widths) - wd) / 2)
        y = pad + k * lh
        if tracking:
            for ch in ln:
                de.text((x, y), ch, font=f, fill=255, stroke_width=outline, stroke_fill=255)
                dm.text((x, y), ch, font=f, fill=255)
                x += tmp.textlength(ch, font=f) + tracking
        else:
            de.text((x, y), ln, font=f, fill=255, stroke_width=outline, stroke_fill=255)
            dm.text((x, y), ln, font=f, fill=255)
    m = np.asarray(mask, np.float32) / 255
    o = np.asarray(edge, np.float32) / 255
    col = np.array(hex_rgb(color), np.float32) / 255
    ocol = np.array(hex_rgb(outline_color), np.float32) / 255
    rgb = np.zeros((H, W, 3), np.float32)
    a = np.zeros((H, W), np.float32)
    if glow > 0:
        g = np.asarray(mask.filter(ImageFilter.GaussianBlur(size * 0.35)), np.float32) / 255
        g = np.clip(g * 2.2 * glow, 0, 1)
        rgb += col * g[..., None]
        a = np.maximum(a, g * 0.6)
    oa = o * 0.82                                      # contorno oscuro semitransparente
    rgb = rgb * (1 - oa[..., None]) + ocol * oa[..., None]
    a = np.maximum(a, oa)
    rgb = rgb * (1 - m[..., None]) + col * m[..., None]
    a = np.maximum(a, m)
    return np.dstack([rgb, a])


def layer(t, w, h):
    """Devuelve (rgba, x0, y0) para componer el texto t en una imagen w x h."""
    k = min(w, h) / 1080.0
    size = int(t.get("size", 48) * k)
    rgba = _raster(t["text"], t.get("font", "texto"), size, t.get("color", "#dfe6ef"),
                   int(t.get("outline", 6) * k), t.get("outline_color", "#05070f"),
                   float(t.get("glow", 0.0)), int(t.get("tracking", 0) * k),
                   int(t.get("max_w", 0.84) * w), float(t.get("line_gap", 1.18)), t.get("align", "center"))
    H, W = rgba.shape[:2]
    cx, top = t.get("pos", [0.5, 0.75])
    align = t.get("align", "center")
    # el margen del contorno y el halo no cuenta: la letra empieza (o termina) en cx
    pad = int(t.get("outline", 6) * k) + int(size * 0.6 * (float(t.get("glow", 0.0)) > 0))
    x0 = int(cx * w - W / 2) if align == "center" else int(cx * w) - pad if align == "left" else int(cx * w - W) + pad
    y0 = int(top * h)
    return rgba, x0, y0


def compose(img, items, alpha_of=None):
    """img: float RGB 0..1 (h, w, 3). items: lista de textos (con "alpha")."""
    h, w = img.shape[:2]
    for t in items:
        al = t.get("alpha", 1.0)
        if al <= 0 or not t.get("text"):
            continue
        rgba, x0, y0 = layer(t, w, h)
        H, W = rgba.shape[:2]
        xa, ya = max(0, x0), max(0, y0)
        xb, yb = min(w, x0 + W), min(h, y0 + H)
        if xa >= xb or ya >= yb:
            continue
        sub = rgba[ya - y0:yb - y0, xa - x0:xb - x0]
        a = sub[..., 3:4] * al
        img[ya:yb, xa:xb] = img[ya:yb, xa:xb] * (1 - a) + sub[..., :3] * a
    return img


def fade_alpha(f, frames, fade):
    """Alfa de un texto visible en [f0, f1] con fundidos de fade = [entrada, salida] frames."""
    f0, f1 = frames
    fi, fo = fade if fade else (0, 0)
    if f < f0 or f > f1:
        return 0.0
    a = 1.0
    if fi and f < f0 + fi:
        a = (f - f0 + 1) / fi
    if fo and f > f1 - fo:
        a = min(a, (f1 - f + 1) / fo)
    return max(0.0, min(1.0, a))
