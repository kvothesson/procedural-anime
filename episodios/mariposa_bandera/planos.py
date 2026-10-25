"""
planos.py - Genera los planos 3 a 7 de LA BANDERA (los que dependen de posiciones
calculadas: las crisalidas del arbol, la camara que sigue a la mariposa).

    python episodios/mariposa_bandera/planos.py

Los planos 1 y 2 se escriben a mano. Todos heredan la luz y el look de 02_alas.
"""

import importlib.util
import json
import math
from pathlib import Path

EP = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("arbol_ep", EP / "arbol.py")
arbol_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(arbol_mod)

FPS = 24
L = 0.05

RESERVA = {"base": [0, 0, 0], "alto": 2.6, "niveles": 4, "seed": 4, "crisalidas": 46,
           "largo": [0.02, 0.028], "radio": 0.05}
ARBOL = arbol_mod.arbol(RESERVA)
COLG = ARBOL["colgadas"]


def v(a, b, k=1.0):
    return [x + y * k for x, y in zip(a, b)]


def mirar(cam, objetivo):
    return {"pos": [round(x, 4) for x in cam], "aim": [round(x, 4) for x in objetivo]}


def guardar(nombre, d):
    (EP / "shots" / f"{nombre}.json").write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    print("plano", nombre)


def libre(p, sin=()):
    return arbol_mod.libre(ARBOL, p, sin)


def camino_libre(a, b, margen=0.065, sin=()):
    return arbol_mod.camino_libre(ARBOL, a, b, margen, sin)


def elegir_intentos():
    """Dos crisalidas bajas, de tramos casi horizontales, con aire alrededor
    para que las alas no toquen ninguna rama, y un camino libre entre ellas."""
    def horizontal(i):
        # de una ramita que baja no hay forma de ponerse enfrente sin cruzarla
        pts = ARBOL["ramas"][COLG[i]["rama"]]["pts"]
        k = min(range(len(pts) - 1), key=lambda j: math.dist(pts[j], COLG[i]["at"]))
        d = [b - a for a, b in zip(pts[k], pts[k + 1])]
        return abs(d[2]) < 0.6 * math.hypot(*d)

    def aire(i):
        t = toque(COLG[i])
        otras = libre(t["toca"], sin=(COLG[i]["rama"],))
        return min(otras, libre(t["cerca"], sin=(COLG[i]["rama"],)), libre(t["lejos"])) > 0.05 \
            and camino_libre(t["cerca"], t["lejos"], sin=(COLG[i]["rama"],))
    buenas = sorted((i for i in range(len(COLG)) if horizontal(i) and aire(i)),
                    key=lambda i: COLG[i]["at"][2] + 0.6 * COLG[i]["at"][1])
    for a in buenas:
        for b in buenas:
            if b == a or not 0.15 < math.dist(COLG[a]["at"], COLG[b]["at"]) < 0.6:
                continue
            ta, tb = toque(COLG[a]), toque(COLG[b])
            for baja in (0.12, 0.2, 0.3, 0.4):
                ab = [(x + y) / 2 for x, y in zip(ta["lejos"], tb["lejos"])]
                ab[2] = min(ta["lejos"][2], tb["lejos"][2]) - baja
                if camino_libre(ta["lejos"], ab) and camino_libre(ab, tb["lejos"]) and libre(ab) > 0.065:
                    return a, b, ab
    raise SystemExit("no hay dos crisalidas con aire alrededor")


def rama_para_posarse():
    """Un tramo casi horizontal de una rama fina (nivel 2), cerca del centro de
    las crisalidas, con aire alrededor. Devuelve el punto (el cuerpo arriba de
    la rama), el rumbo y la pendiente del tramo: la mariposa se posa a lo largo
    de la rama, con las alas a los costados."""
    cx = [sum(c["at"][k] for c in COLG) / len(COLG) for k in range(3)]
    mejor = None
    for k, r in enumerate(ARBOL["ramas"]):
        if r["nivel"] != 2:
            continue
        for a, b in zip(r["pts"][1:-2], r["pts"][2:-1]):
            d = [y - x for x, y in zip(a, b)]
            if abs(d[2]) > 0.35 * math.hypot(*d):
                continue
            p = [(x + y) / 2 for x, y in zip(a, b)]
            if libre(v(p, [0, 0, r["radio"] + 0.17 * L]), sin=(k,)) < 0.07:
                continue
            dist = math.dist(p, cx)
            if mejor is None or dist < mejor[0]:
                mejor = (dist, p, r["radio"], d)
    _, p, rad, d = mejor
    yaw = math.degrees(math.atan2(-d[0], d[1]))
    pitch = math.degrees(math.atan2(d[2], math.hypot(d[0], d[1])))
    return [p[0], p[1], p[2] + rad + 0.17 * L], yaw, pitch


def toque(c, rama_dir=None, camara=(0.12, -0.17)):
    """Donde ponerse para tocar una crisalida con las antenas sin barrerla con
    las alas: de frente a ella, del lado de la camara, con el cuerpo
    perpendicular a la rama (las alas quedan paralelas a la rama y no la
    cruzan), a media altura de la crisalida."""
    if rama_dir is None:
        pts = ARBOL["ramas"][c["rama"]]["pts"]
        k = min(range(len(pts) - 1), key=lambda i: math.dist(pts[i], c["at"]))
        rama_dir = [b - a for a, b in zip(pts[k], pts[k + 1])]
    dx, dy = rama_dir[0], rama_dir[1]
    m = math.hypot(dx, dy) or 1.0
    f = [-dy / m, dx / m]                       # hacia la crisalida, horizontal
    if f[0] * camara[0] + f[1] * camara[1] > 0:
        f = [-f[0], -f[1]]
    z = c["at"][2] - c["largo"] * 0.8
    yaw = math.degrees(math.atan2(-f[0], f[1]))

    def a(d):
        return [c["at"][0] - f[0] * d, c["at"][1] - f[1] * d, z]
    return {"toca": a(0.042), "cerca": a(0.075), "lejos": v(a(0.1), [0, 0, -0.03]), "yaw": yaw}


def main():
    base = {"extends": "02_alas.json", "drop": ["mariposa", "storyboard"]}

    # --- 3. Puerto Madero: se va sola entre las gruas, chica contra la ciudad
    puerto = {
        "ancho": 60, "largo": 520,
        "docks": {"desde": -80, "hasta": 400},
        "gruas": [{"at": [-36, y], "rumbo": 0, "alto": 12, "pluma": 32, "angulo": 38, "cuelga": 14}
                  for y in (0, 75, 150, 225)],
        "torres": [{"at": [70 + 35 * (k % 3), 20 + 60 * k], "tam": [26, 30], "alto": 90 + 25 * ((k * 7) % 4)}
                   for k in range(6)],
        "puente": {"y": 175, "pie_x": 8, "inclina": 39},
    }
    cam3 = [-9.6, -1.2, 23.4]
    p0 = [-9.5, -0.81, 23.28]
    guardar("03_puerto", {**base,
        "_desc": "Plano 3: sale de la punta del cable de la grua y se aleja sobre el dique de Puerto Madero; la ciudad no la mira. Se achica hasta ser un punto de luz.",
        "frames": 132, "storyboard": [1, 50, 120],
        "fog": {"color": "#120c26", "dist": 260.0},
        "line": {"color": "#0d0b24", "radius": 0.012, "crease_deg": 150},
        "puerto": puerto,
        "mascara_anclas": True,
        "mariposa": {"escala": L, "sin_tinta": True, "ancla": True, "keys": [[1, p0, -8, 8], [30, v(p0, [0.4, 3, -0.6]), -10, 8],
                                           [70, v(p0, [3, 18, -4]), -8, 6], [132, v(p0, [9, 70, -11]), -5, 4]],
                     "aleteo": [[1, 10, 62, 22]], "halo": 0.08, "halo_desde": 56, "dorso_k": 0.74,
                     "estela": {"por_golpe": 30, "base": 1.5, "vida": [20, 40], "tam": 0.06, "brillo": 4.0}},
        "camera": {"lens": 24, "lens_keys": [[1, 45], [44, 24]], "clip_start": 0.05, "clip_end": 2000, "ease": True,
                   # la acompana un trecho y la deja ir
                   "keys": [{"frame": 1, **mirar(cam3, v(p0, [0.03, 0.8, -0.2]))},
                            {"frame": 44, **mirar(v(p0, [0.6, 4.0, -0.6]), v(p0, [2.0, 30, -4.0]))},
                            {"frame": 132, **mirar(v(p0, [0.62, 4.1, -0.62]), v(p0, [6.5, 60, -9.0]))}]},
        "post": {"fps_unique": 24, "fps_out": 24, "glow": {"threshold": 0.8, "radii": [5, 18, 55],
                 "weights": [0.7, 0.55, 0.4], "strength": 1.4}}})

    # --- 4. La Reserva: prueba con dos crisalidas y no puede; pierde color
    a, b, abajo = elegir_intentos()        # "abajo": el paso libre por debajo de las ramas
    ca, cb = toque(COLG[a]), toque(COLG[b])
    llega = v(ca["cerca"], [0.4, -0.5, 0.15])
    keys4 = [[1, llega, ca["yaw"], 5], [26, ca["cerca"], ca["yaw"], 5], [36, ca["toca"], ca["yaw"], 10],
             [52, ca["toca"], ca["yaw"], 10], [62, ca["lejos"], ca["yaw"], 0], [74, abajo, cb["yaw"], 0],
             [86, cb["lejos"], cb["yaw"], 0], [94, cb["cerca"], cb["yaw"], 5], [102, cb["toca"], cb["yaw"], 10], [118, cb["toca"], cb["yaw"], 10],
             [132, cb["lejos"], cb["yaw"], 0], [168, v(cb["lejos"], [0.0, 0.0, -0.02]), cb["yaw"], 0]]
    reserva4 = dict(RESERVA, intentos=[[a, 44, "nada"], [b, 110, "parpadeo"]])
    cam4 = [[1, llega], [40, ca["toca"]], [78, abajo], [108, cb["toca"]], [168, cb["toca"]]]
    keys_cam4 = [{"frame": f, **mirar(v(q, [0.12, -0.17, 0.03]), q)} for f, q in cam4]
    guardar("04_reserva", {**base,
        "_desc": "Plano 4: el arbol seco de la Reserva lleno de crisalidas grises. Toca una con las antenas: nada. Otra: un parpadeo que se apaga. Las puntas de sus alas pierden el color.",
        "frames": 168, "storyboard": [30, 112, 160],
        "colision_ok": [["antena_1", f"cris_{a:02d}"], ["antena_-1", f"cris_{a:02d}"],
                        ["antena_1", f"cris_{b:02d}"], ["antena_-1", f"cris_{b:02d}"]],
        "reserva": reserva4,
        "mariposa": {"escala": L, "keys": keys4,
                     # cerca de la crisalida aletea suave y con las alas altas: no la barre
                     "aleteo": [[1, 10, 55, 22], [26, 12, 20, 62], [56, 12, 20, 62], [64, 10, 55, 22],
                                [92, 12, 20, 62], [122, 12, 20, 62], [134, 14, 30, 30]],
                     "antenas": [[1, 0, 0], [30, 0, 0], [36, 22, 8], [56, 22, 8], [62, 0, 0], [96, 0, 0], [102, 22, 8],
                                 [120, 22, 8], [128, 0, 0]],
                     "apaga": [[1, 1.0], [48, 1.0], [60, 0.82], [114, 0.82], [130, 0.62]], "humeda": "#5c6070",
                     "estela": {"por_golpe": 12, "base": 0.3, "vida": [12, 24], "tam": 0.012}},
        "bokeh": {"centro": [0, 0, 1.4], "dir": [-0.6, 0.8, 0.0], "dist": [6, 50], "count": 160, "seed": 9},
        "camera": {"lens": 40, "clip_start": 0.02, "clip_end": 400, "ease": True,
                   "dof": {"objeto": "mariposa", "fstop": 4.0}, "keys": keys_cam4}})

    # --- 5. La entrega: se posa, abre las alas y vuelca su luz en el arbol
    pose, YAW, PITCH = rama_para_posarse()
    f_luz = 50
    rev = 70
    guardar("05_entrega", {**base,
        "_desc": "Plano 5: se posa en una rama, abre las alas y vuelca toda su luz: baja por las ramas y despierta a las crisalidas una por una. Sus alas quedan grises. Silencio.",
        "frames": 144, "storyboard": [30, 80, 140],
        "reserva": dict(RESERVA, despierta={"desde": pose, "frame": f_luz, "vel": 0.025, "revienta": rev}),
        "mariposa": {"escala": L, "keys": [[1, v(pose, [0.25, -0.3, 0.2]), YAW, 5], [26, pose, YAW, PITCH], [144, pose, YAW, PITCH]],
                     "aleteo": [[1, 10, 55, 22], [22, 12, 30, 40], [28, 12, 0, 80], [36, 12, 0, 80], [46, 12, 0, 35], [144, 12, 0, 35]],
                     "apaga": [[1, 0.62], [50, 0.62], [110, 0.06], [144, 0.06]], "rebote": 0.0, "humeda": "#5c6070",
                     "estela": {"por_golpe": 10, "base": 0.6, "vida": [16, 30], "tam": 0.012}},
        "bokeh": {"centro": pose, "dir": [-0.6, 0.8, -0.1], "dist": [6, 50], "count": 160, "seed": 9},
        "camera": {"lens": 40, "clip_start": 0.02, "clip_end": 400, "ease": True,
                   "dof": {"objeto": "mariposa", "fstop": 5.6},
                   "keys": [{"frame": 1, **mirar(v(pose, [0.2, -0.3, 0.12]), pose)},
                            {"frame": 50, **mirar(v(pose, [0.1, -0.16, 0.08]), pose)},
                            {"frame": 144, **mirar(v(pose, [0.9, -1.6, 0.5]), v(pose, [0, 0, -0.2]))}]}})

    # --- 6. El enjambre: revientan y suben sobre el rio, la ciudad atras
    destino = v(pose, [-0.6, 1.2, 1.6])
    guardar("06_enjambre", {**base,
        "_desc": "Plano 6: las crisalidas revientan y el enjambre celeste y blanco sube sobre el rio con la ciudad atras. Ella, gris, queda en la rama.",
        "frames": 144, "storyboard": [20, 70, 140],
        "reserva": dict(RESERVA, despierta={"desde": pose, "frame": f_luz - 144, "vel": 0.025, "revienta": rev},
                        enjambre={"destino": destino, "radio": 0.45, "max": 36, "escala": L, "vuelo": 110}),
        "mariposa": {"escala": L, "keys": [[1, pose, YAW, PITCH], [144, pose, YAW, PITCH]], "aleteo": [[1, 12, 0, 35]],
                     "apaga": [[1, 0.06]], "rebote": 0.0, "humeda": "#5c6070"},
        "bokeh": {"centro": pose, "dir": [-0.5, 0.75, 0.4], "dist": [8, 60], "count": 200, "seed": 12},
        "camera": {"lens": 30, "clip_start": 0.02, "clip_end": 400, "ease": True,
                   "dof": {"dist": 0.7, "fstop": 5.6},
                   "keys": [{"frame": 1, **mirar(v(pose, [0.45, -0.7, 0.15]), v(pose, [0, 0.1, -0.05]))},
                            {"frame": 80, **mirar(v(pose, [0.25, -0.55, 0.7]), v(pose, [-0.3, 0.6, 1.0]))},
                            {"frame": 144, **mirar(v(pose, [0.0, -0.3, 1.2]), v(destino, [-0.3, 0.6, 0.4]))}]}})

    # --- 6b. Ella sola, gris (lo agridulce)
    guardar("06b_gris", {**base,
        "_desc": "Plano 6b: primer plano de ella gris en la rama, quieta; atras, desenfocadas, las luces del enjambre que se van. Una ultima escama cae.",
        "frames": 60, "storyboard": [1, 30, 60],
        "reserva": dict(RESERVA, despierta={"desde": pose, "frame": f_luz - 288, "vel": 0.025, "revienta": rev}),
        "mariposa": {"escala": L, "keys": [[1, pose, YAW, PITCH], [60, pose, YAW, PITCH]], "aleteo": [[1, 12, 0, 35]],
                     "apaga": [[1, 0.06]], "rebote": 0.0, "humeda": "#5c6070",
                     "estela": {"por_golpe": 0, "base": 0.08, "vida": [30, 40], "tam": 0.015, "seed": 3}},
        "bokeh": {"centro": pose, "dir": [-0.5, 0.75, 0.3], "dist": [5, 40], "count": 160, "seed": 12},
        "camera": {"lens": 45, "clip_start": 0.01, "clip_end": 400, "ease": True,
                   "dof": {"objeto": "mariposa", "fstop": 2.8},
                   "keys": [{"frame": 1, **mirar(v(pose, [0.1, -0.13, 0.05]), pose)},
                            {"frame": 60, **mirar(v(pose, [0.085, -0.11, 0.045]), pose)}]}})

    # --- 7. Loop: una de las nuevas llega al cable, toca la crisalida que espera ahi
    # y se va. La chispa que le deja es el latido con que arranca el plano 1.
    cam1 = json.loads((EP / "shots" / "01_crisalida.json").read_text(encoding="utf-8"))["camera"]
    k1 = cam1["keys"][0]
    c7 = toque({"at": [0, 0, 1.5], "largo": 0.026}, rama_dir=(1, 0, 0), camara=(0.095, 0.05))
    guardar("07_loop", {"extends": "01_crisalida.json", "drop": ["storyboard", "post"],
        "_desc": "Plano 7 (loop): una de las nuevas llega al cable de la grua, donde espera otra crisalida apagada. La toca con las antenas, le deja una chispa y se va. El ultimo cuadro es el primero del plano 1.",
        "frames": 120, "storyboard": [24, 56, 120],
        "colision_ok": [["antena_1", "crisalida"], ["antena_-1", "crisalida"]],
        "crisalida": {"at": [0, 0, 1.5], "largo": 0.026, "abierta": False, "luz": 0.003,
                      "grieta": [[1, 0.0]], "sacude": [[1, 0.0], [54, 0.0], [57, 1.5], [66, 0.0]],
                      "latido": [[1, 0.0], [53, 0.0], [56, 0.75], [66, 0.12], [84, 0.0]]},
        "mariposa": {"escala": L, "nombre": "mariposa",
                     "keys": [[1, v(c7["cerca"], [0.05, 0.08, 0.04]), c7["yaw"], 10], [30, c7["cerca"], c7["yaw"], 5],
                              [42, c7["toca"], c7["yaw"], 10], [62, c7["toca"], c7["yaw"], 10],
                              [74, c7["lejos"], c7["yaw"], 0], [100, v(c7["lejos"], [0.08, 0.2, 0.12]), c7["yaw"] - 30, -10],
                              [120, v(c7["lejos"], [0.12, 0.35, 0.2]), c7["yaw"] - 30, -10]],
                     "aleteo": [[1, 10, 55, 22], [30, 12, 20, 62], [64, 12, 20, 62], [74, 10, 60, 22]],
                     "antenas": [[1, 0, 0], [36, 0, 0], [42, 22, 8], [62, 22, 8], [70, 0, 0]],
                     "desaparece": 104,
                     "estela": {"por_golpe": 14, "base": 0.5, "vida": [12, 20], "tam": 0.012, "hasta": 92}},
        "camera": {"lens": 50, "clip_start": 0.01, "clip_end": 400, "ease": True,
                   "dof": {"objeto": "crisalida_piv", "fstop": 2.8},
                   "keys": [{"frame": 1, "pos": v(k1["pos"], [0.04, 0.06, 0.015]), "aim": v(k1["aim"], [0, 0.01, 0])},
                            {"frame": 60, "pos": v(k1["pos"], [0.015, 0.03, 0.005]), "aim": v(k1["aim"], [0, 0.008, 0])},
                            {"frame": 104, "pos": k1["pos"], "aim": k1["aim"]},
                            {"frame": 120, "pos": k1["pos"], "aim": k1["aim"]}]},
        "post": {"fps_unique": 24, "fps_out": 24,
                 "glow": {"threshold": 0.82, "radii": [5, 18, 55], "weights": [0.7, 0.55, 0.4], "strength": 1.3},
                 "rain_dim": [[1, 0.7]]}})

    tl = {"name": "mariposa_bandera", "fps_unique": 24, "fps_out": 24, "shots": ["01_crisalida", "02_despliegue", "03_puerto", "04_reserva", "05_entrega",
                    "06_enjambre", "06b_gris", "07_loop"]}
    (EP / "shots" / "timeline.json").write_text(json.dumps(tl, indent=2), encoding="utf-8")
    print("intentos", a, b, "posada en", [round(x, 3) for x in pose])


if __name__ == "__main__":
    main()
