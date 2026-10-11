"""Andes de noche: cordillera, cresta con camino inca (Qhapaq Nan), tambos con
baliza, puente colgante de soga (Q'eswachaka) y una apacheta.

Todo sale de una sola ruta: la polilinea de "camino.pts" (x, y, z), suavizada
con Catmull-Rom y medida por longitud de arco (s, en metros). El terreno se
arma alrededor de la ruta (la cresta lleva su altura), los tambos y la apacheta
se ubican por s, el puente cuelga entre dos s y el mensaje (piezas/viaje.py)
corre por la misma ruta. Asi nada flota ni se entierra.

El color del terreno va por cara (atributo "col"): pasto, roca y nieve segun
altura y pendiente, en bandas planas como un fondo pintado.
"""

import math
import random

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

from . import ctx
from .base import lin, link, tint_light
from .materiales import _emit_out, _fog, _glow, _toon_light, mat_flat, mat_neon, mat_toon

# ------------------------------------------------------------------ ruta


def _catmull(pts, step=0.25):
    """Catmull-Rom centripeta por los puntos de control, muestreada cada ~step m."""
    P = [np.array(p, float) for p in pts]
    P = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        n = max(2, int(np.linalg.norm(p2 - p1) / step))
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-2])
    return np.array(out)


class Ruta:
    """Ruta densa con longitud de arco. at(s) -> punto, dir(s) -> tangente."""

    def __init__(self, cfg):
        cam = cfg["camino"]
        pts = _catmull(cam["pts"])
        pu = cfg.get("puente")
        self.bridge = None
        if pu:
            # el tramo del puente es recto y cuelga: catenaria aproximada
            s = self._arclen(pts)
            s0, s1 = pu["s"]
            i0, i1 = np.searchsorted(s, s0), np.searchsorted(s, s1)
            a, b = pts[i0].copy(), pts[i1].copy()
            n = max(8, int(np.linalg.norm(b - a) / 0.25))
            t = np.linspace(0, 1, n)[:, None]
            mid = a + (b - a) * t
            mid[:, 2] -= pu.get("sag", 1.8) * 4 * t[:, 0] * (1 - t[:, 0])
            pts = np.concatenate([pts[:i0], mid, pts[i1 + 1:]])
            self.bridge = (a, b)
        self.pts = pts
        self.s = self._arclen(pts)
        self.length = float(self.s[-1])

    @staticmethod
    def _arclen(pts):
        d = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        return np.concatenate([[0.0], np.cumsum(d)])

    def at(self, s):
        s = float(np.clip(s, 0, self.length))
        return Vector([float(np.interp(s, self.s, self.pts[:, k])) for k in range(3)])

    def dir(self, s, ds=0.6):
        a, b = self.at(s - ds), self.at(s + ds)
        d = b - a
        return d.normalized() if d.length > 1e-6 else Vector((0, 1, 0))

    def xz_of_y(self, y):
        """x y z de la ruta en funcion de y (la ruta avanza siempre hacia +y)."""
        order = np.argsort(self.pts[:, 1])
        ys = self.pts[order, 1]
        return np.interp(y, ys, self.pts[order, 0]), np.interp(y, ys, self.pts[order, 2])


_RUTA = {}


def ruta():
    """Ruta del plano en curso (una por plano: ctx.CFG cambia por proceso)."""
    if "r" not in _RUTA:
        _RUTA["r"] = Ruta(ctx.CFG)
    return _RUTA["r"]


# ------------------------------------------------------------------ ruido


def _value_noise(x, y, seed):
    rng = np.random.default_rng(seed)
    perm = rng.permutation(256)
    perm = np.concatenate([perm, perm])
    vals = rng.random(256)
    xi, yi = np.floor(x).astype(int), np.floor(y).astype(int)
    xf, yf = x - xi, y - yi
    u, v = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)

    def h(i, j):
        return vals[perm[(perm[i & 255] + j) & 255]]

    a, b = h(xi, yi), h(xi + 1, yi)
    c, d = h(xi, yi + 1), h(xi + 1, yi + 1)
    return (a + (b - a) * u) * (1 - v) + (c + (d - c) * u) * v


def fbm(x, y, scale, octaves=4, seed=1):
    out = np.zeros_like(x)
    amp, tot, f = 1.0, 0.0, 1.0 / scale
    for o in range(octaves):
        out += amp * (_value_noise(x * f, y * f, seed + o) * 2 - 1)
        tot += amp
        amp *= 0.5
        f *= 2.03
    return out / tot


def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ material por cara


def mat_toon_attr(name, attr="col", glows=None, albedo="#5a6a80"):
    """Como mat_toon, pero el color sale del atributo de la malla (por cara)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    n = nt.nodes
    light = _toon_light(nt)
    at = n.new("ShaderNodeAttribute")
    at.attribute_type = "GEOMETRY"
    at.attribute_name = attr
    mul = n.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(at.outputs["Color"], mul.inputs[6])
    nt.links.new(light, mul.inputs[7])
    col = mul.outputs[2]
    for g in glows or []:
        add = n.new("ShaderNodeVectorMath")
        add.operation = "ADD"
        nt.links.new(col, add.inputs[0])
        nt.links.new(_glow(nt, g, albedo), add.inputs[1])
        col = add.outputs[0]
    _emit_out(nt, _fog(nt, col))
    return mat


def _mesh_with_face_colors(name, verts, faces, face_cols):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    mesh.update()
    attr = mesh.color_attributes.new("col", "FLOAT_COLOR", "CORNER")
    loop_cols = np.repeat(np.asarray(face_cols, np.float32),
                          [len(f) for f in faces], axis=0)
    attr.data.foreach_set("color", loop_cols.ravel())
    return mesh


def _palette(e):
    return {k: np.array(lin(e[k])) for k in ("grass", "grass_dark", "rock", "snow")}


def _colorize(e, z, slope, x, y, seed=3):
    """Color plano por cara: nieve arriba, roca en lo empinado, pasto en dos tonos."""
    P = _palette(e)
    jit = fbm(x, y, e.get("patch", 18.0), 2, seed)
    # manchas grandes de pasto oscuro (no pixeles): solo donde el ruido es fuerte
    out = np.where((jit > e.get("patch_cut", 0.35))[:, None], P["grass_dark"], P["grass"])
    out = np.where((slope > e.get("rock_slope", 0.75))[:, None], P["rock"], out)
    snow_z = e.get("snow_z", 1e9) + 6 * jit
    out = np.where((z > snow_z)[:, None], P["snow"], out)
    return out


# ------------------------------------------------------------------ terreno


def build_terreno(e, colls):
    """Grilla de alturas alrededor de la ruta: la cresta lleva el camino, los
    costados caen a valles y vuelven a subir; una quebrada corta la cresta
    donde va el puente."""
    R = ruta()
    x0, x1 = e["x"]
    y0, y1 = e["y"]
    res = e.get("res", 2.0)
    xs = np.arange(x0, x1 + res, res)
    ys = np.arange(y0, y1 + res, res)
    X, Y = np.meshgrid(xs, ys)
    xp, zp = R.xz_of_y(Y)
    dx = np.abs(X - xp)
    w = e.get("crest", 5.0)
    out = np.maximum(0, dx - w)
    # la caida tiene fondo: sin tope, a 150 m de la cresta el valle quedaba
    # 220 m abajo y por debajo del horizonte se veia cielo
    H = zp - np.minimum(e.get("max_drop", 45.0), e.get("fall", 0.12) * out ** 1.3)
    H += e.get("noise", 6.0) * fbm(X, Y, e.get("noise_scale", 40.0), 4, 11) * _smooth(w, w + 18, dx)
    # los valles vuelven a subir en otras crestas
    H += e.get("rise", 60.0) * _smooth(e.get("valley", 70), e.get("valley", 70) + 110, dx) \
        * (0.6 + 0.4 * fbm(X, Y, 70.0, 3, 21))
    g = e.get("gorge")
    if g:
        gy0, gy1 = g["y"]
        wall = g.get("wall", 5.0)
        cut = _smooth(gy0 - wall, gy0, Y) * (1 - _smooth(gy1, gy1 + wall, Y))
        # paredes irregulares: el borde de la quebrada no es una regla
        cut *= 0.85 + 0.15 * fbm(X, Y, 9.0, 2, 31)
        # lejos de la cresta el fondo sube hasta el valle: la quebrada no se
        # abre al vacio en el borde del terreno (se veian estrellas por abajo)
        if g.get("open"):
            o0, o1 = g["open"]
            cut *= 1 - _smooth(o0, o1, dx)
        H -= g["depth"] * cut
    ny, nx = H.shape
    verts = np.stack([X.ravel(), Y.ravel(), H.ravel()], axis=1)
    idx = np.arange(nx * ny).reshape(ny, nx)
    faces = np.stack([idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(),
                      idx[1:, 1:].ravel(), idx[1:, :-1].ravel()], axis=1)
    # pendiente y altura por cara
    v = verts[faces]
    cz = v[:, :, 2].mean(axis=1)
    dzx = (v[:, 1, 2] + v[:, 2, 2] - v[:, 0, 2] - v[:, 3, 2]) / (2 * res)
    dzy = (v[:, 2, 2] + v[:, 3, 2] - v[:, 0, 2] - v[:, 1, 2]) / (2 * res)
    slope = np.sqrt(dzx ** 2 + dzy ** 2)
    cols = _colorize(e, cz, slope, v[:, :, 0].mean(axis=1), v[:, :, 1].mean(axis=1))
    mesh = _mesh_with_face_colors("terreno", verts, faces, cols)
    ob = bpy.data.objects.new("terreno", mesh)
    ob.data.materials.append(mat_terreno("terreno_m", e))
    for p in ob.data.polygons:
        p.use_smooth = e.get("smooth", False)
    link(ob, colls["main"])
    if g and g.get("river"):
        rv = g["river"]
        river = bpy.data.objects.new("rio", _strip_mesh("rio", x0, x1, (gy0 + gy1) / 2,
                                                         rv.get("width", 3.0)))
        river.location.z = float(zp.mean()) - g["depth"] + rv.get("z", 0.5)
        river.data.materials.append(mat_neon("rio_m", rv["color"], rv.get("strength", 0.5)))
        link(river, colls["neon"])
    return ob


def mat_terreno(name, e):
    """Pasto, manchas de pasto oscuro, roca en lo empinado y nieve arriba, con
    bordes duros pero curvos: umbrales sobre la normal suave, la altura y un
    ruido en coordenadas de mundo. (El color por cara salia en bloques.)"""
    mat = mat_toon(name, e["grass"], glows=e.get("glows"))
    nt = mat.node_tree
    n, L = nt.nodes, nt.links
    mix = next(x for x in n if x.type == "MIX" and x.blend_type == "MULTIPLY")
    geo = n.new("ShaderNodeNewGeometry")
    sp = n.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sp.inputs[0])
    sn = n.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Normal"], sn.inputs[0])
    noi = n.new("ShaderNodeTexNoise")
    noi.inputs["Scale"].default_value = 1.0 / e.get("patch", 90.0)
    noi.inputs["Detail"].default_value = 3.0
    L.new(geo.outputs["Position"], noi.inputs["Vector"])

    def m(op, a, b):
        node = n.new("ShaderNodeMath")
        node.operation = op
        for i, x in enumerate((a, b)):
            if isinstance(x, (int, float)):
                node.inputs[i].default_value = x
            else:
                L.new(x, node.inputs[i])
        return node.outputs[0]

    def pick(fac, a, b):
        node = n.new("ShaderNodeMix")
        node.data_type = "RGBA"
        L.new(fac, node.inputs["Factor"])
        for sock, v in ((node.inputs[6], a), (node.inputs[7], b)):
            if isinstance(v, str):
                sock.default_value = lin(v)
            else:
                L.new(v, sock)
        return node.outputs[2]

    col = pick(m("GREATER_THAN", noi.outputs["Fac"], e.get("patch_cut", 0.56)), e["grass"], e["grass_dark"])
    col = pick(m("LESS_THAN", sn.outputs[2], e.get("rock_nz", 0.72)), col, e["rock"])
    snow_h = m("ADD", sp.outputs[2], m("MULTIPLY", m("SUBTRACT", noi.outputs["Fac"], 0.5), 24.0))
    col = pick(m("GREATER_THAN", snow_h, e.get("snow_z", 1e6)), col, e["snow"])
    L.new(col, mix.inputs[6])
    return mat


def build_luna(e, colls):
    """Luna llena pintada: disco plano mirando a camara, con un halo apenas
    mas oscuro. No ilumina: la luz es el sol frio de "lights"."""
    loc = Vector(e["at"])
    cam = Vector(ctx.CFG["camera"]["keys"][0]["pos"])
    for k, (r, col, strength) in enumerate(((e["r"], e.get("color", "#eef3ff"), e.get("strength", 1.3)),
                                            (e["r"] * e.get("halo", 1.6), e.get("halo_color", "#3a4a80"),
                                             e.get("halo_strength", 0.35)))):
        bpy.ops.mesh.primitive_circle_add(vertices=64, radius=r, fill_type="NGON")
        ob = bpy.context.active_object
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        ob.name = f"luna{k}"
        ob.location = loc + (cam - loc).normalized() * (0.0 if k == 0 else -1.0)
        ob.rotation_euler = (cam - loc).to_track_quat("Z", "Y").to_euler()
        ob.data.materials.append(mat_neon(f"luna{k}_m", col, strength, fog=False))
        ob["keep"] = True
        link(ob, colls["neon"])


def _strip_mesh(name, x0, x1, yc, width):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(x0, yc - width / 2, 0), (x1, yc - width / 2, 0),
                      (x1, yc + width / 2, 0), (x0, yc + width / 2, 0)], [], [(0, 1, 2, 3)])
    return mesh


def build_cordillera(e, colls):
    """Picos lejanos: conos de anillos con borde irregular y nieve arriba. La
    niebla los vuelve siluetas escalonadas."""
    rnd = random.Random(e.get("seed", 7))
    mat = mat_toon_attr("cordillera_m")
    P = _palette(e)
    for i, (px, py, ph, pr) in enumerate(e["peaks"]):
        rings, segs = 9, 28
        verts, faces, cols = [], [], []
        phase = [rnd.uniform(0, 6.28) for _ in range(4)]
        for r in range(rings + 1):
            k = r / rings                      # 0 = cumbre, 1 = base
            z = ph * (1 - k ** 1.35) + rnd.uniform(-0.03, 0.03) * ph * (0 < r < rings)
            for sgi in range(segs):
                a = 2 * math.pi * sgi / segs
                wob = 1 + 0.22 * math.sin(3 * a + phase[0]) + 0.12 * math.sin(7 * a + phase[1]) \
                    + 0.08 * math.sin(13 * a + phase[2] + k * 3)
                rr = pr * k * wob
                verts.append((px + rr * math.cos(a), py + rr * math.sin(a), z if r else ph))
        for r in range(rings):
            for sgi in range(segs):
                a, b = r * segs + sgi, r * segs + (sgi + 1) % segs
                c, d = (r + 1) * segs + (sgi + 1) % segs, (r + 1) * segs + sgi
                faces.append((a, b, c, d))
                kk = (r + 0.5) / rings
                # nieve en la parte alta, con lenguas que bajan por las aristas
                tongue = 0.12 * math.sin(5 * 2 * math.pi * sgi / segs + phase[3])
                if kk < e.get("snow_k", 0.34) + tongue:
                    cols.append(P["snow"])
                elif sgi % 2 and kk < 0.7:
                    cols.append(P["rock"])
                else:
                    cols.append(P["grass_dark"] if kk > 0.7 else P["rock"] * 0.85 + P["grass_dark"] * 0.15)
        mesh = _mesh_with_face_colors(f"pico{i}", verts, faces, cols)
        ob = bpy.data.objects.new(f"pico{i}", mesh)
        ob.data.materials.append(mat)
        link(ob, colls["main"])


# ------------------------------------------------------------------ camino


def _box_at(bm, center, fwd, size, mat_index=0):
    """Caja orientada: x = a lo ancho, y = a lo largo (fwd), z = arriba; base en center."""
    fwd = Vector(fwd)
    fwd.z = 0
    fwd.normalize()
    right = Vector((fwd.y, -fwd.x, 0))
    M = Matrix((right, fwd, Vector((0, 0, 1)))).transposed()
    out = bmesh.ops.create_cube(bm, size=1.0)
    sx, sy, sz = size
    for v in out["verts"]:
        local = Vector((v.co.x * sx, v.co.y * sy, (v.co.z + 0.5) * sz))
        v.co = M @ local + Vector(center)
    for f in {f for v in out["verts"] for f in v.link_faces}:
        f.material_index = mat_index


def _sweep(R, s0, s1, profile, step=0.5, name="barrido"):
    """Barre un perfil [(lateral, alto), ...] (cerrado) a lo largo de la ruta."""
    verts, faces = [], []
    n = len(profile)
    ss = np.arange(s0, s1 + 1e-6, step)
    for k, s in enumerate(ss):
        p, d = R.at(s), R.dir(s)
        right = Vector((d.y, -d.x, 0)).normalized()
        for lat, up in profile:
            verts.append(tuple(p + right * lat + Vector((0, 0, up))))
        if k:
            a, b = (k - 1) * n, k * n
            for j in range(n - 1):
                faces.append((a + j, a + j + 1, b + j + 1, b + j))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh


def mat_lajas(name, color, joint, scale=1.4):
    """Calzada: toon de un color con juntas de lajas pintadas (Voronoi a
    distancia del borde). Sin geometria por laja: la linea de tinta no las
    contornea una por una."""
    mat = mat_toon(name, color)
    nt = mat.node_tree
    n = nt.nodes
    mix = next(x for x in n if x.type == "MIX" and x.blend_type == "MULTIPLY")
    tc = n.new("ShaderNodeTexCoord")
    vor = n.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = scale
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    lt = n.new("ShaderNodeMath")
    lt.operation = "LESS_THAN"
    nt.links.new(vor.outputs["Distance"], lt.inputs[0])
    lt.inputs[1].default_value = 0.055
    pick = n.new("ShaderNodeMix")
    pick.data_type = "RGBA"
    nt.links.new(lt.outputs[0], pick.inputs["Factor"])
    pick.inputs[6].default_value = lin(color)
    pick.inputs[7].default_value = lin(joint)
    nt.links.new(pick.outputs[2], mix.inputs[6])
    return mat


def build_camino(e, colls):
    """Calzada de lajas sobre la cresta y pirca baja a los costados. Saltea
    el tramo del puente."""
    R = ruta()
    W = e.get("width", 3.0)
    skip = ctx.CFG.get("puente", {}).get("s")
    end = min(e.get("to", R.length), R.length)
    tramos = [(e.get("from", 0.0), skip[0] - 0.3), (skip[1] + 0.3, end)] if skip else [(e.get("from", 0.0), end)]
    road_m = mat_lajas("lajas", e["stone"], e.get("joint", "#3d3c52"), e.get("joint_scale", 1.4))
    wall_m = mat_toon("pirca", e["wall"])
    for i, (s0, s1) in enumerate(tramos):
        road = bpy.data.objects.new(f"camino{i}", _sweep(R, s0, s1, [(-W / 2, 0.06), (W / 2, 0.06)],
                                                         name=f"camino{i}"))
        road.data.materials.append(road_m)
        link(road, colls["main"])
        if e.get("wall", True):
            h, t = e.get("wall_h", 0.4), e.get("wall_w", 0.45)
            for side in (-1, 1):
                x0 = side * W / 2
                x1 = side * (W / 2 + t)
                prof = [(x0, -0.3), (x0, h), (x1, h * 0.85), (x1, -0.3)]
                wl = bpy.data.objects.new(f"pirca{i}{side}", _sweep(R, s0, s1, prof, name="pirca"))
                wl.data.materials.append(wall_m)
                link(wl, colls["main"])


# ------------------------------------------------------------------ tambos


def _trapezoid_door(bm, center, fwd, w_bottom, w_top, h, mat_index):
    """Vano trapezoidal inca: angosto arriba. Una placa apenas delante del muro."""
    fwd = Vector(fwd).normalized()
    right = Vector((fwd.y, -fwd.x, 0))
    c = Vector(center)
    vs = [bm.verts.new(c + right * (-w_bottom / 2)), bm.verts.new(c + right * (w_bottom / 2)),
          bm.verts.new(c + right * (w_top / 2) + Vector((0, 0, h))),
          bm.verts.new(c + right * (-w_top / 2) + Vector((0, 0, h)))]
    f = bm.faces.new(vs)
    f.material_index = mat_index


def build_tambos(e, colls):
    """Postas del camino: casa de pirca con techo de paja a dos aguas, vano
    trapezoidal mirando al camino y, al lado, un poste de piedra con la baliza
    hexagonal que el mensaje enciende al pasar (propiedad relevo_s)."""
    R = ruta()
    rnd = random.Random(e.get("seed", 12))
    wall_m = mat_toon("tambo_pirca", e["wall"])
    roof_m = mat_toon("tambo_paja", e["roof"])
    # el vano deja ver un fuego adentro: lo unico calido de la noche
    door_m = mat_neon("tambo_vano", e["fire"], e.get("fire_strength", 0.7)) if e.get("fire")         else mat_flat("tambo_vano", e.get("door", "#0c0d18"))
    beacon_m = mat_neon("baliza_hex", e["beacon"], e.get("beacon_strength", 1.6))
    for i, t in enumerate(e["list"]):
        s, side = t["s"], t.get("side", 1)
        p, d = R.at(s), R.dir(s)
        right = Vector((d.y, -d.x, 0)).normalized()
        off = t.get("off", 6.0)
        c = p + right * side * off
        c.z = p.z - 0.3
        face = -right * side            # la fachada mira al camino
        Wd, Dp, Hh = t.get("w", 5.0), t.get("d", 3.6), t.get("h", 2.3)
        bm = bmesh.new()
        # casa: el eje largo paralelo al camino
        _box_at(bm, c, d, (Dp, Wd, Hh + 0.3))
        _trapezoid_door(bm, c + face * (Dp / 2 + 0.02) + Vector((0, 0, 0.3)), face,
                        0.95, 0.7, 1.6, 2)
        # techo: prisma a dos aguas que sobresale
        rb = bmesh.new()
        ov = 0.35
        ridge = Hh + 0.3 + t.get("roof_h", 1.6)
        hw, hl = Dp / 2 + ov, Wd / 2 + ov
        fw = Vector((d.x, d.y, 0)).normalized()
        rr = Vector((fw.y, -fw.x, 0))
        base = c + Vector((0, 0, Hh + 0.3 - 0.15))
        top = c + Vector((0, 0, ridge))
        v = [rb.verts.new(base + rr * -hw + fw * -hl), rb.verts.new(base + rr * hw + fw * -hl),
             rb.verts.new(base + rr * hw + fw * hl), rb.verts.new(base + rr * -hw + fw * hl),
             rb.verts.new(top + fw * -hl), rb.verts.new(top + fw * hl)]
        for f in ((0, 1, 4), (2, 3, 5), (0, 4, 5, 3), (1, 2, 5, 4), (0, 3, 2, 1)):
            rb.faces.new([v[k] for k in f])
        bmesh.ops.recalc_face_normals(rb, faces=rb.faces)
        mesh = bpy.data.meshes.new(f"tambo{i}")
        bm.to_mesh(mesh)
        bm.free()
        ob = bpy.data.objects.new(f"tambo{i}", mesh)
        for m in (wall_m, wall_m, door_m):
            ob.data.materials.append(m)
        link(ob, colls["main"])
        if e.get("fire"):
            tint_light(f"tambo{i}_fuego", e["fire"], e.get("fire_light", 60),
                       tuple(c + face * (Dp / 2 + 1.2) + Vector((0, 0, 1.0))), colls)
        rmesh = bpy.data.meshes.new(f"tambo{i}_techo")
        rb.to_mesh(rmesh)
        rb.free()
        roof = bpy.data.objects.new(f"tambo{i}_techo", rmesh)
        roof.data.materials.append(roof_m)
        link(roof, colls["main"])
        # poste y baliza entre la casa y el camino
        bp = p + right * side * (W_half(e) + 0.9) + fw * t.get("beacon_ahead", 2.0)
        bp.z = R.at(s).z - 0.3
        ph = e.get("post_h", 2.2)
        pb = bmesh.new()
        _box_at(pb, bp, d, (0.5, 0.5, ph))
        pmesh = bpy.data.meshes.new(f"poste{i}")
        pb.to_mesh(pmesh)
        pb.free()
        post = bpy.data.objects.new(f"poste{i}", pmesh)
        post.data.materials.append(wall_m)
        link(post, colls["main"])
        hexa = hex_prism(f"baliza{i}", e.get("beacon_r", 0.32), e.get("beacon_h", 0.55))
        hexa.location = bp + Vector((0, 0, ph + 0.35 + e.get("beacon_h", 0.55) / 2))
        hexa.data.materials.append(beacon_m)
        hexa["relevo_s"] = s + t.get("beacon_ahead", 2.0)
        link(hexa, colls["neon"])
        li = bpy.data.lights.new(f"baliza{i}_luz", "POINT")
        li.color = lin(e["beacon"])[:3]
        li.energy = e.get("beacon_light", 120)
        li.use_shadow = False
        li.shadow_soft_size = 0.4
        lo = bpy.data.objects.new(f"baliza{i}_luz", li)
        lo.location = hexa.location + Vector((0, 0, 0.6))
        lo["relevo_s"] = hexa["relevo_s"]
        link(lo, colls["lights"])


def W_half(e):
    return ctx.CFG.get("camino", {}).get("width", 3.0) / 2


def hex_prism(name, r, h):
    """Prisma hexagonal con el origen en el centro: el hexagono de chasqui."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=r, radius2=r, depth=h)
    # create_cone ya pone un vertice en +y: girado 90 grados en x queda arriba
    # (punta arriba, como el icono)
    bm.to_mesh(mesh)
    bm.free()
    ob = bpy.data.objects.new(name, mesh)
    ob.rotation_euler = (math.radians(90), 0, 0)
    return ob


# ------------------------------------------------------------------ puente


def build_puente(e, colls):
    """Q'eswachaka: cuatro sogas de piso con travesanos, dos pasamanos y la red
    de sogas finas que los une. Estribos de piedra a cada lado."""
    R = ruta()
    a, b = (Vector(v) for v in R.bridge)
    d = (b - a)
    span = d.length
    fw = Vector((d.x, d.y, 0)).normalized()
    right = Vector((fw.y, -fw.x, 0))
    sag = ctx.CFG["puente"].get("sag", 1.8)
    rail_h = e.get("rail_h", 1.05)
    deck_w = e.get("deck_w", 1.3)
    rope_m = mat_toon("soga", e["rope"])
    deck_m = mat_toon("piso_puente", e.get("deck", e["rope"]))

    def at(t, lateral, up, extra_sag=0.0):
        p = a + d * t
        p.z -= (sag + extra_sag) * 4 * t * (1 - t)
        return p + right * lateral + Vector((0, 0, up))

    def rope(name, pts, r):
        cu = bpy.data.curves.new(name, "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = r
        cu.bevel_resolution = 1
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for k, q in enumerate(pts):
            sp.points[k].co = (q.x, q.y, q.z, 1)
        ob = bpy.data.objects.new(name, cu)
        ob.data.materials.append(rope_m)
        link(ob, colls["main"])
        return ob

    N = 48
    ts = [k / N for k in range(N + 1)]
    for k, lat in enumerate((-0.55, -0.2, 0.2, 0.55)):
        rope(f"soga_piso{k}", [at(t, lat * deck_w / 1.1, -0.05) for t in ts], 0.06)
    # el pasamanos cuelga un poco menos que el piso (va atado mas alto en el estribo)
    for side in (-1, 1):
        rope(f"pasamanos{side}", [at(t, side * (deck_w / 2 + 0.25), rail_h, -0.35) for t in ts], 0.07)
    # travesanos del piso
    bm = bmesh.new()
    n_sl = int(span / e.get("slat_pitch", 0.32))
    for k in range(1, n_sl):
        t = k / n_sl
        _box_at(bm, at(t, 0, -0.06), fw, (deck_w + 0.1, 0.12, 0.05))
    mesh = bpy.data.meshes.new("travesanos")
    bm.to_mesh(mesh)
    bm.free()
    sl = bpy.data.objects.new("travesanos", mesh)
    sl.data.materials.append(deck_m)
    link(sl, colls["main"])
    # red lateral: sogas finas en zigzag del pasamanos al piso
    for side in (-1, 1):
        pts = []
        m = int(span / 0.7)
        for k in range(m + 1):
            t = k / m
            pts.append(at(t, side * (deck_w / 2 + 0.25), rail_h, -0.35) if k % 2 == 0
                       else at(t, side * 0.55 * deck_w / 1.1, -0.02))
        rope(f"red{side}", pts, 0.018)
    # estribos de pirca a cada lado
    wall_m = mat_toon("estribo_m", e.get("abutment", "#6c6a7c"))
    for end, sgn in ((a, -1), (b, 1)):
        eb = bmesh.new()
        _box_at(eb, end + fw * sgn * 1.4 + Vector((0, 0, -3.5)), fw, (deck_w + 2.6, 2.8, 4.6))
        for side in (-1, 1):
            # postes donde se atan los pasamanos
            _box_at(eb, end + fw * sgn * 0.6 + right * side * (deck_w / 2 + 0.45) + Vector((0, 0, 0.9)),
                    fw, (0.45, 0.45, rail_h + 0.4))
        em = bpy.data.meshes.new("estribo")
        eb.to_mesh(em)
        eb.free()
        ob = bpy.data.objects.new("estribo", em)
        ob.data.materials.append(wall_m)
        link(ob, colls["main"])


# ------------------------------------------------------------------ apacheta


def build_apacheta(e, colls):
    """Monticulo de piedras apiladas (ofrenda del caminante) con el cristal
    hexagonal flotando encima. El cristal late (propiedad power) y tine las
    piedras con un resplandor suave (glow_crystal)."""
    R = ruta()
    rnd = random.Random(e.get("seed", 33))
    p = R.at(e.get("s", 0.0))
    d = R.dir(e.get("s", 0.0))
    right = Vector((d.y, -d.x, 0)).normalized()
    c = p + right * e.get("side", 0.0) + Vector((d.x, d.y, 0)) * e.get("ahead", 0.0)
    c.z = p.z - 0.3
    H, Rb = e.get("height", 1.8), e.get("radius", 1.3)
    cr = e["crystal"]
    top = c + Vector((0, 0, H + cr.get("gap", 0.55) + cr["h"] / 2))
    glows = [{"kind": "point", "at": tuple(top), "color": cr["color"],
              "strength": cr.get("glow_strength", 1.4), "falloff": cr.get("glow_falloff", 1.6),
              "prop": "glow_crystal"}]
    bm = bmesh.new()
    layers = e.get("layers", 12)
    for L in range(layers):
        k = L / layers
        rr = Rb * (1 - k) ** 0.8
        z = H * k
        n = max(1, int(2 * math.pi * rr / 0.36) + 1)
        a0 = rnd.uniform(0, 6.28)
        for j in range(n):
            a = a0 + 2 * math.pi * (j + rnd.uniform(-0.3, 0.3)) / n
            q = c + Vector((rr * rnd.uniform(0.85, 1.05) * math.cos(a),
                            rr * rnd.uniform(0.85, 1.05) * math.sin(a), z + rnd.uniform(-0.04, 0.05)))
            out = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
            big = rnd.random() < 0.25
            f = 1.35 if big else 1.0
            sx, sy, sz = (rnd.uniform(0.15, 0.26) * f, rnd.uniform(0.12, 0.2) * f, rnd.uniform(0.07, 0.13) * f)
            rot = Matrix.Rotation(rnd.uniform(0, 6.28), 3, "Z") @ Matrix.Rotation(rnd.uniform(-0.35, 0.35), 3, "X")
            for v in out["verts"]:
                # piedra de canto: aplastada de un lado, no un huevo
                co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz))
                if co.x > sx * 0.55:
                    co.x = sx * 0.55
                v.co = rot @ co + q
    mesh = bpy.data.meshes.new("apacheta")
    bm.to_mesh(mesh)
    bm.free()
    ob = bpy.data.objects.new("apacheta", mesh)
    ob.data.materials.append(mat_toon("apacheta_m", e["stone"], glows=glows))
    ob["glow_crystal"] = 1.0
    link(ob, colls["main"])
    # el piso alrededor tambien recibe el resplandor: lo lleva el terreno y el camino
    hexa = hex_prism("cristal", cr["r"], cr["h"])
    hexa.location = top
    hexa.data.materials.append(mat_neon("cristal_m", cr["color"], cr.get("strength", 1.8), fog=False))
    link(hexa, colls["neon"])
    li = bpy.data.lights.new("cristal_luz", "POINT")
    li.color = lin(cr["color"])[:3]
    li.energy = cr.get("energy", 300)
    li.use_shadow = False
    lo = bpy.data.objects.new("cristal_luz", li)
    lo.location = top + Vector((0, 0, 0.8))
    link(lo, colls["lights"])
    # sin luz puntual sobre las piedras: ahi manda el resplandor suave
    excl = bpy.data.collections.new("apacheta_receptores")
    excl.objects.link(ob)
    lo.light_linking.receiver_collection = excl
    excl.collection_objects[0].light_linking.link_state = "EXCLUDE"
    _latido(e.get("latido"), hexa, lo, ob)
    return hexa


def _latido(lt, hexa, light, stones):
    """Pulso del cristal: base + golpe en sin^3 cada beat_frames. 'flash' = un
    destello (frame, intensidad) cuando sale el mensaje."""
    if not lt:
        return
    e0 = light.data.energy
    flashes = {f: v for f, v in lt.get("flash", [])}
    for f in range(1, ctx.CFG["frames"] + 1):
        ph = (f - 1 + lt.get("phase", 0)) / lt["beat_frames"]
        pw = lt.get("base", 0.55) + lt.get("amp", 0.8) * max(0.0, math.sin(math.pi * (ph % 1.0))) ** 3
        if f in flashes:
            pw = flashes[f]
        hexa["power"] = pw
        hexa.keyframe_insert('["power"]', frame=f)
        light.data.energy = e0 * pw
        light.data.keyframe_insert("energy", frame=f)
        stones["glow_crystal"] = pw
        stones.keyframe_insert('["glow_crystal"]', frame=f)
