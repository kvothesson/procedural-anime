"""
piezas.py - _sakuga: luchadores humanoides de piezas (prueba del rig).

Reconstruido desde el .pyc que quedo (el .py original no estaba en git). Las
poses y su evaluacion pasaron a motor/poses.py; aca queda lo de Blender: mallas,
materiales, cabeza y bufanda.

  - Esqueleto de poses en vista de perfil (x adelante, z arriba) con profundidad
    por lado: "f" es el lado de adelante (+y local), "b" el de atras.
  - Cuerpo sin juntas a la vista: modificador Skin sobre el esqueleto (una malla
    continua), no tubos sueltos. Pelvis ancha, ruedo del pantalon tapa la bota.

Las mallas se animan por vertice con claves CONSTANT: el rig es Python puro y
Blender solo recibe posiciones. Todo es funcion del frame: reproducible.

    "luchadores": {"list": [
        {"id": "tsubame", "look": "bufanda",
         "keys": [[1, "guardia", [-1.0, 3.0], 0],     # frame, pose, [x, y], yaw (grados)
                  [25, "carga", [-1.0, 3.0], 0, {"ib": [[2, {"*": 0.4, "torso": 0.7}]],
                                                  "pasa": [3, 0.3]}],
                  ...],
         "tarde": {"cabeza": 2},                       # la cabeza llega 2 cuadros tarde
         "contactos": [["anklef", 1, 32]]}]}           # pie clavado en el mundo

Las opciones de cada clave estan en motor/poses.py (ib, pasa, antes, slide, suelo).
"""

import math

import bpy
from mathutils import Matrix, Vector

import poses
from piezas.base import lin, link, set_interp
from piezas.materiales import mat_neon, mat_toon

# Huesos (hijo, padre) en orden: el padre antes que el hijo.
HUESOS = [
    ("waist", "hip"), ("chest", "waist"), ("neck", "chest"), ("head", "neck"),
    ("shf", "chest"), ("elbf", "shf"), ("handf", "elbf"),
    ("shb", "chest"), ("elbb", "shb"), ("handb", "elbb"),
    ("hipf", "hip"), ("kneef", "hipf"), ("anklef", "kneef"), ("toef", "anklef"),
    ("hipb", "hip"), ("kneeb", "hipb"), ("ankleb", "kneeb"), ("toeb", "ankleb"),
]

# Largos fijos (m). Hombros y caderas no tienen: van como desplazamiento libre.
LARGO = {"waist": 0.17, "chest": 0.22, "neck": 0.15, "head": 0.12,
         "elbf": 0.29, "handf": 0.27, "elbb": 0.29, "handb": 0.27,
         "kneef": 0.45, "anklef": 0.45, "toef": 0.15,
         "kneeb": 0.45, "ankleb": 0.45, "toeb": 0.15}

PROF = {"hip": 0, "waist": 0, "chest": 0, "neck": 0, "head": 0,
        "shf": 0.19, "elbf": 0.23, "handf": 0.18, "shb": -0.19, "elbb": -0.23, "handb": -0.18,
        "hipf": 0.1, "kneef": 0.11, "anklef": 0.12, "toef": 0.12,
        "hipb": -0.1, "kneeb": -0.11, "ankleb": -0.12, "toeb": -0.12}
TOBILLO = 0.075

POSES = {
    "guardia": {"hip": (0, 0.93), "waist": (0.01, 1.1), "chest": (0.03, 1.33), "neck": (0.04, 1.5), "head": (0.06, 1.63),
                "shf": (0.05, 1.44), "elbf": (0.22, 1.24), "handf": (0.36, 1.42),
                "shb": (0.0, 1.44), "elbb": (0.06, 1.18), "handb": (0.2, 1.36),
                "hipf": (0.02, 0.93), "kneef": (0.21, 0.53), "anklef": (0.28, 0.08), "toef": (0.43, 0.05),
                "hipb": (-0.02, 0.93), "kneeb": (-0.1, 0.5), "ankleb": (-0.26, 0.08), "toeb": (-0.11, 0.05)},
    "carga": {"hip": (-0.05, 0.72), "waist": (0.0, 0.88), "chest": (0.1, 1.08), "neck": (0.18, 1.22), "head": (0.24, 1.33),
              "shf": (0.13, 1.17), "elbf": (0.34, 1.02), "handf": (0.46, 1.18),
              "shb": (0.08, 1.17), "elbb": (-0.14, 1.02), "handb": (-0.02, 1.16),
              "hipf": (-0.03, 0.72), "kneef": (0.33, 0.52), "anklef": (0.3, 0.08), "toef": (0.45, 0.05),
              "hipb": (-0.07, 0.72), "kneeb": (-0.3, 0.4), "ankleb": (-0.5, 0.1), "toeb": (-0.36, 0.03),
              "prof": {"handb": -0.24, "elbb": -0.28}},
    "embestida": {"hip": (0, 0.82), "waist": (0.12, 0.93), "chest": (0.3, 1.06), "neck": (0.43, 1.15), "head": (0.53, 1.22),
                  "shf": (0.33, 1.12), "elbf": (0.58, 1.0), "handf": (0.7, 1.12),
                  "shb": (0.28, 1.12), "elbb": (0.06, 1.02), "handb": (0.2, 1.12),
                  "hipf": (0.02, 0.82), "kneef": (0.38, 0.66), "anklef": (0.28, 0.26), "toef": (0.42, 0.24),
                  "hipb": (-0.02, 0.82), "kneeb": (-0.32, 0.56), "ankleb": (-0.66, 0.32), "toeb": (-0.74, 0.2),
                  "prof": {"handb": -0.22}},
    "golpe": {"hip": (0, 0.84), "waist": (0.08, 1.0), "chest": (0.18, 1.22), "neck": (0.25, 1.37), "head": (0.31, 1.49),
              "shf": (0.14, 1.33), "elbf": (0.02, 1.16), "handf": (0.16, 1.3),
              "shb": (0.22, 1.35), "elbb": (0.5, 1.37), "handb": (0.78, 1.4),
              "hipf": (0.02, 0.84), "kneef": (0.42, 0.5), "anklef": (0.46, 0.08), "toef": (0.61, 0.05),
              "hipb": (-0.02, 0.84), "kneeb": (-0.3, 0.47), "ankleb": (-0.6, 0.12), "toeb": (-0.47, 0.03),
              "prof": {"shf": 0.22, "elbf": 0.2, "handf": 0.12, "shb": -0.07, "elbb": -0.03, "handb": 0.0}},
    "remate": {"hip": (0, 0.64), "waist": (0.03, 0.81), "chest": (0.09, 1.03), "neck": (0.12, 1.19), "head": (0.15, 1.31),
               "shf": (0.07, 1.12), "elbf": (-0.16, 0.98), "handf": (-0.32, 0.88),
               "shb": (0.1, 1.12), "elbb": (0.34, 0.98), "handb": (0.58, 0.9),
               "hipf": (0.02, 0.64), "kneef": (0.44, 0.42), "anklef": (0.46, 0.08), "toef": (0.61, 0.05),
               "hipb": (-0.02, 0.64), "kneeb": (-0.26, 0.12), "ankleb": (-0.66, 0.12), "toeb": (-0.76, 0.03)},
    "recibe": {"hip": (0, 0.92), "waist": (-0.05, 1.08), "chest": (-0.13, 1.28), "neck": (-0.21, 1.42), "head": (-0.3, 1.5),
               "shf": (-0.12, 1.39), "elbf": (0.05, 1.52), "handf": (0.18, 1.7),
               "shb": (-0.16, 1.39), "elbb": (-0.4, 1.3), "handb": (-0.56, 1.44),
               "hipf": (0.02, 0.92), "kneef": (0.17, 0.52), "anklef": (0.26, 0.08), "toef": (0.41, 0.05),
               "hipb": (-0.02, 0.92), "kneeb": (-0.14, 0.5), "ankleb": (-0.3, 0.08), "toeb": (-0.15, 0.05)},
}

RIG = {
    "huesos": HUESOS, "largo": LARGO, "prof": PROF, "tobillo": TOBILLO,
    "pies": ["anklef", "ankleb"], "poses": POSES,
    "ramas": {
        "raiz": ["hip"],
        "torso": ["waist", "chest"],
        "cabeza": ["neck", "head"],
        "brazo_f": ["shf", "elbf", "handf"],
        "brazo_b": ["shb", "elbb", "handb"],
        "pierna_f": ["hipf", "kneef", "anklef", "toef"],
        "pierna_b": ["hipb", "kneeb", "ankleb", "toeb"],
    },
}

LOOKS = {
    "bufanda": {"chaqueta": "#3d4466", "pantalon": "#262a40", "bota": "#15141f", "piel": "#e9b896",
                "guante": "#e9b896", "pelo": "#1a1828", "rasgo": "#e5352b"},
    "capucha": {"chaqueta": "#4f6a8c", "pantalon": "#2c3346", "bota": "#1d1f2c", "piel": "#e2b08f",
                "guante": "#22283a", "pelo": "#6f8db0", "rasgo": "#5ec5e2"},
}

R_PIERNA = {"hip": 0.135, "hipf": 0.105, "kneef": 0.072, "anklef": 0.058,
            "hipb": 0.105, "kneeb": 0.072, "ankleb": 0.058}
R_TORSO = {"hip": 0.14, "waist": 0.125, "chest": 0.15, "neck": 0.055,
           "shf": 0.075, "elbf": 0.056, "wristf": 0.046,
           "shb": 0.075, "elbb": 0.056, "wristb": 0.046}


def mat_luchador(name, color, rim=None):
    """Toon del motor + filo de luz: las caras rasantes (Layer Weight > Facing)
    que miran hacia la fuente se encienden del color de la luz. Es el "1 px de
    luz del lado de la fuente" del pixel art: separa al personaje oscuro de un
    fondo oscuro. rim: {"color", "dir": hacia la luz, "facing", "lado", "fuerza"}."""
    mat = mat_toon(name, color)
    if not rim:
        return mat
    nt = mat.node_tree
    n, L = nt.nodes, nt.links
    em = next(x for x in n if x.type == "EMISSION")
    src = em.inputs["Color"].links[0].from_socket

    def m(op, a, b):
        node = n.new("ShaderNodeMath")
        node.operation = op
        for i, x in enumerate((a, b)):
            if isinstance(x, (int, float)):
                node.inputs[i].default_value = x
            else:
                L.new(x, node.inputs[i])
        return node.outputs[0]

    lw = n.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    geo = n.new("ShaderNodeNewGeometry")
    dot = n.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    L.new(geo.outputs["Normal"], dot.inputs[0])
    dot.inputs[1].default_value = Vector(rim["dir"]).normalized()
    k = m("MULTIPLY", m("GREATER_THAN", lw.outputs["Facing"], rim.get("facing", 0.55)),
          m("GREATER_THAN", dot.outputs["Value"], rim.get("lado", 0.2)))
    mix = n.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    L.new(m("MULTIPLY", k, rim.get("fuerza", 0.85)), mix.inputs["Factor"])
    L.new(src, mix.inputs[6])
    mix.inputs[7].default_value = lin(rim["color"])
    L.new(mix.outputs[2], em.inputs["Color"])
    return mat


def _munecas(pos):
    """La muneca va al 85 % del antebrazo: ahi termina la manga y empieza el guante."""
    for s in "fb":
        e, h = Vector(pos["elb" + s]), Vector(pos["hand" + s])
        pos["wrist" + s] = tuple(e.lerp(h, 0.85))
    return pos


def _skin_obj(name, joints, edges, radios, mat, coll, root_j):
    """Malla Skin: un vertice por articulacion, una arista por hueso."""
    idx = {j: i for i, j in enumerate(joints)}
    me = bpy.data.meshes.new(name)
    me.from_pydata([(0, 0, 0)] * len(joints), [(idx[a], idx[b]) for a, b in edges], [])
    ob = bpy.data.objects.new(name, me)
    ob.modifiers.new("piel", "SKIN")
    sub = ob.modifiers.new("suave", "SUBSURF")
    sub.levels = sub.render_levels = 2
    sv = me.skin_vertices[0].data
    for j, i in idx.items():
        r = radios[j]
        sv[i].radius = (r, r) if isinstance(r, (int, float)) else r
        sv[i].use_root = j == root_j
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    link(ob, coll)
    return ob, idx


def _sphere(name, r, scale, mat, coll):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=r)
    ob = bpy.context.active_object
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    ob.name = name
    ob.data.transform(Matrix.Diagonal([*scale, 1]))
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    link(ob, coll)
    return ob


def _key_verts(ob, idx, frames_pos):
    """frames_pos: [(frame, {articulacion: xyz})]. Clave solo donde cambia."""
    last = None
    for f, pos in frames_pos:
        sig = tuple(round(c, 5) for j in idx for c in pos[j])
        if sig == last:
            continue
        last = sig
        for j, i in idx.items():
            ob.data.vertices[i].co = pos[j]
            ob.data.vertices[i].keyframe_insert("co", frame=f)
    set_interp(ob.data, "CONSTANT")


def _head_frame(pos):
    """Matriz de la cabeza: mira hacia adelante del pecho, inclinada con el cuello."""
    n, h = Vector(pos["neck"]), Vector(pos["head"])
    up = (h - n).normalized()
    left = Vector(pos["shf"]) - Vector(pos["shb"])
    left.z = 0
    fwd = left.cross(Vector((0, 0, 1))).normalized()
    fwd = (fwd - up * fwd.dot(up)).normalized()
    left = up.cross(fwd)
    m = Matrix((fwd, left, up)).transposed().to_4x4()
    m.translation = h
    return m


def build_luchadores(e, colls):
    from piezas import ctx
    N = ctx.CFG["frames"]
    for c in e["list"]:
        look = LOOKS[c.get("look", "bufanda")]
        nm = c["id"]
        rim = e.get("rim")
        M = {k: mat_luchador(f"{nm}_{k}", look[k], rim)
             for k in ("chaqueta", "pantalon", "bota", "piel", "guante", "pelo")}
        if c.get("look") == "capucha":
            M["piel"] = mat_luchador(f"{nm}_sombra", "#151426", rim)
        root = bpy.data.objects.new(nm, None)
        root["ancla"] = True
        link(root, colls["main"])

        piezas = []
        piernas, ip = _skin_obj(
            f"{nm}_piernas", list(R_PIERNA),
            [("hip", "hipf"), ("hipf", "kneef"), ("kneef", "anklef"),
             ("hip", "hipb"), ("hipb", "kneeb"), ("kneeb", "ankleb")],
            R_PIERNA, M["pantalon"], colls["main"], "hip")
        torso_j = list(R_TORSO)
        torso, it = _skin_obj(
            f"{nm}_torso", torso_j,
            [("hip", "waist"), ("waist", "chest"), ("chest", "neck"),
             ("chest", "shf"), ("shf", "elbf"), ("elbf", "wristf"),
             ("chest", "shb"), ("shb", "elbb"), ("elbb", "wristb")],
            R_TORSO, M["chaqueta"], colls["main"], "hip")
        piezas += [(piernas, ip), (torso, it)]
        for s in "fb":
            bota, ib = _skin_obj(f"{nm}_bota{s}", ["ankle" + s, "toe" + s],
                                 [("ankle" + s, "toe" + s)],
                                 {"ankle" + s: 0.062, "toe" + s: 0.045},
                                 M["bota"], colls["main"], "ankle" + s)
            mano, im = _skin_obj(f"{nm}_mano{s}", ["wrist" + s, "hand" + s],
                                 [("wrist" + s, "hand" + s)],
                                 {"wrist" + s: 0.045, "hand" + s: 0.058},
                                 M["guante"], colls["main"], "wrist" + s)
            piezas += [(bota, ib), (mano, im)]
        if c.get("look") == "capucha":
            cuello, ic = _skin_obj(f"{nm}_cuello", ["chest", "neck", "head"],
                                   [("chest", "neck"), ("neck", "head")],
                                   {"chest": 0.1, "neck": 0.115, "head": 0.1},
                                   M["pelo"], colls["main"], "chest")
        else:
            cuello, ic = _skin_obj(f"{nm}_cuello", ["neck", "head"], [("neck", "head")],
                                   {"neck": 0.05, "head": 0.045},
                                   M["piel"], colls["main"], "neck")
        piezas.append((cuello, ic))

        cabeza = _sphere(f"{nm}_cabeza", 0.115, (0.95, 0.88, 1.05), M["piel"], colls["main"])
        if c.get("look") == "capucha":
            cap = _sphere(f"{nm}_capucha", 0.14, (1.0, 0.98, 1.06), M["pelo"], colls["main"])
            cap.parent = cabeza
            cap.location = (-0.04, 0, 0.015)
            bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.07, depth=0.16)
            punta = bpy.context.active_object
            for cc in list(punta.users_collection):
                cc.objects.unlink(punta)
            punta.name = f"{nm}_punta"
            punta.data.materials.append(M["pelo"])
            link(punta, colls["main"])
            punta.parent = cabeza
            punta.location = (-0.17, 0, 0.03)
            punta.rotation_euler = (0, math.radians(-115), 0)
            cara = _sphere(f"{nm}_cara", 0.085, (0.55, 0.9, 0.95), M["piel"], colls["main"])
            cara.parent = cabeza
            cara.location = (0.075, 0, -0.01)
            ojo_m = mat_neon(f"{nm}_ojos", look["rasgo"], 2.5)
            for dy in (-0.03, 0.03):
                ojo = _sphere(f"{nm}_ojo", 0.016, (0.6, 1.0, 0.55), ojo_m, colls["neon"])
                ojo.parent = cabeza
                ojo.location = (0.118, dy, 0.0)
        else:
            pelo = _sphere(f"{nm}_pelo", 0.122, (1.0, 0.95, 0.9), M["pelo"], colls["main"])
            pelo.parent = cabeza
            pelo.location = (-0.025, 0, 0.03)
            ojo_m = mat_toon(f"{nm}_ojos", "#1a1828")
            for dy in (-0.035, 0.035):
                ojo = _sphere(f"{nm}_ojo", 0.012, (0.5, 1.0, 1.4), ojo_m, colls["main"])
                ojo.parent = cabeza
                ojo.location = (0.105, dy, 0.005)

        frames_pos = [(f, _munecas(pos))
                      for f, pos in poses.secuencia(RIG, c, range(1, N + 1))]
        for ob, idx in piezas:
            _key_verts(ob, idx, frames_pos)
            ob.parent = root
        last = None
        for f, pos in frames_pos:
            m = _head_frame(pos)
            sig = tuple(round(v, 5) for row in m for v in row)
            if sig == last:
                continue
            last = sig
            cabeza.matrix_world = m
            cabeza.keyframe_insert("location", frame=f)
            cabeza.keyframe_insert("rotation_euler", frame=f)
        set_interp(cabeza, "CONSTANT")
        cabeza.parent = root
        if c.get("look") != "capucha":
            _bufanda(c, look, frames_pos, root, colls, rim)


def _bufanda(c, look, frames_pos, root, colls, rim=None):
    """Bufanda roja: cadena Verlet determinista (paso fijo de 1/60 s, misma
    entrada = misma salida), anclada en la nuca. Se dibuja como una cinta que
    se afina. La fisica va en doses, como el cuerpo."""
    from piezas import ctx
    fps = ctx.CFG.get("fps", 24)
    n, seg = 11, 0.085
    wind = Vector(c.get("viento", (-5.0, 0.0, 1.5)))
    sub = max(1, round(60 / fps))
    dt = 1.0 / (fps * sub)

    def ancla(pos):
        left = Vector(pos["shf"]) - Vector(pos["shb"])
        left.z = 0
        fwd = left.cross(Vector((0, 0, 1))).normalized()
        return Vector(pos["neck"]) - fwd * 0.07 + Vector((0, 0, 0.02))

    a0 = ancla(frames_pos[0][1])
    p = [a0 + Vector((-0.02 * i, 0, -seg * i)) for i in range(n)]
    q = [v.copy() for v in p]
    out = []
    for fi, (f, pos) in enumerate(frames_pos):
        a1 = ancla(pos)
        a_prev = ancla(frames_pos[fi - 1][1]) if fi else a1
        for s in range(sub):
            a = a_prev.lerp(a1, (s + 1) / sub)
            p[0] = a
            for i in range(1, n):
                v = (p[i] - q[i]) * 0.9
                q[i] = p[i].copy()
                rafaga = 1.0 + 0.35 * math.sin(f * 0.37 + i * 0.8)
                p[i] = p[i] + v + (Vector((0, 0, -9.8)) + wind * rafaga) * dt * dt
            for _ in range(4):
                for i in range(1, n):
                    d = p[i] - p[i - 1]
                    L = d.length or 1e-6
                    p[i] = p[i - 1] + d * (seg / L)
        out.append((f, [v.copy() for v in p]))

    me = bpy.data.meshes.new("bufanda")
    verts = [(0, 0, 0)] * (2 * n)
    faces = [(2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2) for i in range(n - 1)]
    me.from_pydata(verts, [], faces)
    me.materials.append(mat_luchador("bufanda_m", look["rasgo"], rim))
    ob = bpy.data.objects.new("bufanda", me)
    link(ob, colls["main"])
    ob.parent = root
    last = None
    for (f, pts), (_, pos) in zip(out, frames_pos):
        fq = f - (f - 1) % 2
        if fq != f:
            continue
        side = (Vector(pos["shf"]) - Vector(pos["shb"])).normalized()
        sig = tuple(round(c, 4) for v in pts for c in v)
        if sig == last:
            continue
        last = sig
        for i, v in enumerate(pts):
            d = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
            ancho = d.cross(side).normalized()
            w = 0.075 * (1 - 0.3 * i / (n - 1))
            me.vertices[2 * i].co = v + ancho * w
            me.vertices[2 * i + 1].co = v - ancho * w
            me.vertices[2 * i].keyframe_insert("co", frame=f)
            me.vertices[2 * i + 1].keyframe_insert("co", frame=f)
    set_interp(me, "CONSTANT")


PIEZAS = [("luchadores", build_luchadores)]
