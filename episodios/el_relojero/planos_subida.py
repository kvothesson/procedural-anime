"""
planos_subida.py - Genera 03_subida.json: el relojero sube la escalera caracol
del campanario de la Catedral de San Isidro. Camara abajo, entre la escalera y el
muro, mirando hacia arriba: la espiral, las ventanas angostas (arboles y lluvia
afuera) y, arriba, la abertura de la sala de maquinas con una rueda y su pinon en
silueta. El robot pasa por encima a contraluz, dos escalones por tic.

    python episodios/el_relojero/planos_subida.py
"""

import json
from pathlib import Path

D = Path(__file__).resolve().parent / "shots"

# rueda (40 dientes) y pinon (10) arriba, eje vertical, engranados en el angulo 0:
# diente de la rueda en 0 y hueco del pinon en 180 (perfil: diente 0.325, hueco 0.825)
DEPTH = 0.03
R_BIG, R_PIN = 1.0, 0.25
TIP, GAP = 0.325, 0.825


def main():
    c6 = json.loads((D / "06_sacrificio.json").read_text(encoding="utf-8"))
    noche = c6["esfera"]["noche"]
    c = {
        "_desc": ("Plano 3 (la subida): el relojero sube la escalera caracol del campanario, un escalon por tic. "
                  "Corte: camara afuera de la torre, el muro cercano no se dibuja; atras, ventanas a los arboles."),
        "width": 1080, "height": 1920, "fps": 12, "frames": 60, "samples": 8,
        "sky": {"horizon": "#140f24", "top": "#0a0814", "ambient": "#4a3542", "ambient_strength": 0.55},
        "fog": {"color": "#120e1e", "dist": 30.0},
        "toon": c6["toon"],
        "lights": [
            # calida desde la sala de arriba; la fria apenas (si no, el verdin sale azul)
            {"kind": "SUN", "color": "#ffd9a0", "energy": 3.0, "rot": [38, 0, 235], "angle": 0.5},
            {"kind": "SUN", "color": "#7f9cff", "energy": 0.18, "rot": [-75, 0, 140], "shadow": False},
        ],
        "line": c6["line"],
        # ancha: el robot pasa con los brazos (camino a 0,75 m, columna 0,25, parantes 1,25)
        # 12 escalones por vuelta: a 0,8 m del centro la huella es de 42 cm (el pie mide 26)
        "escalera": {"center": [0, 0], "r_in": 0.25, "r_out": 1.3, "rise": 0.2, "per_turn": 12, "steps": 30,
                     "thick": 0.07, "r_wall": 1.75, "step": "#7a5a40", "wall": "#4a3a52", "luz": "#ffd9a0",
                     "luz_fuerza": 1.4, "ventanas": 6, "ventana_ang": -40, "ventana_paso": 28, "ventana_dz": 0.55,
                     "noche": noche},
        "engranajes": {
            "color": "#b08a3e", "tick": {"bps": 1.0, "jump": 0.4},
            "list": [
                {"name": "rueda_campanario", "at": [0, 0, 7.4], "axis": "z", "r": R_BIG, "teeth": 40, "depth": DEPTH,
                 "thick": 0.08, "spokes": 6, "hub": 0.1, "step": 3, "phase": round(-360 * TIP / 40, 3)},
                {"name": "pinon_campanario", "at": [R_BIG + R_PIN - 0.9 * DEPTH, 0, 7.4], "axis": "z", "r": R_PIN,
                 "teeth": 10, "depth": DEPTH, "thick": 0.08, "spokes": 4, "hub": 0.05, "step": -12,
                 "phase": round(180 - 360 * GAP / 10, 3)},
            ],
        },
        "relojero": {
            "face": 0, "cast_shadow": False,
            # un escalon por tic; los pies apoyan 1 cm arriba (si no, cortan el escalon siguiente)
            "camino": {"center": [0, 0], "r": 0.76, "rise": 0.2, "per_turn": 12, "frames_step": 12, "step0": 4,
                       "start": 1, "z0": 0.012},
            # codos doblados: con los brazos colgando las manos tocan los escalones que vienen
            "pose": [{"frame": 1, "cuello": [10, 0, 0], "codo_i": [-35, 0, 0], "codo_d": [-35, 0, 0],
                      "muneca_i": [0, 0, 0], "muneca_d": [0, 0, 0], "tapa": 0, "ojo": 1.0, "corazon": 1.0}],
        },
        # corte: camara afuera de la torre (el muro cercano no se dibuja), el robot sube de perfil
        "camera": {"lens": 24, "clip_end": 60, "ease": True, "keys": [
            {"frame": 1, "pos": [-3.9, -1.0, 1.25], "aim": [-0.35, -0.25, 2.1]},
            {"frame": 60, "pos": [-3.7, -1.6, 1.45], "aim": [-0.3, -0.4, 2.5]}]},
        "post": dict(c6.get("post", {})),
    }
    (D / "03_subida.json").write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ok")


if __name__ == "__main__":
    main()
