"""
subs.py - Subtitulos del corte desde las transcripciones REALES de chasqui.

    python episodios/chasqui_relevo/subs.py    # -> shots/subs.json (lo quema montaje.py)

Cada toma (voz/<toma>/eventos.json) trae los deltas de transcripcion con su
tiempo. Se escriben de a poco, como en la ventana de chasqui: el original
arriba, la traduccion abajo, cada uno con su etiqueta. Hielo = espanol,
violeta = japones (los mismos colores de la app). El texto no se corrige:
solo se limpian espacios sobrantes y puntuacion duplicada.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COLOR = {"es": "#5ec5e2", "ja": "#a98bf5"}
NAME = {"es": "ES", "ja": "JA"}
MUTED = "#8a97ab"


def clean(s):
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"(?<=[\u3000-\u9fff\uff00-\uffef])\s+|\s+(?=[\u3000-\u9fff\uff00-\uffef])", "", s)
    s = re.sub(r"。+", "。", s)
    return s


def reveal(deltas, kind, at):
    acc, out = "", []
    for d in deltas:
        if d["type"].endswith(f"{kind}_transcript.delta"):
            acc += d["text"]
            out.append([round(at + d["t"], 3), clean(acc)])
    return out


def block(take, at, src, tgt, y):
    ev = json.loads((ROOT / "voz" / take / "eventos.json").read_text(encoding="utf-8"))
    src_r = reveal(ev["deltas"], "input", at)
    tgt_r = reveal(ev["deltas"], "output", at)
    t0 = min(src_r[0][0], tgt_r[0][0]) - 0.15
    t1 = max(src_r[-1][0], tgt_r[-1][0]) + 2.4
    tag = {"font": "mono", "size": 26, "color": MUTED, "outline": 5, "tracking": 3}
    txt = {"font": "texto", "size": 46, "outline": 7, "glow": 0.35, "max_w": 0.86}
    return {"t0": t0, "t1": t1, "fade_s": 0.3, "items": [
        dict(tag, text=f"{NAME[src]} · ORIGINAL", pos=[0.5, y]),
        dict(txt, color=COLOR[src], pos=[0.5, y + 0.022], reveal=src_r),
        dict(tag, text=f"{NAME[tgt]} · CHASQUI, EN VIVO", pos=[0.5, y + 0.118], **{"from": tgt_r[0][0]}),
        dict(txt, color=COLOR[tgt], pos=[0.5, y + 0.140], reveal=tgt_r),
    ]}


def main():
    v = json.loads((ROOT / "voces.json").read_text(encoding="utf-8"))
    blocks = [block(v[k]["take"], v[k]["at"], v[k]["src"], v[k]["tgt"], 0.635) for k in ("ida", "vuelta")]
    dst = ROOT / "shots" / "subs.json"
    dst.write_text(json.dumps(blocks, ensure_ascii=False, indent=1), encoding="utf-8")
    for b in blocks:
        print(f"{b['t0']:.2f}-{b['t1']:.2f}s  {b['items'][1]['reveal'][-1][1]}  ->  {b['items'][3]['reveal'][-1][1]}")
    print(f"-> {dst}")


if __name__ == "__main__":
    main()
