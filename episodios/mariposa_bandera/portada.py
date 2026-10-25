"""
portada.py - Portada del short (técnica del canal: un cuadro del propio video +
texto corto con sombra en 8 direcciones sobre una franja oscura en degradé).

    python episodios/mariposa_bandera/portada.py   # -> out/portada.jpg (1080x1920)

El cuadro: el 68 del despliegue, la mariposa abierta y simétrica colgando de la
cáscara, con las escamas cayendo. El texto va debajo de las alas y arriba de la
franja inferior que tapa la interfaz de Shorts.
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

EP = Path(__file__).resolve().parent
W, H = 1080, 1920
CUADRO = EP / "out" / "02_despliegue" / "p_0068.png"
FUENTE = "C:/Windows/Fonts/bahnschrift.ttf"
TEXTOS = [  # texto, tamaño, peso, y, color del halo, color, espaciado
    ("LA BANDERA", 132, "Bold", 1310, (127, 232, 255), (240, 252, 255), 8),
    ("le dio toda su luz", 60, "SemiBold", 1490, (255, 79, 216), (255, 220, 247), 2),
]


def fuente(size, peso):
    f = ImageFont.truetype(FUENTE, size)
    f.set_variation_by_name(peso)
    return f


def main():
    img = Image.open(CUADRO).convert("RGB").resize((W, H))
    y = np.arange(H)[:, None] * np.ones((1, W))
    franja = np.clip(np.minimum((y - 1190) / 140, (1740 - y) / 140), 0, 1) * 0.66
    img = Image.composite(Image.new("RGB", (W, H), (6, 4, 18)), img,
                          Image.fromarray((franja * 255).astype(np.uint8)))
    base = img.convert("RGBA")
    for t, size, peso, yy, brillo, col, sep in TEXTOS:
        f = fuente(size, peso)
        medir = ImageDraw.Draw(Image.new("L", (1, 1)))
        anchos = [medir.textlength(c, font=f) for c in t]
        total = sum(anchos) + sep * (len(t) - 1)
        assert total < W * 0.86, f"{t!r} ocupa {total:.0f} px: se va al borde"
        xs, x = [], (W - total) / 2
        for w in anchos:
            xs.append(x)
            x += w + sep
        # halo de neon debajo del texto, del color de la luz de las alas
        halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dh = ImageDraw.Draw(halo)
        for c, x in zip(t, xs):
            dh.text((x, yy), c, font=f, fill=brillo + (230,))
        base = Image.alpha_composite(base, halo.filter(ImageFilter.GaussianBlur(18)))
        d = ImageDraw.Draw(base)
        for c, x in zip(t, xs):
            for dx, dy in [(-4, -4), (4, -4), (-4, 4), (4, 4), (0, 5), (5, 0), (-5, 0), (0, -5)]:
                d.text((x + dx, yy + dy), c, font=f, fill=(10, 6, 30, 255))
            d.text((x, yy), c, font=f, fill=col + (255,))
    dst = EP / "out" / "portada.jpg"
    base.convert("RGB").save(dst, "JPEG", quality=92)
    print(f"-> {dst} ({dst.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
