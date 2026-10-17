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


def _load_raw(path):
    path = Path(path)
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if "extends" in cfg:
        base = _load_raw(path.parent / cfg.pop("extends"))
        for k in cfg.pop("drop", []):
            base.pop(k, None)
        cfg = merge(base, cfg)
    return cfg


def find_estilo(shot_path, name):
    """estilos/<name>.json del episodio (el JSON vive en <ep>/shots/ o en
    <ep>/render/ para las pruebas de render.py)."""
    src = Path(shot_path).resolve().parent.parent / "estilos" / f"{name}.json"
    if not src.exists():
        raise FileNotFoundError(f"No existe el estilo {src}")
    return json.loads(src.read_text(encoding="utf-8"))


def load_shot(path):
    """Plano resuelto: herencia (extends/drop) y despues el estilo.

    "estilo": "<nombre>" carga <ep>/estilos/<nombre>.json: el look entero
    (sky, fog, toon, lights, line, post, ...) separado de la geometria y la
    camara, para cambiarlo con una palabra. El estilo va debajo: lo que el
    plano dice gana. Sus "piezas" ({"catedral": {...}, ...}) se mezclan solo
    en las piezas que el plano ya tiene: un estilo da colores, no agrega
    objetos."""
    cfg = _load_raw(path)
    name = cfg.pop("estilo", None)
    if not name:
        return cfg
    est = dict(find_estilo(path, name))
    piezas = est.pop("piezas", {})
    est.pop("_desc", None)
    for k, v in piezas.items():
        if k in cfg:
            cfg[k] = merge(v, cfg[k]) if isinstance(cfg[k], dict) else cfg[k]
    cfg = merge(est, cfg)
    cfg["_estilo"] = name
    return cfg
