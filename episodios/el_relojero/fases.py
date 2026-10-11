"""
fases.py - Fases de engrane del reloj de EL RELOJERO (sin Blender).

    python episodios/el_relojero/fases.py

El pinon (10 dientes, igual al corazon) mueve la rueda de escape (30 dientes)
que tiene justo arriba. Para que engranen, en todo momento el diente del pinon
que mira hacia arriba tiene que caer en el hueco de la rueda que mira hacia
abajo. Con pasos y giros en razon 3:1 y signo opuesto, alcanza con fijarlo en
un instante: el tic en que se traba (plano 4).

Escribe en los JSON:
  - 04_falla: fases de pinon y rueda, y que diente se parte (el que empuja).
  - 06_sacrificio: rueda, pinon roto y pinon fantasma (donde se monta el
    corazon) arrancan donde terminaron en el 04 tras desbocarse.
Usa gear_angle del motor: lo que se calcula aca es lo que se renderiza.
"""

import json
import sys
from pathlib import Path
from unittest import mock

EP = Path(__file__).resolve().parent
sys.path.insert(0, str(EP.parents[1] / "motor"))
for name in ("bpy", "bmesh", "mathutils"):
    sys.modules[name] = mock.MagicMock()
from plano import load_shot  # noqa: E402
from piezas import ctx  # noqa: E402
from piezas.mecanica import gear_angle  # noqa: E402

TEETH_P, TEETH_R, TEETH_G = 10, 30, 90
CONTACT_B = 135.0       # el pinon de la escape toca la rueda grande hacia arriba a la izquierda
TIP = 0.325           # centro del diente, en fraccion de paso (perfil de gear_mesh)
GAP = 0.825           # centro del hueco
UP, DOWN = 90.0, 270.0  # angulo local hacia arriba / abajo (ejes x90 + giro en z)

S4 = EP / "shots" / "04_falla.json"
S6 = EP / "shots" / "06_sacrificio.json"


def gears(cfg):
    return {g["name"]: g for g in cfg["engranajes"]["list"]}


def main():
    c4 = json.loads(S4.read_text(encoding="utf-8"))
    r4 = load_shot(S4)
    ctx.CFG = r4
    tick, stop = r4["engranajes"]["tick"], r4["engranajes"].get("stop")
    G = gears(r4)
    p, r = G["pinon_roto"], G["rueda_escape"]
    f_snap = p["salta"]["frame"]
    # fases con todo en cero: cuanto giro cada uno hasta el instante del tic trabado
    p0, r0 = dict(p, phase=0.0), dict(r, phase=0.0)
    p0.pop("free", None)
    r0.pop("free", None)
    ap = gear_angle(p0, f_snap, tick, stop)
    ar = gear_angle(r0, f_snap, tick, stop)
    k = p["salta"]["tooth"]
    php = UP - 360 * (k + TIP) / TEETH_P - ap          # el diente k arriba al partirse
    phr = DOWN - 360 * GAP / TEETH_R - ar              # un hueco de la rueda abajo
    print(f"04: pinon fase {php:.2f}, rueda fase {phr:.2f} (diente {k} arriba en el frame {f_snap})")
    # pinon de la escape (coaxial: misma fase) -> rueda grande, contacto a 135 grados.
    # Si el diente mas cercano al contacto esta delta grados corrido, la grande va
    # corrida -delta/9 al reves (girar el pinon +delta la gira -delta/9).
    pb0 = {k_: v for k_, v in G["rueda_escape_pinon"].items() if k_ != "free"}
    big0 = {k_: v for k_, v in G["rueda_grande"].items() if k_ != "free"}
    a_pb = gear_angle(dict(pb0, phase=0.0), f_snap, tick, stop)
    a_big = gear_angle(dict(big0, phase=0.0), f_snap, tick, stop)
    tooth = 360 * TIP / TEETH_P + phr + a_pb
    delta = ((CONTACT_B - tooth + 18) % 36) - 18
    ph_big = CONTACT_B + 180 + delta / 9 - 360 * GAP / TEETH_G - a_big
    print(f"04: rueda grande fase {ph_big:.2f} (pinon de la escape corrido {delta:.2f})")
    for g in c4["engranajes"]["list"]:
        if g["name"] == "pinon_roto":
            g["phase"] = round(php, 3)
        if g["name"] in ("rueda_escape", "rueda_escape_pinon"):
            g["phase"] = round(phr, 3)
        if g["name"] == "rueda_grande":
            g["phase"] = round(ph_big, 3)
    S4.write_text(json.dumps(c4, ensure_ascii=False, indent=2), encoding="utf-8")

    # donde quedan al final del 04 (tras desbocarse)
    r4 = load_shot(S4)
    G = gears(r4)
    end = r4["frames"]
    fp = gear_angle(G["pinon_roto"], end, tick, stop)
    fr = gear_angle(G["rueda_escape"], end, tick, stop)
    fpb = gear_angle(G["rueda_escape_pinon"], end, tick, stop)
    fg = gear_angle(G["rueda_grande"], end, tick, stop)
    print(f"fin del 04: pinon {fp:.2f}, rueda {fr:.2f}, grande {fg:.2f}")
    final = {"rueda_escape": fr, "rueda_escape_pinon": fpb, "rueda_grande": fg,
             "pinon_roto": fp, "pinon_corazon": fp}

    c6 = json.loads(S6.read_text(encoding="utf-8"))
    r6 = load_shot(S6)
    ctx.CFG = r6
    t6, st6 = r6["engranajes"]["tick"], r6["engranajes"].get("stop")
    G6 = gears(r6)
    for g in c6["engranajes"]["list"]:
        name = g["name"]
        if name in final:
            base = gear_angle(dict(G6[name], phase=0.0), 1, t6, st6)
            g["phase"] = round(final[name] - base, 3)
    S6.write_text(json.dumps(c6, ensure_ascii=False, indent=2), encoding="utf-8")
    print("06: el tren arranca donde quedo")


if __name__ == "__main__":
    main()
