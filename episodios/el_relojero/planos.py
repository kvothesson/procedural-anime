"""
planos.py - Genera los JSON de los planos 4 y 6 (06, 06c, 06d, 06b) de EL RELOJERO.

    python episodios/el_relojero/planos.py && python episodios/el_relojero/fases.py

La accion del plano 6 es una sola (96 frames) y cuatro camaras se reparten
tramos con render_frames. Las fases de engrane las pone fases.py despues.
"""

import json
from pathlib import Path

d = Path(__file__).resolve().parent / "shots"
c = json.loads((d / "06_sacrificio.json").read_text(encoding="utf-8"))
P = [-0.6, -0.05, 1.2]
ROT = [90, 0, 45]
# tren del reloj, todo en el plano diagonal ROT (eje local z = n, hacia el robot):
#   pinon (10 dientes, el que se rompe / el corazon) -> rueda de escape (30) arriba;
#   en el eje de la escape, 6 cm hacia la pared, otro pinon (10) -> rueda grande (90)
# Centros a r1 + r2 - 0.9 * profundidad: con la punta angosta (PERFIL) entra hasta el fondo.
DEPTH = 0.022
R_AT = [P[0], P[1], round(P[2] + 0.1 + 0.3 - 0.9 * DEPTH, 4)]
N = (0.70711, -0.70711, 0.0)              # eje de los engranajes (local z), hacia el robot
EJE_B = -0.06                             # pinon de la escape y rueda grande: hacia la pared
EP_AT = [round(R_AT[i] + EJE_B * N[i], 4) for i in range(3)]
D_G = 0.1 + 0.9 - 0.9 * DEPTH             # pinon b -> rueda grande, a 135 grados en el plano
U135 = (-0.5, -0.5, 0.70711)
G_AT = [round(EP_AT[i] + D_G * U135[i], 4) for i in range(3)]
pin = {"r": 0.1, "teeth": 10, "depth": DEPTH, "thick": 0.03, "r_in": 0.06, "spokes": 4, "hub": 0.022}


def tren(escape_extra=None):
    """Pinon de la escape (coaxial, gira igual que ella) y rueda grande (90 dientes:
    paso, forcejeo y giro libre divididos por 9 y con signo opuesto)."""
    x = escape_extra or {}
    pb = {"name": "rueda_escape_pinon", "at": EP_AT, "rot": ROT, **pin, "step": 6, "phase": 0, **x}
    big = {"name": "rueda_grande", "at": G_AT, "rot": ROT, "r": 0.9, "teeth": 90, "depth": DEPTH, "thick": 0.06,
           "spokes": 6, "hub": 0.08, "r_in": 0.8, "step": -6 / 9, "phase": 0}
    if "strain" in x:
        big["strain"] = dict(x["strain"], amp=-x["strain"]["amp"] / 9)
    if "free" in x:
        big["free"] = dict(x["free"], spin=-x["free"]["spin"] / 9)
    return [pb, big]
c["frames"] = 96
c["render_frames"] = [1, 39]
c["_desc"] = ("Plano 6 (el sacrificio), accion completa de 96 frames que reparten cuatro camaras "
              "(06 general, 06c pecho, 06d eje, 06b ojo). Saca el pinon roto, lo mira, lo suelta; "
              "abre el pecho: su corazon es la misma pieza; lo monta en el eje; el reloj vuelve a andar; se apaga.")
c["sala"] = {"wall_y": 2.1, "room": [-2.8, 2.6, -3.2, 2.1]}
# la esfera desde adentro tiene que ser la misma noche de afuera: cielo violeta,
# resplandor rosado de la ciudad, edificios detras del vidrio y lluvia sobre el
# San Isidro: desde la torre de la catedral se ven copas de arboles y faroles
c["esfera"].update({"top": "#161a44", "bottom": "#6a3a7c", "strength": 1.0,
                    "noche": {"paisaje": "arboles", "copa": "#14202c", "copa_lejos": "#2a2650",
                              "farol": "#ffcf8a", "carriles": 46, "lluvia": "#f0dcff",
                              "lluvia_alfa": 0.45, "gotas": 9.0}})
c["engranajes"] = {
    "color": "#b08a3e",
    "tick": {"bps": 1.0, "jump": 0.4},
    "stop": [1, 81],
    "list": tren() + [
        {"name": "rueda_escape", "at": R_AT, "rot": ROT, "r": 0.3, "teeth": 30, "depth": DEPTH, "thick": 0.05,
         "spokes": 5, "hub": 0.05, "step": 6, "phase": 0},
        {"name": "pinon_roto", "at": P, "rot": ROT, **pin, "missing": [3], "phase": 0, "axle": 0.06, "color": "#8a6a3a"},
        {"name": "pinon_corazon", "at": P, "rot": ROT, **pin, "step": -18, "phase": 0, "ghost": True},
    ],
}
D = {"hombro_d": [0, -6, 0], "codo_d": [-8, 0, 0]}
r = c["relojero"]
r.update({"face": -90, "corazon_mano": 62, "corazon_sale": [50, 53], "cast_shadow": False,
          "pinon": {"obj": "pinon_roto", "grab": 14, "drop": 32},
          "corazon_reloj": {"gear": "pinon_corazon", "slide": [76, 80], "slide_m": 0.12,
                            "glow_gears": ["rueda_escape"]}})
r["pose"] = [
    {"frame": 1, "cintura": [8, 0, 0], "cuello": [25, 0, 0], "muneca_i": [0, 0, 0], **D, "tapa": 0, "ojo": 1.0, "corazon": 1.0},
    {"frame": 8, "cuello": [25, 0, 0]},
    {"frame": 20, "cintura": [8, 0, 0], "cuello": [20, 0, 6]},
    {"frame": 12, "agarre": 0.0},
    {"frame": 14, "agarre": 1.0},
    {"frame": 25, "cintura": [4, 0, 0], "cuello": [15, 0, 25]},
    {"frame": 30, "cintura": [4, 0, 0], "cuello": [16, 0, 22]},
    {"frame": 31, "agarre": 1.0},
    {"frame": 32, "agarre": 0.0},
    {"frame": 35, "cintura": [8, 0, 0], "cuello": [30, 0, 8]},
    {"frame": 40, "muneca_i": [0, 0, 0]},
    {"frame": 40, "cintura": [10, 0, 0], "cuello": [30, 0, 0]},
    {"frame": 45, "tapa": 0},
    {"frame": 51, "tapa": 120},
    {"frame": 58, "cintura": [12, 0, 0], "cuello": [30, 0, 0]},
    {"frame": 60, "agarre": 0.0},
    {"frame": 62, "agarre": 1.0},
    {"frame": 66, "cintura": [6, 0, 0], "cuello": [15, 0, 25]},
    {"frame": 70, "cintura": [6, 0, 0], "cuello": [15, 0, 22]},
    {"frame": 80, "agarre": 1.0},
    {"frame": 82, "agarre": 0.0},
    {"frame": 76, "cintura": [8, 0, 0], "cuello": [22, 0, 2]},
    {"frame": 84, "cintura": [6, 0, 0], "cuello": [20, 0, 0], "ojo": 1.0, "muneca_i": [0, 0, 0]},
    {"frame": 86, "ojo": 0.25},
    {"frame": 87, "ojo": 1.0},
    {"frame": 89, "ojo": 0.6},
    {"frame": 90, "ojo": 0.0},
    {"frame": 92, "ojo": 0.35},
    {"frame": 93, "ojo": 0.0},
    {"frame": 96, "cintura": [14, -8, 0], "cuello": [30, 0, 12], "hombro_d": [3, -6, 0], "codo_d": [-5, 0, 0]},
]
pole = [1.0, -0.4, -0.4]
TO_GEAR = [-0.707, 0.707, 0]     # palma hacia la cara de la rueda (desde el lado del robot)
TO_ROBOT = [1, 0, 0]             # palma hacia el robot (lo que sostiene queda entre la mano y el)
TO_EYE = [0.5, 0.55, 0.65]       # sostenido a su izquierda, mostrandoselo al ojo
r["ik_i"] = [
    {"frame": 1, "rel": [0.42, -0.05, 0.45]},
    {"frame": 8, "rel": [0.42, -0.05, 0.45]},
    {"frame": 12, "to": [-0.47, -0.18, 1.2], "pole": pole, "palm": TO_GEAR},
    {"frame": 14, "obj": "pinon_roto", "off": [0, 0, 0], "pole": pole, "palm": TO_GEAR},
    {"frame": 20, "to": [-0.416, -0.234, 1.2], "pole": pole, "palm": TO_GEAR},
    {"frame": 25, "rel": [0.32, -0.55, 1.22], "pole": pole, "palm": TO_EYE},
    {"frame": 30, "rel": [0.33, -0.56, 1.2], "pole": pole, "palm": TO_EYE},
    {"frame": 32, "rel": [0.35, -0.56, 1.14], "pole": pole, "palm": TO_EYE},
    {"frame": 34, "rel": [0.45, -0.42, 1.05]},
    {"frame": 40, "rel": [0.4, -0.1, 0.6]},
    {"frame": 44, "obj": "tapa_perilla", "off": [0, -0.08, 0.04], "pole": pole},
    {"frame": 45, "obj": "tapa_perilla", "off": [0, -0.08, 0.04], "pole": pole},
    {"frame": 49, "obj": "tapa_perilla", "off": [0, -0.08, 0.04], "pole": pole},
    {"frame": 51, "rel": [0.3, -0.5, 0.95], "pole": pole},
    {"frame": 58, "rel": [0.25, -0.55, 1.0], "pole": pole, "palm": TO_ROBOT},
    {"frame": 61, "obj": "corazon", "off": [0, 0, 0], "pole": pole, "palm": TO_ROBOT},
    {"frame": 62, "obj": "corazon", "off": [0, 0, 0], "pole": pole, "palm": TO_ROBOT},
    {"frame": 66, "rel": [0.32, -0.55, 1.2], "pole": pole, "palm": TO_EYE},
    {"frame": 70, "rel": [0.33, -0.56, 1.22], "pole": pole, "palm": TO_EYE},
    {"frame": 74, "to": [-0.45, -0.2, 1.2], "pole": pole, "palm": TO_GEAR},
    {"frame": 76, "obj": "corazon_reloj", "pole": pole, "palm": TO_GEAR},
    {"frame": 80, "obj": "corazon_reloj", "pole": pole, "palm": TO_GEAR},
    {"frame": 84, "rel": [0.3, -0.45, 1.0], "pole": pole},
    {"frame": 96, "rel": [0.42, -0.08, 0.48]},
]
c["camera"] = {"lens": 32, "clip_end": 100, "ease": True, "keys": [
    {"frame": 1, "pos": [-0.35, -2.45, 1.35], "aim": [-0.35, -0.05, 1.3]},
    {"frame": 39, "pos": [-0.35, -2.25, 1.33], "aim": [-0.35, -0.05, 1.28]}]}
c["colision_ok"] = [["pinon_roto", "pinon_roto_eje"], ["corazon_reloj", "pinon_roto_eje"],
                    ["corazon", "corazon_eje"], ["corazon_eje", "pecho_hueco"], ["corazon_mano", "corazon_eje"],
                    ["tapa_bisagra", "pecho_aro"], ["tapa_bisagra", "torso"], ["tapa_bisagra", "tapa_disco"],
                    ["rueda_escape", "pinon_roto"], ["rueda_escape", "corazon_reloj"],
                    ["pinon_roto_mano", "pinon_roto_eje"], ["pinon_roto_mano", "rueda_escape"]]
(d / "06_sacrificio.json").write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")


def sub(name, frames, cam, desc):
    (d / f"{name}.json").write_text(json.dumps({"extends": "06_sacrificio.json", "_desc": desc,
                                                "render_frames": frames, "camera": cam},
                                               ensure_ascii=False, indent=2), encoding="utf-8")


sub("06c_pecho", [40, 67], {"lens": 40, "clip_end": 100, "ease": True, "keys": [
    {"frame": 40, "pos": [-1.0, 0.58, 1.18], "aim": [-0.25, -0.02, 1.08]},
    {"frame": 67, "pos": [-0.94, 0.54, 1.16], "aim": [-0.25, -0.02, 1.1]}]},
    "Plano 6c: primer plano del pecho. Abre la tapa, el corazon asoma: es la misma pieza que el pinon roto. Lo saca.")
sub("06d_eje", [68, 84], {"lens": 35, "clip_end": 100, "ease": True, "keys": [
    {"frame": 68, "pos": [-0.2, -1.75, 1.35], "aim": [-0.45, -0.1, 1.3]},
    {"frame": 84, "pos": [-0.22, -1.65, 1.35], "aim": [-0.47, -0.1, 1.32]}]},
    "Plano 6d: lo monta en el eje; engrana con la rueda y el reloj vuelve a andar.")
sub("06b_ojo", [85, 96], {"lens": 45, "clip_end": 100, "ease": True, "keys": [
    {"frame": 85, "pos": [-0.88, -0.66, 1.36], "aim": [-0.28, -0.06, 1.55]},
    {"frame": 96, "pos": [-0.86, -0.64, 1.3], "aim": [-0.26, -0.06, 1.4]}]},
    "Plano 6b (contraplano): la cara del relojero mientras el reloj vuelve a andar. El ojo titila, se apaga, la cabeza cae.")

pin4 = {"name": "pinon_roto", "at": P, "rot": ROT, **pin, "missing": [3], "axle": 0.06, "color": "#8a6a3a",
        "step": -18, "phase": 0, "strain": {"from": 37, "to": 40, "amp": -4.5, "hz": 5},
        "free": {"frame": 40, "spin": 450, "tau": 0.45},
        "salta": {"tooth": 3, "frame": 40, "vel": [0.2, -1.0, 1.4], "spin": [520, 260, 90]}}
rue4 = {"name": "rueda_escape", "at": R_AT, "rot": ROT, "r": 0.3, "teeth": 30, "depth": DEPTH, "thick": 0.05,
        "spokes": 5, "hub": 0.05, "step": 6, "phase": 0, "strain": {"from": 37, "to": 40, "amp": 1.5, "hz": 5},
        "free": {"frame": 40, "spin": -150, "tau": 0.45}}
c4 = {
    "extends": "06_sacrificio.json",
    "drop": ["render_frames"],
    "_desc": ("Plano 4 (la falla): el pinon empuja a la rueda tic a tic. En un tic la rueda se resiste, "
              "el pinon forcejea, se le parte el diente y la rueda se desboca hacia atras hasta clavarse."),
    "frames": 60,
    "engranajes": {"color": "#b08a3e", "tick": {"bps": 1.0, "jump": 0.4}, "stop": [37, 999], "list": tren({"strain": rue4["strain"], "free": rue4["free"]}) + [rue4, pin4]},
    "relojero": {
        "corazon_mano": 999, "corazon_sale": [999, 1000], "corazon_reloj": None, "pinon": None,
        "pose": [
            {"frame": 1, "cintura": [6, 0, 0], "cuello": [22, 0, 0], "muneca_i": [0, 0, 0], **D, "tapa": 0, "ojo": 1.0, "corazon": 1.0},
            {"frame": 40, "cintura": [6, 0, 0], "cuello": [22, 0, 0], **D},
            {"frame": 43, "cintura": [-5, 0, 0], "cuello": [0, 0, 6], "hombro_d": [-15, -6, 0], "codo_d": [-30, 0, 0]},
            {"frame": 48, "cintura": [-4, 0, 0], "cuello": [2, 0, 6]},
            {"frame": 60, "cintura": [8, 0, 0], "cuello": [22, 0, 0], **D},
        ],
        "ik_i": [
            {"frame": 1, "rel": [0.42, -0.05, 0.45]},
            {"frame": 40, "rel": [0.42, -0.05, 0.45]},
            {"frame": 43, "rel": [0.48, -0.2, 0.62]},
            {"frame": 48, "rel": [0.47, -0.18, 0.6]},
            {"frame": 60, "rel": [0.42, -0.08, 0.46]},
        ],
    },
    # acercamiento al punto de contacto durante el forcejeo, y vuelve a abrir
    "camera": {"lens": 35, "clip_end": 100, "ease": True, "keys": [
        {"frame": 1, "pos": [-0.32, -1.5, 1.42], "aim": [-0.55, -0.05, 1.38]},
        {"frame": 28, "pos": [-0.33, -1.45, 1.42], "aim": [-0.56, -0.05, 1.38]},
        {"frame": 38, "pos": [-0.27, -0.62, 1.36], "aim": [-0.6, -0.05, 1.3]},
        {"frame": 44, "pos": [-0.28, -0.66, 1.37], "aim": [-0.6, -0.05, 1.32]},
        {"frame": 54, "pos": [-0.33, -1.45, 1.42], "aim": [-0.52, -0.05, 1.36]},
        {"frame": 60, "pos": [-0.33, -1.48, 1.42], "aim": [-0.5, -0.05, 1.36]}]},
    "post": {"glitch": [[40, 41, 0.7]]},
}
(d / "04_falla.json").write_text(json.dumps(c4, ensure_ascii=False, indent=2), encoding="utf-8")
print("ok")
