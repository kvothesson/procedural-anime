"""Viaje: un mensaje de luz que corre por una ruta y enciende las postas.

    "mensaje": {
        "keys": [[frame, s], ...],      # s = metros recorridos sobre la ruta
        "colors": [[0, "#5ec5e2"], [120.5, "#a98bf5"]],   # color segun s (tramos)
        "height": 1.1, "trail": 16, "radius": 0.16, "trail_radius": 0.05,
        "light": 220, "from_frame": 1,
        "points": [[x, y, z], ...]      # opcional; si no, la ruta de piezas/andes.py
    }
    "relevo": {"delay": 1, "flicker": 0.6}

La estela es una curva por tramo de color; lo visible se recorta con
bevel_factor_start/end (mapeo por longitud) en cada frame. La cabeza es una
esfera por color: se ve la del tramo en que esta. Todo con claves por frame,
funcion pura del frame.

relevo: todo objeto con la propiedad "relevo_s" se enciende (power 0 -> 1,
con arranque de tubo) cuando la cabeza pasa por su s. Las luces con
"relevo_s" siguen a su baliza.
"""

import math
import random

import bpy
import numpy as np
from mathutils import Vector

from . import ctx
from .base import key_power, lin, link, set_interp
from .materiales import mat_neon


class _Poly:
    def __init__(self, pts):
        self.pts = np.asarray(pts, float)
        d = np.linalg.norm(np.diff(self.pts, axis=0), axis=1)
        self.s = np.concatenate([[0.0], np.cumsum(d)])
        self.length = float(self.s[-1])

    def at(self, s):
        s = float(np.clip(s, 0, self.length))
        return Vector([float(np.interp(s, self.s, self.pts[:, k])) for k in range(3)])

    def segment(self, s0, s1):
        s0, s1 = max(0.0, s0), min(self.length, s1)
        inner = [tuple(p) for p, ss in zip(self.pts, self.s) if s0 < ss < s1]
        return [tuple(self.at(s0))] + inner + [tuple(self.at(s1))]


def arco_points(a):
    """Circulo maximo sobre la Tierra (piezas/espacio.py) de a["from"] a
    a["to"] ([lon, lat] en grados), levantado a["lift"] radios en el medio.
    Usa la rotacion real del objeto 'tierra' (armado antes que el mensaje)."""
    earth = bpy.data.objects["tierra"]
    C = earth.matrix_world.translation
    R = earth.dimensions.x / 2
    rot = earth.matrix_world.to_3x3().normalized()

    def local(lon, lat):
        lo, la = math.radians(lon), math.radians(lat)
        return Vector((-math.cos(lo) * math.cos(la), -math.sin(lo) * math.cos(la), math.sin(la)))

    u, v = rot @ local(*a["from"]), rot @ local(*a["to"])
    om = math.acos(max(-1.0, min(1.0, u.dot(v))))
    n = a.get("n", 240)
    base = a.get("base", 0.004)
    pts = []
    for k in range(n + 1):
        t = k / n
        d = (u * math.sin((1 - t) * om) + v * math.sin(t * om)) / math.sin(om)
        h = R * (1 + base + a.get("lift", 0.08) * math.sin(math.pi * t))
        pts.append(tuple(C + d.normalized() * h))
    return pts


def _poly(e):
    if e.get("arco"):
        return _Poly(arco_points(e["arco"]))
    if e.get("points"):
        return _Poly(e["points"])
    from .andes import ruta
    return _Poly(ruta().pts)


def head_s(e, f):
    fs, ss = zip(*e["keys"])
    return float(np.interp(f, fs, ss))


def _curve(name, pts, r, mat, coll):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = r
    cu.bevel_resolution = 2
    cu.use_fill_caps = True
    cu.bevel_factor_mapping_start = "SPLINE"
    cu.bevel_factor_mapping_end = "SPLINE"
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for k, q in enumerate(pts):
        sp.points[k].co = (q[0], q[1], q[2], 1)
    ob = bpy.data.objects.new(name, cu)
    ob.data.materials.append(mat)
    link(ob, coll)
    return ob


def build_mensaje(e, colls):
    """Un mensaje, o una lista de mensajes (ida y vuelta en el mismo plano)."""
    if isinstance(e, list):
        for one in e:
            _build_one(one, colls)
        return
    _build_one(e, colls)


def _build_one(e, colls):
    P = _poly(e)
    if e.pop("frac", False):
        # claves y estela en fraccion del recorrido (el largo del arco no se sabe de antemano)
        e["keys"] = [[f, v * P.length] for f, v in e["keys"]]
        e["colors"] = [[v * P.length, c] for v, c in e["colors"]]
        e["trail"] = e.get("trail", 0.2) * P.length
    lift = Vector((0, 0, e.get("height", 1.1)))
    frames = ctx.CFG["frames"]
    trail = e.get("trail", 16.0)
    bounds = [c[0] for c in e["colors"]] + [P.length]
    pieces = []
    for i, (s0, col) in enumerate(e["colors"]):
        s1 = bounds[i + 1]
        if s1 <= s0:
            continue
        pts = [tuple(Vector(p) + lift) for p in P.segment(s0, s1)]
        mat = mat_neon(f"estela{i}_m", col, e.get("strength", 2.2), fog=False)
        cur = _curve(f"estela{i}", pts, e.get("trail_radius", 0.05), mat, colls["neon"])
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=e.get("radius", 0.16))
        hd = bpy.context.active_object
        for c in list(hd.users_collection):
            c.objects.unlink(hd)
        hd.name = f"cabeza{i}"
        hd.data.materials.append(mat_neon(f"cabeza{i}_m", col, e.get("head_strength", 3.0), fog=False))
        hd["keep"] = True
        cur["keep"] = True
        link(hd, colls["neon"])
        pieces.append((s0, s1, col, cur, hd))
    li = bpy.data.lights.new("mensaje_luz", "POINT")
    li.energy = e.get("light", 220)
    li.use_shadow = False
    li.shadow_soft_size = 0.3
    lo = bpy.data.objects.new("mensaje_luz", li)
    lo["keep"] = True
    link(lo, colls["lights"])
    born = e.get("from_frame", 1)      # antes de este frame el mensaje no existe
    dies = e.get("to_frame", 10 ** 6)  # desde este frame ya llego: no se ve
    for f in range(1, frames + 1):
        s = head_s(e, f)
        pos = P.at(s) + lift
        for s0, s1, col, cur, hd in pieces:
            a, b = max(s0, s - trail), min(s1, s)
            vis = b > a + 1e-3 and born <= f < dies
            span = s1 - s0
            cu = cur.data
            cu.bevel_factor_start = (a - s0) / span if vis else 0.0
            cu.bevel_factor_end = (b - s0) / span if vis else 0.0
            cu.keyframe_insert("bevel_factor_start", frame=f)
            cu.keyframe_insert("bevel_factor_end", frame=f)
            cur.hide_render = not vis
            cur.keyframe_insert("hide_render", frame=f)
            here = (s0 <= s < s1 or (s >= s1 and s1 == P.length and s0 <= s)) and born <= f < dies
            hd.hide_render = not here
            hd.keyframe_insert("hide_render", frame=f)
            hd.location = pos
            hd.keyframe_insert("location", frame=f)
            if here:
                li.color = lin(col)[:3]
                li.keyframe_insert("color", frame=f)
        lo.location = pos + Vector((0, 0, 0.4))
        lo.keyframe_insert("location", frame=f)
        # la luz existe solo mientras se ve la cabeza (si no, alumbraba la
        # apacheta antes de que el mensaje saliera y rompia el empalme del loop)
        li.energy = e.get("light", 220) if born <= f < dies else 0.0
        li.keyframe_insert("energy", frame=f)
    for s0, s1, col, cur, hd in pieces:
        set_interp(cur, "CONSTANT")
        set_interp(cur.data, "LINEAR")
        set_interp(hd, "LINEAR")
    set_interp(lo, "LINEAR")
    set_interp(li, "CONSTANT")
    if e.get("arco", {}).get("spin"):
        _spin_globe(e, P, pieces)
    if "relevo" in ctx.CFG:
        _relevo(e, ctx.CFG["relevo"])
    if ctx.CFG.get("camera", {}).get("follow"):
        _follow_camera(e, P, ctx.CFG["camera"])


def _spin_globe(e, P, pieces):
    """Camara quieta, globo que gira: la Tierra, la atmosfera y el mensaje
    cuelgan de un pivote que rota para que la cabeza pase siempre por +Z
    (arriba del globo) avanzando hacia +Y. Asi el arriba de la imagen es
    siempre el cielo (con la camara orbitando, el Track To usa +Z del mundo y
    el cuadro salia girado 90 grados) y el lado de noche, que se calcula en
    el mundo, queda fijo respecto de la camara."""
    earth = bpy.data.objects["tierra"]
    C = earth.matrix_world.translation.copy()
    piv = bpy.data.objects.new("globo_pivote", None)
    piv.location = C
    link(piv)
    piv.rotation_mode = "QUATERNION"
    kids = [earth] + [o for o in (bpy.data.objects.get("atmosfera"),) if o]
    for s0, s1, col, cur, hd in pieces:
        kids += [cur, hd]
    for ob in kids:
        mw = ob.matrix_world.copy()
        ob.parent = piv
        ob.matrix_parent_inverse = piv.matrix_world.inverted()
        ob.matrix_world = mw
    from mathutils import Matrix
    B = Matrix(((0, -1, 0), (1, 0, 0), (0, 0, 1)))     # columnas: t0=+Y, b0=-X, n0=+Z
    for f in range(1, ctx.CFG["frames"] + 1):
        s = head_s(e, f)
        n = (P.at(s) - C).normalized()
        t = P.at(s + 0.5) - P.at(s - 0.5)
        t = (t - n * t.dot(n)).normalized()
        b = n.cross(t)
        A = Matrix((t, b, n)).transposed()
        piv.rotation_quaternion = (B @ A.transposed()).to_quaternion()
        piv.keyframe_insert("rotation_quaternion", frame=f)


def _follow_camera(e, P, cam):
    """Camara que acompana al mensaje: 'behind' metros atras, 'side' al costado,
    'up' de altura, mirando 'ahead' metros adelante. Escribe cam["keys"]
    (build_camera corre despues de las piezas)."""
    fo = cam["follow"]
    keys = []
    frames = ctx.CFG["frames"]
    # "center": arriba es la vertical del globo (orbita), si no +z del mundo
    center = Vector(fo["center"]) if fo.get("center") else None
    for f in list(range(1, frames + 1, fo.get("every", 3))) + [frames]:
        s = head_s(e, f)
        a, b = P.at(s - 0.8), P.at(s + 0.8)
        here = P.at(s)
        up = (here - center).normalized() if center else Vector((0, 0, 1))
        d = (b - a)
        d -= up * d.dot(up)
        d.normalize()
        right = d.cross(up)
        back = P.at(s - fo.get("behind", 7.0))
        if center:
            back = here - d * fo.get("behind", 7.0)
        pos = back + right * fo.get("side", 2.5) + up * fo.get("up", 2.4)
        ahead = P.at(s + fo.get("ahead", 25.0)) if not center else here + d * fo.get("ahead", 25.0)
        aim = ahead + up * fo.get("aim_up", 2.0)
        keys.append({"frame": f, "pos": tuple(pos), "aim": tuple(aim)})
    cam["keys"] = keys
    cam["ease"] = False


def _relevo(e, rv):
    """Enciende lo que tiene relevo_s cuando la cabeza pasa. Lo que ya quedo
    atras al empezar el plano arranca encendido."""
    rnd = random.Random(rv.get("seed", 8))
    frames = ctx.CFG["frames"]
    passed = {}
    lead = rv.get("lead", 0.0)        # se enciende cuando la cabeza esta a 'lead' metros
    for f in range(1, frames + 1):
        passed[f] = head_s(e, f) + lead

    def on_frame(s):
        for f in range(1, frames + 1):
            if passed[f] >= s:
                return f + rv.get("delay", 1)
        return None

    for ob in bpy.data.objects:
        if "relevo_s" not in ob:
            continue
        f = on_frame(ob["relevo_s"])
        if ob.type == "LIGHT":
            e0 = ob.data.energy
            ob.data.energy = e0 if f is not None and f <= 1 else 0.0
            ob.data.keyframe_insert("energy", frame=1)
            if f is not None and f > 1:
                ob.data.energy = e0
                ob.data.keyframe_insert("energy", frame=f)
            set_interp(ob.data, "CONSTANT")
            continue
        off = rv.get("off", 0.12)        # apagada: vidrio oscuro, no un agujero negro
        if f is not None and f <= 1:
            key_power(ob, 1, 1.0)
        else:
            key_power(ob, 1, off)
            if f is not None:
                if rnd.random() < rv.get("flicker", 0.6):
                    key_power(ob, f, 1.0)       # arranque: prende, duda, prende
                    key_power(ob, f + 1, off)
                    key_power(ob, f + 2, 1.0)
                else:
                    key_power(ob, f, 1.0)
        set_interp(ob, "CONSTANT")
