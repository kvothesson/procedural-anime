"""
planos_ciudad.py - Genera 02_ciudad.json y 05_desincronia.json: la Catedral de
San Isidro de noche, bajo la lluvia, vista desde la calle (la torre del reloj a la
derecha, la nave con sus vitrales hacia el fondo, arboles a los dos lados). En el
02 todo late con el tic; en el 05, cuando el reloj se traba, cada luz pierde el
compas. Tambien es duena del orden del montaje (timeline.json).

    python episodios/el_relojero/planos_ciudad.py
"""

import json
from pathlib import Path

D = Path(__file__).resolve().parent / "shots"
NODO = Path(__file__).resolve().parents[1] / "nodo_404" / "shots"

CATEDRAL = {
    "torre": [7.0, 14.0], "ancho": 9.0, "ladrillo": "#b8655c", "piedra": "#e6d3b3", "techo": "#3a3a52",
    "vitrales": ["#ffb860", "#5aa8ff", "#ff6ab0"], "reloj": "#ffe7b8", "reloj_z": 25.0, "reloj_r": 1.7,
    "aguja_r": 3.3, "aguja_h": 26.0, "nave_largo": 40.0, "nave_ancho": 15.0, "nave_alto": 24.0, "nave_paso": 4.4,
    "lateral_ancho": 5.0, "lateral_alto": 11.0, "cerco": [1.0, -6.0, 9.0],
    # nubes detras de la torre, en la direccion de la camara (entre 26 y 58 grados de elevacion)
    "nubes": [[69.1, 126.0, 86.6, 55, 22, 8], [130.3, 86.7, 132.8, 70, 25, 9], [72.7, 182.4, 190.0, 60, 20, 8], [186.7, 83.1, 250.3, 80, 28, 10], [169.0, 27.6, 78.0, 50, 18, 7], [148.9, 156.3, 368.1, 90, 30, 10]],
    "hora": [23, 59], "cordon_x": -0.6,
    "piso": {"color": "#2a2d48", "puddles": {"scale": 2.4, "threshold": 0.56, "stretch": 0.35}},
    "faroles": [[0.5, -12.0], [0.5, -1.0], [0.5, 9.0], [0.5, 30.0]], "farol_energia": 900,
}
ARBOLES = {
    "seed": 21, "colors": ["#1f3a3a", "#24443c", "#1b3340"], "trunk": "#2a2030", "scale": [2.6, 3.4],
    # enmarcan como en la foto: la otra vereda, uno grande cerca a cada lado y una fila detras de la nave
    "rows": [{"x": -32.0, "y": [14, 90], "spacing": 9.0}, {"x": -2.2, "y": [1.5, 2.5], "spacing": 9.0},
             {"x": 36.0, "y": [8, 60], "spacing": 7.0}],
}


def main():
    base = json.loads((NODO / "02_calle.json").read_text(encoding="utf-8"))
    c2 = {
        "_desc": ("Plano 2 (la ciudad al compas): la Catedral de San Isidro de noche bajo la lluvia, la torre del "
                  "reloj, la nave con sus vitrales, arboles. En cada tic todo late: vitrales, faroles, el reloj."),
        "width": 1080, "height": 1920, "fps": 12, "frames": 60, "samples": 8,
        # noche nublada de ciudad: nada de negro puro arriba
        "sky": dict(base["sky"], top="#171a40", zenith_at=0.95), "fog": dict(base["fog"], dist=110.0),
        "toon": base.get("toon"),
        # la noche de NODO 404 + reflectores calidos desde la vereda sobre la fachada
        "lights": base["lights"] + [{"kind": "SUN", "color": "#ffc98a", "energy": 1.3, "rot": [0, -112, 20],
                                     "shadow": False}],
        "line": base.get("line", {"color": "#0d0b24"}),
        "catedral": CATEDRAL,
        "trees": ARBOLES,
        "reflection_tint": "#0b0d22",
        "pulso": {"bps": 1.0, "lo": 0.35, "hi": 1.0, "decay": 0.3},
        "camera": {"lens": 16, "ease": True, "keys": [
            # cerca y desde abajo, como la foto: la torre llena el cuadro
            {"frame": 1, "pos": [-17.0, -3.0, 1.5], "aim": [3.5, 15.0, 27.0]},
            {"frame": 60, "pos": [-16.2, -2.2, 1.5], "aim": [3.5, 15.0, 28.5]}]},
    }
    c2 = {k: v for k, v in c2.items() if v is not None}
    (D / "02_ciudad.json").write_text(json.dumps(c2, ensure_ascii=False, indent=2), encoding="utf-8")
    bus = json.loads((NODO / "03_colectivo.json").read_text(encoding="utf-8"))["colectivo"]
    c5 = {
        "extends": "02_ciudad.json",
        "_desc": ("Plano 5 (la desincronia): la catedral. El reloj se traba: cada luz late con su propio ritmo, "
                  "algunas titilan y se apagan, el reloj de la torre se apaga y el colectivo frena en el aire."),
        "pulso": {"bps": 1.0, "lo": 0.35, "hi": 1.0, "decay": 0.3, "seed": 11,
                  "desync": {"frame": 18, "die": 0.55, "spread": 36, "revive": 0.4}},
        # viene por la calle y frena en el aire cuando el reloj se traba (frame 18)
        "colectivo": dict(bus, lane_x=-4.2, path=[[1, 40], [14, 6], [18, -2], [22, -7], [27, -9.4], [32, -9.9],
                                                  [60, -10.1]]),
        "camera": {"lens": 16, "ease": True, "keys": [
            {"frame": 1, "pos": [-16.0, -2.5, 1.4], "aim": [3.0, 15.0, 22.0]},
            {"frame": 60, "pos": [-15.4, -1.9, 1.38], "aim": [3.0, 15.0, 22.5]}]},
        "post": {"glitch": [[18, 19, 0.6], [31, 31, 0.35], [45, 46, 0.5]]},
    }
    (D / "05_desincronia.json").write_text(json.dumps(c5, ensure_ascii=False, indent=2), encoding="utf-8")
    # el orden del montaje vive aca (los otros generadores no tocan timeline.json)
    t = json.loads((D / "timeline.json").read_text(encoding="utf-8"))
    order = ["01_gancho", "02_ciudad", "03_subida", "04_falla", "05_desincronia", "06_sacrificio", "06c_pecho",
             "06d_eje", "06b_ojo", "07_nacimiento"]
    t["shots"] = [s for s in order if (D / f"{s}.json").exists()]
    (D / "timeline.json").write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ok:", t["shots"])


if __name__ == "__main__":
    main()
