"""Eventos animados: apagon en cascada, reencendido y la Luz Mala."""

import math
import random

import bpy

from . import ctx
from .base import key_power, lin, link, set_interp
from .materiales import mat_neon


def apply_blackout(bo, colls, crystal):
    """Apagon en cascada: cada objeto se apaga en un frame que depende de su
    distancia al origen del apagon (y). Antes, a veces, un parpadeo. Todo
    CONSTANTE: la luz no se desvanece, se corta."""
    rnd = random.Random(bo.get("seed", 404))
    f0, speed, y0 = bo["start"], bo["m_per_frame"], bo["origin_y"]

    def off_frame(ob):
        yy = ob.get("blackout_y", ob.matrix_world.translation.y)
        return int(f0 + max(0.0, y0 - yy) / speed + rnd.uniform(0, bo.get("jitter", 3)))

    if bo.get("mode") == "on":
        return apply_reignite(bo, colls, crystal, rnd, off_frame)

    targets = list(colls["neon"].objects) + list(colls["veil"].objects) + \
        [o for o in colls["main"].objects if o.type == "MESH"]
    for ob in targets:
        if ob.get("keep") or ob.name.startswith("velo") or ob.type == "EMPTY":
            continue
        f = off_frame(ob)
        key_power(ob, 1, 1.0)
        if rnd.random() < bo.get("flicker", 0.6) and f > 6:
            key_power(ob, f - 4, 0.0)
            key_power(ob, f - 3, 1.0)
            if rnd.random() < 0.5:
                key_power(ob, f - 2, 0.15)
                key_power(ob, f - 1, 1.0)
        key_power(ob, f, 0.0)
        set_interp(ob, "CONSTANT")
    for lo in colls["lights"].objects:
        if lo.get("keep") or lo.type != "LIGHT" or lo.data.type == "SUN":
            continue
        e0 = lo.data.energy
        lo.data.keyframe_insert("energy", frame=1)
        lo.data.energy = 0.0
        lo.data.keyframe_insert("energy", frame=off_frame(lo))
        lo.data.energy = e0
        set_interp(lo.data, "CONSTANT")
    # la luna queda, pero mas tenue: el negro tiene que leerse como negro
    for lo in colls["lights"].objects:
        if lo.type == "LIGHT" and lo.data.type == "SUN":
            e0 = lo.data.energy
            lo.data.keyframe_insert("energy", frame=f0 + bo.get("sky_delay", 6))
            lo.data.energy = e0 * bo.get("moon_after", 0.35)
            lo.data.keyframe_insert("energy", frame=bo["dark_from"])
            lo.data.energy = e0
    world = bpy.context.scene.world
    amb = world.node_tree.nodes[world["amb"]].inputs["Strength"]
    a0 = amb.default_value
    amb.keyframe_insert("default_value", frame=f0 + bo.get("sky_delay", 6))
    amb.default_value = a0 * bo.get("ambient_after", 0.25)
    amb.keyframe_insert("default_value", frame=bo["dark_from"])
    amb.default_value = a0
    ramp = world.node_tree.nodes[world["ramp"]]
    el = ramp.color_ramp.elements[0]
    el.keyframe_insert("color", frame=f0 + bo.get("sky_delay", 6))
    el.color = lin(bo["sky_dark"])
    el.keyframe_insert("color", frame=bo["dark_from"])
    # cristal: solo si la escena tiene Obelisco
    if crystal:
        cr, cl = crystal
        base_e = cl.data.energy
        for f in range(1, ctx.CFG["frames"] + 1):
            if f < bo["dark_from"]:
                pw = 1.0
            else:
                ph = (f - bo["dark_from"]) / bo["beat_frames"]
                pw = 0.25 + 1.6 * max(0.0, math.sin(math.pi * (ph % 1.0))) ** 3 if ph < bo["beats"] else 0.25
            key_power(cr, f, pw)
            cl.data.energy = base_e * pw
            cl.data.keyframe_insert("energy", frame=f)
            _key_glow("glow_crystal", f, pw)
    obel = bpy.data.objects.get("obelisco")
    if obel:
        for k in [p for p in obel.keys() if p.startswith("glow_ring")]:
            _key_glow(k, 1, 1.0)
            _key_glow(k, off_frame(obel), 0.0)
        set_interp(obel, "CONSTANT")


def _key_glow(prop, frame, value):
    obel = bpy.data.objects.get("obelisco")
    if obel and prop in obel:
        obel[prop] = value
        obel.keyframe_insert(f'["{prop}"]', frame=frame)


def apply_reignite(bo, colls, crystal, rnd, on_frame):
    """El apagon al reves: todo arranca en 0 y se enciende en cascada desde
    el origen hacia afuera. Distancia ABSOLUTA al origen (hacia los dos lados)."""
    f0, speed, y0 = bo["start"], bo["m_per_frame"], bo["origin_y"]

    def frame_for(ob):
        yy = ob.get("blackout_y", ob.matrix_world.translation.y)
        return int(f0 + abs(y0 - yy) / speed + rnd.uniform(0, bo.get("jitter", 3)))

    targets = list(colls["neon"].objects) + list(colls["veil"].objects) + \
        [o for o in colls["main"].objects if o.type == "MESH"]
    for ob in targets:
        if ob.get("keep") or ob.name.startswith("velo") or ob.type == "EMPTY":
            continue
        f = frame_for(ob)
        key_power(ob, 1, 0.0)
        if rnd.random() < bo.get("flicker", 0.6):
            key_power(ob, f - 3, 1.0)       # arranque de tubo: prende, duda, prende
            key_power(ob, f - 2, 0.0)
        key_power(ob, f, 1.0)
        set_interp(ob, "CONSTANT")
    for lo in colls["lights"].objects:
        if lo.get("keep") or lo.type != "LIGHT" or lo.data.type == "SUN":
            continue
        e0 = lo.data.energy
        lo.data.energy = 0.0
        lo.data.keyframe_insert("energy", frame=1)
        lo.data.energy = e0
        lo.data.keyframe_insert("energy", frame=frame_for(lo))
        set_interp(lo.data, "CONSTANT")
    # luna, ambiente y cielo: de oscuro a normal mientras corre la cascada
    l0, l1 = bo["light_from"], bo["light_to"]
    for lo in colls["lights"].objects:
        if lo.type == "LIGHT" and lo.data.type == "SUN":
            e0 = lo.data.energy
            lo.data.energy = e0 * bo.get("moon_after", 0.1)
            lo.data.keyframe_insert("energy", frame=l0)
            lo.data.energy = e0
            lo.data.keyframe_insert("energy", frame=l1)
    world = bpy.context.scene.world
    amb = world.node_tree.nodes[world["amb"]].inputs["Strength"]
    a0 = amb.default_value
    amb.default_value = a0 * bo.get("ambient_after", 0.25)
    amb.keyframe_insert("default_value", frame=l0)
    amb.default_value = a0
    amb.keyframe_insert("default_value", frame=l1)
    el = world.node_tree.nodes[world["ramp"]].color_ramp.elements[0]
    c0 = tuple(el.color)
    el.color = lin(bo["sky_dark"])
    el.keyframe_insert("color", frame=l0)
    el.color = c0
    el.keyframe_insert("color", frame=l1)
    # cristal (si hay Obelisco): sigue latiendo desde el plano anterior y se aquieta encendido
    if crystal:
        cr, cl = crystal
        base_e = cl.data.energy
        for f in range(1, ctx.CFG["frames"] + 1):
            ph = (f - 1 + bo.get("beat_phase", 0)) / bo["beat_frames"]
            if f < bo["steady_from"]:
                pw = 0.25 + 1.6 * max(0.0, math.sin(math.pi * (ph % 1.0))) ** 3
            else:
                pw = 1.0
            key_power(cr, f, pw)
            cl.data.energy = base_e * pw
            cl.data.keyframe_insert("energy", frame=f)
            _key_glow("glow_crystal", f, pw)
    obel = bpy.data.objects.get("obelisco")
    if obel:
        for k in [p for p in obel.keys() if p.startswith("glow_ring")]:
            _key_glow(k, 1, 0.0)
            _key_glow(k, frame_for(obel), 1.0)
        set_interp(obel, "CONSTANT")


def build_luz_mala(e, colls):
    """Destello verde a ras del horizonte. No hagas ping."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=e["r"], location=e["at"])
    sp = bpy.context.active_object
    for cc in list(sp.users_collection):
        cc.objects.unlink(sp)
    sp.data.materials.append(mat_neon("luzmala_m", e["color"], 2.0, fog=False))
    sp["keep"] = True
    link(sp, colls["neon"])
    li = bpy.data.lights.new("luzmala_luz", "POINT")
    li.color = lin(e["color"])[:3]
    li.use_shadow = False
    lo = bpy.data.objects.new("luzmala_luz", li)
    lo.location = e["at"]
    lo["keep"] = True
    link(lo, colls["lights"])
    on = set(e["frames_on"])
    for f in range(1, ctx.CFG["frames"] + 1):
        key_power(sp, f, 1.0 if f in on else 0.0)
        # apagada con emision 0 se ve como un punto negro: se oculta
        sp.hide_render = f not in on
        sp.keyframe_insert("hide_render", frame=f)
        li.energy = e["energy"] if f in on else 0.0
        li.keyframe_insert("energy", frame=f)
    set_interp(sp, "CONSTANT")
    set_interp(li, "CONSTANT")
