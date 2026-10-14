"""
storyboard.py - Hoja de storyboard: un cuadro clave (o varios) por plano, con
el post aplicado y la descripcion del plano. Para aprobar historia y encuadres
antes de renderizar planos enteros (es barato iterar aca).

    python motor/storyboard.py episodios/<ep>                 # todos los planos del timeline
    python motor/storyboard.py episodios/<ep> 03_tarde 06_antes

Cada plano elige sus cuadros con "storyboard": [frames] en su JSON (si no, el
del medio). Renderiza con render.py --frames (render/_prueba_<plano>/), aplica
el post a esos cuadros y arma out/storyboard.png.
"""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

MOTOR = Path(__file__).resolve().parent
sys.path.insert(0, str(MOTOR))
import post  # noqa: E402
from plano import load_shot, merge  # noqa: E402

TW, TH = 300, 533          # miniatura 9:16
CAP = 150                  # alto del texto debajo


def main():
    ep = Path(sys.argv[1]).resolve()
    tl = json.loads((ep / "shots" / "timeline.json").read_text(encoding="utf-8"))
    shots = sys.argv[2:] or tl["shots"]
    celdas = []
    for shot in shots:
        cfg = load_shot(ep / "shots" / f"{shot}.json")
        frames = cfg.get("storyboard") or [max(1, cfg["frames"] // 2)]
        subprocess.run([sys.executable, str(MOTOR / "render.py"), str(ep), shot, "--frames", *map(str, frames)],
                       check=True, stdout=subprocess.DEVNULL)
        P = merge(post.DEFAULTS, cfg.get("post", {}))
        src = ep / "render" / f"_prueba_{shot}"
        dst = ep / "out" / f"_storyboard_{shot}"
        dst.mkdir(parents=True, exist_ok=True)
        post._init(P, cfg["width"], cfg["height"], dst)
        for f in frames:
            post._frame(src / f"f_{f:04d}.png")
            celdas.append((shot, f, cfg.get("_desc", ""), dst / f"p_{f:04d}.png"))
        print(f"{shot}: {frames}")
    cols = 4
    rows = (len(celdas) + cols - 1) // cols
    hoja = Image.new("RGB", (cols * TW, rows * (TH + CAP)), (14, 12, 22))
    d = ImageDraw.Draw(hoja)
    try:
        f1 = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", 17)
        f2 = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 12)
    except OSError:
        f1 = f2 = ImageFont.load_default()
    for k, (shot, f, desc, path) in enumerate(celdas):
        x, y = (k % cols) * TW, (k // cols) * (TH + CAP)
        img = cv2.cvtColor(cv2.resize(cv2.imread(str(path)), (TW, TH), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
        hoja.paste(Image.fromarray(img), (x, y))
        d.text((x + 8, y + TH + 6), f"{shot} · f{f}", fill=(255, 176, 0), font=f1)
        txt = desc.split(" - ", 1)[-1]
        for i, line in enumerate(textwrap.wrap(txt, 40)[:8]):
            d.text((x + 8, y + TH + 30 + i * 14), line, fill=(220, 214, 200), font=f2)
    out = ep / "out" / "storyboard.png"
    hoja.save(out)
    print("->", out)


if __name__ == "__main__":
    main()
