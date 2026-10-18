"""Compara la planta con una foto aerea: renderiza una cenital lejana con
teleobjetivo (_qa_aerea) y dibuja sus bordes en rojo sobre la foto, en el
mismo marco (lat/lon -> escena con la georef de los datos del entorno).

    python episodios/catedral/aerea.py [--sin-render]   # -> out/_aerea.png

La foto (Esri World Imagery, z19) se baja una vez a ref/aerea/, que no se
commitea: es solo referencia. Un corrimiento parejo de varios metros entre
calles y edificios es de la imagen, no del modelo.
"""
import io
import json
import math
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
EP = ROOT / "episodios" / "catedral"
sys.path.insert(0, str(ROOT / "motor"))
import osm  # noqa: E402

Z = 19
LADO_TILES = 5
ALTO, LENTE, RES = 1500.0, 175.0, 1280        # camara cenital: altura, mm, px
CENTRO_Y = 24.0


def tiles(lat, lon):
    n = 2 ** Z
    xt = (lon + 180) / 360 * n
    yt = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return int(xt) - LADO_TILES // 2, int(yt) - LADO_TILES // 2


def foto(lat, lon):
    dst = EP / "ref" / "aerea" / f"z{Z}.png"
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        x0, y0 = tiles(lat, lon)
        im = Image.new("RGB", (256 * LADO_TILES, 256 * LADO_TILES))
        for i in range(LADO_TILES):
            for j in range(LADO_TILES):
                url = ("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/"
                       f"{Z}/{y0 + j}/{x0 + i}")
                req = urllib.request.Request(url, headers={"User-Agent": "procedural-anime/1"})
                im.paste(Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=30).read())), (256 * i, 256 * j))
        im.save(dst)
    return np.array(Image.open(dst).convert("RGB")).astype(float)


def main():
    spec = json.loads((EP / "data" / "osm.json").read_text(encoding="utf-8"))
    M = osm.Marco(spec)
    lat, lon = spec["origen"]
    if "--sin-render" not in sys.argv:
        c = {"extends": "vistas.json", "estilo": "maqueta", "hora": "13:00", "fecha": "2026-12-21",
             "clima": "despejado", "width": RES, "height": RES, "frames": 1, "storyboard": [1],
             "line": {"radius": 0.06},
             "camera": {"keys": [{"frame": 1, "pos": [0, CENTRO_Y, ALTO], "aim": [0, CENTRO_Y + 0.2, 0]}],
                        "lens_keys": [[1, LENTE]], "clip_end": 3000}}
        (EP / "shots" / "_qa_aerea.json").write_text(json.dumps(c, indent=2), encoding="utf-8")
        subprocess.run([sys.executable, str(ROOT / "motor" / "render.py"), str(EP), "_qa_aerea", "--frames", "1"],
                       check=True, stdout=subprocess.DEVNULL)
    A = foto(lat, lon)
    bordes = np.array(Image.open(EP / "render" / "_prueba__qa_aerea" / "f_0001.png").convert("L")
                      .filter(ImageFilter.FIND_EDGES)) > 18
    n = 2 ** Z
    x0, y0 = tiles(lat, lon)

    def escena(px, py):
        X, Y = x0 + px / 256, y0 + py / 256
        return np.array(M({"lat": math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * Y / n)))),
                           "lon": X / n * 360 - 180}))
    p00 = escena(0, 0)
    ex, ey = (escena(1000, 0) - p00) / 1000, (escena(0, 1000) - p00) / 1000
    H, W = A.shape[:2]
    py, px = np.mgrid[0:H, 0:W]
    sx = p00[0] + px * ex[0] + py * ey[0]
    sy = p00[1] + px * ex[1] + py * ey[1]
    mpp = ALTO * 36 / LENTE / RES
    ri = (RES / 2 + sx / mpp).astype(int)
    rj = (RES / 2 - (sy - CENTRO_Y) / mpp).astype(int)
    ok = (ri >= 0) & (ri < RES) & (rj >= 0) & (rj < RES)
    tinta = np.zeros((H, W), bool)
    tinta[ok] = bordes[rj[ok], ri[ok]]
    out = A.copy()
    out[tinta] = [255, 40, 40]
    dst = EP / "out" / "_aerea.png"
    Image.fromarray(out.astype(np.uint8)).save(dst)
    print("->", dst)


if __name__ == "__main__":
    main()
