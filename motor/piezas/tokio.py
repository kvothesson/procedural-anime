"""Tokio: callejon bajo las vias (gado-shita de Yurakucho), faroles de papel,
expendedoras, el viaducto con el tren que pasa y un farol hexagonal.

El callejon reusa la calle mojada y las hileras de piezas/ciudad.py; aca va
lo que lo hace Tokio y no Buenos Aires. Sin carteles con palabras: el sabor
sale del lugar (vias, faroles, maquinas), no de neon con texto.
"""

import math
import random

import bpy
import numpy as np
from mathutils import Vector

from . import ctx
from .base import box_mesh, key_power, lin, link, set_interp, tint_light
from .materiales import mat_neon, mat_toon


def _sphere(name, r, loc, sz=1.0, segs=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segs, ring_count=segs // 2, radius=r, location=loc)
    ob = bpy.context.active_object
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    ob.name = name
    ob.scale = (1, 1, sz)
    return ob


def build_chochin(e, colls):
    """Faroles de papel colgados de las fachadas en hileras: cuerpo emisivo
    (rojo o blanco), tapas oscuras, y la luz calida que tinen la vereda."""
    rnd = random.Random(e.get("seed", 3))
    cap_m = mat_toon("chochin_tapa", e.get("cap", "#1a1416"))
    mats = {c: mat_neon(f"chochin_{c}", c, e.get("strength", 1.1)) for c in e["colors"]}
    for row in e["rows"]:
        x, z = row["x"], row["z"]
        y = row["y"][0]
        while y < row["y"][1]:
            col = rnd.choice(e["colors"])
            r = row.get("r", 0.28) * rnd.uniform(0.9, 1.1)
            body = _sphere("chochin", r, (x, y, z), sz=1.35)
            body.data.materials.append(mats[col])
            link(body, colls["neon"])
            for dz in (-1, 1):
                cap = bpy.data.objects.new("chochin_tapa", box_mesh("ct", r * 1.1, r * 1.1, 0.07))
                cap.location = (x, y, z + dz * r * 1.3 - (0.07 if dz > 0 else 0))
                cap.data.materials.append(cap_m)
                link(cap, colls["main"])
            if rnd.random() < row.get("light_rate", 0.5):
                tint_light("chochin_luz", col, e.get("light", 90), (x - math.copysign(0.8, x), y, z - 0.4), colls)
            y += row.get("pitch", 1.6) * rnd.uniform(0.85, 1.2)


def build_expendedoras(e, colls):
    """Maquinas expendedoras: caja clara con el frente emisivo (botellas en
    hileras pintadas por bandas) y un charco de luz fria delante."""
    body_m = mat_toon("expendedora_m", e.get("body", "#d9dde6"))
    for i, m in enumerate(e["list"]):
        x, y = m["at"]
        side = 1 if x > 0 else -1
        ob = bpy.data.objects.new(f"expendedora{i}", box_mesh("exp", 0.75, 1.0, 1.85))
        ob.location = (x, y, 0)
        ob.data.materials.append(body_m)
        link(ob, colls["main"])
        col = m.get("color", "#cfe8ff")
        for k, (z0, h) in enumerate(((0.95, 0.75), (0.55, 0.3))):
            pn = bpy.data.objects.new(f"exp_panel{i}_{k}", box_mesh("pn", 0.04, 0.82, h))
            pn.location = (x - side * 0.39, y, z0)
            pn.data.materials.append(mat_neon(f"exp_panel{i}_{k}_m", col if k == 0 else m.get("accent", "#5ec5e2"),
                                              1.2 if k == 0 else 0.8))
            link(pn, colls["neon"])
        tint_light(f"exp_luz{i}", col, e.get("light", 260), (x - side * 1.4, y, 1.0), colls)


def build_viaducto(e, colls):
    """Viaducto de ladrillo que cruza el callejon (eje x) a la altura y, con
    pilares, tablero y baranda. Bajo los arcos, la luz calida de los bares.
    Encima, el tren con la franja de color y las ventanas encendidas."""
    y, z, L = e["y"], e["z"], e.get("length", 200)
    brick = mat_toon("viaducto_m", e.get("brick", "#5b3a36"))
    deck = bpy.data.objects.new("viaducto", box_mesh("vd", L, e.get("depth", 9), e.get("thick", 1.4)))
    deck.location = (0, y, z)
    deck.data.materials.append(brick)
    link(deck, colls["main"])
    rail = bpy.data.objects.new("baranda", box_mesh("vb", L, 0.25, 1.1))
    rail.location = (0, y - e.get("depth", 9) / 2 + 0.15, z + e.get("thick", 1.4))
    rail.data.materials.append(mat_toon("baranda_m", e.get("rail", "#2a2a36")))
    link(rail, colls["main"])
    span = e.get("span", 9.0)
    x = -L / 2
    while x <= L / 2:
        if abs(x) > e.get("gap", 4.0):          # el callejon pasa por el arco del medio
            p = bpy.data.objects.new("pilar", box_mesh("vp", 1.6, e.get("depth", 9), z))
            p.location = (x, y, 0)
            p.data.materials.append(brick)
            link(p, colls["main"])
        x += span
    # bajo los arcos: frentes de bares (calidos) que tinen el ladrillo
    warm = e.get("bars", "#ffb46a")
    for sgn in (-1, 1):
        for k in range(e.get("bars_count", 3)):
            bx = sgn * (span * (k + 0.5) + 0.8)
            fr = bpy.data.objects.new("bar", box_mesh("bf", span - 2.2, 0.1, 2.4))
            fr.location = (bx, y - e.get("depth", 9) / 2 - 0.02, 0.2)
            fr.data.materials.append(mat_neon("bar_m", warm, 0.65))
            link(fr, colls["neon"])
            tint_light("bar_luz", warm, e.get("bar_light", 300), (bx, y - e.get("depth", 9) / 2 - 1.6, 1.6), colls)
    tr = e.get("tren")
    if tr:
        _tren(tr, y, z + e.get("thick", 1.4), colls)


def _tren(t, y, z0, colls):
    """Coches que cruzan el viaducto: caja plateada, franja de linea, banda
    de ventanas emisivas. x(frame) lineal entre t["x"][0] y t["x"][1]."""
    body = mat_toon("tren_m", t.get("body", "#c3c8d2"))
    stripe = mat_toon("tren_franja", t.get("stripe", "#7ac143"))
    win = mat_neon("tren_ventanas", t.get("windows", "#fff2d8"), 1.1)
    piv = bpy.data.objects.new("tren", None)
    link(piv)
    cars, Lc, gap = t.get("cars", 4), t.get("car_len", 20.0), 0.8
    for k in range(cars):
        cx = -k * (Lc + gap)
        c = bpy.data.objects.new("coche", box_mesh("tc", Lc, 2.9, 3.6))
        c.location = (cx, 0, 0.4)
        c.data.materials.append(body)
        c.parent = piv
        link(c, colls["main"])
        s = bpy.data.objects.new("franja", box_mesh("tf", Lc + 0.02, 2.94, 0.3))
        s.location = (cx, 0, 1.3)
        s.data.materials.append(stripe)
        s.parent = piv
        link(s, colls["main"])
        w = bpy.data.objects.new("ventanas", box_mesh("tw", Lc - 1.0, 2.96, 0.9))
        w.location = (cx, 0, 2.0)
        w.data.materials.append(win)
        w.parent = piv
        link(w, colls["neon"])
    f0, f1 = t["frames"]
    piv.location = (t["x"][0], y, z0)
    piv.keyframe_insert("location", frame=f0)
    piv.location = (t["x"][1], y, z0)
    piv.keyframe_insert("location", frame=f1)
    set_interp(piv, "LINEAR")
    li = bpy.data.lights.new("tren_luz", "POINT")
    li.color = lin(t.get("windows", "#fff2d8"))[:3]
    li.energy = t.get("light", 1500)
    li.use_shadow = False
    lo = bpy.data.objects.new("tren_luz", li)
    lo.parent = piv
    lo.location = (-Lc, -3, 1.0)
    link(lo, colls["lights"])


def build_farol_hex(e, colls):
    """Farol hexagonal colgado sobre el callejon: donde aterriza el mensaje y
    de donde sale la respuesta. Un prisma por color, visible segun 'colors'
    [[frame, color], ...]; su brillo sigue 'power' [[frame, valor], ...] o la
    envolvente de un wav (la voz real), si se da 'envelope'."""
    from .andes import hex_prism
    at = Vector(e["at"])
    r, h = e.get("r", 0.42), e.get("h", 0.7)
    frames = ctx.CFG["frames"]
    hold = bpy.data.objects.new("farol_soporte", box_mesh("fs", 0.06, 0.06, e.get("hang", 2.5)))
    hold.location = at + Vector((0, 0, h * 0.5))
    hold.data.materials.append(mat_toon("farol_soporte_m", "#1a1830"))
    link(hold, colls["main"])
    pw = _envelope(e.get("envelope"), frames) if e.get("envelope") else None
    keys = e.get("power", [[1, 1.0]])
    changes = e["colors"]
    objs = []
    for i, (f_on, col) in enumerate(changes):
        f_off = changes[i + 1][0] if i + 1 < len(changes) else frames + 1
        hx = hex_prism(f"farol_hex{i}", r, h)
        hx.location = at
        # el farol mira a camara: gira con el plano
        hx.rotation_euler.z = math.radians(e.get("yaw", 0))
        hx.data.materials.append(mat_neon(f"farol_hex{i}_m", col, e.get("strength", 2.0), fog=False))
        hx["keep"] = True
        link(hx, colls["neon"])
        li = bpy.data.lights.new(f"farol_luz{i}", "POINT")
        li.color = lin(col)[:3]
        li.use_shadow = False
        lo = bpy.data.objects.new(f"farol_luz{i}", li)
        lo.location = at + Vector((0, -0.8, -0.3))
        link(lo, colls["lights"])
        for f in range(1, frames + 1):
            vis = f_on <= f < f_off
            v = float(np.interp(f, *zip(*keys))) if not pw else pw[f - 1]
            hx.hide_render = not vis
            hx.keyframe_insert("hide_render", frame=f)
            key_power(hx, f, v)
            li.energy = e.get("light", 300) * v if vis else 0.0
            li.keyframe_insert("energy", frame=f)
        set_interp(hx, "CONSTANT")
        set_interp(li, "LINEAR")
        objs.append(hx)
    return objs


def _envelope(env, frames):
    """Brillo por frame desde la envolvente RMS de un wav (24/48 kHz mono o
    estereo): base + gain * rms normalizado. offset_s = segundo del wav que
    cae en el frame 1."""
    import wave
    from pathlib import Path
    path = Path(env["wav"])
    if not path.is_absolute():
        path = Path(ctx.CFG["_ep_dir"]) / path if ctx.CFG.get("_ep_dir") else path
    with wave.open(str(path), "rb") as w:
        sr, ch = w.getframerate(), w.getnchannels()
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    fps = ctx.CFG["fps"]
    out = []
    for f in range(1, frames + 1):
        t0 = env.get("offset_s", 0.0) + (f - 1) / fps
        i0, i1 = int(t0 * sr), int((t0 + 1 / fps) * sr)
        seg = a[max(0, i0):max(0, i1)]
        out.append(float(np.sqrt((seg ** 2).mean())) if len(seg) else 0.0)
    peak = max(out) or 1.0
    return [env.get("base", 0.7) + env.get("gain", 1.2) * v / peak for v in out]
