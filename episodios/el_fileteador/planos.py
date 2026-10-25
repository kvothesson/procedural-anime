"""planos.py - Genera los JSON de los planos de EL FILETEADOR (menos el 03, que
se escribe a mano) y el orden del montaje.

    python episodios/el_fileteador/planos.py

Los planos de la calle ubican al robot y las camaras sobre el plan real de
los conventillos (calle.lotes: el mismo que arma caminito.py). Al final
proyecta al robot en cada camara y avisa si queda afuera o al borde.

La historia del gris (s = metros de Caminito desde Garibaldi; el gris viene
desde s = 0 hacia Magallanes):
  02: el frente va de s 34 a 52    04: de 64 a 74 (paso el 03)
  05: sigue avanzando hasta que la banda lo alcanza y lo empuja para atras
"""

import json
import math
from pathlib import Path

import numpy as np

from calle import PISO, cargar, en_lote, lotes

EP = Path(__file__).resolve().parent
SH = EP / "shots"
CAM = {"seed": 3, "ancho": 8.0, "datos": "data/entorno.json"}


def guardar(nombre, d):
    (SH / f"{nombre}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def cara(N):
    """Grados de "face" para que el robot (mira a -Y local) mire hacia N."""
    return math.degrees(math.atan2(N[0], -N[1]))


def mirar(cam, aim):
    return {"pos": [round(v, 3) for v in cam], "aim": [round(v, 3) for v in aim]}


def main():
    C = cargar(EP, CAM["datos"])
    plan = lotes(C, CAM)
    base = {
        "width": 1080, "height": 1920, "fps": 12, "samples": 8,
        "sky": {"horizon": "#f2c9a2", "top": "#6d9bd2", "ambient": "#8a9cc0", "ambient_strength": 0.55,
                "zenith_at": 0.55},
        "fog": {"color": "#d9c8b2", "dist": 260.0},
        "toon": {"steps": [[0.0, 0.42], [0.10, 0.70], [0.38, 1.0]]},
        "lights": [{"kind": "SUN", "color": "#ffdcb0", "energy": 3.2, "hacia": [-0.30, -0.30, 0.90],
                    "angle": 0.8}],
        "line": {"color": "#1a1230", "radius": 0.018, "crease_deg": 120},
        "post": {"rain": False, "glow": {"threshold": 0.97}},
        "entorno": {"datos": "data/entorno_caminito.json", "terreno": False, "z": 0.0, "radio": 300,
                    "colores": {"piso": "#9c9488", "vereda": "#b9b0a2", "asfalto": "#6f6a66",
                                "camino": "#a89a86", "pasto": "#8fa77f", "playa": "#7f8a90",
                                "edificio": ["#c9b9a0", "#b8a58e", "#d4c4ab", "#bfae9a"],
                                "techo": "#7d6a5e", "teja": "#a2584a", "copa": ["#6f9a5a", "#83a866"],
                                "tronco": "#5a4a3c"},
                    "ventanas": {"pitch_x": 2.6, "pitch_z": 3.0, "base": 0.0, "margin_x": 0.32,
                                 "margin_z": 0.3, "lit": 0.0, "cold_ratio": 0.0, "warm": "#ffb05c",
                                 "cold": "#9ff0ff", "dark": "#3a3a48"}},
        "caminito": dict(CAM),
    }
    guardar("_calle", base)
    informe = []

    # ---------------------------------------------------------- 02_calle
    # robot en el balcon de un conventillo con escalera, cerca de Magallanes
    cand = [lo for lo in plan if lo.get("escalera") and 95 < lo["s0"] < 128]
    lo = max(cand, key=lambda lo: lo["s0"])
    b0, b1 = lo["balcon"]
    u = (b0 + b1) / 2
    pie = en_lote(lo, u, -0.55, PISO)
    pared = en_lote(lo, u + 0.15, -0.03, PISO + 1.25)
    s_lo = (lo["s0"] + lo["s1"]) / 2
    lado_lo = lo["lado"]
    cam = C.punto(s_lo + 13.0, -lado_lo * 1.0, 6.8)
    cam2 = C.punto(s_lo + 11.5, -lado_lo * 1.0, 6.5)
    aim = C.punto(s_lo - 22.0, lado_lo * 0.8, 0.0)
    d02 = {"extends": "_calle.json", "frames": 60, "storyboard": [1, 40],
           "_desc": "02 calle: el gris avanza desde el fondo; el fileteador pinta en un balcon",
           "caminito": {"barrido": {"keys": [[1, 34], [60, 52]], "alto": 24.0, "alfa": 0.55}},
           "camera": {"lens": 30, "keys": [{"frame": 1, **mirar(cam, aim)}, {"frame": 60, **mirar(cam2, aim)}]},
           "robot": {"at": list(pie), "face": cara(lo["N"]), "cast_shadow": True,
                     "ik_i": [{"frame": 1, "to": list(pared), "pole": [1.0, -0.4, -0.4]},
                              {"frame": 20, "to": [pared[0] + 0.15 * lo["U"][0], pared[1] + 0.15 * lo["U"][1],
                                                   pared[2] + 0.12], "pole": [1.0, -0.4, -0.4]},
                              {"frame": 40, "to": list(pared), "pole": [1.0, -0.4, -0.4]},
                              {"frame": 60, "to": [pared[0], pared[1], pared[2] - 0.1], "pole": [1.0, -0.4, -0.4]}],
                     "pose": [{"frame": 1, "cuello": [12, 0, 0]}]}}
    guardar("02_calle", d02)
    informe.append(("02_calle", d02, pie))

    # ---------------------------------------------------------- 04_duda
    s_r = 96.0
    pr, tr, nr = C.at(s_r)
    at = C.punto(s_r, 0.4, 0.0)
    fwd = -tr
    izq = np.array([-fwd[1], fwd[0]])
    frente = lambda d, l, z: [at[0] + fwd[0] * d + izq[0] * l, at[1] + fwd[1] * d + izq[1] * l, z]
    cam = [at[0] - fwd[0] * 2.3 + izq[0] * 1.05, at[1] - fwd[1] * 2.3 + izq[1] * 1.05, 1.55]
    aim = [at[0] + fwd[0] * 2.2 - izq[0] * 0.25, at[1] + fwd[1] * 2.2 - izq[1] * 0.25, 1.25]
    d04 = {"extends": "_calle.json", "frames": 48, "storyboard": [1, 18, 44],
           "_desc": "04 duda: de espaldas, la calle gris hasta la mitad; mira el pincel, saca la banda",
           "caminito": {"barrido": {"keys": [[1, 64], [48, 74]]}},
           "camera": {"lens": 28, "keys": [{"frame": 1, **mirar(cam, aim)},
                                           {"frame": 48, **mirar([cam[0] + fwd[0] * 0.3, cam[1] + fwd[1] * 0.3, 1.5], aim)}]},
           "robot": {"at": list(at), "face": cara(fwd), "cast_shadow": True,
                     "ik_i": [{"frame": 1, "to": frente(0.18, 0.28, 0.85), "pole": [1.0, 0.2, -0.6]},
                              {"frame": 10, "to": frente(0.32, 0.30, 1.40), "pole": [1.0, 0.2, -0.6]},
                              {"frame": 24, "to": frente(0.30, 0.28, 1.42), "pole": [1.0, 0.2, -0.6]},
                              {"frame": 32, "to": frente(0.05, 0.30, 0.78), "pole": [1.0, 0.2, -0.6]},
                              {"frame": 38, "to": frente(0.05, 0.30, 0.78), "pole": [1.0, 0.2, -0.6]},
                              {"frame": 46, "to": frente(0.35, 0.12, 1.05), "pole": [1.0, 0.2, -0.6]}],
                     "pose": [{"frame": 1, "cuello": [0, 0, 0]}, {"frame": 10, "cuello": [8, 0, 28]},
                              {"frame": 26, "cuello": [8, 0, 28]}, {"frame": 32, "cuello": [-6, 0, 0]},
                              {"frame": 48, "cuello": [-6, 0, 0]}],
                     "pincel_rot": [180, 0, 0], "banda_rot": [180, 0, 0],
                     "herramienta": [[1, "pincel"], [35, "banda"]]}}
    guardar("04_duda", d04)
    informe.append(("04_duda", d04, at))

    # ---------------------------------------------------------- 05_banda
    # el lado con mas balcones entre s 10 y 92
    def balcones(lado):
        return sum(1 for lo in plan if lo["lado"] == lado and lo.get("balcon") and 10 < lo["s0"] < 92)
    lado = 1 if balcones(1) >= balcones(-1) else -1
    s0, s1 = 92.5, 3.0
    cab = [[1, s0], [8, s0 - 0.8], [20, s0 - 8.0], [132, s1]]
    fr = np.arange(1, 133)
    head = np.interp(fr, [c[0] for c in cab], [c[1] for c in cab])
    gris = 76.0 + 0.10 * (fr - 1)
    F = np.minimum(gris, head)
    bkeys = [[int(f), round(float(v), 2)] for f, v in zip(fr, F) if f % 2 == 1 or f == 132]
    choque = int(fr[np.argmax(head <= gris)])
    at = C.punto(s0 + 0.2, lado * (4.0 - 0.6), 0.0)
    p0, t0, n0 = C.at(s0)
    N = n0 * lado
    toca = C.punto(s0, lado * 3.92, 1.4)
    # primero el robot apoyando la banda (de atras, a la altura de la mano)
    ckeys = [{"frame": 1, **mirar(C.punto(s0 + 3.2, -lado * 0.8, 1.9), C.punto(s0 - 1.0, lado * 3.4, 1.3))}]
    for f in (16, 28, 40, 52, 64, 76, 88, 100, 112, 124, 132):
        h = float(np.interp(f, fr, head))
        sc = min(h + 6.0, s0 + 4.0)
        ckeys.append({"frame": f, **mirar(C.punto(sc, -lado * 2.6, 3.6), C.punto(h - 2.0, lado * 4.0, 3.0))})
    d05 = {"extends": "_calle.json", "frames": 132, "storyboard": [10, 56, 110],
           "_desc": "05 banda: una sola linea corre por las fachadas y devuelve el color; frena al gris",
           "caminito": {"barrido": {"keys": bkeys, "hasta": [choque, choque + 6]}},
           "camera": {"lens": 26, "keys": ckeys},
           "banda_larga": {"lado": lado, "desde": s0, "hasta": s1, "keys": cab, "z_ini": 1.4, "radio": 0.075,
                           "firulete_dz": 0.17},
           "robot": {"at": list(at), "face": cara(N), "cast_shadow": True,
                     "ik_i": [{"frame": 1, "to": list(toca), "pole": [1.0, -0.4, -0.4]},
                              {"frame": 10, "to": list(toca), "pole": [1.0, -0.4, -0.4]},
                              {"frame": 20, "to": [toca[0] - t0[0] * 0.5, toca[1] - t0[1] * 0.5, 1.45],
                               "pole": [1.0, -0.4, -0.4]}],
                     "herramienta": [[1, "banda"]]}}
    guardar("05_banda", d05)
    informe.append(("05_banda", d05, at))

    # ---------------------------------------------------------- 06 y 01: la chapa del 03
    c03 = {"pos": [-0.20, -1.45, -0.25], "aim": [0.0, 0.0, -0.10]}
    # cerca, pero con el motivo entero; el barrido asoma justo adentro del borde derecho
    c_fin = {"pos": [-0.10, -1.42, -0.22], "aim": [0.03, 0.0, -0.11]}
    borde = 0.37
    d06 = {"extends": "03_filete.json", "frames": 60, "storyboard": [14, 60],
           "_desc": "06 firma: repique bajo el remate; la camara se acerca y asoma otro barrido (loop)",
           "chapa": {"colorida": True},
           "filete": {"terminado": True, "firma": [6, 22]},
           "corte": [[1, 5.0], [48, 5.0], [60, borde]],
           "camera": {"lens": 38, "ease": True, "keys": [{"frame": 1, **c03}, {"frame": 30, **c03},
                                                         {"frame": 60, **c_fin}]}}
    guardar("06_firma", d06)
    d01 = {"extends": "03_filete.json", "frames": 36, "storyboard": [1, 12, 36],
           "_desc": "01 gancho: el barrido cian borra el filete en bloques y deja la chapa gris; entra el pincel",
           "chapa": {"colorida": True},
           "filete": {"terminado": True, "firma": [-30, -25]},
           "corte": [[1, borde], [4, 0.30], [20, -0.70]],
           "pincel": {"camino": [[1, 0.70, -0.75, 0.30], [22, 0.70, -0.75, 0.30], [36, -0.24, -0.10, 0.02]]},
           "camera": {"lens": 38, "keys": [{"frame": 1, **c_fin}]}}
    guardar("01_gancho", d01)
    (SH / "timeline.json").write_text(json.dumps(
        {"name": "el_fileteador", "fps_unique": 12, "fps_out": 24,
         "shots": ["01_gancho", "02_calle", "03_filete", "04_duda", "05_banda", "06_firma"]}, indent=1),
        encoding="utf-8")

    # ---------------------------------------------------------- encuadre del robot
    for nombre, d, p in informe:
        k = d["camera"]["keys"][0]
        x, y = proyectar(k["pos"], k["aim"], d["camera"]["lens"], (p[0], p[1], p[2] + 0.8))
        estado = "ok" if 0.08 < x < 0.92 and 0.06 < y < 0.94 else ("al borde" if -0.02 < x < 1.02 and -0.02 < y < 1.02 else "AFUERA")
        print(f"{nombre}: robot en pantalla ({x:.2f}, {y:.2f}) {estado}")


def proyectar(pos, aim, lens, q, w=1080, h=1920):
    """(x, y) en pantalla (0..1, y hacia abajo) de q: camara que mira a aim,
    sensor de 36 mm en el alto."""
    pos, aim, q = (np.asarray(v, float) for v in (pos, aim, q))
    f = aim - pos
    f /= np.linalg.norm(f)
    r = np.cross(f, (0, 0, 1))
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    d = q - pos
    z = d @ f
    sx = (d @ r) / z * lens / (36.0 * w / h)
    sy = (d @ u) / z * lens / 36.0
    return 0.5 + sx, 0.5 - sy


if __name__ == "__main__":
    main()
