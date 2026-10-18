"""planos.py - Genera los JSON de los planos de NUNCA SE APAGAN.

Las posiciones salen del terreno real (../catedral/data/entorno.json): la
camara va a la altura de los ojos del papa (1,70 m) y la nena camina sobre el
piso de verdad. Avisa si la nena queda fuera de cuadro.

    python episodios/nunca_se_apagan/planos.py
"""

import json
import math
from pathlib import Path

EP = Path(__file__).resolve().parent
ENT = json.loads((EP.parent / "catedral" / "data" / "entorno.json").read_text(encoding="utf-8"))
T = ENT["terreno"]
OJOS = 1.70
TORRE = (0.0, -3.6, 62.0)          # punta de la torre (para senalar y mirar)


def H(x, y):
    n = T["n"]
    fx = min(max((x - T["x0"]) / T["paso"], 0), n - 1.001)
    fy = min(max((y - T["y0"]) / T["paso"], 0), n - 1.001)
    i, j = int(fx), int(fy)
    ax, ay = fx - i, fy - j
    g = T["z"]
    return ((g[j * n + i] * (1 - ax) + g[j * n + i + 1] * ax) * (1 - ay)
            + (g[(j + 1) * n + i] * (1 - ax) + g[(j + 1) * n + i + 1] * ax) * ay)


def ojo(x, y):
    return [x, y, round(H(x, y) + OJOS, 3)]


def pie(x, y):
    return [x, y, round(H(x, y), 3)]


def en_cuadro(cam, aim, lens, p, w=1080, h=1920):
    """Proyecta p a pantalla (0..1) con la camara del motor (sensor vertical
    de 36 mm). None si queda detras."""
    import numpy as np
    c, a, p = (np.array(v, float) for v in (cam, aim, p))
    f = a - c
    f /= np.linalg.norm(f)
    r = np.cross(f, [0, 0, 1])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    d = p - c
    z = d @ f
    if z <= 0:
        return None
    k = lens / 18.0
    y = 0.5 - (d @ u) / z * k / 2
    x = 0.5 + (d @ r) / z * k / 2 * (h / w)
    return round(float(x), 3), round(float(y), 3)


def encuadrar(cam, punto, objetivo, lens, extra=()):
    """Mira de la camara (giro e inclinacion de la cabeza del papa, desde +y)
    para que `punto` caiga en `objetivo` (0..1) de la pantalla; `extra`:
    puntos que ademas tienen que quedar en cuadro."""
    import itertools
    best = None
    for yaw, pitch in itertools.product(range(-81, 82, 3), range(-81, 43, 3)):
        a, b = math.radians(yaw), math.radians(pitch)
        aim = [cam[0] + math.sin(a) * math.cos(b) * 5, cam[1] + math.cos(a) * math.cos(b) * 5,
               cam[2] + math.sin(b) * 5]
        q = en_cuadro(cam, aim, lens, punto)
        if not q or any(not (r := en_cuadro(cam, aim, lens, e)) or not (0.03 < r[0] < 0.97 and 0.03 < r[1] < 0.97)
                        for e in extra):
            continue
        d = (q[0] - objetivo[0]) ** 2 + (q[1] - objetivo[1]) ** 2
        if best is None or d < best[0]:
            best = (d, aim)
    if best is None:
        raise SystemExit(f"no hay encuadre para {punto} desde {cam}")
    return [round(v, 3) for v in best[1]]


ESCENA = {
    "catedral": {"techo": True, "anexos": True, "suelo": 0},
    "servidores": {},
    "entorno": {"datos": "../catedral/data/entorno.json", "piso": 6000, "radio": 450},
}


def prueba_nena():
    """Prototipo: tres poses de la nena por el medio de Libertador (en el
    futuro no pasan autos; en la vereda los arboles y las casas tapaban)."""
    x_papa, x_nena = 19.4, 20.05     # ella va al costado y apenas adelante
    poses = []

    def cabeza(at):
        return [at[0], at[1], at[2] + 1.0]

    # 1: caminando de la mano; ella habla ("Papa, que es eso?")
    y = -80.0
    cam, at = ojo(x_papa, y), pie(x_nena, y + 0.3)
    poses.append(dict(cam=cam, aim=encuadrar(cam, cabeza(at), (0.66, 0.66), 18), lens=18,
                      nena=dict(at=at, cabeza=[8, 5], paso=18, habla=1)))
    # 2: gira la cabeza hacia arriba, hacia el papa
    y = -78.0
    cam, at = ojo(x_papa, y), pie(x_nena, y + 0.35)
    poses.append(dict(cam=cam, aim=encuadrar(cam, cabeza(at), (0.6, 0.5), 20), lens=20,
                      nena=dict(at=at, cabeza=[150, 38], paso=0, habla=1)))
    # 3: se adelanta un paso, tirando de la mano, y senala la torre
    y = -76.0
    cam, at = ojo(x_papa, y), pie(x_nena - 0.25, y + 1.0)
    poses.append(dict(cam=cam, aim=encuadrar(cam, cabeza(at), (0.68, 0.72), 13, extra=[TORRE]), lens=13,
                      nena=dict(at=at, cabeza=[12, 25], paso=0, habla=0, senala=[0.0, -3.6, 34.0])))
    # 4 (solo revision, no va al short): primer plano de frente para juzgar la cara
    y = -70.0
    g = pie(x_nena, y)
    poses.append(dict(cam=[x_nena + 0.05, y + 0.75, g[2] + 1.0], aim=[x_nena, y, g[2] + 0.95], lens=40,
                      nena=dict(at=g, cabeza=[0, 8], paso=0, habla=1, rumbo=[0, 1])))
    return poses


def _shot(poses, estilo, desc, radios):
    keys, nkeys = [], []
    for i, p in enumerate(poses, 1):
        keys.append({"frame": i, "pos": p["cam"], "aim": p["aim"]})
        n = {"rumbo": [0, 1], **p["nena"], "frame": i}
        nkeys.append(n)
        head = [n["at"][0], n["at"][1], n["at"][2] + 1.0]
        print(f"  {i}: cabeza de la nena en pantalla {en_cuadro(p['cam'], p['aim'], p['lens'], head)}")
    return {
        "_desc": desc, "estilo": estilo, "width": 1080, "height": 1920, "fps": 12, "frames": len(poses),
        "samples": 8, "storyboard": list(range(1, len(poses) + 1)),
        **ESCENA,
        "nena": {"keys": nkeys},
        "papa_brazo": {"hombro": [0.24, 0.05, 0.36]},
        "line": {"radius": radios[0], "radius_keys": [[i, r] for i, r in enumerate(radios, 1)]},
        "camera": {"lens": 18, "ease": False, "clip_start": 0.05, "clip_end": 3000, "keys": keys,
                   "lens_keys": [[i, p["lens"]] for i, p in enumerate(poses, 1)]},
    }


NUCLEO = (0.0, 35.6, 6.0)


def prueba_estilo():
    """Cuadros clave del estilo afuera: caminando (barrio calido) y senalando
    la torre ya cerca (a ~40 m la torre pasa por arriba de los arboles)."""
    ps = prueba_nena()
    x_papa, x_nena = 19.4, 20.05
    y = -45.0
    cam, at = ojo(x_papa, y), pie(x_nena - 0.25, y + 1.0)
    senala = dict(cam=cam, aim=encuadrar(cam, [at[0], at[1], at[2] + 1.0], (0.7, 0.76), 14, extra=[TORRE]),
                  lens=14, nena=dict(at=at, cabeza=[25, 35], paso=0, habla=0, senala=[0.0, -3.6, 40.0]))
    return [ps[0], senala]


def prueba_adentro():
    """Adentro, en el pasillo de la nave (el piso de la nave es z = 0)."""
    cam, at = [-0.3, 7.0, OJOS], [0.35, 7.3, 0.0]
    return [dict(cam=cam, aim=encuadrar(cam, [at[0], at[1], 1.0], (0.64, 0.74), 16),
                 lens=16, nena=dict(at=at, cabeza=[-6, 22], paso=10, habla=1))]


# ---------------------------------------------------------------- el short
TORRE_MEDIO = (0.0, -3.6, 36.0)
FPS = 12


def suelo(x, y):
    """Piso real: adentro de la catedral z = 0; la escalinata del frente sube
    de -1 a 0; el resto es el terreno."""
    if -7.2 < y < 52 and abs(x) < 15.4:
        return 0.0
    if abs(x) < 6.5 and -8.6 <= y <= -7.2:
        return 0.0
    if abs(x) < 6.5 and -10.6 <= y < -8.6:
        return -1.0 + (y + 10.6) / 2.0
    return H(x, y)


def _lerp(a, b, t):
    return [a[i] + (b[i] - a[i]) * t for i in range(len(a))]


def _tramo(keys, f):
    """keys: [(frame, valor)] -> (valor_a, valor_b, t) para interpolar en f."""
    if f <= keys[0][0]:
        return keys[0][1], keys[0][1], 0.0
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        if f0 <= f <= f1:
            return v0, v1, (f - f0) / (f1 - f0) if f1 > f0 else 1.0
    return keys[-1][1], keys[-1][1], 0.0


def _num(keys, f):
    a, b, t = _tramo(keys, f)
    return a + (b - a) * t


def _deg(a):
    return (a + 180) % 360 - 180


def toma(estilo, frames, desc, dialogo, tramos, mira, nena, lens, radio, storyboard, rumbo_fijo=None,
         escena=None):
    """Un plano del short. tramos: [(f0, f1, (x, y) del papa en f0, en f1)];
    mira: [(frame, objetivo)] con objetivo = punto, "nena", "adelante",
    "adelante_nena", "papa" o ("encuadre", (x, y) de la cabeza en pantalla,
    [puntos que tambien tienen que entrar]); nena: {"lado": [(f, m)], "delante": [(f, m)],
    "mira": [(f, objetivo)], "senala": [(f0, f1, punto)]}. Claves cada 3
    cuadros: las piernas alternan y la camara se mece al paso."""
    cam_keys, n_keys = [], []
    last_dir = rumbo_fijo or (0.0, 1.0)
    fs = list(range(1, frames + 1, 3))
    if fs[-1] != frames:
        fs.append(frames)
    for f in fs:
        tr = next((t for t in tramos if t[0] <= f <= t[1]), tramos[-1] if f > tramos[-1][1] else tramos[0])
        f0, f1, a, b = tr
        t = 0.0 if f1 == f0 else min(max((f - f0) / (f1 - f0), 0), 1)
        x, y = _lerp(a, b, t)
        mov = math.hypot(b[0] - a[0], b[1] - a[1]) > 0.01 and f0 <= f <= f1
        if mov and not rumbo_fijo:
            d = math.hypot(b[0] - a[0], b[1] - a[1])
            last_dir = ((b[0] - a[0]) / d, (b[1] - a[1]) / d)
        fwd = last_dir
        right = (fwd[1], -fwd[0])
        fase = (f // 3) % 4
        bob = (0.0, 0.015, 0.0, 0.015)[fase] if mov else 0.0
        cam = [round(x, 3), round(y, 3), round(suelo(x, y) + OJOS - bob, 3)]
        lado = _num(nena.get("lado", [(1, 0.65)]), f)
        delante = _num(nena.get("delante", [(1, 0.3)]), f)
        gx, gy = x + right[0] * lado + fwd[0] * delante, y + right[1] * lado + fwd[1] * delante
        gat = [round(gx, 3), round(gy, 3), round(suelo(gx, gy), 3)]
        cabeza = [gat[0], gat[1], gat[2] + 1.0]

        def resolver(o):
            if o == "nena":
                return cabeza
            if o == "papa":
                return cam
            ade = [x + fwd[0] * 8, y + fwd[1] * 8, cam[2] - 1.0]
            if o == "adelante":
                return ade
            if o == "adelante_nena":
                return _lerp(ade, cabeza, 0.55)
            if isinstance(o, tuple) and o and o[0] == "encuadre":
                # la mira que pone la cabeza de la nena en ese lugar de la
                # pantalla (y, si se pide, otros puntos en cuadro)
                return encuadrar(cam, cabeza, o[1], lens, extra=o[2] if len(o) > 2 else ())
            return list(o)

        def mezcla(keys):
            va, vb, tt = _tramo(keys, f)
            return _lerp(resolver(va), resolver(vb), tt)

        aim = [round(v, 3) for v in mezcla(mira)]
        cam_keys.append({"frame": f, "pos": cam, "aim": aim})
        look = mezcla(nena.get("mira", [(1, "adelante")]))
        d = [look[i] - cabeza[i] for i in range(3)]
        giro = _deg(math.degrees(math.atan2(-d[0], d[1]) - math.atan2(-fwd[0], fwd[1])))
        incl = math.degrees(math.atan2(d[2], math.hypot(d[0], d[1])))
        k = {"frame": f, "at": gat, "rumbo": [round(fwd[0], 4), round(fwd[1], 4)],
             "cabeza": [round(max(-160, min(160, giro)), 1), round(max(-25, min(55, incl)), 1)],
             "paso": (18, 0, -18, 0)[fase] if mov else 0,
             "habla": int(any(ln["quien"] == "ella" and ln["f0"] <= f <= ln["f1"] for ln in dialogo))}
        for s0, s1, pt in nena.get("senala", []):
            if s0 <= f <= s1:
                k["senala"] = list(pt)
        n_keys.append(k)
    texto = " / ".join(("ELLA: " if ln["quien"] == "ella" else "EL: ") + ln["texto"] for ln in dialogo)
    return {
        "_desc": desc + (" | " + texto if texto else ""),
        "estilo": estilo, "width": 1080, "height": 1920, "fps": FPS, "frames": frames, "samples": 8,
        "storyboard": storyboard, **ESCENA, **(escena or {}),
        "nena": {"keys": n_keys}, "papa_brazo": {"hombro": [0.24, 0.05, 0.36]},
        "dialogo": dialogo,
        "line": {"radius": radio},
        "camera": {"lens": lens, "ease": False, "clip_start": 0.05, "clip_end": 3000, "keys": cam_keys},
    }


def linea(quien, texto, f0, f1):
    return {"quien": quien, "texto": texto, "f0": f0, "f1": f1}


def planos_del_short():
    X = -0.35                      # adentro el papa va por el pasillo central, ella a su derecha
    P = {}
    P["01_libertador"] = toma(
        "cyberpunk", 72, "Libertador, de la mano. Ella se adelanta y senala la torre",
        [linea("ella", "Papá, ¿qué es eso?", 30, 72)],
        [(1, 60, (19.4, -63.0), (19.4, -57.0)), (60, 72, (19.4, -57.0), (19.4, -57.0))],
        [(1, ("encuadre", (0.64, 0.84))), (30, ("encuadre", (0.64, 0.76))),
         (60, ("encuadre", (0.68, 0.8), [TORRE])), (72, ("encuadre", (0.68, 0.8), [TORRE]))],
        {"lado": [(1, 0.65), (44, 0.65), (60, 0.5)], "delante": [(1, 0.3), (44, 0.3), (60, 0.8)],
         "mira": [(1, "adelante"), (28, "adelante"), (34, TORRE)], "senala": [(40, 72, TORRE_MEDIO)]},
        16, 0.006, [12, 66])
    P["02_torre"] = toma(
        "cyberpunk", 60, "Contrapicado desde el borde del atrio: ella mira la torre; el papa sube la vista; ella se da vuelta",
        [linea("el", "Una catedral. ¿Querés entrar?", 6, 54)],
        [(1, 60, (10.5, -27.0), (10.5, -27.0))],
        [(1, ("encuadre", (0.62, 0.72))), (16, ("encuadre", (0.62, 0.72))),
         (34, TORRE_MEDIO), (42, TORRE_MEDIO), (56, ("encuadre", (0.6, 0.62))), (60, ("encuadre", (0.6, 0.62)))],
        {"lado": [(1, 0.6)], "delante": [(1, 0.5)], "mira": [(1, TORRE), (40, TORRE), (48, "papa")]},
        14, 0.006, [12, 38, 58], rumbo_fijo=(-0.45, 0.89))
    P["03_atrio"] = toma(
        "cyberpunk", 84, "El atrio: la escalinata y la portada; ella tira de la mano",
        [], [(1, 84, (5.0, -22.0), (1.0, -11.4))],
        [(1, ("encuadre", (0.62, 0.76), [(0.0, -7.2, 14.0)])), (84, ("encuadre", (0.62, 0.74)))],
        {"lado": [(1, 0.6)], "delante": [(1, 0.5)], "mira": [(1, (0.0, -7.2, 12.0))]},
        16, 0.006, [10, 80],
        escena={"catedral": dict(ESCENA["catedral"], puertas={"abre": [[1, 0], [44, 0], [74, 78], [84, 82]]})})
    P["04_umbral"] = toma(
        "cyberpunk_adentro", 72, "Bajo el coro alto: el frio, la niebla, el zumbido",
        [linea("ella", "¡Qué frío!", 8, 34), linea("el", "Las iglesias siempre fueron frías.", 36, 72)],
        [(1, 72, (X, -6.0), (X, 1.5))],
        [(1, "adelante"), (16, ("encuadre", (0.62, 0.74))), (40, ("encuadre", (0.62, 0.74))), (56, (0.0, 30.0, 4.0)), (72, (0.0, 30.0, 4.0))],
        {"mira": [(1, "adelante"), (8, "papa"), (36, "papa"), (46, (0.0, 30.0, 3.0))]},
        16, 0.005, [20, 60])
    P["05_nave"] = toma(
        "cyberpunk_adentro", 84, "El pasillo entre racks",
        [linea("ella", "¿Es una iglesia o una computadora?", 6, 48), linea("el", "Las dos.", 52, 84)],
        [(1, 84, (X, 2.0), (X, 9.5))],
        [(1, "adelante"), (14, ("encuadre", (0.62, 0.74))), (46, ("encuadre", (0.62, 0.74))), (60, (0.0, 30.0, 9.0)), (84, (0.0, 30.0, 10.0))],
        {"mira": [(1, "papa"), (44, "papa"), (54, (0.0, 30.0, 12.0))]},
        16, 0.005, [24, 70])
    P["06_misa"] = toma(
        "cyberpunk_adentro", 84, "Caminando: para que la usan",
        [linea("ella", "¿Para qué la usan?", 4, 30),
         linea("el", "Los domingos hay misa. Los otros días rezan ellas.", 34, 84)],
        [(1, 84, (X, 10.0), (X, 17.5))],
        [(1, "adelante"), (10, ("encuadre", (0.62, 0.74))), (30, ("encuadre", (0.62, 0.74))), (48, (3.5, 22.0, 1.5)), (84, (2.5, 28.0, 2.0))],
        {"mira": [(1, "papa"), (28, "papa"), (38, (3.5, 22.0, 1.5))]},
        16, 0.005, [20, 64])
    P["07_nucleo"] = toma(
        "cyberpunk_adentro", 96, "El nucleo en el crucero",
        [linea("ella", "¿Por qué las pusieron acá?", 6, 36),
         linea("el", "Nadie se acuerda. Dicen que antes la gente venía a escuchar una palabra.", 40, 96)],
        [(1, 60, (X, 24.0), (X, 30.5)), (60, 96, (X, 30.5), (X, 30.5))],
        [(1, (0.0, 35.6, 4.0)), (14, ("encuadre", (0.62, 0.74))), (40, ("encuadre", (0.62, 0.74))), (64, (0.0, 35.6, 5.0)), (96, (0.0, 36.0, 7.0))],
        {"mira": [(1, (0.0, 35.6, 3.0)), (6, "papa"), (34, "papa"), (44, (0.0, 35.6, 4.0))]},
        16, 0.005, [24, 84])
    P["08_boveda"] = toma(
        "cyberpunk_adentro", 96, "Bajo la boveda: los leds laten todos juntos, una vez",
        [linea("ella", "¿Qué palabra?", 6, 30), linea("el", "No sé. Pero ellas la siguen escuchando.", 34, 84)],
        [(1, 96, (X, 30.8), (X, 30.8))],
        [(1, ("encuadre", (0.62, 0.74))), (30, ("encuadre", (0.62, 0.74))), (56, (0.0, 36.1, 19.0)), (70, (0.0, 36.1, 19.0)),
         (82, (7.0, 35.0, 1.6)), (96, (7.0, 35.0, 1.6))],
        {"mira": [(1, "papa"), (28, "papa"), (38, (0.0, 36.1, 19.0)), (76, (7.0, 35.0, 1.6))]},
        14, 0.005, [20, 60, 88],
        escena={"servidores": {"latido": [[1, 0], [85, 0], [87, 1], [90, 1], [95, 0]]}})
    return P


def arboles_que_tapan(planos, objetivos, escala=1.3):
    """Arboles de relleno cuya copa corta la linea de vista entre la camara
    (en cada clave) y los objetivos. Copa: esfera aproximada sobre el tronco,
    como la arma piezas/entorno.py."""
    import numpy as np
    out = []
    for x, y, s, src in ENT["arboles"]:
        if src != "relleno":
            continue
        k = s * escala
        c = np.array([x, y, H(x, y) - 0.2 + k * 4.1])
        r = k * 2.4 + 0.5
        for shot in planos:
            hit = False
            for key in shot["camera"]["keys"]:
                o = np.array(key["pos"])
                for t in objetivos:
                    d = np.array(t) - o
                    L = np.linalg.norm(d)
                    d /= L
                    u = min(max((c - o) @ d, 0), L)
                    if np.linalg.norm(o + d * u - c) < r:
                        hit = True
                        break
                if hit:
                    break
            if hit:
                out.append([round(x, 1), round(y, 1)])
                break
    return out


def escribir_short(out):
    planos = planos_del_short()
    vista = [planos[k] for k in ("01_libertador", "02_torre", "03_atrio")]
    quitar = arboles_que_tapan(vista, [TORRE, TORRE_MEDIO, (0.0, -3.6, 20.0)])
    print(f"  {len(quitar)} arboles de relleno tapaban la torre: se quitan")
    for name, shot in planos.items():
        shot["entorno"] = dict(shot["entorno"], quitar_arboles=quitar)
        if name >= "04":
            # adentro las puertas ya quedaron abiertas
            shot["catedral"] = dict(shot["catedral"], puertas={"abre": [[1, 82]]})
    for name, shot in planos.items():
        (out / f"{name}.json").write_text(json.dumps(shot, indent=2, ensure_ascii=False), encoding="utf-8")
        ks = {k["frame"]: k for k in shot["camera"]["keys"]}
        ns = {k["frame"]: k for k in shot["nena"]["keys"]}
        for f in shot["storyboard"]:
            kf = min(ks, key=lambda q: abs(q - f))
            c, n = ks[kf], ns[kf]
            q = en_cuadro(c["pos"], c["aim"], shot["camera"]["lens"], [n["at"][0], n["at"][1], n["at"][2] + 1.0])
            print(f"  {name} f{f}: cabeza de la nena en {q}")
    total = sum(p["frames"] for p in planos.values())
    tl = {"name": "nunca_se_apagan", "fps_unique": FPS, "fps_out": 24, "shots": list(planos)}
    (out / "timeline.json").write_text(json.dumps(tl, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"timeline: {len(planos)} planos, {total} cuadros = {total / FPS:.1f} s")


def main():
    out = EP / "shots"
    out.mkdir(exist_ok=True)
    print("_nena")
    shot = _shot(prueba_nena(), "maqueta", "Prototipo de la nena (POV del papa) + primer plano de revision.",
                 [0.004, 0.004, 0.006, 0.004])
    (out / "_nena.json").write_text(json.dumps(shot, indent=2, ensure_ascii=False), encoding="utf-8")
    print("_estilo")
    shot = _shot(prueba_estilo(), "cyberpunk", "Prueba de estilo afuera: caminando, senalando la torre.",
                 [0.005, 0.006])
    (out / "_estilo.json").write_text(json.dumps(shot, indent=2, ensure_ascii=False), encoding="utf-8")
    print("_estilo_adentro")
    shot = _shot(prueba_adentro(), "cyberpunk_adentro", "Prueba de estilo adentro: el pasillo de la nave.",
                 [0.005])
    (out / "_estilo_adentro.json").write_text(json.dumps(shot, indent=2, ensure_ascii=False), encoding="utf-8")
    print("short")
    escribir_short(out)


if __name__ == "__main__":
    main()
