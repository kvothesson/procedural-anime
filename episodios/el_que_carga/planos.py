"""planos.py - Genera los JSON de EL QUE CARGA (shots/*.json + timeline).

    python episodios/el_que_carga/planos.py

Un mundo comun (roca, Hombre-Tanque, linea, toon, post con papel) y cada
plano pisa paleta, paisaje, camara y post. Los biomas cambian solo de color:
la pose y el encuadre de la caminata se repiten (como en el corto).
"""

import copy
import json
import math
from pathlib import Path

SHOTS = Path(__file__).resolve().parent / "shots"


def pol(a, d, z):
    return [round(d * math.cos(math.radians(a)), 1), round(d * math.sin(math.radians(a)), 1), z]


def cam(pos, aim, lens=24, f=1):
    return {"lens": lens, "clip_end": 3000, "keys": [{"frame": f, "pos": pos, "aim": aim}]}


BASE = {
    "width": 1080, "height": 1920, "fps": 12, "samples": 8,
    "toon": {"steps": [[0.0, 0.6], [0.25, 1.0]]},
    "lights": [{"kind": "SUN", "color": "#fff1d6", "energy": 4.5, "hacia": [0.5, -0.45, 0.75], "angle": 0.6}],
    "line": {"color": "#1d1030", "radius": 0.055, "crease_deg": 100},
    "post": {"rain": False, "glow": {"threshold": 0.985, "strength": 0.6}, "grain": 0.012,
             "papel": {"manchas": 0.07, "fibra": 0.03, "seed": 11}},
    "roca": {"punta": [0.49, 0.0, 6.95], "radio": 85, "alto": 58, "forma": 1.0, "rugosidad": 0.12,
             "anillos": 26, "segmentos": 48, "seed": 7},
    "tanque": {"at": [0, 0, 0], "paso": 0.12, "abre": 0.7, "inclina": 0.14, "mano_z": 6.7},
    # la bombacha entra debajo de la faja: es la costura, no un traspaso
    "colision_ok": [["bombacha_i", "faja"], ["bombacha_d", "faja"]],
}

TORRES = [[0, 0, 34, 5], [-18, 10, 24, 4], [16, -8, 20, 4], [-8, -22, 14, 3.5], [26, 14, 16, 3.5], [-30, -6, 12, 3]]

PAMPA = {
    "sky": {"horizon": "#c4e6ea", "top": "#4d8fd1", "ambient": "#9fb6d6", "ambient_strength": 0.6, "zenith_at": 0.5},
    "fog": {"color": "#c4e6ea", "dist": 4000.0},
    "paisaje": {"piso": "#9dbb52", "cerros": [
        {"dist": 1100, "alto": 70, "color": "#86aed3", "arco": [60, 210], "picos": True},
        {"dist": 700, "alto": 30, "color": "#5f8fbf", "arco": [60, 210]},
        {"dist": 420, "alto": 9, "color": "#7fa64a", "arco": [60, 210], "ondas": [[5, 0.6], [17, 0.3]]}],
        "nubes": [{"at": pol(118, 650, 70), "escala": 60}, {"at": pol(150, 720, 30), "escala": 75},
                  {"at": pol(100, 520, 170), "escala": 40}, {"at": pol(165, 600, 210), "escala": 50}]},
}

MEZCLA = ("roca", "tanque", "post")      # claves que se mezclan en vez de pisarse


def bioma(sky, fog, piso, cerros, luz, nubes=(), **extra):
    return {"sky": sky, "fog": {"color": fog, "dist": 4000.0},
            "lights": [dict(BASE["lights"][0], **luz)],
            "paisaje": {"piso": piso, "cerros": cerros, "nubes": list(nubes)}, **extra}


CICLO = {"frames": 18, "zancada": 0.85}           # un paso doble cada 1,5 s: pesado
VEL = 4 * CICLO["zancada"] / CICLO["frames"]     # m por cuadro (el pie apoyado no patina)


def sigue(n, pos, aim, lens):
    """Camara que acompaña al que camina: se corre en X a su velocidad."""
    d = VEL * (n - 1)
    return {"lens": lens, "clip_end": 3000, "keys": [
        {"frame": 1, "pos": pos, "aim": aim},
        {"frame": n, "pos": [pos[0] + d, pos[1], pos[2]], "aim": [aim[0] + d, aim[1], aim[2]]}]}


def matas(n, cam_pos, color, dist=3.2):
    """Franja recta de matas entre la camara y el, a lo largo del camino."""
    x0 = cam_pos[0] - 25
    x1 = cam_pos[0] + 25 + VEL * n
    return {"recta": {"y": cam_pos[1] + dist, "x0": x0, "x1": x1, "n": int((x1 - x0) * 6)},
            "alto": 2.7, "base": -1.2, "color": color, "ondas": [[45 * (x1 - x0) / 20, 0.5], [113 * (x1 - x0) / 20, 0.35],
                                                                  [7 * (x1 - x0) / 20, 0.4]]}


def caminata(cerca, n):
    """El encuadre de la caminata: de 3/4, camina y la camara lo acompaña.
    'cerca' = color de las matas del primer plano."""
    pos = [9.0, -26.0, 1.9]
    return {"tanque": {"ciclo": CICLO, "inclina": 0.2, "mano_z": 6.6},
            "camera": sigue(n, pos, [0.5, 0.0, 12.5], 26),
            "_fg": matas(n, pos, cerca)}


def plano(desc, frames, sb, *capas):
    d = copy.deepcopy(BASE)
    fgs = []
    for c in capas:
        for k, v in copy.deepcopy(c).items():
            if k == "_fg":
                fgs.append(v)
            elif k in MEZCLA:
                d[k] = {**d.get(k, {}), **v}
            else:
                d[k] = v
    for fg in fgs:
        d["paisaje"]["cerros"].append(fg)
    d.update(_desc=desc, frames=frames, storyboard=sb)
    return d


P = {}

P["01_revelacion"] = plano(
    "01 revelacion - Todo violeta: la panza de la roca. La camara baja hasta el Hombre-Tanque que la sostiene en la pampa",
    48, [1, 48], PAMPA,
    {"camera": {"lens": 24, "clip_end": 3000, "keys": [
        {"frame": 1, "pos": [21.0, -23.0, 1.6], "aim": [-1.0, 2.0, 60.0]},
        {"frame": 48, "pos": [21.0, -23.0, 1.6], "aim": [-1.0, 2.0, 11.5]}]},
     "_fg": {"centro": [21.0, -23.0], "dist": 3.2, "alto": 2.2, "base": -1.2, "color": "#2f4a2c",
             "arco": [85, 180], "ondas": [[70, 0.5], [151, 0.4], [9, 0.3]]}})

P["02_cima"] = plano(
    "02 cima - Arriba: pasto lima, torres del laboratorio con ventanas cian, nubes abajo. Calma total",
    36, [18],
    {"sky": {"horizon": "#c6fbf2", "top": "#2fd3d0", "ambient": "#9ee9e2", "ambient_strength": 0.7, "zenith_at": 0.55},
     "fog": {"color": "#c6fbf2", "dist": 4000.0},
     "roca": {"pasto": "#b9e04a", "laboratorio": {"torres": TORRES}},
     "paisaje": {"piso": "#9dbb52", "cerros": [], "nubes": [
         {"at": [-40, -120, 40], "escala": 30}, {"at": [70, -90, 30], "escala": 26}, {"at": [-160, 200, 60], "escala": 50}]},
     "camera": cam([62.0, -150.0, 78.0], [0.0, 0.0, 84.0], 35)})

P["03_pie"] = plano(
    "03 pie - Detalle sobre rojo: la bota vendada pisa y el aceite negro gotea de la rodilla",
    36, [6],
    {"sky": {"horizon": "#b8302f", "top": "#8e1f2a", "ambient": "#c46a6a", "ambient_strength": 0.6, "zenith_at": 0.6},
     "fog": {"color": "#b8302f", "dist": 4000.0},
     "paisaje": {"piso": "#8a4a36", "cerros": [{"dist": 60, "alto": 1.2, "color": "#5a1a24", "arco": [40, 140]}], "nubes": []},
     "tanque": {"ciclo": CICLO},
     "camera": sigue(36, [2.4, -7.5, 0.5], [0.2, 0.3, 0.55], 60),
     "line": {"color": "#1d1030", "radius": 0.012, "crease_deg": 100}})

P["04_puna"] = plano(
    "04 puna - Camina por la Puna al atardecer: cerros rojos y violetas, suelo ocre",
    42, [21],
    bioma({"horizon": "#f4b987", "top": "#6e5aa8", "mid": "#d98a8f", "mid_at": 0.25, "interp": "EASE",
           "ambient": "#c89aa8", "ambient_strength": 0.6, "zenith_at": 0.6}, "#f0b48c", "#b98a5e",
          [{"dist": 1300, "alto": 120, "color": "#6b4a86", "arco": [30, 150], "picos": True},
           {"dist": 800, "alto": 70, "color": "#9a3f6b", "arco": [30, 150], "picos": True},
           {"dist": 450, "alto": 28, "color": "#bf4a3a", "arco": [30, 150], "picos": True},
           {"dist": 160, "alto": 3, "color": "#a8744a", "arco": [30, 150], "ondas": [[11, 0.5], [31, 0.3]]}],
          {"color": "#ffc89a", "energy": 2.6, "hacia": [0.7, -0.3, 0.4]},
          [{"at": [-500, 700, 200], "escala": 60, "color": "#f6d2c0"}],
          roca={"color": "#2b1230"}, tanque={"colores": {"poncho": "#efd9b8", "metal": "#8aa39a"}}),
    caminata("#4a2a2a", 42))

P["05_nieve"] = plano(
    "05 nieve - Patagonia: cerros blancos, cielo gris, nieve que cae de costado",
    42, [21],
    bioma({"horizon": "#dfe8ee", "top": "#7f9bb8", "ambient": "#b9c8d8", "ambient_strength": 0.75, "zenith_at": 0.55},
          "#dfe8ee", "#eef3f6",
          [{"dist": 1200, "alto": 160, "color": "#a9bdd2", "arco": [30, 150], "picos": True},
           {"dist": 700, "alto": 80, "color": "#d6e2ec", "arco": [30, 150], "picos": True},
           {"dist": 300, "alto": 12, "color": "#5d7a8e", "arco": [30, 150], "ondas": [[13, 0.5], [41, 0.3]]}],
          {"color": "#e8f0ff", "energy": 2.8, "hacia": [0.4, -0.6, 0.6]},
          roca={"color": "#26203a"},
          post={"rain": {"angle_deg": 24, "color": "#ffffff", "layers": [
              {"count": 500, "length": [2, 4], "width": 3, "speed": 160, "alpha": 0.55},
              {"count": 160, "length": [4, 7], "width": 6, "speed": 260, "alpha": 0.7},
              {"count": 30, "length": [8, 12], "width": 11, "speed": 420, "alpha": 0.8}]}}),
    caminata("#3a4a5e", 42))

P["06_salinas"] = plano(
    "06 salinas - Salinas Grandes: piso blanco, cielo azul profundo, cerros lejanos violeta",
    36, [18],
    bioma({"horizon": "#a8d4f4", "top": "#1d47b0", "ambient": "#9fbde0", "ambient_strength": 0.6, "zenith_at": 0.45},
          "#a8d4f4", "#f5f6f1",
          [{"dist": 1300, "alto": 60, "color": "#8b7ba6", "arco": [30, 150], "picos": True},
           {"dist": 900, "alto": 22, "color": "#b2a6c4", "arco": [30, 150]}],
          {"color": "#ffffff", "energy": 4.0, "hacia": [0.3, -0.5, 0.8]},
          roca={"color": "#1e1440"}),
    caminata("#c9cfd6", 36))

P["07_leyenda"] = {
    **{k: BASE[k] for k in ("width", "height", "fps", "samples")},
    "_desc": "07 leyenda - Cartel fileteado (leyenda.py): EL QUE CARGA, leyenda del Hombre-Tanque",
    "frames": 60, "storyboard": [30],
    "sky": {"horizon": "#120e0c", "top": "#120e0c", "ambient": "#000000", "ambient_strength": 0.0},
    "camera": cam([0, -10, 2], [0, 0, 2], 35),
    "post": {"rain": False, "glow": {"threshold": 0.99, "strength": 0.0}, "vignette": 0.0, "aberration": 0.0,
             "grain": 0.008, "imagenes": [{"src": "out/leyenda.png", "pos": [0.5, 0.5], "height": 1.0,
                                           "frames": [1, 60], "shadow": 0.0}]},
}

P["08_visor"] = plano(
    "08 visor - Primer plano del visor bajo el ala del sombrero; a mitad del plano se glitchea",
    48, [12, 30], PAMPA,
    {"tanque": {"ciclo": CICLO},
     "camera": sigue(48, [7.5, -2.6, 5.2], [0.45, 0.0, 5.2], 115),
     "line": {"color": "#1d1030", "radius": 0.014, "crease_deg": 100},
     "post": {"glitch": [[26, 34, 0.6]]}})

P["09_lejos"] = plano(
    "09 lejos - Muy lejos: la roca con el laboratorio es una columna oscura sobre el horizonte; el diminuto abajo",
    60, [30, 60], PAMPA,
    {"sky": {"horizon": "#f6d7a0", "top": "#5c8fd0", "mid": "#c9c4c0", "mid_at": 0.2, "interp": "EASE",
             "ambient": "#c9b8a8", "ambient_strength": 0.6, "zenith_at": 0.55},
     # sin niebla: a 900 m la roca tiene que llegar con el mismo violeta del 01 (loop)
     "fog": {"color": "#f6d7a0", "dist": 10000000.0},
     "lights": [{"kind": "SUN", "color": "#ffd9a0", "energy": 3.4, "hacia": [-0.6, 0.3, 0.35], "angle": 0.6}],
     # el violeta que la niebla del 01 le da a la roca en su primer cuadro (medido)
     "roca": {"color": "#2d1e3a", "pasto": "#9dbb52", "laboratorio": {"torres": TORRES}},
     "tanque": {"ciclo": CICLO},
     # loop: desde el cuadro 36 la lente se cierra sobre la panza de la roca
     # hasta llenar el cuadro de violeta, que es el primer cuadro del 01
     "camera": {"lens": 85, "clip_end": 3000, "lens_keys": [[1, 85], [34, 85], [58, 1400], [60, 1400]], "keys": [
         {"frame": 1, "pos": [620.0, -660.0, 3.0], "aim": [0.0, 0.0, 110.0]},
         {"frame": 34, "pos": [620.0, -660.0, 3.0], "aim": [VEL * 33, 0.0, 110.0]},
         {"frame": 58, "pos": [620.0, -660.0, 3.0], "aim": [VEL * 57, 0.0, 38.0]},
         {"frame": 60, "pos": [620.0, -660.0, 3.0], "aim": [VEL * 59, 0.0, 38.0]}]}})


def main():
    for k, v in P.items():
        (SHOTS / f"{k}.json").write_text(json.dumps(v, indent=1, ensure_ascii=False), encoding="utf-8")
    (SHOTS / "02_puna.json").unlink(missing_ok=True)       # la prueba de look paso a ser 04_puna
    tl = {"name": "el_que_carga", "fps_unique": 12, "fps_out": 24, "shots": list(P)}
    (SHOTS / "timeline.json").write_text(json.dumps(tl, indent=1), encoding="utf-8")
    print(len(P), "planos")


if __name__ == "__main__":
    main()
