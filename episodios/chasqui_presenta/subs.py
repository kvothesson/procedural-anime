"""
subs.py - Subtitulos del corte desde las transcripciones REALES de chasqui
(las tomas de El relevo, ver voces.json). Es el subs.py de El relevo con el
bloque en el tercio de abajo del cuadro horizontal.

    python episodios/chasqui_presenta/subs.py    # -> shots/subs.json (lo quema montaje.py)
    python episodios/chasqui_presenta/subs.py episodios/chasqui_presenta_en   # otra version

El texto no se corrige: solo se limpian espacios sobrantes y puntuacion duplicada.
Ningun bloque pasa del final de Tokio (o de "subs_fin_s" en voces.json, si una toma
termina mas tarde): en los tambos, abajo van las tarjetas. Las etiquetas de cada
bloque salen de "etiquetas" en voces.json (en espanol si no esta).
"""

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE
_spec = importlib.util.spec_from_file_location("subs_relevo", HERE.parent / "chasqui_relevo" / "subs.py")
rel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rel)
sys.path.insert(0, str(HERE.parents[1] / "motor"))
from plano import load_shot  # noqa: E402

# el color sigue a la luz, no al idioma: la ida sale de los Andes en hielo y la
# traduccion la vuelve violeta; la vuelta llega violeta a Tokio y sale en hielo
HIELO, VIOLETA = rel.COLOR["es"], rel.COLOR["ja"]
COLORES = {"ida": (HIELO, VIOLETA), "vuelta": (VIOLETA, HIELO)}
NAME = dict(rel.NAME, en="EN")
ETIQUETAS = {"orig": "{src} · ORIGINAL", "vivo": "{tgt} · CHASQUI, EN VIVO", "font": "mono"}

# donde va el bloque: y = etiqueta del original, el resto cuelga de ahi. Un short lo
# pisa con "subs_layout" en voces.json (zona segura: YouTube tapa abajo y a la derecha)
LAYOUT = {"x": 0.5, "y": 0.70, "gap": (0.025, 0.105, 0.13), "size": 42, "tag": 24, "max_w": 0.8}


def block(vdir, take, at, src, tgt, et, colors, L):
    ev = json.loads((vdir / take / "eventos.json").read_text(encoding="utf-8"))
    src_r = rel.reveal(ev["deltas"], "input", at)
    tgt_r = rel.reveal(ev["deltas"], "output", at)
    tag = {"font": et["font"], "size": L["tag"], "color": rel.MUTED, "outline": 5, "tracking": 3}
    txt = {"font": "texto", "size": L["size"], "outline": 7, "glow": 0.35, "max_w": L["max_w"]}
    X, Y, GAP = L["x"], L["y"], L["gap"]
    return {"t0": min(src_r[0][0], tgt_r[0][0]) - 0.15, "t1": max(src_r[-1][0], tgt_r[-1][0]) + 2.4,
            "fade_s": 0.3, "items": [
        dict(tag, text=et["orig"].format(src=NAME[src], tgt=NAME[tgt]), pos=[X, Y]),
        dict(txt, color=colors[0], pos=[X, Y + GAP[0]], reveal=src_r),
        dict(tag, text=et["vivo"].format(src=NAME[src], tgt=NAME[tgt]), pos=[X, Y + GAP[1]], **{"from": tgt_r[0][0]}),
        dict(txt, color=colors[1], pos=[X, Y + GAP[2]], reveal=tgt_r),
    ]}


def tambos_start():
    tl = json.loads((ROOT / "shots" / "timeline.json").read_text(encoding="utf-8"))
    t = 0.0
    for s in tl["shots"]:
        if s == "05_tambos":
            return t
        t += load_shot(ROOT / "shots" / f"{s}.json")["frames"] / tl["fps_unique"]


def main():
    v = json.loads((ROOT / "voces.json").read_text(encoding="utf-8"))
    vdir = (ROOT / v["dir"]).resolve()
    et = dict(ETIQUETAS, **v.get("etiquetas", {}))
    L = dict(LAYOUT, **v.get("subs_layout", {}))
    blocks = [block(vdir, v[k]["take"], v[k]["at"], v[k]["src"], v[k]["tgt"], et, COLORES[k], L) for k in ("ida", "vuelta")]
    end = v.get("subs_fin_s", tambos_start() - 0.1)
    for b in blocks:
        b["t1"] = min(b["t1"], end)
    dst = ROOT / "shots" / "subs.json"
    dst.write_text(json.dumps(blocks, ensure_ascii=False, indent=1), encoding="utf-8")
    for b in blocks:
        print(f"{b['t0']:.2f}-{b['t1']:.2f}s  {b['items'][1]['reveal'][-1][1]}  ->  {b['items'][3]['reveal'][-1][1]}")
    print(f"-> {dst}")


if __name__ == "__main__":
    main()
