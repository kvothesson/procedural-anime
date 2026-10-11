"""
plano.py - Carga de planos JSON con herencia. Python puro (sin bpy): lo usan
escena.py dentro de Blender, post.py, render.py y las bandas de sonido.

Un plano puede heredar de otro ("extends": "06_apagon.json", relativo al
archivo) y pisar solo lo que cambia. "drop" borra claves heredadas. Los dict
se mezclan en profundidad; las listas se reemplazan enteras.
"""

import json
from pathlib import Path


def merge(base, over):
    out = dict(base)
    for k, v in over.items():
        out[k] = merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def load_shot(path):
    path = Path(path)
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if "extends" in cfg:
        base = load_shot(path.parent / cfg.pop("extends"))
        for k in cfg.pop("drop", []):
            base.pop(k, None)
        cfg = merge(base, cfg)
    return cfg
