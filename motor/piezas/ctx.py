"""Configuracion del plano que se esta armando. escena.py llama a configurar()
una vez, antes de construir nada; las piezas leen ctx.CFG, ctx.FOG, etc."""

import os

CFG = {}
FOG = {}
TOON = {}
FONT = ""
DRAFT = False


def configurar(cfg, draft=False):
    global CFG, FOG, TOON, FONT, DRAFT
    CFG = cfg
    FOG = dict(cfg.get("fog", {"color": "#1b2a4a", "dist": 80.0}))
    TOON = cfg.get("toon", {"steps": [[0.0, 0.22], [0.10, 0.55], [0.45, 1.0]]})
    # Fuente de los textos 3D: la del JSON ("font"), si no Bahnschrift de Windows y,
    # si no existe (Linux, macOS), la que trae Blender.
    win = "C:/Windows/Fonts/bahnschrift.ttf"
    FONT = cfg.get("font") or (win if os.path.exists(win) else "")
    DRAFT = draft
