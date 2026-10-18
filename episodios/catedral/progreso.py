"""Ronda de progreso de la estructura: camaras puestas como fotos de
referencia, render neutro de dia (maqueta, 15:30, despejado) y una hoja con
la foto arriba y el render abajo.

    python progreso.py <iteracion>   # -> episodios/catedral/out/_progreso_<it>.png
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(r"D:\repos\procedural-anime")
EP = ROOT / "episodios" / "catedral"
# fotos de referencia (Wikimedia Commons, CC): se bajan aparte, no van al repo
REF = Path(__file__).resolve().parent / "ref"
sys.path.insert(0, str(ROOT / "motor"))

ENT = json.loads((EP / "data" / "entorno.json").read_text(encoding="utf-8"))
T = ENT["terreno"]


def H(x, y):
    n = T["n"]
    fx = min(max((x - T["x0"]) / T["paso"], 0), n - 1.001)
    fy = min(max((y - T["y0"]) / T["paso"], 0), n - 1.001)
    i, j = int(fx), int(fy)
    ax, ay = fx - i, fy - j
    g = T["z"]
    return ((g[j * n + i] * (1 - ax) + g[j * n + i + 1] * ax) * (1 - ay)
            + (g[(j + 1) * n + i] * (1 - ax) + g[(j + 1) * n + i + 1] * ax) * ay)


def ojo(x, y, h=1.6):
    return [x, y, round(H(x, y) + h, 2)]


# (nombre, foto de referencia, pos, mira, lente, tinta)
AFUERA = [
    ("frente desde la plaza", "67.jpg", ojo(2.0, -30.0), [0, -6, 32], 13, 0.012),
    ("3/4 desde adelante a la izquierda", "70.jpg", ojo(-28.0, -30.0), [0, 8, 22], 16, 0.012),
    ("costado desde Libertador", "31.jpg", ojo(27.0, 2.0), [0, 16, 16], 17, 0.012),
    ("hastial del crucero", "05.jpg", ojo(26.0, 36.1), [15.4, 36.1, 21], 20, 0.012),
    ("desde el rio", "45.jpg", [-560.0, 140.0, -24.0], [0, 20, 22], 60, 0.15),
]
ADENTRO = [
    ("nave desde la entrada", "50.jpg", [0, 1.0, 1.6], [0, 46, 8.5], 16, 0.006),
    ("presbiterio y abside", "61.jpg", [0, 24.0, 1.6], [0, 48, 9.0], 18, 0.006),
    ("nave lateral", "57.jpg", [-7.4, 6.0, 1.6], [-4.7, 20, 9.5], 16, 0.006),
]


def shot(name, vistas, interior):
    c = {"extends": "vistas.json", "estilo": "maqueta", "hora": "15:30", "fecha": "2026-10-17", "clima": "despejado",
         "frames": len(vistas), "storyboard": list(range(1, len(vistas) + 1)),
         "line": {"radius": vistas[0][5], "radius_keys": [[i + 1, v[5]] for i, v in enumerate(vistas)]},
         "camera": {"keys": [{"frame": i + 1, "pos": v[2], "aim": v[3]} for i, v in enumerate(vistas)],
                    "lens_keys": [[i + 1, v[4]] for i, v in enumerate(vistas)]}}
    if interior:
        c["drop"] = ["servidores"]          # la estructura se compara sin los racks
        # sin GI, EEVEE ilumina el interior con todo el cielo: ambiente bajo y un
        # sol sin sombra desde arriba para que la forma se lea por sombreado
        for k in ("hora", "fecha", "clima"):
            c.pop(k)
        c["sky"] = {"horizon": "#8a8f9a", "top": "#5a606c", "ambient": "#6a707c", "ambient_strength": 0.45}
        c["lights"] = [{"kind": "SUN", "color": "#fff4e6", "energy": 1.7, "rot": [38, 0, 25], "shadow": False}]
        c["catedral"] = {"puertas": {"abre": [[1, 80]]}}
    (EP / "shots" / f"{name}.json").write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    it = sys.argv[1]
    shot("_prog_afuera", AFUERA, False)
    shot("_prog_adentro", ADENTRO, True)
    for name, vistas in (("_prog_afuera", AFUERA), ("_prog_adentro", ADENTRO)):
        subprocess.run([sys.executable, str(ROOT / "motor" / "render.py"), str(EP), name, "--frames",
                        *map(str, range(1, len(vistas) + 1))], check=True, stdout=subprocess.DEVNULL)
    todas = [("_prog_afuera", i + 1, v) for i, v in enumerate(AFUERA)] + \
            [("_prog_adentro", i + 1, v) for i, v in enumerate(ADENTRO)]
    w, h = 300, 533
    hoja = Image.new("RGB", (w * len(todas), h * 2 + 40), (14, 12, 22))
    d = ImageDraw.Draw(hoja)
    keep = EP / "out" / f"_progreso_{it}"
    keep.mkdir(parents=True, exist_ok=True)
    for c, (name, f, v) in enumerate(todas):
        ref = Image.open(REF / v[1]).convert("RGB")
        ref.thumbnail((w, h))
        hoja.paste(ref, (c * w + (w - ref.width) // 2, 20 + (h - ref.height) // 2))
        r = Image.open(EP / "render" / f"_prueba_{name}" / f"f_{f:04d}.png").convert("RGB")
        r.save(keep / f"{c + 1:02d}.png")
        hoja.paste(r.resize((w, h)), (c * w, h + 40))
        d.text((c * w + 4, 4), v[0], fill=(255, 210, 120))
    d.text((4, h + 24), f"iteracion {it}: render (arriba, foto real)", fill=(255, 255, 255))
    out = EP / "out" / f"_progreso_{it}.png"
    hoja.save(out)
    print("->", out)


if __name__ == "__main__":
    main()
