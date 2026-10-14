"""
piezas.py - NODO 0 (La marea de cobre): el galpon ferroviario de San Antonio
de los Cobres, la radio de cobre, la torre que solo existe en la sombra y los
drones.

Ejes del galpon: muros largos en x = +-ancho/2, el largo sobre y, z arriba.
El sol de la tarde entra por la brecha del faldon izquierdo (x < 0) y pega en
el muro derecho: el piso queda en sombra (lo tapa el muro izquierdo) y el muro
derecho es la pantalla donde cae la sombra de la torre.

    "galpon": {"ancho": 10, "largo": 20, "alto": 6, "cumbrera": 8,
               "brecha": [-6, 5], "cerchas": 2.5},
    "radio": {"at": [3.7, 0, 0], "face": -90, "erratico": [1, 72]},
    "torre": {"at": [3.7, 0.0, 0], "alto": 14, "escala": [[1, 0], [24, 0.3], ...]},
    "nyx": {"keys": [[1, [x, y, z], yaw, alas]], "cable": [x, y, z]}

Las piezas de "dron" miran a -y en sus ejes; "yaw" las gira sobre z
(90 = mirar a +x).
"""

import math
import random

import bmesh
import bpy
from mathutils import Euler, Vector

from piezas import ctx
from piezas.base import action_fcurves, collection, key_power, lin, link, set_interp
from piezas.materiales import _emit_out, _fog, _toon_light, mat_beam, mat_flat, mat_neon, mat_tint, mat_toon

COBRE = "#b8733a"
ACERO = "#3a3236"
TINTA = "#0d0b24"


# --- utilidades ---------------------------------------------------------------

def sun_dir():
    """Direccion en la que viaja la luz del primer sol del plano."""
    rot = ctx.CFG["lights"][0]["rot"]
    return Euler([math.radians(a) for a in rot]).to_matrix() @ Vector((0, 0, -1))


def _m(nt, op, a, b=None):
    node = nt.nodes.new("ShaderNodeMath")
    node.operation = op
    for i, x in enumerate((a, b)):
        if x is None:
            continue
        if isinstance(x, (int, float)):
            node.inputs[i].default_value = x
        else:
            nt.links.new(x, node.inputs[i])
    return node.outputs[0]


def _mix(nt, fac, a, b, blend="MIX"):
    mx = nt.nodes.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    mx.blend_type = blend
    for sock, x in ((mx.inputs["Factor"], fac), (mx.inputs[6], a), (mx.inputs[7], b)):
        if isinstance(x, (int, float)):
            sock.default_value = x
        elif isinstance(x, str):
            sock.default_value = lin(x)
        else:
            nt.links.new(x, sock)
    return mx.outputs[2]


def mat_toon_albedo(name, build_albedo):
    """Como mat_toon, pero el color de la superficie lo arma build_albedo(nt)
    (un patron por shader: chapa acanalada, oxido, manchas de aceite)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    light = _toon_light(nt)
    col = _mix(nt, 1.0, build_albedo(nt), light, "MULTIPLY")
    _emit_out(nt, _fog(nt, col))
    return mat


def _noise(nt, scale, stretch=(1, 1, 1), detail=2.0):
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = stretch
    nt.links.new(geo.outputs["Position"], mp.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = detail
    nt.links.new(mp.outputs[0], nz.inputs["Vector"])
    return nz.outputs["Fac"]


def _dot(nt, a, vec):
    node = nt.nodes.new("ShaderNodeVectorMath")
    node.operation = "DOT_PRODUCT"
    nt.links.new(a, node.inputs[0])
    node.inputs[1].default_value = tuple(vec)
    return node.outputs["Value"]


def mat_dron(name, color, luz=1.0):
    """Cel de los drones con luz analitica: Lambert contra la direccion del
    sol del plano, no la luz de la escena, asi
    las sombras de las cerchas no los manchan. Dos tonos con la sombra tenida
    de violeta, un tono de brillo en las caras que miran de lleno al sol y un
    filo calido en el contorno del lado del sol. luz (0..1): cuanto sol les
    toca (0 = todo en el tono de sombra, para un dron en la penumbra)."""
    L = -sun_dir()

    def albedo(nt):
        return color

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    lum = _dot(nt, geo.outputs["Normal"], L)
    lit = _m(nt, "MULTIPLY", _m(nt, "GREATER_THAN", lum, 0.05), luz)
    hi = _m(nt, "MULTIPLY", _m(nt, "GREATER_THAN", lum, 0.7), luz)
    tone = _mix(nt, lit, "#6b5f8f", "#fff1dc")
    tone = _mix(nt, _m(nt, "MULTIPLY", hi, 0.25), tone, "#ffffff", "ADD")
    col = _mix(nt, 1.0, color, tone, "MULTIPLY")
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    edge = _m(nt, "GREATER_THAN", lw.outputs["Facing"], 0.82)
    side = _m(nt, "GREATER_THAN", lum, -0.25)
    rim = _m(nt, "MULTIPLY", _m(nt, "MULTIPLY", edge, side), 0.45 * luz)
    col = _mix(nt, rim, col, "#ffc98a", "ADD")
    _emit_out(nt, _fog(nt, col))
    return mat


def mat_chapa(name, zinc, oxido, pitch=0.22, oxido_umbral=0.66):
    """Chapa acanalada oxidada. Las canaletas son bandas por shader (con
    geometria la tinta dibujaria cada una); el oxido son manchas grandes mas
    chorreaduras verticales."""
    def albedo(nt):
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        sp = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(geo.outputs["Position"], sp.inputs[0])
        sn = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(geo.outputs["Normal"], sn.inputs[0])
        # coordenada a lo ancho de la chapa: y en muros que miran a +-x y en
        # el techo (las canaletas bajan por la pendiente), x en los testeros
        ay = _m(nt, "ADD", _m(nt, "ABSOLUTE", sn.outputs[0]), _m(nt, "ABSOLUTE", sn.outputs[2]))
        u = _m(nt, "ADD", _m(nt, "MULTIPLY", sp.outputs[1], ay),
               _m(nt, "MULTIPLY", sp.outputs[0], _m(nt, "ABSOLUTE", sn.outputs[1])))
        banda = _m(nt, "GREATER_THAN", _m(nt, "FRACT", _m(nt, "DIVIDE", u, pitch)), 0.62)
        manchas = _m(nt, "GREATER_THAN", _noise(nt, 1.3, (1, 1, 1), 3.0), oxido_umbral)
        chorro = _m(nt, "GREATER_THAN", _noise(nt, 3.0, (4.0, 4.0, 0.12), 1.0), 0.68)
        ox = _m(nt, "MAXIMUM", manchas, chorro)
        base = _mix(nt, ox, zinc, oxido)
        return _mix(nt, _m(nt, "MULTIPLY", banda, 0.24), base, "#000000")
    return mat_toon_albedo(name, albedo)


def mat_piso(name, color, mancha):
    """Piso de tierra apisonada con manchas de aceite."""
    def albedo(nt):
        f = _m(nt, "GREATER_THAN", _noise(nt, 3.5, (1, 1, 1), 1.0), 0.64)
        return _mix(nt, f, color, mancha)
    return mat_toon_albedo(name, albedo)


def _bm_quad_slab(bm, quad, t, mi=0):
    """Placa: un cuadrilatero con espesor t hacia adentro de su normal."""
    q = [Vector(p) for p in quad]
    n = (q[1] - q[0]).cross(q[3] - q[0]).normalized()
    top = [bm.verts.new(p) for p in q]
    bot = [bm.verts.new(p - n * t) for p in q]
    faces = [top, bot[::-1]] + [[top[i], bot[i], bot[(i + 1) % 4], top[(i + 1) % 4]][::-1]
                               for i in range(4)]
    for f in faces:
        bm.faces.new(f).material_index = mi


def _bm_beam(bm, a, b, s, mi=0):
    """Viga de seccion cuadrada s entre dos puntos."""
    a, b = Vector(a), Vector(b)
    v = b - a
    ref = Vector((0, 0, 1)) if abs(v.normalized().z) < 0.95 else Vector((1, 0, 0))
    u = v.cross(ref).normalized() * s / 2
    w = v.cross(u).normalized() * s / 2
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    ra = [bm.verts.new(a + u * i + w * j) for i, j in corners]
    rb = [bm.verts.new(b + u * i + w * j) for i, j in corners]
    faces = [ra[::-1], rb] + [[ra[k], ra[(k + 1) % 4], rb[(k + 1) % 4], rb[k]] for k in range(4)]
    for f in faces:
        bm.faces.new(f).material_index = mi


def _bm_box(bm, c, s, mi=0):
    out = bmesh.ops.create_cube(bm, size=1.0)
    for v in out["verts"]:
        v.co = Vector((v.co.x * s[0] + c[0], v.co.y * s[1] + c[1], v.co.z * s[2] + c[2]))
    for f in {f for v in out["verts"] for f in v.link_faces}:
        f.material_index = mi


def _bm_cyl(bm, c, r, depth, axis="z", segs=16, mi=0, r2=None):
    """Cilindro (o cono si r2) centrado en c, eje x/y/z."""
    out = bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r,
                                radius2=r if r2 is None else r2, depth=depth)
    rot = {"z": Euler((0, 0, 0)), "x": Euler((0, math.radians(90), 0)),
           "y": Euler((math.radians(90), 0, 0))}[axis].to_matrix()
    for v in out["verts"]:
        v.co = rot @ v.co + Vector(c)
    for f in {f for v in out["verts"] for f in v.link_faces}:
        f.material_index = mi


def _mesh_obj(name, bm, mats, coll, smooth=False, parent=None):
    mesh = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    for m in mats:
        mesh.materials.append(m)
    if smooth:
        for p in mesh.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, mesh)
    if parent:
        ob.parent = parent
    link(ob, coll)
    return ob


def _catmull(pts, n=8):
    pts = [Vector(p) for p in pts]
    P = [pts[0]] + pts + [pts[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(pts[-1])
    return out


def _bm_tube(bm, path, r, segs=8, mi=0):
    rings = []
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        u = t.cross(ref).normalized()
        w = t.cross(u).normalized()
        rings.append([bm.verts.new(p + (u * math.cos(a) + w * math.sin(a)) * r)
                      for a in (2 * math.pi * k / segs for k in range(segs))])
    for a, b in zip(rings, rings[1:]):
        for k in range(segs):
            bm.faces.new([a[k], a[(k + 1) % segs], b[(k + 1) % segs], b[k]]).material_index = mi


def _cable(p0, p1, sag, n=6):
    """Puntos de un cable que cuelga entre dos puntos."""
    p0, p1 = Vector(p0), Vector(p1)
    return [p0.lerp(p1, i / n) - Vector((0, 0, sag * math.sin(math.pi * i / n))) for i in range(n + 1)]


def _keys_interp(ob, path, keys, interp, index=-1):
    for f, v in keys:
        if index >= 0:
            getattr(ob, path)[index] = v
            ob.keyframe_insert(path, index=index, frame=f)
        else:
            setattr(ob, path, v)
            ob.keyframe_insert(path, frame=f)
    set_interp(ob, interp)


# --- galpon ---------------------------------------------------------------------

def build_galpon(e, colls):
    W, L, H, R = e.get("ancho", 10), e.get("largo", 20), e.get("alto", 6), e.get("cumbrera", 8)
    x0, x1, y0, y1 = -W / 2, W / 2, -L / 2, L / 2
    rng = random.Random(e.get("seed", 7))
    chapa = mat_chapa("chapa", e.get("zinc", "#7f8b96"), e.get("oxido", "#9a4a22"))
    acero = mat_toon("acero", e.get("acero", ACERO))
    piso = mat_piso("piso", e.get("piso", "#6e5a48"), e.get("piso_mancha", "#4e4038"))
    t = 0.06

    # muros y testeros (con hastial)
    bm = bmesh.new()
    _bm_box(bm, (x0 - t / 2, 0, H / 2), (t, L, H))
    _bm_box(bm, (x1 + t / 2, 0, H / 2), (t, L, H))
    for yy, s in ((y0, -1), (y1, 1)):
        q = [(x0, yy, 0), (x1, yy, 0), (x1, yy, H), (0, yy, R), (x0, yy, H)]
        top = [bm.verts.new(Vector(p)) for p in q]
        bot = [bm.verts.new(Vector(p) + Vector((0, s * t, 0))) for p in q]
        bm.faces.new(top if s < 0 else top[::-1])
        bm.faces.new(bot[::-1] if s < 0 else bot)
        for i in range(5):
            j = (i + 1) % 5
            bm.faces.new([top[i], bot[i], bot[j], top[j]] if s > 0 else [top[j], bot[j], bot[i], top[i]])
    _mesh_obj("galpon_muros", bm, [chapa], colls["main"])

    # techo: chapas de 1 m bajando por cada faldon; en la brecha (faldon
    # izquierdo) faltan o quedan arrancadas desde el alero
    ov = 0.35
    bm = bmesh.new()
    b0, b1 = e.get("brecha", [-6, 5])
    n = int(L)
    for side in (-1, 1):
        xe = side * (W / 2 + ov)
        ze = H - ov * (R - H) / (W / 2)
        for i in range(n):
            ya, yb = y0 + i, y0 + i + 1
            frac = 1.0
            if side < 0 and ya >= b0 and yb <= b1:
                frac = rng.choice([0.0, 0.0, 0.0, 0.18, 0.3])
                if frac == 0:
                    continue
            elif side > 0 and rng.random() < e.get("huecos", 0.08):
                frac = rng.uniform(0.5, 0.8)
            top_x = xe + (0 - xe) * frac
            top_z = ze + (R - ze) * frac
            q = [(xe, ya, ze), (xe, yb, ze), (top_x, yb, top_z), (top_x, ya, top_z)]
            if side > 0:
                q = q[::-1]
            _bm_quad_slab(bm, [(x, y, z + 0.13) for x, y, z in q], 0.03)
    ob = _mesh_obj("galpon_techo", bm, [chapa], colls["main"])
    ob.visible_shadow = e.get("sombra_techo", True)

    # estructura: cerchas, correas y columnas
    bm = bmesh.new()
    s = 0.13
    k = e.get("cerchas", 2.5)
    ys = [y0 + k * i for i in range(1, int(L / k))]
    for y in ys:
        _bm_beam(bm, (x0, y, H), (x1, y, H), s)
        _bm_beam(bm, (x0, y, H), (0, y, R), s)
        _bm_beam(bm, (x1, y, H), (0, y, R), s)
        _bm_beam(bm, (0, y, H), (0, y, R), s * 0.8)
        for side in (-1, 1):
            xm = side * W / 4
            _bm_beam(bm, (xm, y, H), (xm, y, H + (R - H) / 2), s * 0.6)
            _bm_beam(bm, (0, y, H), (xm, y, H + (R - H) / 2), s * 0.6)
            _bm_box(bm, (side * (W / 2 - 0.1), y, H / 2), (0.2, 0.22, H))
    for side in (-1, 1):
        for f in (0.0, 0.33, 0.66, 1.0):
            xc = side * (W / 2) * (1 - f)
            zc = H + (R - H) * f + 0.08
            _bm_beam(bm, (xc, y0, zc), (xc, y1, zc), 0.1)
    ob = _mesh_obj("galpon_estructura", bm, [acero], colls["main"])
    # en el plano de la sombra, el muro tiene que ser una pantalla limpia
    ob.visible_shadow = e.get("sombra_estructura", True)

    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    for v in bm.verts:
        v.co = Vector((v.co.x * (W + 1), v.co.y * (L + 1), 0))
    _mesh_obj("galpon_piso", bm, [piso], colls["main"])

    # el haz de sol que entra por la brecha: un prisma translucido desde la
    # brecha hasta donde pega (muro derecho o piso)
    if e.get("haz", True):
        d = sun_dir()
        pts = [(x0, b0, H), (x0, b1, H), (0, b1, R), (0, b0, R)]
        ends = []
        for p in pts:
            p = Vector(p)
            tt = min((x1 - p.x) / d.x if d.x > 0 else 1e9, p.z / -d.z)
            ends.append(p + d * tt)
        bm = bmesh.new()
        top = [bm.verts.new(Vector(p)) for p in pts]
        bot = [bm.verts.new(p) for p in ends]
        bm.faces.new(top)
        bm.faces.new(bot[::-1])
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new([top[j], top[i], bot[i], bot[j]])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        ob = _mesh_obj("haz_sol", bm, [mat_beam("haz", e.get("haz_color", "#ffd59a"),
                                                e.get("haz_alpha", 0.06))], colls["veil"])
        ob.visible_shadow = False


def build_polvo(e, colls):
    """Polvo y esporas de datos flotando en el haz. Una malla de octaedros
    chicos; la deriva es un shape key con valor lineal 0..1 (funcion del frame)."""
    e = {**ctx.CFG.get("galpon", {}), **e}      # medidas del galpon
    W, H, R = e.get("ancho", 10), e.get("alto", 6), e.get("cumbrera", 8)
    b0, b1 = e.get("brecha", [-6, 5])
    d = sun_dir()
    rng = random.Random(e.get("seed", 11))
    frames = ctx.CFG["frames"]
    secs = frames / ctx.CFG["fps"]
    for kind, color, strength, count, size in (
            ("polvo", e.get("color", "#ffe6c0"), e.get("strength", 0.7), e.get("n", 500), 0.012),
            ("esporas", e.get("esporas_color", "#ffb000"), 1.8, e.get("n_esporas", 70), 0.02)):
        bm = bmesh.new()
        offs = []
        for _ in range(count):
            fx = rng.random()
            p = Vector((-W / 2 * (1 - fx), rng.uniform(b0, b1), H + (R - H) * fx))
            tt = min((W / 2 - p.x) / d.x, p.z / -d.z)
            # lejos del techo: contra la chapa en sombra el polvo parecia estrellas
            c = p + d * (tt * rng.uniform(0.4, 0.97))
            if c.z > H - e.get("techo_libre", 2.5):
                continue
            s = size * rng.uniform(0.6, 1.3)
            vs = [bm.verts.new(c + Vector(o) * s) for o in
                  ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
            for a, b, cc in ((0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4),
                             (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)):
                bm.faces.new((vs[a], vs[b], vs[cc]))
            drift = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.4, 1.0))) * \
                rng.uniform(0.02, 0.07) * secs
            offs.extend([drift] * 6)
        ob = _mesh_obj(kind, bm, [mat_neon(kind, color, strength)], colls["neon"])
        ob.visible_shadow = False
        ob.shape_key_add(name="base")
        sk = ob.shape_key_add(name="deriva")
        for i, v in enumerate(sk.data):
            v.co = v.co + offs[i]
        sk.value = 0.0
        sk.keyframe_insert("value", frame=1)
        sk.value = 0.0 if e.get("quieto") else 1.0
        sk.keyframe_insert("value", frame=frames)
        set_interp(ob.data.shape_keys, "LINEAR")


# --- la radio de cobre --------------------------------------------------------

def build_radio(e, colls):
    """Rack de radio a valvulas atado con cables de cobre: dial, vumetros,
    tablero de clavijas, rejilla y valvulas arriba. Su par folklorico, el
    manipulador Morse de la estafeta, en un estante al frente."""
    at = Vector(e.get("at", (3.7, 0, 0)))
    yaw = math.radians(e.get("face", -90))
    root = bpy.data.objects.new("radio", None)
    root.location = at
    root.rotation_euler = (0, 0, yaw)
    link(root, colls["main"])

    cuerpo = mat_toon("radio_cuerpo", e.get("color", "#2f2a2e"))
    cobre = mat_toon("cobre", e.get("cobre", COBRE))
    oscuro = mat_toon("radio_oscuro", "#151219")
    madera = mat_toon("madera", "#6b4426")
    bm = bmesh.new()
    _bm_box(bm, (0, 0, 1.0), (1.0, 0.6, 2.0), 0)
    for sx in (-1, 1):
        _bm_box(bm, (sx * 0.47, -0.31, 1.0), (0.05, 0.03, 2.0), 1)
    _bm_box(bm, (0, -0.305, 0.88), (0.84, 0.02, 0.32), 1)          # tablero de clavijas
    for i in range(7):
        _bm_box(bm, (0, -0.305, 0.2 + i * 0.06), (0.8, 0.03, 0.022), 2)   # rejilla
    _bm_box(bm, (0, -0.33, 1.08), (0.6, 0.12, 0.03), 3)            # estante del manipulador
    _bm_box(bm, (0, 0, 2.02), (1.04, 0.64, 0.05), 1)
    for xx in (-0.3, -0.1, 0.1, 0.3):
        _bm_cyl(bm, (xx, -0.05, 2.07), 0.035, 0.04, mi=2)
    ob = _mesh_obj("radio_rack", bm, [cuerpo, cobre, oscuro, madera], colls["main"], parent=root)

    bm = bmesh.new()
    for row in range(2):
        for i in range(8):
            _bm_cyl(bm, (-0.315 + i * 0.09, -0.32, 0.95 - row * 0.13), 0.018, 0.02, axis="y", segs=10)
    _mesh_obj("radio_clavijas", bm, [oscuro], colls["main"], parent=root)

    # manipulador Morse: base de madera, palanca y perilla de bronce
    bm = bmesh.new()
    _bm_box(bm, (0, -0.34, 1.11), (0.22, 0.09, 0.03), 0)
    _bm_beam(bm, (0, -0.3, 1.14), (0, -0.4, 1.135), 0.02, 1)
    _bm_cyl(bm, (0, -0.41, 1.15), 0.022, 0.02, mi=1)
    _mesh_obj("morse", bm, [madera, cobre], colls["main"], parent=root)

    # lo que emite: dial, vumetros y valvulas (titilan erraticos)
    em = []
    dial = mat_neon("dial", e.get("dial", "#ffb347"), 1.3)
    bm = bmesh.new()
    _bm_box(bm, (0, -0.31, 1.72), (0.78, 0.02, 0.16))
    em.append(_mesh_obj("radio_dial", bm, [dial], colls["neon"], parent=root))
    vu = mat_neon("vumetro", e.get("vu", "#ffe7b5"), 1.0)
    bm = bmesh.new()
    for sx in (-1, 1):
        _bm_cyl(bm, (sx * 0.2, -0.31, 1.32), 0.11, 0.02, axis="y", segs=24)
    em.append(_mesh_obj("radio_vu", bm, [vu], colls["neon"], parent=root))
    valv = mat_neon("valvula", e.get("valvula", "#ff9d3c"), 1.6)
    bm = bmesh.new()
    for xx in (-0.3, -0.1, 0.1, 0.3):
        _bm_cyl(bm, (xx, -0.05, 2.17), 0.03, 0.16, segs=12)
    em.append(_mesh_obj("radio_valvulas", bm, [valv], colls["neon"], parent=root))
    # agujas (sin tinta: son trazos finos)
    bm = bmesh.new()
    _bm_box(bm, (0.12, -0.325, 1.72), (0.012, 0.01, 0.15))
    for sx in (-1, 1):
        _bm_beam(bm, (sx * 0.2, -0.325, 1.24), (sx * 0.2 + 0.05, -0.325, 1.39), 0.01)
    _mesh_obj("radio_agujas", bm, [mat_neon("aguja", "#7a1d10", 1.0, fog=False)], colls["neon"], parent=root)

    if e.get("erratico"):
        f0, f1 = e["erratico"]
        rng = random.Random(e.get("seed", 3))
        for ob in em:
            for f in range(f0, f1 + 1, 2):
                key_power(ob, f, rng.choice([1.0, 1.0, 0.85, 0.55, 0.25]))
            set_interp(ob, "CONSTANT")
    if e.get("latido"):
        # el nodo estabilizado: un golpe de luz por latido sobre una base tibia
        L = e["latido"]
        paso = round(ctx.CFG["fps"] * 60 / L.get("bpm", 60))
        for ob in em:
            # base -> golpe -> base: sin la clave de antes del golpe, la luz
            # subia en rampa todo el intervalo
            base = L.get("base", 0.6)
            for f in range(L["desde"], ctx.CFG["frames"] + 1, paso):
                for ff, v in ((f - 1, base), (f, 1.0), (f + 3, base)):
                    if ff >= 1:
                        key_power(ob, ff, v)
            set_interp(ob, "LINEAR")

    # cables de cobre: suben por detras al muro y corren hasta un aislador;
    # otros salen por abajo y se enroscan en el piso
    bm = bmesh.new()
    wall = e.get("muro", 1.0)        # distancia del dorso del rack al muro (y local)
    for i, dx in enumerate((-0.3, -0.18, -0.05, 0.08, 0.2, 0.33)):
        h = 3.2 + 0.25 * i
        path = [(dx, 0.2, 1.95), (dx, 0.35, 2.3), (dx * 0.6, wall - 0.12, 2.6 + 0.1 * i),
                (dx * 0.4 - 0.2, wall - 0.06, h), (-1.6 - 0.15 * i, wall - 0.06, h + 0.3 * math.sin(i))]
        _bm_tube(bm, _catmull(path, 6), 0.018 + 0.006 * (i % 2))
    for i in range(4):
        a = 0.6 * i
        path = [(-0.4 + 0.25 * i, -0.1, 0.25), (-0.5 + 0.2 * i, -0.45, 0.04),
                (-0.9 - 0.2 * i, -0.8 + 0.1 * math.sin(a), 0.03), (-1.4 - 0.3 * i, -0.4 - 0.4 * i, 0.03),
                (-2.2 - 0.2 * i, -1.2 - 0.2 * i, 0.03)]
        _bm_tube(bm, _catmull(path, 6), 0.022)
    _mesh_obj("radio_cables", bm, [cobre], colls["main"], smooth=True, parent=root)
    return root


# --- la torre que solo existe en la sombra -----------------------------------

def build_torre(e, colls):
    """Torre de transmision reticulada (como las antenas del cerro de San
    Antonio de los Cobres). Invisible a la camara: solo proyecta sombra. Crece
    desde el pie de la radio con claves de escala (CONSTANT: aparece a saltos,
    como un glitch)."""
    if "sombra" not in colls:
        colls["sombra"] = collection("sombra", "EXCLUDE")
    Ht = e.get("alto", 14.0)
    b = e.get("base", 1.6)
    top = b * 0.22
    zt = Ht * 0.78
    s = e.get("grosor", 0.09)
    bm = bmesh.new()

    def half(z):
        return (b + (top - b) * z / zt) / 2

    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    for cx, cy in corners:
        _bm_beam(bm, (cx * b / 2, cy * b / 2, 0), (cx * top / 2, cy * top / 2, zt), s)
    nseg = e.get("tramos", 9)
    for i in range(nseg):
        za, zb = zt * i / nseg, zt * (i + 1) / nseg
        ha, hb = half(za), half(zb)
        for k in range(4):
            c0, c1 = corners[k], corners[(k + 1) % 4]
            _bm_beam(bm, (c0[0] * hb, c0[1] * hb, zb), (c1[0] * hb, c1[1] * hb, zb), s * 0.8)
            _bm_beam(bm, (c0[0] * ha, c0[1] * ha, za), (c1[0] * hb, c1[1] * hb, zb), s * 0.6)
            _bm_beam(bm, (c1[0] * ha, c1[1] * ha, za), (c0[0] * hb, c0[1] * hb, zb), s * 0.6)
    # remate: mastiles de distinto alto, travesano con dipolos y dos parabolas
    for (dx, dy), h in zip(((0, 0), (-0.25, 0.1), (0.2, -0.1)), (Ht, Ht * 0.93, Ht * 0.88)):
        _bm_beam(bm, (dx, dy, zt), (dx, dy, h), s * 0.7)
    zc = zt + (Ht - zt) * 0.45
    _bm_beam(bm, (0, -1.1, zc), (0, 1.1, zc), s * 0.7)
    for yy in (-1.0, -0.5, 0.5, 1.0):
        _bm_beam(bm, (0, yy, zc - 0.4), (0, yy, zc + 0.4), s * 0.5)
    for zz, side in ((zt * 0.8, 1), (zt * 0.62, -1)):
        _bm_cyl(bm, (side * (half(zz) + 0.2), 0, zz), 0.32, 0.1, axis="x", segs=20)
    ob = _mesh_obj("torre_sombra", bm, [mat_toon("torre", "#000000")], colls["sombra"])
    ob.location = e.get("at", (3.7, 0, 0))
    ob.rotation_euler = (0, 0, math.radians(e.get("rot", 0)))
    ob.visible_camera = False
    ob.visible_diffuse = False
    ob.visible_glossy = False
    ob.visible_transmission = False
    ob.visible_volume_scatter = False
    for f, v in e.get("escala", [[1, 1.0]]):
        ob.scale = (v, v, v)
        ob.keyframe_insert("scale", frame=f)
    set_interp(ob, e.get("interp", "CONSTANT"))
    return ob


# --- drones ---------------------------------------------------------------------
# Los drones son cajas: aristas planas que la tinta marca limpio y se leen como
# maquinas. La personalidad sale de las opticas, la ceja y los paneles.

def _pose_root(root, e):
    """keys: [[frame, [x, y, z], yaw, alas]]. Flota: un vaiven chico sumado."""
    for k in e["keys"]:
        root.location = k[1]
        root.rotation_euler = (0, 0, math.radians(k[2]))
        root.keyframe_insert("location", frame=k[0])
        root.keyframe_insert("rotation_euler", frame=k[0])
    set_interp(root, "BEZIER")
    amp = e.get("vaiven", 0.015)
    if amp:
        fc = next(c for c in action_fcurves(root.animation_data.action)
                  if c.data_path == "location" and c.array_index == 2)
        mod = fc.modifiers.new("FNGENERATOR")
        mod.function_type = "SIN"
        mod.amplitude = amp
        mod.phase_multiplier = 2 * math.pi / (ctx.CFG["fps"] * e.get("periodo", 2.0))
        mod.use_additive = True


def build_nyx(e, colls):
    """Nyx, dron de escucha (lechuza vizcachera). Caja negra mate con una placa
    facial, dos opticas grandes en marcos cuadrados herrumbre con lente
    amarilla, ceja en V (la expresion), pico de cobre y dos paneles-ala con
    bisagra arriba. Sin rotores: flota sobre una tobera cuadrada tenue."""
    root = _dron_root("nyx", colls)
    negro = mat_dron("nyx_cuerpo", e.get("color", "#2b2933"), e.get("luz", 1.0))
    placa = mat_dron("nyx_placa", e.get("placa", "#4a4452"), e.get("luz", 1.0))
    herr = mat_dron("nyx_herrumbre", e.get("herrumbre", "#b7410e"), e.get("luz", 1.0))
    cobre = mat_dron("nyx_pico", COBRE, e.get("luz", 1.0))

    bm = bmesh.new()
    _bm_box(bm, (0, 0, 0), (0.36, 0.3, 0.32), 0)                    # cuerpo
    _bm_box(bm, (0, 0.02, 0.185), (0.3, 0.24, 0.05), 0)             # tapa
    _bm_box(bm, (0, 0.17, 0.0), (0.24, 0.04, 0.2), 0)               # mochila
    _bm_box(bm, (0, -0.16, 0.0), (0.32, 0.03, 0.27), 1)             # placa facial
    for sx in (-1, 1):
        _bm_box(bm, (sx * 0.075, -0.185, 0.025), (0.125, 0.04, 0.125), 2)   # marcos
    _bm_box(bm, (0, -0.19, -0.075), (0.05, 0.05, 0.04), 3)          # pico
    _bm_box(bm, (0, -0.205, -0.095), (0.03, 0.03, 0.03), 3)
    for sx in (-1, 1):                                                # ceja en V
        _bm_beam(bm, (sx * 0.01, -0.2, 0.1), (sx * 0.15, -0.2, 0.135), 0.024, 0)
    _bm_box(bm, (0, 0, -0.18), (0.16, 0.16, 0.04), 0)               # tobera
    _mesh_obj("nyx_cuerpo", bm, [negro, placa, herr, cobre], colls["main"])
    bpy.data.objects["nyx_cuerpo"].parent = root

    lente = mat_neon("nyx_lente", e.get("lente_color", "#ffc83d"), 1.4)
    bm = bmesh.new()
    for sx in (-1, 1):
        _bm_cyl(bm, (sx * 0.075, -0.206, 0.025), 0.045, 0.006, axis="y", segs=24)
    lens = _mesh_obj("nyx_lentes", bm, [lente], colls["neon"], parent=root)
    bm = bmesh.new()
    for sx in (-1, 1):
        _bm_box(bm, (sx * 0.075, -0.211, 0.025), (0.026, 0.006, 0.026))
    _mesh_obj("nyx_pupilas", bm, [mat_flat("nyx_pupila", TINTA)], colls["neon"], parent=root)

    # alas: paneles rectangulares con bisagra en el borde de arriba
    alas = []
    for sx in (-1, 1):
        piv = bpy.data.objects.new(f"nyx_ala_piv_{sx}", None)
        piv.parent = root
        piv.location = (sx * 0.195, 0.0, 0.14)
        link(piv, colls["main"])
        bm = bmesh.new()
        _bm_box(bm, (sx * 0.012, 0.0, -0.13), (0.024, 0.28, 0.26), 0)
        _bm_box(bm, (sx * 0.026, 0.0, -0.205), (0.008, 0.22, 0.03), 1)   # franja herrumbre
        _bm_cyl(bm, (0, 0, 0), 0.016, 0.3, axis="y", segs=8, mi=1)        # bisagra
        _mesh_obj(f"nyx_ala_{sx}", bm, [negro, herr], colls["main"], parent=piv)
        alas.append((piv, sx))

    bm = bmesh.new()
    _bm_box(bm, (0, 0, -0.202), (0.11, 0.11, 0.006))
    _mesh_obj("nyx_tobera", bm, [mat_neon("nyx_tobera", e.get("tobera", "#ff7a3a"), 0.9)],
              colls["neon"], parent=root)

    if e.get("venas"):
        # las aristas del cuerpo se encienden cuando la energia pasa por Nyx
        bm = bmesh.new()
        sx, sy, sz = 0.185, 0.155, 0.165
        cs = [Vector((x, y, z)) for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)]
        for a in range(8):
            for b in range(a + 1, 8):
                if sum(1 for i in range(3) if cs[a][i] != cs[b][i]) == 1:
                    _bm_beam(bm, cs[a], cs[b], 0.014)
        venas = _mesh_obj("nyx_venas", bm, [mat_neon("nyx_venas", "#ffb000", 1.8)], colls["neon"], parent=root)
        for f, v in e["venas"]:
            key_power(venas, f, v)
        set_interp(venas, "LINEAR")
    _pose_root(root, e)
    # alas: 0 pegadas al cuerpo, 1 abiertas 55 grados
    for k in e["keys"]:
        a = k[3] if len(k) > 3 else 0.0
        for piv, sx in alas:
            piv.rotation_euler = (0, sx * math.radians(-55 * a), 0)
            piv.keyframe_insert("rotation_euler", frame=k[0])
    for f, v in e.get("lente", []):
        key_power(lens, f, v)
    if e.get("lente"):
        set_interp(lens, "CONSTANT")

    if "cable" in e:
        # cable de interfaz del pico al tablero (quieto mientras esta
        # conectado: se arma con la ultima pose). "crece": [f0, f1] lo hace
        # salir del pico y avanzar hasta el tablero.
        k = e["keys"][-1]
        tip = Vector(k[1]) + Euler((0, 0, math.radians(k[2]))).to_matrix() @ Vector((0, -0.21, -0.1))
        pts = _cable(tip, e["cable"], e.get("comba", 0.12))
        RUTAS["cable"] = pts[::-1]          # del tablero al pico
        mat = mat_toon("cable", COBRE)
        if e.get("crece"):
            _cable_crece(tip, pts, *e["crece"], mat, colls)
        else:
            bm = bmesh.new()
            _bm_tube(bm, _catmull(pts, 4), 0.012)
            _mesh_obj("nyx_cable", bm, [mat], colls["main"], smooth=True)
    if "cable2" in e:
        # segundo cable, de la mochila a la abrazadera del poste (la tierra)
        k = e["keys"][-1]
        back = Vector(k[1]) + Euler((0, 0, math.radians(k[2]))).to_matrix() @ Vector((0, 0.19, -0.02))
        dest = Vector(e["cable2"].get("a") or RUTAS["abrazadera"])
        pts = _cable(back, dest, e["cable2"].get("comba", 0.3))
        RUTAS["cable2"] = pts
        if e["cable2"].get("crece"):
            _cable_crece(back, pts, *e["cable2"]["crece"], mat_toon("cable2", COBRE), colls,
                         nombre="nyx_cable2", ancla=True)
        else:
            bm = bmesh.new()
            _bm_tube(bm, _catmull(pts, 4), 0.012)
            _mesh_obj("nyx_cable2", bm, [mat_toon("cable2", COBRE)], colls["main"], smooth=True)
    return root


def _dron_root(name, colls, ancla=True):
    root = bpy.data.objects.new(name, None)
    root["ancla"] = ancla       # el glitch del post no lo toca (ver escena.py)
    link(root, colls["main"])
    return root


def build_aegis(e, colls):
    """Aegis, dron escudo. Caja pesada con los colores del poncho salteno
    (rojo con guardas negras y grecas ocre), visor de una sola ranura bajo una
    ceja recta (severo), dos toberas laterales. Su escudo es un telar: un
    marco que se despliega y la trama que se teje hilo por hilo.

        "aegis": {"keys": [[frame, [x, y, z], yaw]],
                  "escudo": {"desde": 10, "hilo": 1, "lado": 1.2, "hilos": 9, "dist": 0.6}}
    """
    root = _dron_root("aegis", colls, e.get("ancla", True))
    rojo = mat_dron("aegis_rojo", e.get("color", "#b3302a"), e.get("luz", 1.0))
    negro = mat_dron("aegis_negro", "#1f1c22", e.get("luz", 1.0))
    ocre = mat_dron("aegis_ocre", e.get("ocre", "#c99a3b"), e.get("luz", 1.0))
    bm = bmesh.new()
    _bm_box(bm, (0, 0, 0), (0.5, 0.42, 0.4), 0)                         # cuerpo
    for z in (-0.13, 0.13):                                              # guardas negras
        _bm_box(bm, (0, 0, z), (0.51, 0.43, 0.045), 1)
    for k in range(-3, 4):                                               # grecas
        _bm_box(bm, (k * 0.07, -0.218, -0.13), (0.022, 0.006, 0.022), 2)
    _bm_box(bm, (0, -0.225, 0.065), (0.36, 0.05, 0.1), 1)               # visor
    _bm_beam(bm, (-0.22, -0.25, 0.135), (0.22, -0.25, 0.135), 0.05, 1)  # ceja recta
    _bm_box(bm, (0, 0.02, 0.215), (0.38, 0.32, 0.03), 1)                # tapa
    for sx in (-1, 1):                                                   # toberas laterales
        _bm_box(bm, (sx * 0.31, 0, -0.02), (0.1, 0.26, 0.24), 1)
        _bm_box(bm, (sx * 0.31, 0, 0.11), (0.104, 0.264, 0.03), 2)
    _mesh_obj("aegis_cuerpo", bm, [rojo, negro, ocre], colls["main"], parent=root)
    bm = bmesh.new()
    _bm_box(bm, (0, -0.252, 0.065), (0.3, 0.006, 0.026))
    visor = _mesh_obj("aegis_visor", bm, [mat_neon("aegis_visor", e.get("visor", "#ffd27a"), 1.5)],
                      colls["neon"], parent=root)
    bm = bmesh.new()
    for sx in (-1, 1):
        _bm_box(bm, (sx * 0.31, 0, -0.143), (0.07, 0.2, 0.006))
    _mesh_obj("aegis_toberas", bm, [mat_neon("aegis_tobera", "#ff7a3a", 0.9)], colls["neon"], parent=root)
    for f, v in e.get("visor_power", []):
        key_power(visor, f, v)
    if e.get("escudo"):
        _telar(root, e["escudo"], ocre, colls)
    _pose_root(root, e)
    return root


def _scale_keys(ob, keys, axis_fn, interp):
    for f, v in keys:
        ob.scale = axis_fn(v)
        ob.keyframe_insert("scale", frame=f)
    set_interp(ob, interp)


def _telar(root, esc, ocre, colls):
    """El escudo-telar: marco ocre que se despliega y hilos de luz: primero
    la urdimbre (vertical, crece de abajo hacia arriba), despues la trama, que
    pasa por arriba y por abajo de cada hilo de urdimbre."""
    S = esc.get("lado", 1.2)
    n = esc.get("hilos", 9)
    f0 = esc.get("desde", 10)
    dt = esc.get("hilo", 1)
    h = S / 2
    piv = bpy.data.objects.new("telar", None)
    piv.parent = root
    piv.location = (0, -esc.get("dist", 0.6), esc.get("alto", 0.0))
    link(piv, colls["main"])
    bm = bmesh.new()
    for a, b in (((-h, 0, -h), (h, 0, -h)), ((h, 0, -h), (h, 0, h)),
                 ((h, 0, h), (-h, 0, h)), ((-h, 0, h), (-h, 0, -h))):
        _bm_beam(bm, a, b, 0.045)
    for sx in (-1, 1):
        for sz in (-1, 1):
            _bm_box(bm, (sx * h, 0, sz * h), (0.08, 0.08, 0.08))
    marco = _mesh_obj("telar_marco", bm, [ocre], colls["main"], parent=piv)
    _scale_keys(marco, ((1, 0.001), (f0, 0.001), (f0 + 3, 1.0)), lambda v: (v, v, v), "BEZIER")
    hilo = mat_neon("telar_hilo", esc.get("color", "#ff6a4a"), 1.2)
    f = f0 + 4
    xs = [-h + S * (i + 1) / (n + 1) for i in range(n)]
    for i, x in enumerate(xs):
        bm = bmesh.new()
        _bm_box(bm, (0, 0, S / 2), (0.014, 0.014, S))
        ob = _mesh_obj(f"urdimbre_{i}", bm, [hilo], colls["neon"], parent=piv)
        ob.location = (x, 0, -h)
        _scale_keys(ob, ((1, 0.001), (f, 0.001), (f + dt, 1.0)), lambda v: (1, 1, v), "LINEAR")
        f += dt
    for j in range(n):
        z = -h + S * (j + 1) / (n + 1)
        pts = [Vector((-h, 0, 0))]
        for i, x in enumerate(xs):
            pts.append(Vector((x, 0.018 * (1 if (i + j) % 2 else -1), 0)))
        pts.append(Vector((h, 0, 0)))
        bm = bmesh.new()
        _bm_tube(bm, pts, 0.007, 6)
        ob = _mesh_obj(f"trama_{j}", bm, [hilo], colls["neon"], parent=piv)
        ob.location = (-h, 0, z)
        for p in ob.data.vertices:          # que crezca desde el borde izquierdo
            p.co.x += h
        _scale_keys(ob, ((1, 0.001), (f, 0.001), (f + dt, 1.0)), lambda v: (v, 1, 1), "LINEAR")
        f += dt


def _espiral(c, ax, az, r0, turns=1.25, n=16):
    """Voluta de filete: espiral en el plano de una cara (ejes ax, az)."""
    pts = []
    for k in range(n + 1):
        t = k / n
        a = t * turns * 2 * math.pi
        r = r0 * (1 - 0.8 * t)
        pts.append(Vector(c) + Vector(ax) * (r * math.cos(a)) + Vector(az) * (r * math.sin(a)))
    return pts


def _bm_piramide(bm, c, r, depth, r2=0.0, mi=0):
    """Tronco de piramide de base cuadrada con las caras paralelas a x e y."""
    out = bmesh.ops.create_cone(bm, cap_ends=True, segments=4, radius1=r, radius2=r2, depth=depth)
    R = Euler((0, 0, math.pi / 4)).to_matrix()
    for v in out["verts"]:
        v.co = R @ v.co + Vector(c)
    for f in {f for v in out["verts"] for f in v.link_faces}:
        f.material_index = mi


def build_vesper(e, colls):
    """Vesper, dron de luz: un farol de querosen cuadrado. Postes y techo
    piramidal de hierro negro, vidrios que brillan, filete dorado (marco y
    volutas en cada vidrio), la llama adentro y un lente proyector abajo al
    frente. La expresion es la llama ("llama": claves de power)."""
    root = _dron_root("vesper", colls, e.get("ancla", True))
    hierro = mat_dron("vesper_hierro", "#24212a", e.get("luz", 1.0))
    oro = mat_dron("filete_oro", e.get("oro", "#d4a017"), e.get("luz", 1.0))
    w, hgt = 0.3, 0.36
    bm = bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            _bm_box(bm, (sx * w / 2, sy * w / 2, 0), (0.035, 0.035, hgt + 0.04))
    _bm_box(bm, (0, 0, -hgt / 2 - 0.03), (w + 0.06, w + 0.06, 0.05))
    _bm_piramide(bm, (0, 0, -hgt / 2 - 0.1), (w + 0.04) * 0.72, 0.09, r2=0.06)   # pie
    _bm_box(bm, (0, 0, hgt / 2 + 0.03), (w + 0.12, w + 0.12, 0.03))               # ala del techo
    _bm_piramide(bm, (0, 0, hgt / 2 + 0.125), (w + 0.06) * 0.72, 0.16, r2=0.03)  # techo
    _mesh_obj("vesper_hierro", bm, [hierro], colls["main"], parent=root)

    # filete: marco interior en cada vidrio, dos volutas y un rombo al centro
    bm = bmesh.new()
    ins = w / 2 - 0.035
    for k in range(4):
        R = Euler((0, 0, math.radians(90 * k))).to_matrix()
        fy = -w / 2 - 0.006
        ax, az = R @ Vector((1, 0, 0)), Vector((0, 0, 1))
        corners = [R @ Vector((sx * ins, fy, sz * (hgt / 2 - 0.035))) for sx, sz in
                   ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        for a, b in zip(corners, corners[1:] + corners[:1]):
            _bm_beam(bm, a, b, 0.009)
        for sx, sz in ((-1, 1), (1, -1)):
            c = R @ Vector((sx * (ins - 0.045), fy, sz * (hgt / 2 - 0.08)))
            _bm_tube(bm, _espiral(c, ax * -sx, az * -sz, 0.04), 0.006, 6)
        rombo = [R @ Vector(p) for p in ((0, fy, -0.03), (0.03, fy, 0), (0, fy, 0.03), (-0.03, fy, 0))]
        for a, b in zip(rombo, rombo[1:] + rombo[:1]):
            _bm_beam(bm, a, b, 0.008)
    top = hgt / 2 + 0.2
    _bm_tube(bm, _catmull([(0, 0, top), (-0.06, 0, top + 0.05), (0, 0, top + 0.11),
                           (0.06, 0, top + 0.05), (0, 0, top)], 4), 0.01, 6)       # argolla
    _mesh_obj("vesper_filete", bm, [oro], colls["main"], parent=root)

    vidrio = mat_neon("vesper_vidrio", e.get("vidrio", "#ffcf7a"), e.get("vidrio_strength", 0.45))
    bm = bmesh.new()
    _bm_box(bm, (0, 0, 0), (w - 0.004, w - 0.004, hgt - 0.01))
    vid = _mesh_obj("vesper_vidrio", bm, [vidrio], colls["neon"], parent=root)
    bm = bmesh.new()
    _bm_piramide(bm, (0, 0, -0.01), 0.05, 0.14)
    flame = _mesh_obj("vesper_llama", bm, [mat_neon("vesper_llama", e.get("llama_color", "#ffb000"), 2.2)],
                      colls["neon"], parent=root)
    bm = bmesh.new()
    _bm_cyl(bm, (0, -w / 2 - 0.04, -hgt / 2 - 0.03), 0.035, 0.03, axis="y", segs=16)
    lente = _mesh_obj("vesper_lente", bm, [mat_neon("vesper_lente", "#fff1c4", 1.6)],
                      colls["neon"], parent=root)
    for f, v in e.get("llama", []):
        for ob in (flame, vid, lente):
            key_power(ob, f, v)
    _pose_root(root, e)
    return root


def _cable_crece(tip, pts, f0, f1, mat, colls, nombre="nyx_cable", ancla=False):
    """Cable que sale del pico y avanza hasta el tablero: un tramo por frame
    (cada uno un objeto que aparece con escala CONSTANT; el origen en el pico,
    asi el tramo oculto queda colapsado adentro del dron)."""
    path = _catmull(pts, 4)
    acc = [0.0]
    for a, b in zip(path, path[1:]):
        acc.append(acc[-1] + (b - a).length)
    total = acc[-1]
    K = max(1, f1 - f0)
    for k in range(1, K + 1):
        L = total * k / K
        sub = [path[0]]
        for i in range(1, len(path)):
            if acc[i] <= L:
                sub.append(path[i])
            else:
                t = (L - acc[i - 1]) / (acc[i] - acc[i - 1])
                sub.append(path[i - 1].lerp(path[i], t))
                break
        if len(sub) < 2:
            continue
        bm = bmesh.new()
        _bm_tube(bm, [p - tip for p in sub], 0.012)
        ob = _mesh_obj(f"{nombre}_{k:02d}", bm, [mat], colls["main"], smooth=True)
        ob.location = tip
        ob["ancla"] = ancla
        fa = f0 + k
        fb = f0 + k + 1 if k < K else None
        keys = [(1, 0.001), (fa, 1.0)] + ([(fb, 0.001)] if fb else [])
        _scale_keys(ob, keys, lambda v: (v, v, v), "CONSTANT")


def _texto(name, body, size, mat, coll, parent, loc, font="C:/Windows/Fonts/consolab.ttf"):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    try:
        cu.font = bpy.data.fonts.load(font, check_existing=True)
    except RuntimeError:
        pass
    cu.size = size
    cu.align_x = "LEFT"
    cu.align_y = "CENTER"
    ob = bpy.data.objects.new(name, cu)
    ob.data.materials.append(mat)
    ob.parent = parent
    ob.location = loc
    link(ob, coll)
    return ob


def build_hud(e, colls):
    """HUD de un dron: placa holografica con marco de filete (volutas en las
    esquinas, en oro) y la orden en herrumbre, que se escribe de a una letra.
    El Verbo va cortado: solo la letra del fragmento, el resto en bloques.

        "hud": {"at": [x, y, z], "mira": [x, y, z], "desde": 8,
                "letra": "D", "bloques": 5, "resto": " /NODO_00",
                "cuenta": [[18, "3"], [30, "2"], [42, "1"]]}
    """
    # la placa queda en el mundo (en "at") y mira siempre a "mira" (la camara):
    # pegada al dron y vista de abajo se leia torcida y chica
    piv = bpy.data.objects.new("hud", None)
    piv.location = e["at"]
    link(piv, colls["neon"])
    mira = bpy.data.objects.new("hud_mira", None)
    mira.location = e["mira"]
    link(mira, colls["neon"])
    tc = piv.constraints.new("TRACK_TO")
    tc.target = mira
    tc.track_axis = "TRACK_Z"
    tc.up_axis = "UP_Y"
    f0 = e.get("desde", 8)
    texto = mat_neon("hud_texto", e.get("color", "#ff4a1c"), 1.25, fog=False)
    oro = mat_neon("hud_filete", e.get("filete", "#ffb000"), 1.2, fog=False)
    W, H = e.get("ancho", 1.08), e.get("alto", 0.52)

    # placa oscura translucida (sin tinta), para que el texto se lea
    bm = bmesh.new()
    _bm_box(bm, (0, 0, -0.004), (W, H, 0.004))
    # en una subcoleccion de main que solo ocluye: Line Art no la dibuja pero
    # deja de dibujar las cerchas que quedan detras de la placa
    if "oclusion" not in colls:
        colls["oclusion"] = bpy.data.collections.new("oclusion")
        colls["main"].children.link(colls["oclusion"])
        colls["oclusion"].lineart_usage = "OCCLUSION_ONLY"
    placa = _mesh_obj("hud_placa", bm, [mat_beam_placa()], colls["oclusion"], parent=piv)
    placa.visible_shadow = False

    # filete: borde, volutas en las cuatro esquinas y una filacteria abajo
    bm = bmesh.new()
    h, v = W / 2 - 0.03, H / 2 - 0.03
    corners = [Vector((-h, -v, 0)), Vector((h, -v, 0)), Vector((h, v, 0)), Vector((-h, v, 0))]
    for a, b in zip(corners, corners[1:] + corners[:1]):
        _bm_tube(bm, [a, b], 0.006, 6)
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        c = Vector((sx * (h - 0.05), sy * (v - 0.05), 0))
        _bm_tube(bm, _espiral(c, (-sx, 0, 0), (0, -sy, 0), 0.045), 0.005, 6)
    _bm_tube(bm, _catmull([(-0.16, -v + 0.06, 0), (-0.08, -v + 0.03, 0), (0, -v + 0.06, 0),
                           (0.08, -v + 0.03, 0), (0.16, -v + 0.06, 0)], 6), 0.004, 6)
    filete = _mesh_obj("hud_filete", bm, [oro], colls["neon"], parent=piv)
    objs = [placa, filete]
    for ob in objs:
        _scale_keys(ob, ((1, 0.001), (f0, 0.001), (f0 + 2, 1.0)), lambda s: (s, s, s), "CONSTANT")

    # la orden: letra del fragmento, bloques, resto (una pieza por frame)
    size = e.get("size", 0.085)
    adv = size * 0.55
    x = -h + 0.13             # lejos de la voluta de la esquina
    z = H / 2 - 0.13
    f = f0 + 3
    piezas = [("letra", e.get("letra", "D"))] + [("bloque", None)] * e.get("bloques", 5) + \
        [("resto", ch) for ch in e.get("resto", " /NODO_00")]
    for i, (kind, ch) in enumerate(piezas):
        if kind == "bloque":
            bm = bmesh.new()
            _bm_box(bm, (x + adv / 2, z, 0), (adv * 0.78, size * 0.7, 0.004))
            ob = _mesh_obj(f"hud_bloque_{i}", bm, [texto], colls["neon"], parent=piv)
        elif ch.strip():
            # la letra del fragmento, un poco mas grande que el resto
            ob = _texto(f"hud_c{i}", ch, size * (1.25 if kind == "letra" else 1.0), texto,
                        colls["neon"], piv, (x, z, 0))
        else:
            x += adv
            continue
        _scale_keys(ob, ((1, 0.001), (f, 0.001), (f + 1, 1.0)), lambda s: (s, s, s), "CONSTANT")
        x += adv
        f += 1

    # cuenta regresiva: un digito grande que cambia
    cuenta = e.get("cuenta", [])
    for j, (fc, digit) in enumerate(cuenta):
        ob = _texto(f"hud_cuenta_{j}", digit, size * 2.0, texto, colls["neon"], piv,
                    (-adv * 1.1, -0.04, 0))
        fend = cuenta[j + 1][0] if j + 1 < len(cuenta) else None
        keys = [(1, 0.001), (fc, 1.0)] + ([(fend, 0.001)] if fend else [])
        _scale_keys(ob, keys, lambda s: (s, s, s), "CONSTANT")
    return piv


def mat_beam_placa():
    from piezas.materiales import mat_tint
    return mat_tint("hud_placa", "#120a12", 0.78)


RUTAS = {}      # recorridos con nombre (cables, bajada a tierra) para los pulsos


def mat_quebracho(name, color="#6b3324", veta="#4a2116"):
    """Madera de quebracho colorado labrada a hacha: vetas largas verticales."""
    def albedo(nt):
        f = _m(nt, "GREATER_THAN", _noise(nt, 4.0, (6.0, 6.0, 0.25), 2.0), 0.58)
        return _mix(nt, f, color, veta)
    return mat_toon_albedo(name, albedo)


def build_poste(e, colls):
    """Poste de telegrafo de quebracho reusado como puntal del galpon (llega a
    la cercha). Cruceta con aisladores de loza, abrazadera de cobre de la
    puesta a tierra, bajada de cobre por la cara del poste y jabalina en el
    piso. Es el par folklorico de la puesta a tierra."""
    at = Vector(e.get("at", (3.4, -2.6, 0)))
    Hp = e.get("alto", 7.0)
    zc = e.get("abrazadera", 1.2)
    madera = mat_quebracho("quebracho")
    cobre = mat_toon("cobre_tierra", COBRE)
    loza = mat_toon("loza", "#e9e2d0")
    bm = bmesh.new()
    _bm_box(bm, (0, 0, Hp / 2), (0.22, 0.22, Hp), 0)
    _bm_box(bm, (0, 0, Hp - 1.3), (0.12, 1.3, 0.12), 0)          # cruceta (a lo largo de y)
    _bm_beam(bm, (0, -0.5, Hp - 1.36), (0, -0.05, Hp - 1.9), 0.06, 0)   # riostras
    _bm_beam(bm, (0, 0.5, Hp - 1.36), (0, 0.05, Hp - 1.9), 0.06, 0)
    for yy in (-0.55, -0.2, 0.2, 0.55):
        _bm_cyl(bm, (0, yy, Hp - 1.17), 0.04, 0.12, segs=10, mi=2)
        _bm_cyl(bm, (0, yy, Hp - 1.09), 0.055, 0.03, segs=10, mi=2)
    _bm_box(bm, (0, 0, zc), (0.26, 0.26, 0.07), 1)               # abrazadera
    _bm_box(bm, (-0.115, 0, zc / 2), (0.02, 0.04, zc), 1)        # bajada
    _bm_cyl(bm, (-0.2, 0, 0.12), 0.025, 0.24, segs=8, mi=1)      # jabalina
    _bm_beam(bm, (-0.115, 0, 0.02), (-0.2, 0, 0.02), 0.03, 1)
    ob = _mesh_obj("poste", bm, [madera, cobre, loza], colls["main"])
    ob.location = at
    ob.rotation_euler = (0, 0, math.radians(e.get("rot", 0)))
    R = Euler((0, 0, math.radians(e.get("rot", 0)))).to_matrix()
    RUTAS["tierra"] = [at + R @ Vector((-0.13, 0, zc)), at + R @ Vector((-0.13, 0, 0.03)),
                       at + R @ Vector((-0.2, 0, 0.03))]
    RUTAS["abrazadera"] = at + R @ Vector((-0.13, 0, zc))
    RUTAS["pie"] = at + R @ Vector((-0.2, 0, 0.0))
    return ob


def build_pulsos(e, colls):
    """Pulsos de energia que corren por un recorrido con nombre (RUTAS):
    [{"ruta": "cable", "de": f0, "a": f1, "n": 3, "inverso": false}]. Cada pulso es
    un rombo de luz con estela corta; es parte de lo que hace el ancla (no se
    congela)."""
    for j, p in enumerate(e):
        path = RUTAS[p["ruta"]]
        if p.get("inverso"):
            path = path[::-1]
        path = _catmull(path, 6) if len(path) > 2 else [Vector(path[0]).lerp(Vector(path[1]), t / 12)
                                                         for t in range(13)]
        acc = [0.0]
        for a, b in zip(path, path[1:]):
            acc.append(acc[-1] + (b - a).length)

        def at_len(L):
            for i in range(1, len(path)):
                if acc[i] >= L:
                    t = (L - acc[i - 1]) / max(1e-6, acc[i] - acc[i - 1])
                    return path[i - 1].lerp(path[i], t)
            return path[-1]

        mat = mat_neon(f"pulso_{j}", p.get("color", "#ffd060"), 2.4, fog=False)
        f0, f1 = p["de"], p["a"]
        n = p.get("n", 3)
        lag = p.get("separacion", 2)
        for k in range(n):
            bm = bmesh.new()
            s = p.get("size", 0.035)
            vs = [bm.verts.new(Vector(o) * s) for o in
                  ((1.6, 0, 0), (-1.6, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
            for a, b, c in ((0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4),
                            (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)):
                bm.faces.new((vs[a], vs[b], vs[c]))
            ob = _mesh_obj(f"pulso_{j}_{k}", bm, [mat], colls["neon"])
            ob["ancla"] = True
            ob.visible_shadow = False
            a0, a1 = f0 + k * lag, f1 + k * lag
            for f in range(a0, a1 + 1):
                ob.location = at_len(acc[-1] * (f - a0) / max(1, a1 - a0))
                ob.keyframe_insert("location", frame=f)
            _scale_keys(ob, [(1, 0.001), (a0, 1.0), (a1 + 1, 0.001)], lambda v: (v, v, v), "CONSTANT")
            set_interp(ob, "CONSTANT")


def build_descarga(e, colls):
    """El arco a tierra al pie del poste: rayos quebrados que cambian cada
    cuadro (frame .. frame+dur) y grietas de luz ambar que se abren en el piso
    y quedan latiendo."""
    f0 = e.get("frame", 44)
    dur = e.get("dur", 6)
    base = Vector(e.get("at") or RUTAS.get("pie", (3.2, -2.6, 0)))
    rng = random.Random(e.get("seed", 5))
    rayo = mat_neon("rayo", e.get("rayo", "#fff0c0"), 3.0, fog=False)
    for f in range(f0, f0 + dur):
        bm = bmesh.new()
        for _ in range(3):
            ang = rng.uniform(0, 2 * math.pi)
            r = rng.uniform(0.5, 1.1)
            end = base + Vector((math.cos(ang) * r, math.sin(ang) * r, 0.01))
            start = base + Vector((0, 0, rng.uniform(0.25, 0.6)))
            pts = [start]
            for k in range(1, 6):
                p = start.lerp(end, k / 6)
                pts.append(p + Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.5, 0.5))) * 0.08)
            pts.append(end)
            _bm_tube(bm, pts, 0.006, 5)
        ob = _mesh_obj(f"rayo_{f}", bm, [rayo], colls["neon"])
        ob["ancla"] = True
        ob.visible_shadow = False
        _scale_keys(ob, ([(1, 0.001)] if f > 1 else []) + [(f, 1.0), (f + 1, 0.001)],
                    lambda v: (v, v, v), "CONSTANT")
    grieta = mat_neon("grieta", e.get("grieta", "#ff9a1a"), 1.5, fog=False)
    bm = bmesh.new()
    for i in range(e.get("grietas", 9)):
        ang = 2 * math.pi * i / e.get("grietas", 9) + rng.uniform(-0.25, 0.25)
        pts = [Vector((0, 0, 0.012))]
        r = 0.0
        a = ang
        while r < e.get("radio", 1.1) * rng.uniform(0.6, 1.0):
            r += rng.uniform(0.12, 0.22)
            a += rng.uniform(-0.35, 0.35)
            pts.append(Vector((math.cos(a) * r, math.sin(a) * r, 0.012)))
        _bm_tube(bm, pts, 0.006, 4)
    ob = _mesh_obj("grietas", bm, [grieta], colls["neon"])
    ob.location = base
    ob["ancla"] = True
    ob.visible_shadow = False
    # con frame < 1 la descarga ya paso: las grietas estan abiertas desde el principio
    _scale_keys(ob, ([(1, 0.001)] if f0 > 1 else []) + [(f0, 0.05), (f0 + 6, 1.0)],
                lambda v: (v, v, 1), "LINEAR")
    for f, v in e.get("latido", [[f0, 1.0], [f0 + 8, 0.6], [f0 + 10, 0.9], [f0 + 14, 0.55]]):
        key_power(ob, f, v)


# Ruta 40 (lat, lon), de La Quiaca a Cabo Virgenes: el gemelo de la Ruta 404
RUTA_40 = [(-22.1, -65.6), (-24.2, -66.3), (-26.07, -65.97), (-27.65, -67.03), (-29.16, -67.5),
           (-30.24, -68.75), (-32.9, -68.85), (-35.47, -69.58), (-37.38, -70.27), (-38.9, -70.06),
           (-41.13, -71.3), (-42.9, -71.32), (-46.6, -70.93), (-49.6, -71.45), (-50.34, -72.26),
           (-51.62, -69.22), (-52.33, -68.35)]
SAN_ANTONIO = (-24.2, -66.3)


def _orientar(ob, at, mira):
    """Matriz de mundo con +z local mirando a 'mira' y +y local hacia arriba."""
    at, mira = Vector(at), Vector(mira)
    z = (mira - at).normalized()
    x = Vector((0, 0, 1)).cross(z).normalized()
    y = z.cross(x)
    from mathutils import Matrix
    M = Matrix((x, y, z)).transposed().to_4x4()
    M.translation = at
    ob.matrix_world = M
    return M


def _marco_filete(bm, W, H, filacteria=True):
    """Borde, volutas en las cuatro esquinas y una filacteria abajo (plano XY)."""
    h, v = W / 2 - 0.03, H / 2 - 0.03
    corners = [Vector((-h, -v, 0)), Vector((h, -v, 0)), Vector((h, v, 0)), Vector((-h, v, 0))]
    for a, b in zip(corners, corners[1:] + corners[:1]):
        _bm_tube(bm, [a, b], 0.006, 6)
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        c = Vector((sx * (h - 0.05), sy * (v - 0.05), 0))
        _bm_tube(bm, _espiral(c, (-sx, 0, 0), (0, -sy, 0), 0.045), 0.005, 6)
    if filacteria:
        _bm_tube(bm, _catmull([(-0.16, -v + 0.06, 0), (-0.08, -v + 0.03, 0), (0, -v + 0.06, 0),
                               (0.08, -v + 0.03, 0), (0.16, -v + 0.06, 0)], 6), 0.004, 6)


def _oclusion(colls):
    if "oclusion" not in colls:
        colls["oclusion"] = bpy.data.collections.new("oclusion")
        colls["main"].children.link(colls["oclusion"])
        colls["oclusion"].lineart_usage = "OCCLUSION_ONLY"
    return colls["oclusion"]


def build_mapa(e, colls):
    """El mapa que proyecta Vesper: placa holografica con marco de filete, la
    Ruta 404 (el sur en cian, el norte en ambar), los relevos y el NODO 0 en
    San Antonio de los Cobres: titila en herrumbre (falla) hasta "luz_mala",
    y ahi se vuelve una luz mala ambar con halo y fuegos que la orbitan. Un
    cono de luz une el lente de Vesper con la placa.

        "mapa": {"at": [x, y, z], "mira": [x, y, z], "ancho": 0.8, "alto": 1.25,
                 "luz_mala": 30, "de": "vesper"}
    """
    W, H = e.get("ancho", 0.8), e.get("alto", 1.25)
    piv = bpy.data.objects.new("mapa", None)
    link(piv, colls["neon"])
    M = _orientar(piv, e["at"], e["mira"])
    F = e.get("luz_mala", 30)
    ap = e.get("aparece")

    bm = bmesh.new()
    _bm_box(bm, (0, 0, -0.004), (W, H, 0.004))
    placa = _mesh_obj("mapa_placa", bm, [mat_tint("mapa_placa", "#0c0a14", 0.7)], _oclusion(colls), parent=piv)
    placa.visible_shadow = False
    bm = bmesh.new()
    _marco_filete(bm, W, H)
    _mesh_obj("mapa_filete", bm, [mat_neon("mapa_filete", "#ffb000", 1.1, fog=False)], colls["neon"], parent=piv)

    # proyeccion de lat/lon a la placa
    lat0, lat1 = -21.0, -53.5
    lon_c = -68.9
    k = (H - 0.24) / (lat0 - lat1)

    def P(lat, lon):
        return Vector(((lon - lon_c) * k * 0.85 * 1.9, (lat - (lat0 + lat1) / 2) * k - 0.02, 0.006))

    pts = _catmull([P(*p) for p in RUTA_40], 4)
    corte = P(-40.0, -70)[1]
    norte = [p for p in pts if p.y >= corte]
    sur = [p for p in pts if p.y <= corte + 0.02]
    for name, tramo, col in (("mapa_norte", norte, "#ffb000"), ("mapa_sur", sur, "#00e5ff")):
        bm = bmesh.new()
        _bm_tube(bm, tramo, 0.007, 6)
        _mesh_obj(name, bm, [mat_neon(name, col, 1.4, fog=False)], colls["neon"], parent=piv)
    bm = bmesh.new()
    for lat, lon in RUTA_40[2::2]:
        c = P(lat, lon)
        _bm_box(bm, (c.x + 0.025, c.y, c.z), (0.012, 0.012, 0.004))
    _mesh_obj("mapa_relevos", bm, [mat_neon("mapa_relevo", "#ffd27a", 0.9, fog=False)], colls["neon"], parent=piv)
    titulo = mat_neon("mapa_texto", "#ffb000", 1.2, fog=False)
    _texto("mapa_titulo", "RUTA 404", 0.066, titulo, colls["neon"], piv, (-W / 2 + 0.11, H / 2 - 0.1, 0.006))

    nodo = P(*SAN_ANTONIO)
    # el nodo en falla: rombo herrumbre que titila
    bm = bmesh.new()
    _bm_box(bm, nodo, (0.028, 0.028, 0.004))
    falla = _mesh_obj("mapa_falla", bm, [mat_neon("mapa_falla", "#ff3a14", 1.6, fog=False)],
                      colls["neon"], parent=piv)
    for f in range(1, F, 2):
        key_power(falla, f, 1.0 if (f // 2) % 2 == 0 else 0.15)
    set_interp(falla, "CONSTANT")
    _scale_keys(falla, ((1, 1.0), (F, 0.001)), lambda v: (v, v, v), "CONSTANT")

    # la luz mala: orbe, halo que respira y tres fuegos que la orbitan
    ambar = mat_neon("luz_mala", e.get("color", "#ffb000"), 2.6, fog=False)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.032)
    orbe = _mesh_obj("luz_mala", bm, [ambar], colls["neon"], parent=piv)
    orbe.location = nodo + Vector((0, 0, 0.03))
    _scale_keys(orbe, ((1, 0.001), (F, 0.3), (F + 2, 1.4), (F + 4, 1.0)), lambda v: (v, v, v), "BEZIER")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.09)
    halo = _mesh_obj("luz_mala_halo", bm, [mat_tint("luz_mala_halo", "#ffb000", 0.22)], colls["veil"], parent=piv)
    halo.location = orbe.location
    halo.visible_shadow = False
    frames = ctx.CFG["frames"]
    keys = [(1, 0.001), (F, 0.001)]
    for f in range(F + 2, frames + 1, 6):
        keys.append((f, 1.0 if ((f - F) // 6) % 2 == 0 else 0.75))
    _scale_keys(halo, keys, lambda v: (v, v, v), "BEZIER")
    for j in range(3):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=0.009)
        ob = _mesh_obj(f"fuego_{j}", bm, [ambar], colls["neon"], parent=piv)
        for f in range(1, frames + 1):
            a = 2 * math.pi * (j / 3 + (f - F) / 30)
            r = 0.07 + 0.012 * math.sin(f * 0.7 + j)
            ob.location = orbe.location + Vector((math.cos(a) * r, math.sin(a) * r * 0.7, 0.01 * j))
            ob.keyframe_insert("location", frame=f)
        set_interp(ob, "LINEAR")
        _scale_keys(ob, ((1, 0.001), (F + 3 + 2 * j, 1.0)), lambda v: (v, v, v), "CONSTANT")
    _texto("mapa_nodo", "NODO 0", 0.044, titulo, colls["neon"], piv, nodo + Vector((0.055, -0.012, 0)))

    # el cono de luz desde el lente de Vesper hasta las esquinas de la placa
    de = e.get("de")
    if de and de in bpy.data.objects:
        root = bpy.data.objects[de]
        k0 = ctx.CFG[de]["keys"][0]
        lens = Vector(k0[1]) + Euler((0, 0, math.radians(k0[2]))).to_matrix() @ Vector((0, -0.19, -0.21))
        cs = [M @ Vector((sx * W / 2, sy * H / 2, 0)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        bm = bmesh.new()
        tip = bm.verts.new(lens)
        vs = [bm.verts.new(c) for c in cs]
        for i in range(4):
            bm.faces.new((tip, vs[i], vs[(i + 1) % 4]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        cono = _mesh_obj("mapa_cono", bm, [mat_beam("mapa_cono", "#ffd59a", e.get("cono_alpha", 0.15))], colls["veil"])
        cono.visible_shadow = False
        del root
        if ap:
            for f, v in ((1, 0.0), (ap[0], 0.0), (ap[0] + 2, 1.0)):
                key_power(cono, f, v)
            set_interp(cono, "CONSTANT")

    med = e.get("medidor")
    if med:
        # medidor fileteado: semicirculo de oro, zona roja al final y la aguja
        # herrumbre que sube hasta clavarse en el maximo (consume sin procesar)
        c = Vector((W / 2 - 0.17, -H / 2 + 0.2, 0.006))
        r = 0.1
        bm = bmesh.new()
        arco = [c + Vector((math.cos(a) * r, math.sin(a) * r, 0)) for a in
                (math.pi * (1 - k / 16) for k in range(17))]
        _bm_tube(bm, arco, 0.005, 6)
        for k in range(7):
            a = math.pi * (1 - k / 6)
            d = Vector((math.cos(a), math.sin(a), 0))
            _bm_tube(bm, [c + d * (r * 0.78), c + d * r], 0.004, 4)
        _mesh_obj("medidor", bm, [mat_neon("medidor", "#ffb000", 1.1, fog=False)], colls["neon"], parent=piv)
        bm = bmesh.new()
        roja = [c + Vector((math.cos(a) * r * 1.12, math.sin(a) * r * 1.12, 0)) for a in
                (math.pi * 0.22 * (1 - k / 6) for k in range(7))]
        _bm_tube(bm, roja, 0.007, 6)
        _mesh_obj("medidor_rojo", bm, [mat_neon("medidor_rojo", "#ff3a14", 1.6, fog=False)], colls["neon"], parent=piv)
        aguja = bpy.data.objects.new("aguja_piv", None)
        aguja.parent = piv
        aguja.location = c
        link(aguja, colls["neon"])
        bm = bmesh.new()
        _bm_box(bm, (r * 0.45, 0, 0.004), (r * 0.9, 0.008, 0.004))
        _bm_cyl(bm, (0, 0, 0.004), 0.012, 0.006, segs=10)
        _mesh_obj("aguja", bm, [mat_neon("aguja_h", "#ff4a1c", 1.8, fog=False)], colls["neon"], parent=aguja)
        f0 = med.get("desde", 18)
        rng = random.Random(9)
        keys = [(1, 170), (f0, 170), (f0 + 8, 20), (f0 + 10, 30)]
        f = f0 + 12
        while f <= ctx.CFG["frames"]:
            keys.append((f, rng.uniform(8, 24)))
            f += 3
        for ff, ang in keys:
            aguja.rotation_euler = (0, 0, math.radians(ang))
            aguja.keyframe_insert("rotation_euler", frame=ff)
        set_interp(aguja, "BEZIER")
    if ap:
        # la proyeccion se abre: la placa crece desde el centro
        for f, v in ((1, 0.001), (ap[0], 0.001), (ap[1], 1.0)):
            piv.scale = (v, v, v)
            piv.keyframe_insert("scale", frame=f)
        set_interp(piv, "BEZIER")
    return piv


# --- exterior: San Antonio de los Cobres ----------------------------------------
# El galpon queda donde esta (origen); la via pasa del lado del sol (x < 0), el
# pueblo y el cerro de las antenas hacia +x, como en la foto de referencia.

def _altura_puna(x, y, e):
    """Estepa: plana alrededor del galpon y del pueblo, ondulada lejos."""
    from mathutils import noise
    r = math.hypot(x, y)
    amp = max(0.0, min(1.0, (r - e.get("llano", 140)) / 260)) * e.get("ondas", 30)
    return amp * (noise.noise(Vector((x / 180, y / 180, 0.3))) + 0.35) - 0.05


def build_puna(e, colls):
    """Suelo de la Puna (ocre con manchones), ichu cerca de camara y una
    serrania baja que cierra el horizonte."""
    def albedo(nt):
        f = _m(nt, "GREATER_THAN", _noise(nt, 0.04, (1, 1, 1), 3.0), 0.55)
        g = _m(nt, "GREATER_THAN", _noise(nt, 0.4, (1, 1, 1), 2.0), 0.62)
        c = _mix(nt, f, e.get("color", "#a88458"), e.get("mancha", "#8d6c47"))
        return _mix(nt, _m(nt, "MULTIPLY", g, 0.5), c, e.get("piedra", "#6f5a48"))
    suelo = mat_toon_albedo("puna", albedo)
    S, n = e.get("tam", 1400), e.get("res", 140)
    bm = bmesh.new()
    rows = []
    for j in range(n + 1):
        row = []
        for i in range(n + 1):
            x, y = -S / 2 + S * i / n, -S / 2 + S * j / n
            row.append(bm.verts.new((x, y, _altura_puna(x, y, e))))
        rows.append(row)
    for j in range(n):
        for i in range(n):
            bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
    _mesh_obj("puna", bm, [suelo], colls["main"], smooth=True)

    # ichu: matas de pajas finas (sin tinta: a esta escala la linea las empasta)
    rng = random.Random(e.get("seed", 21))
    x0, x1, y0, y1 = e.get("ichu_zona", [-60, 0, -60, 30])
    bm = bmesh.new()
    for _ in range(e.get("ichu", 500)):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        if -12 < x < 7 and -12 < y < 12:      # ni en la via ni pegado al galpon
            continue
        z = _altura_puna(x, y, e)
        for _ in range(rng.randint(5, 8)):
            a = rng.uniform(0, 2 * math.pi)
            lean = rng.uniform(0.1, 0.35)
            h = rng.uniform(0.35, 0.6)
            base = Vector((x + rng.uniform(-0.12, 0.12), y + rng.uniform(-0.12, 0.12), z))
            tip = base + Vector((math.cos(a) * lean, math.sin(a) * lean, h))
            side = Vector((-math.sin(a), math.cos(a), 0)) * 0.03
            vs = [bm.verts.new(base - side), bm.verts.new(base + side), bm.verts.new(tip)]
            bm.faces.new(vs)
    ob = _mesh_obj("ichu", bm, [mat_toon("ichu", e.get("ichu_color", "#c9a35a"))], colls["veil"])
    ob.visible_shadow = False

    # serrania del horizonte: una banda dentada lejos, que la niebla aplana
    R = e.get("serrania_r", 650)
    bm = bmesh.new()
    segs = 160
    top, bot = [], []
    for k in range(segs):
        a = 2 * math.pi * k / segs
        h = 35 + 30 * math.sin(3 * a + 1.0) + 18 * math.sin(7 * a) + 9 * math.sin(17 * a + 2)
        p = Vector((math.cos(a) * R, math.sin(a) * R, 0))
        top.append(bm.verts.new(p + Vector((0, 0, max(12, h)))))
        bot.append(bm.verts.new(p - Vector((0, 0, 30))))
    for k in range(segs):
        m = (k + 1) % segs
        bm.faces.new((bot[k], bot[m], top[m], top[k]))
    ob = _mesh_obj("serrania", bm, [mat_toon("serrania", e.get("serrania", "#7a5f5a"))], colls["main"])
    ob.visible_shadow = False


def build_via(e, colls):
    """Via del Ramal C14 (trocha angosta) con durmientes de quebracho y la linea
    de telegrafo al costado: postes de quebracho con cruceta y aisladores y
    cables que cuelgan."""
    xv = e.get("x", -9.5)
    y0, y1 = e.get("de", -220), e.get("a", 220)
    acero = mat_toon("riel", "#5a5560")
    madera = mat_quebracho("durmiente")
    balasto = mat_toon("balasto", "#7c726a")
    bm = bmesh.new()
    _bm_box(bm, (xv, (y0 + y1) / 2, 0.08), (3.2, y1 - y0, 0.16), 2)
    y = y0
    while y < y1:
        _bm_box(bm, (xv, y, 0.2), (2.0, 0.22, 0.12), 1)
        y += 0.7
    for dx in (-0.5, 0.5):
        _bm_box(bm, (xv + dx, (y0 + y1) / 2, 0.31), (0.07, y1 - y0, 0.1), 0)
    _mesh_obj("via", bm, [acero, madera, balasto], colls["main"])

    xp = xv - e.get("linea_dx", 3.5)
    paso = e.get("paso", 30)
    hp = 7.0
    bm = bmesh.new()
    tops = []
    y = y0
    while y <= y1:
        _bm_box(bm, (xp, y, hp / 2), (0.22, 0.22, hp))
        _bm_box(bm, (xp, y, hp - 0.5), (1.3, 0.12, 0.12))
        tops.append([Vector((xp + dx, y, hp - 0.38)) for dx in (-0.55, -0.2, 0.2, 0.55)])
        y += paso
    _mesh_obj("telegrafo", bm, [madera], colls["main"])
    bm = bmesh.new()
    for a, b in zip(tops, tops[1:]):
        for pa, pb in zip(a, b):
            _bm_tube(bm, _cable(pa, pb, 0.7, 10), 0.025, 4)
    ob = _mesh_obj("hilos", bm, [mat_flat("hilos", "#1d1820")], colls["veil"])
    ob.visible_shadow = False


def build_pueblo(e, colls):
    """Casas bajas de San Antonio de los Cobres: adobe, ladrillo a la vista,
    alguna pintada (la rosa de la foto), techos de chapa casi planos, tanques
    de agua negros, puertas y ventanas oscuras."""
    rng = random.Random(e.get("seed", 33))
    x0, x1, y0, y1 = e.get("zona", [22, 120, -90, 90])
    paredes = e.get("colores", ["#9b6b4a", "#a0522d", "#b9937a", "#8e7766", "#d9cfc0", "#e07aa8"])
    mats = [mat_toon(f"casa_{i}", c) for i, c in enumerate(paredes)]
    techo = mat_chapa("chapa_casa", "#8a949e", "#7d4630", pitch=0.3)
    oscuro = mat_toon("vano", "#241c22")
    tanque = mat_toon("tanque", "#1f1d22")
    nm = len(mats)
    bm = bmesh.new()
    casas = []
    for _ in range(e.get("n", 46)):
        for _try in range(20):
            cx, cy = rng.uniform(x0, x1), rng.uniform(y0, y1)
            w, d = rng.uniform(5, 10), rng.uniform(6, 11)
            if all(abs(cx - a) > (w + aw) / 2 + 2 or abs(cy - b) > (d + ad) / 2 + 2
                   for a, b, aw, ad in casas):
                break
        casas.append((cx, cy, w, d))
        h = rng.uniform(2.6, 3.3) * (1.8 if rng.random() < 0.15 else 1.0)
        mi = rng.choices(range(nm), weights=[5, 4, 3, 3, 2, 1][:nm])[0]
        _bm_box(bm, (cx, cy, h / 2), (w, d, h), mi)
        q = [(cx - w / 2 - 0.2, cy - d / 2 - 0.2, h + 0.15), (cx + w / 2 + 0.2, cy - d / 2 - 0.2, h - 0.15),
             (cx + w / 2 + 0.2, cy + d / 2 + 0.2, h - 0.15), (cx - w / 2 - 0.2, cy + d / 2 + 0.2, h + 0.15)]
        _bm_quad_slab(bm, [(x, y, z + 0.06) for x, y, z in q], 0.06, nm)
        _bm_box(bm, (cx - w / 2 - 0.02, cy + rng.uniform(-d / 4, d / 4), 1.0), (0.06, 0.9, 2.0), nm + 1)
        for k in range(rng.randint(1, 2)):
            _bm_box(bm, (cx - w / 2 - 0.02, cy + rng.uniform(-d / 2.5, d / 2.5), h * 0.6),
                    (0.06, 0.8, 0.7), nm + 1)
        if rng.random() < 0.35:
            _bm_cyl(bm, (cx + rng.uniform(-w / 4, w / 4), cy, h + 0.9), 0.55, 1.3, segs=12, mi=nm + 2)
    _mesh_obj("pueblo", bm, mats + [techo, oscuro, tanque], colls["main"])


def _torre_mesh(bm, Ht, b, s, nseg=9, antenas=True):
    """Torre reticulada (piramide truncada de cuatro patas con riostras en X)."""
    top = b * 0.22
    zt = Ht * (0.78 if antenas else 1.0)

    def half(z):
        return (b + (top - b) * z / zt) / 2

    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    for cx, cy in corners:
        _bm_beam(bm, (cx * b / 2, cy * b / 2, 0), (cx * top / 2, cy * top / 2, zt), s)
    for i in range(nseg):
        za, zb = zt * i / nseg, zt * (i + 1) / nseg
        ha, hb = half(za), half(zb)
        for k in range(4):
            c0, c1 = corners[k], corners[(k + 1) % 4]
            _bm_beam(bm, (c0[0] * hb, c0[1] * hb, zb), (c1[0] * hb, c1[1] * hb, zb), s * 0.8)
            _bm_beam(bm, (c0[0] * ha, c0[1] * ha, za), (c1[0] * hb, c1[1] * hb, zb), s * 0.6)
            _bm_beam(bm, (c1[0] * ha, c1[1] * ha, za), (c0[0] * hb, c0[1] * hb, zb), s * 0.6)
    if antenas:
        for (dx, dy), h in zip(((0, 0), (-0.25 * b, 0.1 * b), (0.2 * b, -0.1 * b)), (Ht, Ht * 0.93, Ht * 0.88)):
            _bm_beam(bm, (dx, dy, zt), (dx, dy, h), s * 0.7)
    return zt


def _altura_cerro(x, y, e):
    from mathutils import noise
    z = 0.0
    for cx, cy, h, rx, ry in e["lomas"]:
        z += h * math.exp(-(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2))
    # lomas con aristas: ruido ridged sumado, no un domo liso
    rid = 1 - abs(noise.noise(Vector((x / 55, y / 70, 3.1))))
    return z * (0.85 + 0.25 * rid + 0.1 * noise.noise(Vector((x / 25, y / 25, 1.7)))) - 2.0


def build_cerro(e, colls):
    """El cerro del pueblo (foto de referencia): dos lomas, la de atras ocre
    rojiza; el via crucis de capillitas blancas en zigzag por la de adelante,
    una capilla, y arriba las antenas repetidoras (con balizas rojas de noche).

        "cerro": {"lomas": [[cx, cy, alto, rx, ry], ...], "antenas": 4,
                  "balizas": {"periodo": 24, "fase": 0}}
    """
    def albedo(nt):
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        sp = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(geo.outputs["Position"], sp.inputs[0])
        alto = _m(nt, "GREATER_THAN", _m(nt, "ADD", sp.outputs[2],
                                         _m(nt, "MULTIPLY", _noise(nt, 0.05, (1, 1, 1), 2.0), 30)),
                  e.get("ocre_desde", 70))
        c = _mix(nt, alto, e.get("bajo", "#7b6555"), e.get("ocre", "#b5653b"))
        surco = _m(nt, "GREATER_THAN", _noise(nt, 0.08, (1, 1, 0.15), 2.0), 0.6)
        return _mix(nt, _m(nt, "MULTIPLY", surco, 0.35), c, "#3a2a2a")
    mat = mat_toon_albedo("cerro", albedo)
    x0, x1, y0, y1 = e.get("zona", [60, 420, -200, 220])
    n = e.get("res", 90)
    bm = bmesh.new()
    rows = []
    for j in range(n + 1):
        row = []
        for i in range(n + 1):
            x, y = x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * j / n
            row.append(bm.verts.new((x, y, _altura_cerro(x, y, e))))
        rows.append(row)
    for j in range(n):
        for i in range(n):
            bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
    _mesh_obj("cerro", bm, [mat], colls["main"], smooth=True)

    # via crucis: capillitas blancas en zigzag por la loma de adelante, y la capilla
    blanco = mat_toon("cal", "#ece6da")
    bm = bmesh.new()
    lx, ly, lh = e["lomas"][1][:3] if len(e["lomas"]) > 1 else e["lomas"][0][:3]
    for k in range(e.get("estaciones", 10)):
        t = k / max(1, e.get("estaciones", 10) - 1)
        x = lx - 70 + 60 * t
        y = ly - 30 + (28 if k % 2 else -8) + 20 * t
        z = _altura_cerro(x, y, e)
        _bm_box(bm, (x, y, z + 1.0), (1.4, 1.4, 2.4))
        _bm_piramide(bm, (x, y, z + 2.5), 1.05, 0.7)
    cx, cy = e.get("capilla", (lx - 12, ly + 18))
    z = _altura_cerro(cx, cy, e)
    _bm_box(bm, (cx, cy, z + 2.5), (6, 9, 6))
    _bm_piramide(bm, (cx, cy, z + 6.6), 5.6, 2.6, r2=0.4)
    _bm_box(bm, (cx, cy - 4.8, z + 5), (2.2, 2.2, 10))
    _mesh_obj("via_crucis", bm, [blanco], colls["main"])

    # antenas en la cumbre de la loma alta
    hx, hy = e["lomas"][0][:2]
    acero = mat_toon("antena", "#d9d4cc")
    bm = bmesh.new()
    rng = random.Random(4)
    puntas = []
    for k in range(e.get("antenas", 4)):
        ax, ay = hx + rng.uniform(-30, 30), hy + rng.uniform(-35, 35)
        az = _altura_cerro(ax, ay, e)
        Ht = rng.uniform(32, 46)
        sub = bmesh.new()
        _torre_mesh(sub, Ht, 3.6, 0.6, nseg=7)
        for v in sub.verts:
            v.co += Vector((ax, ay, az - 0.5))
        me = bpy.data.meshes.new("tmp")
        sub.to_mesh(me)
        sub.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        puntas.append(Vector((ax, ay, az - 0.5 + Ht)))
        _bm_box(bm, (ax + 6, ay, az + 1.2), (5, 4, 3))
    _mesh_obj("antenas", bm, [acero], colls["main"])
    if e.get("balizas"):
        B = e["balizas"]
        bm = bmesh.new()
        for p in puntas:
            bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=B.get("r", 0.9),
                                      matrix=__import__("mathutils").Matrix.Translation(p))
        ob = _mesh_obj("balizas", bm, [mat_neon("baliza", "#ff2a1a", 2.4)], colls["neon"])
        per, fase = B.get("periodo", 24), B.get("fase", 0)
        for f in range(1, ctx.CFG["frames"] + 1):
            key_power(ob, f, 1.0 if ((f + fase) % per) < per // 2 else 0.12)
        set_interp(ob, "CONSTANT")


def build_resplandor(e, colls):
    """De noche, el nodo late: luz ambar adentro del galpon (sin sombra: se
    derrama sobre la tierra alrededor), un velo ambar sobre la brecha y la
    brecha misma encendida. Late como la radio estabilizada.

        "resplandor": {"latido": {"desde": 6, "bpm": 60, "base": 0.55}}
    """
    g = {**ctx.CFG.get("galpon", {})}
    W, H, R = g.get("ancho", 10), g.get("alto", 7), g.get("cumbrera", 9.5)
    b0, b1 = g.get("brecha", [-6, 5])
    color = e.get("color", "#ffb000")
    bm = bmesh.new()
    _bm_box(bm, (-W / 4, (b0 + b1) / 2, H - 0.3), (W / 2 - 0.4, b1 - b0 - 0.4, 0.05))
    luz = _mesh_obj("brecha_luz", bm, [mat_neon("brecha_luz", color, 1.6)], colls["neon"])
    # un haz tenue que sube de la brecha (un velo de una cara, como los conos
    # de los faroles): de lejos marca el lugar sin tapar nada
    halos = []
    cx, cy = -W / 4, (b0 + b1) / 2
    hz = e.get("haz_alto", 60)
    bm = bmesh.new()
    abajo = [bm.verts.new(Vector((cx + dx, cy + dy, H))) for dx, dy in
             ((-W / 4, b0 - cy), (W / 4, b0 - cy), (W / 4, b1 - cy), (-W / 4, b1 - cy))]
    arriba = [bm.verts.new(Vector((cx + dx * 1.6, cy + dy * 1.6, H + hz))) for dx, dy in
              ((-W / 4, b0 - cy), (W / 4, b0 - cy), (W / 4, b1 - cy), (-W / 4, b1 - cy))]
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((abajo[i], abajo[j], arriba[j], arriba[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if e.get("haz_alpha", 0):
        # contra el cielo de noche el velo se leia como una losa: apagado por defecto
        halo = _mesh_obj("haz_nodo", bm, [mat_beam("haz_nodo", color, e["haz_alpha"])], colls["veil"])
        halo.visible_shadow = False
        halos.append(halo)
    else:
        bm.free()
    li = bpy.data.lights.new("nodo_luz", "POINT")
    li.color = lin(color)[:3]
    li.use_shadow = False
    li.shadow_soft_size = 2.0
    lo = bpy.data.objects.new("nodo_luz", li)
    lo.location = (-1.5, 0, H - 1.0)
    link(lo, colls["lights"])
    E = e.get("energia", 6000)
    L = e.get("latido", {"desde": 6, "bpm": 60, "base": 0.55})
    paso = round(ctx.CFG["fps"] * 60 / L.get("bpm", 60))
    base = L.get("base", 0.55)
    frames = ctx.CFG["frames"]
    beats = list(range(L["desde"], frames + paso, paso))
    for ob in [luz] + halos:
        key_power(ob, 1, base)
    li.energy = E * base
    li.keyframe_insert("energy", frame=1)
    for f in beats:
        for ff, v in ((f - 1, base), (f, 1.0), (f + 3, base)):
            if ff < 1:
                continue
            for ob in [luz] + halos:
                key_power(ob, ff, v)
            li.energy = E * v
            li.keyframe_insert("energy", frame=ff)
    for ob in [luz, li] + halos:
        set_interp(ob, "LINEAR")


PIEZAS = [
    ("puna", build_puna),
    ("cerro", build_cerro),
    ("pueblo", build_pueblo),
    ("via", build_via),
    ("galpon", build_galpon),
    ("polvo", build_polvo),
    ("radio", build_radio),
    ("poste", build_poste),
    ("torre", build_torre),
    ("nyx", build_nyx),
    ("aegis", build_aegis),
    ("vesper", build_vesper),
    ("hud", build_hud),
    ("pulsos", build_pulsos),
    ("descarga", build_descarga),
    ("mapa", build_mapa),
    ("resplandor", build_resplandor),
]
