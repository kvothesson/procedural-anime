"""Genera los planos del demo de reglas.

    python episodios/_reglas/planos.py

giro_mal / giro_bien: la regla "Giro continuo y cadencia" (docs/PRODUCCION.md,
3b). Las mismas dos ruedas, engranadas, a dos velocidades. La velocidad se da
en grados por cuadro unico y se pasa a grados por segundo con la fps del plano.
"""

import json
from pathlib import Path

SHOTS = Path(__file__).resolve().parent / "shots"
FPS, FRAMES = 12, 36

# rueda arriba, pinon abajo, mismos ejes ("rot"): el diente de la rueda mira
# al pinon (270 grados locales) y el hueco del pinon mira a la rueda (90).
# Centro del diente en 0.325 del paso y del hueco en 0.825 (mecanica.PERFIL).
R1, N1, R2, N2, DEPTH = 0.6, 24, 0.3, 12, 0.06
Z1 = 1.95
Z2 = Z1 - (R1 + R2 - 0.9 * DEPTH)
PASO1 = 360 / N1


def gear(name, z, r, n, r_in, hub, phase, spin):
    return {"name": name, "at": [0, 0, round(z, 4)], "rot": [90, 0, 0], "r": r, "teeth": n,
            "depth": DEPTH, "thick": 0.08, "r_in": r_in, "spokes": 0, "hub": hub,
            "phase": round(phase, 4), "spin": round(spin, 4)}


def label(text, color):
    return {"text": text, "font": "texto", "size": 46, "color": color, "pos": [0.5, 0.82], "frames": [1, FRAMES],
            "outline": 6, "glow": 0.15, "max_w": 0.9}


def shot(grados_por_cuadro, texto, color):
    spin1 = grados_por_cuadro * FPS              # grados por segundo
    spin2 = -spin1 * N1 / N2                     # razon inversa, signo opuesto
    return {
        "_desc": "Generado por planos.py. Demo de la regla 'Giro continuo y cadencia'.",
        "width": 1080, "height": 1920, "fps": FPS, "frames": FRAMES, "samples": 8,
        "storyboard": [1, 18, 36],
        "sky": {"horizon": "#140f24", "top": "#0a0814", "ambient": "#1a1530", "ambient_strength": 0.5},
        "fog": {"color": "#120e1e", "dist": 40.0},
        "toon": {"steps": [[0.0, 0.07], [0.04, 0.32], [0.4, 1.0]]},
        "lights": [
            {"kind": "SUN", "color": "#ffd9a0", "energy": 2.2, "rot": [50, 0, -35], "angle": 0.3},
            {"kind": "SUN", "color": "#7fd6ff", "energy": 1.4, "rot": [-70, 0, 0], "shadow": False},
        ],
        "line": {"color": "#0d0b24", "radius": 0.006, "crease_deg": 140},
        "engranajes": {"color": "#b08a3e", "list": [
            gear("rueda", Z1, R1, N1, 0.46, 0.09, 270 - 0.325 * PASO1, spin1),
            gear("pinon", Z2, R2, N2, 0.17, 0.06, 90 - 0.825 * 360 / N2, spin2),
        ]},
        "camera": {"lens": 50, "clip_end": 100, "keys": [
            {"frame": 1, "pos": [0, -3.9, 1.62], "aim": [0, 0, 1.62]}]},
        "post": {"rain": False, "glow": {"threshold": 0.9}, "textos": [label(texto, color)]},
    }


def main():
    SHOTS.mkdir(exist_ok=True)
    planos = {
        # casi un paso entero por cuadro: el ojo ve -1 grado por cuadro (al reves)
        "giro_mal": shot(PASO1 - 1, f"MAL\n{PASO1 - 1:.0f} grados por cuadro, el paso es de {PASO1:.0f}", "#ff7a7a"),
        # menos de medio paso: se lee el giro real
        "giro_bien": shot(4, f"BIEN\n4 grados por cuadro, menos de medio paso", "#8dffb0"),
    }
    for name, d in planos.items():
        g = d["engranajes"]["list"][0]
        avance = g["spin"] / FPS
        print(f"{name}: {avance:.1f} grados por cuadro unico = {avance / PASO1:.2f} pasos"
              + ("  (AVISO: medio paso o mas)" if avance >= PASO1 / 2 else ""))
        (SHOTS / f"{name}.json").write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tl = {"name": "_reglas", "fps_unique": FPS, "fps_out": 24, "shots": list(planos)}
    (SHOTS / "timeline.json").write_text(json.dumps(tl, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
