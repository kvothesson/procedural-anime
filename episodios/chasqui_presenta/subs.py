"""
subs.py - Subtitulos del corte desde las transcripciones REALES de chasqui
(las tomas de El relevo, ver voces.json). Es el subs.py de El relevo con el
bloque en el tercio de abajo del cuadro horizontal.

    python episodios/chasqui_presenta/subs.py    # -> shots/subs.json (lo quema montaje.py)

El texto no se corrige: solo se limpian espacios sobrantes y puntuacion duplicada.
Ningun bloque pasa del final de Tokio: en los tambos abajo van las tarjetas.
"""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("subs_relevo", ROOT.parent / "chasqui_relevo" / "subs.py")
rel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rel)

Y = 0.70            # etiqueta del original; el resto del bloque cuelga de aca
GAP = (0.025, 0.105, 0.13)


def block(vdir, take, at, src, tgt):
    ev = json.loads((vdir / take / "eventos.json").read_text(encoding="utf-8"))
    src_r = rel.reveal(ev["deltas"], "input", at)
    tgt_r = rel.reveal(ev["deltas"], "output", at)
    tag = {"font": "mono", "size": 24, "color": rel.MUTED, "outline": 5, "tracking": 3}
    txt = {"font": "texto", "size": 42, "outline": 7, "glow": 0.35, "max_w": 0.8}
    return {"t0": min(src_r[0][0], tgt_r[0][0]) - 0.15, "t1": max(src_r[-1][0], tgt_r[-1][0]) + 2.4,
            "fade_s": 0.3, "items": [
        dict(tag, text=f"{rel.NAME[src]} · ORIGINAL", pos=[0.5, Y]),
        dict(txt, color=rel.COLOR[src], pos=[0.5, Y + GAP[0]], reveal=src_r),
        dict(tag, text=f"{rel.NAME[tgt]} · CHASQUI, EN VIVO", pos=[0.5, Y + GAP[1]], **{"from": tgt_r[0][0]}),
        dict(txt, color=rel.COLOR[tgt], pos=[0.5, Y + GAP[2]], reveal=tgt_r),
    ]}


def tambos_start():
    tl = json.loads((ROOT / "shots" / "timeline.json").read_text(encoding="utf-8"))
    t = 0.0
    for s in tl["shots"]:
        if s == "05_tambos":
            return t
        t += json.loads((ROOT / "shots" / f"{s}.json").read_text(encoding="utf-8"))["frames"] / tl["fps_unique"]


def main():
    v = json.loads((ROOT / "voces.json").read_text(encoding="utf-8"))
    vdir = (ROOT / v["dir"]).resolve()
    blocks = [block(vdir, v[k]["take"], v[k]["at"], v[k]["src"], v[k]["tgt"]) for k in ("ida", "vuelta")]
    end = tambos_start() - 0.1
    for b in blocks:
        b["t1"] = min(b["t1"], end)
    dst = ROOT / "shots" / "subs.json"
    dst.write_text(json.dumps(blocks, ensure_ascii=False, indent=1), encoding="utf-8")
    for b in blocks:
        print(f"{b['t0']:.2f}-{b['t1']:.2f}s  {b['items'][1]['reveal'][-1][1]}  ->  {b['items'][3]['reveal'][-1][1]}")
    print(f"-> {dst}")


if __name__ == "__main__":
    main()
