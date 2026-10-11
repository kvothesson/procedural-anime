"""Mecanica de relojeria: engranajes con dientes reales (sin textura) que
avanzan a golpes de escape, como un reloj, o giran continuo.

    "engranajes": {
        "color": "#b08a3e", "tick": {"bps": 1.0, "jump": 0.18, "offset": 0},
        "list": [{"at": [x, y, z], "axis": "y", "r": 1.2, "teeth": 40,
                  "depth": 0.08, "thick": 0.1, "spokes": 5, "step": 9,
                  "missing": [3, 4]}, ...]
    }

step: grados por tic (negativo = al reves). "spin" en vez de "step": grados por
segundo, continuo. "missing": dientes rotos (indices) -> el engranaje roto.
"stop": [f0, f1] el reloj trabado entre esos frames (en la raiz o por engranaje).
"salta": {"tooth": 3, "frame": 40, "vel": [0.6, -1.2, 2.0], "spin": [400, 200, 0]}:
el diente se suelta en ese frame y vuela (balistico, con giro); hasta ahi
viaja pegado al engranaje. Va solo: el engranaje lo tiene en "missing". La
trayectoria se calcula al armar: si otra pieza mueve el engranaje despues, el
diente no se entera (dar el "at" definitivo en el JSON).
"""

import math

import bpy
import bmesh

from . import ctx
from .base import action_fcurves, link
from .materiales import mat_toon

# perfil del diente (fraccion de paso, en la punta?). Centro del diente en
# 0.325 y del hueco en 0.825 (lo usan los calculos de fase). La punta ocupa
# 29 % del paso: entra hasta el fondo del hueco de una rueda de mas dientes
# (con 35 % la punta del pinon era mas ancha que ese fondo y habia que dejar
# holgura: se veian separados).
PERFIL = ((0.0, 0), (0.18, 1), (0.47, 1), (0.65, 0))

AXES = {"x": (0.0, math.pi / 2, 0.0), "y": (math.pi / 2, 0.0, 0.0), "z": (0.0, 0.0, 0.0)}


def ease_back(t, s=1.4):
    """Llega, se pasa y vuelve: el diente que traba en el escape."""
    t = min(1.0, max(0.0, t))
    t -= 1
    return 1 + t * t * ((s + 1) * t + s)


def tick_count(f, tick, stop=None):
    """Tics (con fraccion animada) transcurridos hasta el frame f. Un tic dura
    tick["jump"] segundos y despues queda quieto hasta el proximo.
    stop: [f0, f1] = el reloj trabado entre esos frames (no hay tics)."""
    fps = ctx.CFG["fps"]
    bps = tick.get("bps", 1.0)
    if stop:
        f0, f1 = stop
        f = f if f < f0 else (f0 if f < f1 else f - (f1 - f0))
    t = (f - 1) / fps * bps + tick.get("offset", 0.0)
    k = math.floor(t)
    return k + ease_back((t - k) / bps / tick.get("jump", 0.18))


def gear_mesh(name, r, teeth, depth, thick, r_in=None, spokes=0, hub=None, missing=()):
    """Engranaje plano (eje z, centrado en el origen): corona dentada
    trapezoidal + cubo + rayos. Los vertices caen justo en las esquinas de los
    dientes para que Line Art marque cada diente nitido."""
    r_in = r_in if r_in is not None else r * 0.78
    hub = hub if hub is not None else r * 0.16
    bm = bmesh.new()
    prof = []
    for k in range(teeth):
        broken = k in missing
        for ph, tip in PERFIL:
            a = 2 * math.pi * (k + ph) / teeth
            rr = r - depth + (0 if broken else depth * tip)
            prof.append((a, rr))
    n = len(prof)
    ot, ob, it, ib = [], [], [], []
    for a, rr in prof:
        c, s = math.cos(a), math.sin(a)
        ot.append(bm.verts.new((rr * c, rr * s, thick / 2)))
        ob.append(bm.verts.new((rr * c, rr * s, -thick / 2)))
        it.append(bm.verts.new((r_in * c, r_in * s, thick / 2)))
        ib.append(bm.verts.new((r_in * c, r_in * s, -thick / 2)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((ot[i], ot[j], it[j], it[i]))
        bm.faces.new((ob[i], ib[i], ib[j], ob[j]))
        bm.faces.new((ob[i], ob[j], ot[j], ot[i]))
        bm.faces.new((ib[i], it[i], it[j], ib[j]))
    # cubo
    bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=hub, radius2=hub,
                          depth=thick * 1.6)
    # rayos: cajas del cubo a la corona
    for k in range(spokes):
        a = 2 * math.pi * k / spokes
        w = r * 0.07
        L0, L1 = hub * 0.8, r_in * 1.02
        out = bmesh.ops.create_cube(bm, size=1.0)
        for v in out["verts"]:
            x = (v.co.x + 0.5) * (L1 - L0) + L0
            y = v.co.y * w
            z = v.co.z * thick * 0.8
            v.co = (x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a), z)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def key_rotation(ob, angle_fn, frames):
    """Giro sobre el eje propio (z local). Una clave por frame: la pose es
    funcion pura del frame."""
    base = ob.rotation_euler.copy()
    for f in range(1, frames + 1):
        ob.rotation_euler = base
        ob.rotation_euler.rotate_axis("Z", math.radians(angle_fn(f)))
        ob.keyframe_insert("rotation_euler", frame=f)
    if ob.animation_data and ob.animation_data.action:
        for fc in action_fcurves(ob.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


def gear_angle(g, f, tick, stop=None, free=True):
    """Angulo (grados, sobre z local) del engranaje g en el frame f. Funcion
    pura: la usan la escena y los calculos de fase de engrane (sin Blender).

    Ademas de "step"/"spin":
      "strain": {"from", "to", "amp", "hz"}  forcejeo: oscila sin avanzar
      "free":   {"frame", "spin", "tau"}     suelto: gira a "spin" grados/s y
                                             frena con constante tau (s)
    Dos engranajes que engranan llevan step, amp y spin en razon inversa a sus
    dientes y con signo opuesto: asi siguen engranados en todo momento."""
    fps = ctx.CFG["fps"]
    fr = g.get("free")
    if free and fr and f > fr["frame"]:
        a0 = gear_angle(g, fr["frame"], tick, stop, free=False)
        t = (f - fr["frame"]) / fps
        return a0 + fr["spin"] * fr["tau"] * (1 - math.exp(-t / fr["tau"]))
    a = g.get("phase", 0.0)
    if "spin" in g:
        a += g["spin"] * (f - 1) / fps
    elif g.get("step"):
        a += g["step"] * tick_count(f, tick, g.get("stop", stop))
    st = g.get("strain")
    if st and st["from"] <= f <= st["to"]:
        u = (f - st["from"]) / max(1, st["to"] - st["from"])
        a += st["amp"] * math.sin(2 * math.pi * st["hz"] * (f - st["from"]) / fps) * math.sin(math.pi * u)
    return a


def axle_mesh(name, r, z0, z1):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=r, radius2=r, depth=z1 - z0)
    for v in bm.verts:
        v.co.z += (z0 + z1) / 2
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def build_engranajes(e, colls):
    frames = ctx.CFG["frames"]
    tick = e.get("tick", {"bps": 1.0, "jump": 0.18})
    stop = e.get("stop")
    mats = {}
    out = {}
    for i, g in enumerate(e["list"]):
        color = g.get("color", e.get("color", "#b08a3e"))
        if color not in mats:
            mats[color] = mat_toon(f"engranaje_{color}", color)
        name = g.get("name", f"engranaje{i}")
        mesh = gear_mesh(name, g["r"], g.get("teeth", 24), g.get("depth", g["r"] * 0.08),
                         g.get("thick", g["r"] * 0.08), g.get("r_in"), g.get("spokes", 0),
                         g.get("hub"), set(g.get("missing", [])))
        mesh.materials.append(mats[color])
        ob = bpy.data.objects.new(name, mesh)
        ob.location = g["at"]
        # "rot": orientacion libre en grados (pisa "axis"); el giro va sobre z local
        ob.rotation_euler = [math.radians(a) for a in g["rot"]] if "rot" in g else AXES[g.get("axis", "y")]
        link(ob, colls["main"])
        if g.get("axle"):
            # eje fijo (no gira): sale del lado +z local "axle" metros
            ax = bpy.data.objects.new(name + "_eje", axle_mesh(name + "_eje", g.get("axle_r", 0.016),
                                                                 -g.get("thick", 0.05), g["axle"]))
            ax.data.materials.append(mats[color])
            ax.location = ob.location
            ax.rotation_euler = ob.rotation_euler
            link(ax, colls["main"])
        if g.get("ghost"):
            # engranaje invisible que solo lleva el giro (algo se le cuelga despues)
            ob.hide_render = True
            ob.visible_shadow = False
        if "spin" in g or g.get("step") or "free" in g or "strain" in g:
            key_rotation(ob, lambda f, g=g: gear_angle(g, f, tick, stop), frames)
        out[name] = ob
        if "salta" in g:
            _tooth_jump(ob, g, mats[color], colls, frames)
    return out


def tooth_mesh(name, g):
    """Un diente suelto, en coordenadas del engranaje (mismo perfil que la corona)."""
    k, n = g["salta"]["tooth"], g.get("teeth", 24)
    r = g["r"]
    depth = g.get("depth", r * 0.08)
    thick = g.get("thick", r * 0.08)
    pts = []
    for ph, tip in PERFIL:
        a = 2 * math.pi * (k + ph) / n
        rr = r - depth + depth * tip
        pts.append((rr * math.cos(a), rr * math.sin(a)))
    bm = bmesh.new()
    top = [bm.verts.new((x, y, thick / 2)) for x, y in pts]
    bot = [bm.verts.new((x, y, -thick / 2)) for x, y in pts]
    bm.faces.new(top)
    bm.faces.new(list(reversed(bot)))
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def _tooth_jump(gear, g, mat, colls, frames):
    from mathutils import Euler, Matrix, Vector
    j = g["salta"]
    mesh = tooth_mesh(gear.name + "_diente", g)
    mesh.materials.append(mat)
    tooth = bpy.data.objects.new(gear.name + "_diente", mesh)
    link(tooth, colls["main"])
    scene = bpy.context.scene
    f0 = j["frame"]
    scene.frame_set(f0)
    m0 = gear.matrix_world.copy()
    # gira sobre su propio centro, no sobre el eje del engranaje
    c0 = m0 @ (sum((v.co for v in mesh.vertices), Vector()) / len(mesh.vertices))
    vel = Vector(j.get("vel", (0.5, -1.0, 1.8)))
    spin = [math.radians(a) for a in j.get("spin", (360, 180, 0))]
    fps = ctx.CFG["fps"]
    for f in range(1, frames + 1):
        if f <= f0:
            scene.frame_set(f)
            m = gear.matrix_world.copy()
        else:
            t = (f - f0) / fps
            # cae hasta el piso ("floor", z de mundo) y queda ahi
            floor = j.get("floor", 0.03)
            land = None
            a, b, cz = -4.9, vel.z, c0.z - floor      # a t^2 + b t + cz = 0
            disc = b * b - 4 * a * cz
            if disc >= 0:
                land = (-b - math.sqrt(disc)) / (2 * a)
            t = min(t, land) if land and land > 0 else t
            loc = c0 + vel * t + Vector((0, 0, -4.9 * t * t))
            rot = Euler([a_ * t for a_ in spin]).to_matrix().to_4x4()
            m = Matrix.Translation(loc) @ rot @ Matrix.Translation(-c0) @ m0
        tooth.matrix_world = m
        tooth.keyframe_insert("location", frame=f)
        tooth.keyframe_insert("rotation_euler", frame=f)
        tooth.keyframe_insert("scale", frame=f)
    for fc in action_fcurves(tooth.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
