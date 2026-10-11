"""Colectivo porteno flotante."""

import bpy
import bmesh
import math

from .base import bm_box, lin, link, linearize, text
from .materiales import mat_flat, mat_neon, mat_toon


def build_colectivo(e, colls):
    """Colectivo porteño flotante. Un solo objeto (varios slots de material)
    para que la copia del reflejo herede la animacion; luces y numero van
    emparentados. Largo sobre y, el frente mira hacia donde viaja (-y)."""
    L, Wd = e["length"], e["width"]
    mesh = bpy.data.meshes.new("colectivo")
    bm = bmesh.new()
    BODY, CREAM, STRIPE, GLASS, PAD, DARK = range(6)
    bm_box(bm, 0, 0, 0.0, Wd, L, 1.25, BODY)                       # pollera
    bm_box(bm, 0, 0, 1.0, Wd + 0.04, L + 0.04, 0.16, STRIPE)        # franja
    bm_box(bm, 0, 0.15, 1.25, Wd - 0.06, L - 0.9, 1.05, GLASS)     # banda de ventanas
    y = -L / 2 + 0.9
    while y < L / 2 - 0.4:                                          # parantes
        bm_box(bm, 0, y, 1.25, Wd + 0.02, 0.16, 1.05, CREAM)
        y += e.get("window_pitch", 1.45)
    bm_box(bm, 0, -L / 2 + 0.25, 1.25, Wd - 0.1, 0.5, 1.05, GLASS)  # parabrisas
    bm_box(bm, 0, 0, 2.3, Wd, L, 0.3, CREAM)                        # techo
    bm_box(bm, 0, 0.4, 2.6, Wd * 0.75, L * 0.7, 0.22, CREAM)        # domo
    bm_box(bm, 0, -L / 2 - 0.02, 2.0, Wd * 0.7, 0.08, 0.3, DARK)    # cartel de destino
    for py in (-L * 0.32, L * 0.32):                                # patines antigravedad
        for px in (-Wd * 0.28, Wd * 0.28):
            bm_box(bm, px, py, -0.18, 0.7, 1.8, 0.14, PAD)
    bm.to_mesh(mesh)
    bm.free()
    bus = bpy.data.objects.new("colectivo", mesh)
    for name, col, kind in (("bondi_rojo", e["body"], "toon"), ("bondi_crema", e["cream"], "toon"),
                            ("bondi_franja", e["stripe"], "toon"),
                            ("bondi_vidrio", e["interior"], "glass"), ("bondi_patin", e["pad"], "neon"),
                            ("bondi_oscuro", "#141226", "flat")):
        if kind == "toon":
            m = mat_toon(name, col)
        elif kind == "neon":
            m = mat_neon(name, col, 0.9)
        elif kind == "glass":
            # interior iluminado: emisivo pero tenue, o la banda sale blanca plana
            m = mat_neon(name, col, e.get("interior_strength", 0.45))
        else:
            m = mat_flat(name, col)
        bus.data.materials.append(m)
    link(bus, colls["main"])
    # numero de linea al costado que mira a camara. El texto nace mirando a -y;
    # girarlo +90 en z lo lleva a -x pero leido al reves: va side*90.
    side = -1 if e.get("number_side", "-x") == "-x" else 1
    num = text("bondi_num", e["number"], e.get("number_size", 0.75), mat_toon("bondi_num_m", e["number_color"]),
                (side * (Wd / 2 + 0.03), L * 0.18, 0.62), (math.pi / 2, 0, side * math.pi / 2), colls["main"])
    num.parent = bus
    dest = text("bondi_dest", e.get("destination", "404"), 0.22, mat_neon("bondi_dest_m", "#ffb03a", 1.2),
                 (0, -L / 2 - 0.08, 2.15), (math.pi / 2, 0, 0), colls["neon"])
    dest.parent = bus
    # luz cian bajo el colectivo (tine el asfalto) y calida adentro
    for nm, col, en, z in (("bondi_luz_patin", e["pad"], e.get("pad_light", 2500), -0.4),
                           ("bondi_luz_int", e["interior"], e.get("interior_light", 400), 1.8)):
        li = bpy.data.lights.new(nm, "POINT")
        li.color = lin(col)[:3]
        li.energy = en
        li.use_shadow = False
        li.shadow_soft_size = 2.0
        lo = bpy.data.objects.new(nm, li)
        lo.location = (0, 0, z)
        lo.parent = bus
        link(lo, colls["lights"])
    # recorrido: claves lineales; flota con un vaiven chico
    x, z = e["lane_x"], e["hover"]
    for f, yy in e["path"]:
        bus.location = (x, yy, z)
        bus.keyframe_insert("location", frame=f)
    linearize(bus)
    return bus
