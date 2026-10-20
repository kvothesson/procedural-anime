"""Genera los JSON de los planos 01-06, 08 y 09 de DUENDE ROJO (marco de la calle) y chequea el encuadre.

    python episodios/duende_rojo/planos.py episodios/duende_rojo
"""
import json
import math
import sys
from pathlib import Path

EP = Path(sys.argv[1])
AZ = 61
A = math.radians(AZ)


def mundo(x, y, z):
    return [round(x * math.cos(A) + y * math.sin(A), 3), round(-x * math.sin(A) + y * math.cos(A), 3), round(z, 3)]


def apunta(cam, el_deg, dazi=0.0, d=100):
    el = math.radians(el_deg)
    azc = math.radians(AZ + dazi)
    return [round(cam[0] + math.sin(azc) * d * math.cos(el), 2), round(cam[1] + math.cos(azc) * d * math.cos(el), 2),
            round(cam[2] + d * math.sin(el), 2)]


NYX = (-0.9, 40.0, 7.2)
VES = (1.0, 40.0, 7.32)
CERRO, PUEBLO = 180 - AZ, -AZ          # yaw: mirando al Uritorco / mirando al pueblo
VES_A_NYX = -151                         # Vesper mirando a Nyx


def lente(yaw, sx=1):
    """Posicion de la lente derecha (sx=1) de Nyx en el mundo, con su yaw."""
    t = math.radians(yaw)
    lx, ly, lz = sx * 0.075, -0.206, 0.025
    wx = lx * math.cos(t) - ly * math.sin(t)
    wy = lx * math.sin(t) + ly * math.cos(t)
    c = mundo(*NYX)
    return [c[0] + wx, c[1] + wy, c[2] + lz]


def frente(yaw):
    t = math.radians(yaw)
    return (math.sin(t), -math.cos(t))


def giro(f, de, a, extra=None):
    """Giro en seco a la FighterZ: pose sostenida, un intermedio al 60 %, pose final."""
    mid = de + (a - de) * 0.6
    return [[f, de], [f + 1, mid], [f + 2, a]]


def nyx_keys(yaws, alas, frames):
    """yaws: [[frame, yaw]]; alas: [[frame, valor]] -> keys de nyx con posicion fija."""
    fs = sorted({1, frames} | {f for f, _ in yaws} | {f for f, _ in alas})

    def at(lst, f):
        prev = lst[0][1]
        for ff, v in lst:
            if ff <= f:
                prev = v
        return prev

    def interp(lst, f):
        lst = sorted(lst)
        if f <= lst[0][0]:
            return lst[0][1]
        for (fa, va), (fb, vb) in zip(lst, lst[1:]):
            if fa <= f <= fb:
                return va + (vb - va) * (f - fa) / max(1, fb - fa)
        return lst[-1][1]
    return [[f, mundo(*NYX), at(yaws, f), round(interp(alas, f), 3)] for f in fs]


def ves_keys(yaws, frames, pos=None):
    fs = sorted({1, frames} | {f for f, _ in yaws})

    def at(lst, f):
        prev = lst[0][1]
        for ff, v in lst:
            if ff <= f:
                prev = v
        return prev
    return [[f, pos or mundo(*VES), at(yaws, f)] for f in fs]


SIN = {"brillo": [[1, 0.0]]}            # duende apagado
UNO = lambda daz, f, cola=0: {           # un duende solo, encendido un cuadro (y una cola de "resto pintado")
    "grupo": [{"daz": daz, "seed": 30 + f, "ancho_deg": 12, "elev": [15, 27], "columnas": 14}],
    "fase": [[1, 1.0]],
    "brillo": [[1, 0.0], [f - 1, 0.0], [f, 1.0]] + ([[f + 1, 0.3], [f + cola, 0.0]] if cola else [[f + 1, 0.0]])}
planos = {}

# 01: la lente de Nyx se abre; la camara se aleja hasta la foto de la calle. Un duende de un cuadro, que nadie ve
F1 = 48
cam0 = lente(PUEBLO)
fx, fy = frente(PUEBLO)
camA = [cam0[0] + fx * 0.11, cam0[1] + fy * 0.11, cam0[2] + 0.004]
planos["01_lente"] = {
    "_desc": "01 - La lente de Nyx se abre (de cerca); la camara se aleja hasta la calle techada: Nyx chiquito en el arco, el Uritorco detras. En el cuadro 40, un duende de un solo cuadro a la izquierda que nadie ve.",
    "frames": F1, "storyboard": [3, 46],
    "duende": UNO(-14, 40),
    "tormenta": {"rayos": [12, 33], "dispara": 39},
    "nyx": {"keys": nyx_keys([[1, PUEBLO]], [[1, 0.15]], F1), "lente": [[1, 0.0], [5, 0.3], [6, 0.1], [8, 1.0]], "vaiven": 0.008},
    "vesper": {"keys": ves_keys([[1, CERRO]], F1)},
    "camera": {"lens": 50, "clip_start": 0.01, "clip_end": 60000, "ease": True, "keys": [
        {"frame": 1, "pos": camA, "aim": cam0}, {"frame": 10, "pos": camA, "aim": cam0},
        {"frame": 26, "pos": mundo(-0.6, 33, 6.4), "aim": mundo(-0.9, 40, 7.3)},
        {"frame": F1, "pos": [0, 0, 1.7], "aim": apunta([0, 0, 1.7], 10)}]},
    "line": {"color": "#0d0b24", "radius": 0.012, "crease_deg": 120}}

# 02: Nyx se da vuelta hacia el cerro y abre las alas como antenas; Vesper cuenta los relampagos
F2 = 60
planos["02_antenas"] = {
    "_desc": "02 - En el arco. Nyx se da vuelta hacia el Uritorco (giro en seco) y abre las alas como antenas: empiezan los chasquidos de radio. Vesper cuenta los relampagos con su llama.",
    "frames": F2, "storyboard": [40],
    "duende": SIN, "tormenta": {"rayos": [8, 22, 35, 49], "dispara": 0},
    "nyx": {"keys": nyx_keys(giro(10, PUEBLO, CERRO), [[1, 0.15], [14, 0.15], [22, 1.0]], F2), "vaiven": 0.008},
    "vesper": {"keys": ves_keys([[1, CERRO]], F2),
               "llama": [[1, 0.6], [8, 1.0], [10, 0.6], [22, 1.0], [24, 0.6], [35, 1.0], [37, 0.6], [49, 1.0], [51, 0.6]]},
    "camera": {"lens": 35, "clip_start": 0.05, "clip_end": 60000, "ease": True, "keys": [
        {"frame": 1, "pos": mundo(3.4, 35.2, 7.9), "aim": mundo(-0.4, 44, 9.2)},
        {"frame": F2, "pos": mundo(3.1, 35.6, 7.85), "aim": mundo(-0.4, 44, 9.4)}]},
    "line": {"color": "#0d0b24", "radius": 0.01, "crease_deg": 120}}

# 03: primer intento. Nyx mira para otro lado; chasquido y destello; gira tarde: queda un resto rojo
F3 = 72
planos["03_tarde"] = {
    "_desc": "03 - Primer intento. Nyx mira para otro lado. Chasquido y destello en el horizonte (30), el duende vive un cuadro (31). Nyx gira tarde (36-38): el resto rojo se borro medio segundo antes (35). Llego tarde.",
    "frames": F3, "storyboard": [31, 40],
    "duende": UNO(3, 31, cola=5), "tormenta": {"rayos": [10], "dispara": 30},
    "nyx": {"keys": nyx_keys([[1, CERRO + 70]] + giro(36, CERRO + 70, CERRO), [[1, 1.0]], F3), "vaiven": 0.008},
    "vesper": {"keys": ves_keys([[1, CERRO]], F3)},
    "camera": {"lens": 32, "clip_start": 0.05, "clip_end": 60000, "ease": True, "keys": [
        {"frame": 1, "pos": mundo(0.1, 35.6, 8.5), "aim": apunta(mundo(0.1, 35.6, 8.5), 13)},
        {"frame": F3, "pos": mundo(0.1, 35.9, 8.5), "aim": apunta(mundo(0.1, 35.9, 8.5), 13.5)}]},
    "line": {"color": "#0d0b24", "radius": 0.01, "crease_deg": 120}}

# 04: segundo intento, igual; Vesper proyecta el registro: hay un ritmo y el duende viene detras del chasquido
F4 = 60
camR = mundo(2.6, 37.4, 7.7)
planos["04_registro"] = {
    "_desc": "04 - Segundo intento: tarde otra vez (destello 5, duende 6, Nyx gira 11). Vesper proyecta el registro de los chasquidos: hay un ritmo, y el duende llega siempre medio segundo despues del chasquido.",
    "frames": F4, "storyboard": [6, 48],
    "duende": UNO(-6, 6, cola=4), "tormenta": {"rayos": [30, 44], "dispara": 5},
    "nyx": {"keys": nyx_keys([[1, CERRO - 60]] + giro(11, CERRO - 60, CERRO), [[1, 1.0]], F4), "vaiven": 0.008},
    "vesper": {"keys": ves_keys([[1, CERRO], [16, VES_A_NYX]], F4)},
    "registro": {"at": mundo(0.1, 39.2, 8.15), "mira": camR, "desde": 20,
                 "golpes": [0, 1, 2, 3.5, 4.5, 5.5, 7], "duendes": [1, 3.5, 5.5]},
    "camera": {"lens": 32, "clip_start": 0.05, "clip_end": 60000, "ease": True, "keys": [
        {"frame": 1, "pos": camR, "aim": mundo(-0.2, 40.5, 7.9)},
        {"frame": F4, "pos": mundo(2.4, 37.6, 7.75), "aim": mundo(-0.1, 40.2, 7.95)}]},
    "line": {"color": "#0d0b24", "radius": 0.008, "crease_deg": 120}}

# 05: Nyx apaga las lentes y escucha; las alas se mueven con cada chasquido
F5 = 96
camP = mundo(-2.7, 40.4, 7.45)
cl = [12, 24, 36, 54, 66, 78, 96]
planos["05_escucha"] = {
    "_desc": "05 - Nyx apaga las lentes y escucha. Con cada chasquido las alas tiemblan; detras, la tormenta parpadea sobre el cerro. La banda se vuelve el ritmo.",
    "frames": F5, "storyboard": [50],
    "duende": SIN, "tormenta": {"rayos": cl, "dispara": 0},
    "nyx": {"keys": nyx_keys([[1, CERRO + 25]], [[1, 1.0]] + [x for f in cl for x in ([f, 0.85], [f + 2, 1.0])], F5),
            "lente": [[1, 1.0], [10, 0.4], [12, 0.05]], "vaiven": 0.006},
    "vesper": {"keys": ves_keys([[1, VES_A_NYX]], F5)},
    "camera": {"lens": 40, "clip_start": 0.02, "clip_end": 60000, "ease": True, "keys": [
        {"frame": 1, "pos": camP, "aim": mundo(-0.9, 40.1, 7.3)},
        {"frame": F5, "pos": mundo(-2.2, 40.35, 7.42), "aim": mundo(-0.9, 40.1, 7.3)}]},
    "line": {"color": "#0d0b24", "radius": 0.004, "crease_deg": 120}}

# 06: gira ANTES del chasquido y prende las lentes
F6 = 24
planos["06_antes"] = {
    "_desc": "06 - Nyx gira ANTES del chasquido (giro en seco en 8-10) y prende las lentes. Corte al 07: el chasquido es su primer cuadro.",
    "frames": F6, "storyboard": [12],
    "duende": SIN, "tormenta": {"rayos": [], "dispara": 0},
    "nyx": {"keys": nyx_keys([[1, CERRO + 25]] + giro(8, CERRO + 25, CERRO), [[1, 1.0], [8, 1.0], [11, 1.15]], F6),
            "lente": [[1, 0.05], [9, 1.0]], "vaiven": 0.0},
    "vesper": {"keys": ves_keys([[1, VES_A_NYX]], F6)},
    "camera": {"lens": 50, "clip_start": 0.02, "clip_end": 60000, "ease": True, "keys": [
        {"frame": 1, "pos": mundo(-2.0, 40.3, 7.4), "aim": mundo(-0.9, 40.1, 7.3)},
        {"frame": F6, "pos": mundo(-1.85, 40.3, 7.4), "aim": mundo(-0.9, 40.1, 7.3)}]},
    "line": {"color": "#0d0b24", "radius": 0.004, "crease_deg": 120}}

# 08: la pausa. Cielo vacio; Nyx baja las alas; Vesper lo mira
F8 = 60
planos["08_pausa"] = {
    "_desc": "08 - La pausa. El cielo vacio sobre el Uritorco. Nyx baja las alas despacio: esta vez lo vio. Vesper se da vuelta a mirarlo.",
    "frames": F8, "storyboard": [40],
    "duende": SIN, "tormenta": {"rayos": [50], "dispara": 0},
    "nyx": {"keys": nyx_keys([[1, CERRO]], [[1, 1.0], [12, 1.0], [40, 0.25]], F8), "vaiven": 0.008},
    "vesper": {"keys": ves_keys([[1, CERRO]] + giro(24, CERRO, VES_A_NYX), F8)},
    "camera": {"lens": 30, "clip_start": 0.05, "clip_end": 60000, "ease": True, "keys": [
        {"frame": 1, "pos": mundo(0.0, 33.8, 8.3), "aim": apunta(mundo(0.0, 33.8, 8.3), 13)},
        {"frame": F8, "pos": mundo(0.0, 34.6, 8.2), "aim": apunta(mundo(0.0, 34.6, 8.2), 12)}]},
    "line": {"color": "#0d0b24", "radius": 0.012, "crease_deg": 120}}

# 09: el mapa: un punto rojo nuevo junto a la luz mala. Vesper sigue viaje; Nyx se da vuelta y cierra las lentes (loop)
F9 = 96
camM = mundo(2.2, 37.2, 7.9)
fin_cam = mundo(0, 0, 0)
cam_fin = [camA[0], camA[1], camA[2]]
planos["09_mapa"] = {
    "_desc": "09 - Vesper proyecta el mapa de la Ruta 404: aparece un punto rojo en Capilla del Monte, junto a la luz mala de NODO 0. Vesper sigue viaje por la ruta. Nyx se da vuelta y cierra las lentes: el ultimo cuadro es el primero del 01.",
    "frames": F9, "storyboard": [40, 96],
    "duende": SIN, "tormenta": {"rayos": [20, 60], "dispara": 0},
    "nyx": {"keys": nyx_keys([[1, CERRO]] + giro(66, CERRO, PUEBLO), [[1, 0.25], [66, 0.15]], F9),
            "lente": [[1, 1.0], [86, 1.0], [88, 0.4], [90, 0.0]], "vaiven": 0.008},
    "vesper": {"keys": [[1, mundo(*VES), VES_A_NYX], [30, mundo(*VES), CERRO], [56, mundo(1.0, 40.0, 7.32), CERRO],
                        [74, mundo(3.0, 52.0, 13.0), CERRO], [F9, mundo(6.0, 90.0, 26.0), CERRO]]},
    "mapa": {"at": mundo(0.2, 39.3, 8.35), "mira": camM, "luz_mala": 0, "de": "vesper", "aparece": [6, 14],
             "puntos": [{"lat": -30.86, "lon": -64.52, "color": "#ff2a3a", "desde": 22, "rotulo": "DUENDE"}]},
    "camera": {"lens": 32, "clip_start": 0.01, "clip_end": 60000, "ease": True, "keys": [
        {"frame": 1, "pos": camM, "aim": mundo(0.0, 39.6, 8.2)},
        {"frame": 56, "pos": mundo(2.0, 37.4, 7.9), "aim": mundo(0.0, 39.6, 8.2)},
        {"frame": 76, "pos": mundo(-0.4, 38.6, 7.4), "aim": mundo(-0.9, 40.0, 7.25)},
        {"frame": 86, "pos": cam_fin, "aim": lente(PUEBLO)}, {"frame": F9, "pos": cam_fin, "aim": lente(PUEBLO)}]},
    "line": {"color": "#0d0b24", "radius": 0.006, "crease_deg": 120}}


# ------------------------------------------------------------------ ajustes de encuadre (verificados con chequear)

def cara(yaw, d):
    """Punto frente a la cara de Nyx, a d metros de la placa."""
    fx, fy = frente(yaw)
    c = mundo(*NYX)
    return [round(c[0] + fx * (0.21 + d), 3), round(c[1] + fy * (0.21 + d), 3), round(c[2] + 0.03, 3)]


LENTE_CAM = {"pos": cara(PUEBLO, 0.36), "aim": cara(PUEBLO, 0.0)}
planos["01_lente"]["camera"]["keys"][0].update(LENTE_CAM)
planos["01_lente"]["camera"]["keys"][1].update(LENTE_CAM)
planos["01_lente"]["nyx"]["vaiven"] = 0.0
planos["01_lente"]["line"]["radius"] = 0.004
planos["02_antenas"]["camera"]["keys"] = [
    {"frame": 1, "pos": mundo(-3.0, 35.8, 7.95), "aim": mundo(0.45, 41.5, 8.6)},
    {"frame": F2, "pos": mundo(-2.8, 36.1, 7.95), "aim": mundo(0.45, 41.5, 8.7)}]
planos["03_tarde"]["camera"]["keys"] = [
    {"frame": 1, "pos": mundo(-1.7, 35.9, 8.0), "aim": mundo(-0.2, 46.0, 10.0)},
    {"frame": F3, "pos": mundo(-1.6, 36.1, 8.0), "aim": mundo(-0.2, 46.0, 10.1)}]
camR = mundo(0.05, 36.2, 7.85)
planos["04_registro"]["camera"]["lens"] = 27
planos["04_registro"]["camera"]["keys"] = [
    {"frame": 1, "pos": camR, "aim": mundo(0.05, 40.0, 8.1)},
    {"frame": F4, "pos": mundo(0.05, 36.5, 7.85), "aim": mundo(0.05, 40.0, 8.15)}]
planos["04_registro"]["registro"].update({"at": mundo(0.05, 39.2, 8.3), "mira": camR, "ancho": 0.95, "alto": 0.48})
planos["05_escucha"]["camera"]["keys"] = [
    {"frame": 1, "pos": mundo(-2.3, 41.6, 7.45), "aim": mundo(-0.9, 40.05, 7.3)},
    {"frame": F5, "pos": mundo(-2.0, 41.3, 7.43), "aim": mundo(-0.9, 40.05, 7.3)}]
planos["06_antes"]["camera"]["keys"] = [
    {"frame": 1, "pos": mundo(-1.95, 41.2, 7.42), "aim": mundo(-0.9, 40.05, 7.3)},
    {"frame": F6, "pos": mundo(-1.85, 41.1, 7.42), "aim": mundo(-0.9, 40.05, 7.3)}]
camM = mundo(0.55, 36.6, 7.95)
planos["09_mapa"]["mapa"].update({"at": mundo(0.2, 39.3, 8.35), "mira": camM, "se_va": 54})
# el gancho y su rima: la cara de cerca mas en penumbra (la lente es lo que importa), un
# destello antes de abrirse; el 09 termina en el mismo cuadro (mismo filo, lente apagada)
for nm in ("01_lente", "09_mapa"):
    planos[nm]["rim_drones"] = 0.35
# el loop: el ultimo cuadro del 09 y el primero del 01 son la misma toma; el lente
# no se anima, asi que tiene que ser el mismo en los dos planos
planos["01_lente"]["camera"]["lens"] = planos["09_mapa"]["camera"]["lens"]
planos["01_lente"]["nyx"]["lente"] = [[1, 0.0], [3, 0.0], [4, 0.25], [5, 0.0], [7, 0.4], [9, 1.0]]
planos["09_mapa"]["nyx"]["vaiven"] = 0.0
planos["09_mapa"]["line"]["radius"] = 0.004
planos["09_mapa"]["camera"]["keys"] = [
    {"frame": 1, "pos": camM, "aim": mundo(0.0, 39.8, 8.25)},
    {"frame": 56, "pos": mundo(0.65, 36.8, 7.95), "aim": mundo(0.0, 39.8, 8.25)},
    {"frame": 76, "pos": mundo(-0.6, 38.4, 7.45), "aim": mundo(-0.9, 40.0, 7.25)},
    {"frame": 86, **LENTE_CAM}, {"frame": F9, **LENTE_CAM}]


# ------------------------------------------------------------------ 08: continuacion del 07, no un corte
# El 08 arranca en la toma exacta con que termina el 07_hombro (camara, lente, alas,
# cadencia de 24 fps, drones en silueta sin filo) y se abre despacio. Con un corte a un
# encuadre parecido (jump cut), luz distinta y otra cadencia, el paso se leia roto.
_h = json.loads((EP / "shots" / "07_hombro.json").read_text(encoding="utf-8"))
_fin = sorted(_h["camera"]["keys"], key=lambda k: k["frame"])[-1]
F8 = 120
planos["08_pausa"].update({
    "_desc": "08 - La pausa, sin corte: sigue la toma del 07 con el cielo ya vacio. La camara se abre despacio; Nyx baja las alas: esta vez lo vio. La luz de los faroles vuelve de a poco y Vesper se da vuelta a mirarlo.",
    "frames": F8, "fps": 24, "storyboard": [1, 110],
    "tormenta": {"rayos": [104], "dispara": 0},
    "nyx": {"keys": nyx_keys([[1, CERRO]], [[1, 0.9], [24, 0.9], [84, 0.25]], F8), "vaiven": 0.0,
            "rim": [[1, 0.0], [36, 0.0], [100, 1.0]]},
    "vesper": {"keys": ves_keys([[1, CERRO]] + giro(56, CERRO, VES_A_NYX), F8), "rim": [[1, 0.0], [36, 0.0], [100, 1.0]]},
    "rim_drones": 0.45,
    "camera": {"lens": _h["camera"]["lens"], "clip_start": 0.05, "clip_end": 60000, "ease": True, "keys": [
        {"frame": 1, "pos": _fin["pos"], "aim": _fin["aim"]},
        {"frame": 12, "pos": _fin["pos"], "aim": _fin["aim"]},
        {"frame": F8, "pos": mundo(-0.75, 35.4, 8.05), "aim": apunta(mundo(-0.75, 35.4, 8.05), 13)}]},
    "line": {"color": "#0d0b24", "radius": _h.get("line", {}).get("radius", 0.008), "crease_deg": 120}})


# ------------------------------------------------------------------ chequeo de encuadre

def _interp_keys(keys, f, campo):
    ks = sorted(keys, key=lambda k: k["frame"])
    if f <= ks[0]["frame"]:
        return ks[0][campo]
    for a, b in zip(ks, ks[1:]):
        if a["frame"] <= f <= b["frame"]:
            u = (f - a["frame"]) / max(1, b["frame"] - a["frame"])
            u = u * u * (3 - 2 * u)                       # aproxima el easing
            return [a[campo][i] + (b[campo][i] - a[campo][i]) * u for i in range(3)]
    return ks[-1][campo]


def proyectar(cam, aim, lens, p):
    import numpy as np
    c, a, p = np.array(cam, float), np.array(aim, float), np.array(p, float)
    fw = (a - c) / np.linalg.norm(a - c)
    rt = np.cross(fw, [0, 0, 1.0]); rt /= np.linalg.norm(rt)
    up = np.cross(rt, fw)
    v = p - c
    z = v @ fw
    if z <= 0:
        return None
    th, tw = 18 / lens, 18 * 9 / 16 / lens
    return ((v @ rt) / z / tw, (v @ up) / z / th, z)     # -1..1 dentro del cuadro


def chequear(name, j):
    cam = j["camera"]
    for f in j.get("storyboard", []):
        pos, aim = _interp_keys(cam["keys"], f, "pos"), _interp_keys(cam["keys"], f, "aim")
        cosas = {"Nyx": mundo(*NYX), "Vesper": mundo(*VES)}
        for k in ("registro", "mapa"):
            if k in j:
                cosas[k] = j[k]["at"]
        out = []
        for nm, p in cosas.items():
            q = proyectar(pos, aim, cam["lens"], p)
            if q is None:
                out.append(f"{nm}: detras")
            else:
                x, y, z = q
                estado = "ok" if abs(x) < 0.85 and abs(y) < 0.85 else ("borde" if abs(x) < 1 and abs(y) < 1 else "FUERA")
                out.append(f"{nm}: x={x:+.2f} y={y:+.2f} d={z:.1f}m {estado}")
        print(f"  {name} f{f}: " + " | ".join(out))

for name, j in planos.items():
    # sin duende en el cielo, el filo de los drones es el calido de los faroles
    j.setdefault("rim_drones", 0.6)
    j.setdefault("rim_desde", "pueblo")
    j.setdefault("rim_color", "#ffb46a")
    chequear(name, j)
    j = {"_desc": j.pop("_desc"), "extends": "_calle.json", "fps": 12, **j}
    j = {**j, "post": {"fps_unique": j["fps"], "fps_out": 24, "resplandor": {"radios": [50, 140, 300], "pesos": [0.45, 0.4, 0.3],
                                                                   "fuerza": 0.9, "tinte": "#ff2438"}}}
    (EP / "shots" / f"{name}.json").write_text(json.dumps(j, indent=2, ensure_ascii=False), encoding="utf-8")
tl = json.loads((EP / "shots" / "timeline.json").read_text(encoding="utf-8"))
tl["shots"] = ["01_lente", "02_antenas", "03_tarde", "04_registro", "05_escucha", "06_antes",
               "07_duende", "07_lentes", "07_hombro", "08_pausa", "09_mapa"]
(EP / "shots" / "timeline.json").write_text(json.dumps(tl, indent=2), encoding="utf-8")
print("planos:", ", ".join(planos))
