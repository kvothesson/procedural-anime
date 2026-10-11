"""El Obelisco con reflectores, anillos holograficos y el cristal hexagonal."""

import math
import random

import bpy
import bmesh

from . import ctx
from .base import box_mesh, lin, link, linearize
from .materiales import mat_flat, mat_neon, mat_toon


def build_obelisco(e, colls):
    """Obelisco: tronco piramidal + punta. Reflectores desde la base (los
    reales existen). Anillos holograficos de arcos que giran. Arriba, el
    cristal hexagonal: lo unico que sobrevive al apagon."""
    x, y = e["at"]
    H, tip = e["height"], e["tip"]
    b, t = e["base"] / 2, e["top"] / 2
    mesh = bpy.data.meshes.new("obelisco")
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in [(-b, -b, 0), (b, -b, 0), (b, b, 0), (-b, b, 0),
                                    (-t, -t, H), (t, -t, H), (t, t, H), (-t, t, H),
                                    (0, 0, H + tip)]]
    for f in [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (3, 2, 1, 0),
              (4, 5, 8), (5, 6, 8), (6, 7, 8), (7, 4, 8)]:
        bm.faces.new([vs[i] for i in f])
    bm.to_mesh(mesh)
    bm.free()
    ob = bpy.data.objects.new("obelisco", mesh)
    ob.location = (x, y, 0)
    gl = e.get("glow", {})
    c = e["crystal"]
    glows = [{"kind": "point", "at": (x, y, H + tip + c["gap"]), "color": c["color"],
              "strength": gl.get("crystal_strength", 1.6), "falloff": gl.get("crystal_falloff", 14.0),
              "prop": "glow_crystal"}]
    for i, ring in enumerate(e["rings"]):
        glows.append({"kind": "ring", "at": (x, y, ring["z"] + ring.get("thick", 0.35) / 2),
                      "r": ring["r"], "color": ring["color"],
                      "strength": gl.get("ring_strength", 0.9), "falloff": gl.get("ring_falloff", 5.0),
                      "prop": f"glow_ring{i}"})
    ob.data.materials.append(mat_toon("obelisco_m", e["color"], glows=glows))
    for g in glows:
        ob[g["prop"]] = 1.0
    link(ob, colls["main"])
    # puerta en la base y ventanita cerca de la punta, en la cara a camara
    dark = mat_flat("obelisco_hueco", e.get("openings", "#1d1a2a"))
    taper = (b - t) / H
    for name, z0, w, h in (("puerta", 0.5, 1.6, 2.8), ("ventana", H - 5.5, 0.8, 1.3)):
        o = bpy.data.objects.new(name, box_mesh(name, w, 0.12, h))
        o.location = (x, y - (b - taper * (z0 + h / 2)) - 0.02, z0)
        o.data.materials.append(dark)
        link(o, colls["main"])
    for k, (dx, dy) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)]):
        sp = bpy.data.lights.new(f"reflector{k}", "SPOT")
        sp.color = lin(e["uplight"])[:3]
        sp.energy = e["uplight_energy"]
        sp.spot_size = math.radians(30)
        sp.use_shadow = False
        lo = bpy.data.objects.new(f"reflector{k}", sp)
        lo.location = (x + dx * (b + 6), y + dy * (b + 6), 0.5)
        lo["blackout_y"] = y
        link(lo, colls["lights"])
        # un spot mira a -Z: sin apuntarlo, ilumina el piso y no el Obelisco
        aim = bpy.data.objects.new(f"reflector{k}_mira", None)
        aim.location = (x, y, H * 0.45)
        link(aim, colls["lights"])
        tc = lo.constraints.new("TRACK_TO")
        tc.target = aim
        tc.track_axis = "TRACK_NEGATIVE_Z"
        tc.up_axis = "UP_Y"
    rnd = random.Random(5)
    frames = ctx.CFG["frames"]
    for i, ring in enumerate(e["rings"]):
        z, r, col = ring["z"], ring["r"], ring["color"]
        piv = bpy.data.objects.new(f"anillo{i}", None)
        piv.location = (x, y, z)
        link(piv, colls["neon"])
        mat = mat_neon(f"anillo{i}_m", col, 1.2)
        segs = ring.get("segs", 7)
        th = ring.get("thick", 0.35)
        for k in range(segs):
            a0 = 2 * math.pi * k / segs
            a1 = a0 + 2 * math.pi / segs * rnd.uniform(0.35, 0.75)
            am = bpy.data.meshes.new("arco")
            bm = bmesh.new()
            n = 10
            pts = []
            for j in range(n + 1):
                a = a0 + (a1 - a0) * j / n
                pts.append((bm.verts.new((r * math.cos(a), r * math.sin(a), 0)),
                            bm.verts.new((r * math.cos(a), r * math.sin(a), th))))
            for j in range(n):
                bm.faces.new([pts[j][0], pts[j + 1][0], pts[j + 1][1], pts[j][1]])
            bm.to_mesh(am)
            bm.free()
            arc = bpy.data.objects.new(f"arco{i}_{k}", am)
            arc.data.materials.append(mat)
            arc.parent = piv
            arc["blackout_y"] = y
            link(arc, colls["neon"])
        spin = ring.get("spin", 1) * math.radians(ring.get("deg_per_s", 20)) * frames / ctx.CFG["fps"]
        piv.rotation_euler = (0, 0, 0)
        piv.keyframe_insert("rotation_euler", frame=1)
        piv.rotation_euler = (0, 0, spin)
        piv.keyframe_insert("rotation_euler", frame=frames)
        linearize(piv)
    c = e["crystal"]
    bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=c["r"], depth=c["h"],
                                        location=(x, y, H + tip + c["gap"]))
    cr = bpy.context.active_object
    for cc in list(cr.users_collection):
        cc.objects.unlink(cr)
    cr.data.materials.append(mat_neon("cristal_m", c["color"], c.get("strength", 1.6), fog=False))
    cr["keep"] = True
    link(cr, colls["neon"])
    li = bpy.data.lights.new("cristal_luz", "POINT")
    li.color = lin(c["color"])[:3]
    li.energy = c["energy"]
    li.use_shadow = False
    lo = bpy.data.objects.new("cristal_luz", li)
    # Encima del cristal, la luz roza las caras del Obelisco y no las tine.
    # Corrida hacia camara (y negativo) le pega de frente a la cara visible.
    ox, oy, oz = c.get("light_offset", (0, 0, 0))
    lo.location = (x + ox, y + oy, H + tip + c["gap"] + oz)
    lo["keep"] = True
    link(lo, colls["lights"])
    # Light linking: con la luz puntual, la rampa toon partia el brillo del
    # cristal en capas sobre el Obelisco. Ahi manda el resplandor suave.
    excl = bpy.data.collections.new("cristal_receptores")
    excl.objects.link(ob)
    lo.light_linking.receiver_collection = excl
    # collection_objects no acepta nombre como clave: el Obelisco es el unico
    excl.collection_objects[0].light_linking.link_state = "EXCLUDE"
    return cr, lo
