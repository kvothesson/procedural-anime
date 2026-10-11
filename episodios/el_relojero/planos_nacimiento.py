"""
planos_nacimiento.py - Genera 07_nacimiento.json (el reloj arma un relojero nuevo)
y 01_gancho.json (el ojo nuevo se enciende). Es una sola escena de 108 frames:
el 07 muestra 1-80 y el 01 muestra 80-108, asi el ultimo cuadro del corto (el 80
del 07) es el primero (el 80 del 01): loop exacto.

    python episodios/el_relojero/planos_nacimiento.py

Depende de 06_sacrificio.json (fases de la rueda y del pinon fantasma: el reloj
sigue engranado con el corazon del robot viejo).
"""

import json
import math
from pathlib import Path

D = Path(__file__).resolve().parent / "shots"

# piezas del robot nuevo, de abajo hacia arriba: (nombre, frame de llegada)
ORDEN = [
    ("pie_i", 10), ("pie_d", 11), ("canilla_i", 12), ("canilla_d", 13), ("rodilla_bola_i", 15), ("rodilla_bola_d", 15),
    ("muslo_i", 17), ("muslo_d", 17),
    ("pelvis", 20), ("ribete_bajo", 23), ("torso", 27), ("ribete_alto", 31), ("pecho_hueco", 33),
    ("pecho_aro", 34), ("corazon_eje", 36), ("llave_eje", 37), ("llave_ala1", 38), ("llave_ala-1", 39),
    ("hombrera_i", 41), ("hombrera_d", 42), ("brazo_i", 43), ("brazo_d", 44), ("codo_bola_i", 45),
    ("codo_bola_d", 45), ("antebrazo_i", 47), ("antebrazo_d", 48), ("muneca_bola_i", 49),
    ("muneca_bola_d", 49), ("palma_i", 50), ("palma_d", 51), ("dedo_i0", 52), ("dedo_i1", 52),
    ("dedo_i2", 52), ("pulgar_i", 52), ("dedo_d0", 54), ("dedo_d1", 54), ("dedo_d2", 54), ("pulgar_d", 54),
    ("cuello_eje", 57), ("craneo", 60), ("antena", 62), ("antena_bola", 63),
    ("ojo_aro", 64), ("ojo", 65), ("visera", 67),
    # lo ultimo: un corazon nuevo que el reloj le da, y la tapa que se cierra
    ("corazon", 72), ("tapa_bisagra", 74), ("tapa_disco", 76), ("tapa_perilla", 77),
]


ORDEN_D = dict(ORDEN)


def jitter(i, k):
    """Azar fijo por pieza (-1..1)."""
    return math.sin(i * 12.9898 + k * 78.233) * 43758.5453 % 2 - 1


def main():
    c6 = json.loads((D / "06_sacrificio.json").read_text(encoding="utf-8"))
    gears = {g["name"]: g for g in c6["engranajes"]["list"]}
    bg = [gears[n] for n in ("rueda_grande", "rueda_escape_pinon")]   # el tren completo
    rueda = dict(gears["rueda_escape"])
    ghost = dict(gears["pinon_corazon"], axle=0.06)

    # las piezas estan desde el principio tiradas en el piso (una pila de
    # repuestos frente al lugar donde va a quedar) y vuelan en arco a su lugar;
    # piezas.py calcula el "from" de cada una. El corazon no: baja del reloj.
    partes = {}
    for name, f1 in ORDEN:
        travel = 10 if name != "corazon" else 12
        partes[name] = {"span": [f1 - travel, f1]}
    partes["corazon"] = {"from": [0, -0.5, 2.4], "via": [0, -0.42, 0], "spin": [0, 0, 720],
                         "span": [ORDEN_D["corazon"] - 12, ORDEN_D["corazon"]], "ocultar": True}

    neutro = {"cintura": [0, 0, 0], "cuello": [12, 0, 0], "hombro_i": [0, 0, 6], "codo_i": [-6, 0, 0],
              "muneca_i": [0, 0, 0], "hombro_d": [0, 0, -6], "codo_d": [-6, 0, 0], "muneca_d": [0, 0, 0], "tapa": 0}
    c = {
        "_desc": ("Escena del nacimiento (108 frames): el relojero viejo desplomado; el reloj, que anda con su "
                  "corazon, arma uno nuevo pieza por pieza y le da un corazon nuevo. 07 = frames 1-80 (armado y "
                  "acercamiento), 01 = 80-108 (el ojo se enciende)."),
        "width": 1080, "height": 1920, "fps": 12, "frames": 108, "samples": 8,
        "sky": c6["sky"], "fog": c6["fog"], "toon": c6["toon"], "lights": c6["lights"], "line": c6["line"],
        "perf": c6.get("perf", {}),
        # pared de enfrente mas lejos: el plano es abierto
        "sala": dict(c6["sala"], room=[-2.8, 2.6, -4.4, 2.1]),
        "esfera": dict(c6["esfera"], hora=[0, 1]),
        "engranajes": {"color": "#b08a3e", "tick": {"bps": 1.0, "jump": 0.4}, "list": bg + [rueda, ghost]},
        "relojero": {
            "at": [1.05, -0.05, 0], "face": -20, "cast_shadow": False,
            "ojo_fuerza": 1.0,      # en primer plano el ojo a 2.2 se quemaba en blanco
            "despiece": {"modo": "armar", "partes": partes,
                         "pila": {"center": [0.7, -0.95], "radius": 0.48, "seed": 3, "clac": 0.012, "arc": 0.5,
                                  # por su derecha esta el robot viejo: ese brazo entra de frente
                                  "lados": {"i": [1.0, -0.7, 0.0], "d": [-0.35, -1.0, 0.0]},
                                  "arriba": ["ribete_alto", "visera", "antena", "antena_bola"],
                                  # la llave entra por atras y desde arriba: desde la pila pasa por encima
                                  "vias": {"llave_eje": [0, 0.2, 0.7], "llave_ala1": [0, 0.2, 0.7],
                                           "llave_ala-1": [0, 0.2, 0.7]},
                                  "clac_en": ["pie_i", "pie_d", "canilla_i", "canilla_d", "pelvis", "torso",
                                              "ribete_bajo", "craneo"],
                                  "quietas": ["llave_eje", "llave_ala1", "llave_ala-1", "tapa_disco", "tapa_perilla", "tapa_bisagra", "ojo_aro", "ojo", "visera",
                                              "hombrera_i", "hombrera_d", "brazo_i", "brazo_d", "codo_bola_i",
                                              "codo_bola_d", "antebrazo_i", "antebrazo_d", "muneca_bola_i",
                                              "muneca_bola_d", "palma_i", "palma_d"],
                                  "grupos": {"mano_i": ["dedo_i0", "dedo_i1", "dedo_i2", "pulgar_i"],
                                             "mano_d": ["dedo_d0", "dedo_d1", "dedo_d2", "pulgar_d"]}}},
            "pose": [
                {"frame": 1, **neutro, "ojo": 0.0, "corazon": 1.0},
                {"frame": 86, "ojo": 0.0},
                {"frame": 87, "ojo": 0.45},
                {"frame": 88, "ojo": 0.0},
                {"frame": 90, "ojo": 1.0},
                {"frame": 91, "ojo": 0.5},
                {"frame": 92, "ojo": 1.0, "cuello": [12, 0, 0]},
                {"frame": 102, "cuello": [-6, 0, -8]},
                {"frame": 108, "cuello": [-7, 0, -9]},
            ],
        },
        "relojero_viejo": {
            "at": [0, 0, 0], "face": -90, "cast_shadow": False,
            "corazon_reloj": {"gear": "pinon_corazon", "slide": [1, 1], "glow_gears": ["rueda_escape"]},
            "pose": [{"frame": 1, "cintura": [14, -8, 0], "cuello": [30, 0, 12], "hombro_i": [3, 0, 10],
                      "codo_i": [-5, 0, 0], "muneca_i": [0, 0, 0], "hombro_d": [3, -6, 0], "codo_d": [-5, 0, 0],
                      "tapa": 120, "ojo": 0.0, "corazon": 1.0}],
        },
        "camera": {"lens": 30, "clip_end": 100, "ease": True, "keys": [
            # abierto: el viejo, su corazon en el eje (el reloj anda con el) y el nuevo
            {"frame": 1, "pos": [0.25, -3.5, 1.3], "aim": [0.25, 0.0, 1.2]},
            {"frame": 60, "pos": [0.35, -3.2, 1.32], "aim": [0.4, 0.0, 1.22]},
            {"frame": 80, "pos": [0.8, -0.62, 1.58], "aim": [1.05, -0.05, 1.58]},
            {"frame": 108, "pos": [0.8, -0.6, 1.58], "aim": [1.05, -0.05, 1.6]}]},
        "post": dict(c6.get("post", {})),
        "render_frames": [1, 80],
        "colision_base": [1, 108],
        "colision_ok": [["corazon", "corazon_eje"], ["antena", "craneo"], ["pecho_hueco", "tapa_bisagra"],
                        ["pelvis", "torso"]],
    }
    (D / "07_nacimiento.json").write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    g = {"extends": "07_nacimiento.json", "render_frames": [80, 108],
         "_desc": "Plano 1 (gancho): en la oscuridad de la sala, el ojo de un relojero nuevo titila y se enciende."}
    (D / "01_gancho.json").write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ok")


if __name__ == "__main__":
    main()
