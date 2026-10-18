"""NUNCA SE APAGAN: la nena (poncho con guardas, capucha, visor de realidad
aumentada) y el brazo del papa en primera persona.

La nena es una jerarquia de piezas simples (sin rig): una raiz en los pies,
piernas que giran en la cadera, el poncho, la cabeza que gira en el cuello y
brazos que van del hombro a un punto del mundo. Cada pose es una clave del
JSON ("keys"); entre claves, Blender interpola.

    "nena": {"keys": [{"frame": 1, "at": [x, y, z], "rumbo": [dx, dy],
                       "cabeza": [giro, inclinacion], "paso": 18,
                       "senala": [x, y, z] o null, "habla": 0 o 1}],
             "colores": {...}}
    "papa_brazo": {"hombro": [derecha, adelante, abajo]}

La mano izquierda de la nena va de la mano del papa: el punto de encuentro
sale del hombro de ella y del hombro de el (que sale de la camara de cada
clave), asi que la pose y la camara nunca se separan.
"""

import math

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

from piezas import ctx
from piezas.base import key_power, link
from piezas.materiales import mat_neon, mat_toon

ALTO = 1.12                     # nena de ~6 anios
# los brazos nacen adentro del poncho, abajo y al costado: asoman por el
# costado (donde el poncho se levanta), no por el medio de la espalda
HOMBRO_I = Vector((-0.13, 0.0, 0.64))
HOMBRO_D = Vector((0.13, 0.0, 0.64))
CUELLO = Vector((0.0, 0.0, 0.87))
CADERA = 0.50


# ---------------------------------------------------------------- mallas
def _mesh(name, bm, mats, coll, parent=None, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    for m in mats:
        ob.data.materials.append(m)
    ob.parent = parent
    link(ob, coll)
    return ob


def _poncho():
    """Poncho: hombros redondos que se abren en un rombo con puntas adelante,
    atras y a los costados (las puntas caen un poco mas). Dos guardas claras
    con una oscura en el medio, cerca del ruedo."""
    bm = bmesh.new()
    seg = 24

    def ring(z, r_side, r_corner, droop=0.0):
        pts = []
        zz = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            c = abs(math.cos(2 * a)) ** 1.4
            r = r_side + (r_corner - r_side) * c
            pts.append((r * math.cos(a), r * math.sin(a)))
            zz.append(z - droop * c)
        return pts, zz

    rows = []
    top = [(0.86, 0.075, 0.075, 0.0), (0.84, 0.12, 0.125, 0.0), (0.79, 0.16, 0.18, 0.0)]
    for z, rs, rc, d in top:
        rows.append(ring(z, rs, rc, d))
    steps = 10
    for i in range(1, steps + 1):
        t = i / steps
        z = 0.79 + (0.53 - 0.79) * t
        rows.append(ring(z, 0.16 + 0.10 * t, 0.18 + 0.19 * t, 0.07 * t))
    vs = [[bm.verts.new((x, y, z)) for (x, y), z in zip(pts, zz)] for pts, zz in rows]
    # guardas: filas 9 y 11 claras, 10 oscura (cerca del ruedo)
    mat_rows = {9: 1, 10: 2, 11: 1}
    for r in range(len(vs) - 1):
        for k in range(seg):
            j = (k + 1) % seg
            f = bm.faces.new([vs[r][k], vs[r][j], vs[r + 1][j], vs[r + 1][k]])
            f.material_index = mat_rows.get(r, 0)
    bm.faces.new(list(reversed(vs[0])))
    return bm


def _esf(c, r, th, ph):
    """Punto de una esfera: th = giro desde el frente (+y), ph = altura."""
    return c + r * Vector((math.sin(th) * math.cos(ph), math.cos(th) * math.cos(ph), math.sin(ph)))


def _cabeza():
    """Cabeza (origen en el cuello): cara, capucha abierta adelante, flequillo
    que asoma bajo la capucha, visor fino y mejillas."""
    cara, capucha, visor, pelo, mejillas = (bmesh.new() for _ in range(5))
    c = Vector((0.0, 0.01, 0.115))
    bmesh.ops.create_uvsphere(cara, u_segments=20, v_segments=12, radius=0.108,
                              matrix=Matrix.Translation(c))
    bmesh.ops.create_uvsphere(capucha, u_segments=20, v_segments=12, radius=0.135,
                              matrix=Matrix.Translation(c + Vector((0, -0.02, 0.012))))
    # abre la capucha adelante (la cara) y abajo (el cuello)
    kill = [f for f in capucha.faces if f.calc_center_median().y > c.y + 0.035
            or f.calc_center_median().z < c.z - 0.085]
    bmesh.ops.delete(capucha, geom=kill, context="FACES")
    # flequillo: un casquete sobre la frente con el borde en zigzag (mechones)
    cols, rows = 13, 5
    grid = []
    for i in range(cols):
        th = math.radians(-64 + 128 * i / (cols - 1))
        # puntas y huecos de largo desparejo (un serrucho parejo parece corona);
        # a los costados el pelo sube hacia la capucha
        tip = (30, 13, 21, 7, 24, 11, 18, 9, 23, 12, 20, 14, 30)[i]
        col = []
        for k in range(rows):
            ph = math.radians(62 + (tip - 62) * k / (rows - 1))
            col.append(pelo.verts.new(_esf(c, 0.1125, th, ph)))
        grid.append(col)
    for a, b in zip(grid, grid[1:]):
        for k in range(rows - 1):
            pelo.faces.new([a[k], b[k], b[k + 1], a[k + 1]])
    # visor: banda fina a la altura de los ojos, de -70 a 70 grados
    n = 14
    ring = []
    for k in range(n + 1):
        a = math.radians(-70 + 140 * k / n)
        d = Vector((math.sin(a), math.cos(a), 0))
        col = []
        for r, dz in ((0.112, -0.006), (0.112, 0.013), (0.12, 0.015), (0.12, -0.008)):
            col.append(visor.verts.new(c + d * r + Vector((0, 0, dz))))
        ring.append(col)
    for a, b in zip(ring, ring[1:]):
        for k in range(4):
            j = (k + 1) % 4
            visor.faces.new([a[k], a[j], b[j], b[k]])
    for col, flip in ((ring[0], True), (ring[-1], False)):
        visor.faces.new(list(reversed(col)) if flip else col)
    # mejillas: dos ovalos rosados apenas sobre la piel, debajo del visor
    for sx in (-1, 1):
        th, ph = math.radians(sx * 36), math.radians(-17)
        nrm = (_esf(c, 1.0, th, ph) - c).normalized()
        u = nrm.cross(Vector((0, 0, 1))).normalized()
        v = u.cross(nrm)
        o = c + nrm * 0.1088
        vs = [mejillas.verts.new(o + u * 0.019 * math.cos(t) + v * 0.011 * math.sin(t))
              for t in (2 * math.pi * k / 12 for k in range(12))]
        mejillas.faces.new(vs)
    return cara, capucha, visor, pelo, mejillas


def _cyl(r0, r1, length, segs=10):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r0, radius2=r1, depth=length,
                          matrix=Matrix.Translation((0, 0, length / 2)))
    return bm


def _pierna():
    """Pierna desde la cadera hacia abajo (origen en la cadera) con bota."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.04, radius2=0.046,
                          depth=CADERA - 0.06, matrix=Matrix.Translation((0, 0, -(CADERA - 0.06) / 2)))
    bota = bmesh.new()
    bmesh.ops.create_cube(bota, size=1.0, matrix=Matrix.Translation((0, 0.025, -CADERA + 0.05))
                          @ Matrix.Diagonal((0.085, 0.16, 0.10, 1)))
    return bm, bota


# ---------------------------------------------------------------- poses
def _yaw(d):
    return math.atan2(-d[0], d[1])


def _root_matrix(at, yaw):
    return Matrix.Translation(at) @ Matrix.Rotation(yaw, 4, "Z")


def _aim(ob, frame, origin, target, base_len=1.0):
    """Objeto con malla a lo largo de +z: lo ubica en origin apuntando a
    target, estirado al largo justo."""
    d = target - origin
    ob.rotation_mode = "QUATERNION"
    ob.location = origin
    ob.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    ob.scale = (1, 1, d.length / base_len)
    for p in ("location", "rotation_quaternion", "scale"):
        ob.keyframe_insert(p, frame=frame)


def _cam_at(frame):
    """Posicion y mira de la camara del plano en esa clave."""
    keys = ctx.CFG["camera"]["keys"]
    k = min(keys, key=lambda k: abs(k["frame"] - frame))
    return Vector(k["pos"]), Vector(k["aim"])


def _hombro_papa(frame, off):
    pos, aim = _cam_at(frame)
    fwd = (aim - pos)
    fwd.z = 0
    fwd.normalize()
    right = fwd.cross(Vector((0, 0, 1)))
    return pos + right * off[0] + fwd * off[1] - Vector((0, 0, off[2]))


def build_nena(e, colls):
    col = {"poncho": "#c4553d", "guarda": "#efe1c2", "guarda_osc": "#2b2840", "piel": "#f0c4a2",
           "medias": "#2e3150", "botas": "#5b3a2c", "manga": "#3c4a70", "visor": "#5ef2ff",
           "pelo": "#3b2a2c", "mejillas": "#f2988c",
           **e.get("colores", {})}
    main = colls["main"]
    m_poncho = mat_toon("nena_poncho", col["poncho"])
    mats_poncho = [m_poncho, mat_toon("nena_guarda", col["guarda"]), mat_toon("nena_guarda_osc", col["guarda_osc"])]
    m_piel = mat_toon("nena_piel", col["piel"])
    m_medias = mat_toon("nena_medias", col["medias"])
    m_botas = mat_toon("nena_botas", col["botas"])
    m_manga = mat_toon("nena_manga", col["manga"])
    m_visor = mat_neon("nena_visor", col["visor"], e.get("visor_fuerza", 2.2))

    root = bpy.data.objects.new("nena", None)
    root["ancla"] = True        # el post no la toca con glitch ni congelado
    link(root, main)
    _mesh("nena_poncho", _poncho(), mats_poncho, main, root, smooth=True)
    head = bpy.data.objects.new("nena_cuello", None)
    head.parent = root
    head.location = CUELLO
    link(head, main)
    cara, capucha, visor, pelo, mejillas = _cabeza()
    _mesh("nena_cara", cara, [m_piel], main, head, smooth=True)
    _mesh("nena_capucha", capucha, [m_poncho], main, head, smooth=True)
    _mesh("nena_flequillo", pelo, [mat_toon("nena_pelo", col["pelo"])], main, head, smooth=True)
    mj = _mesh("nena_mejillas", mejillas, [mat_toon("nena_mejillas", col["mejillas"])], main, head)
    mj.lineart.usage = "EXCLUDE"        # rubor sin contorno, como en el anime
    vis = _mesh("nena_visor", visor, [m_visor], colls["neon"], head)
    legs = []
    for sx in (-1, 1):
        hip = bpy.data.objects.new(f"nena_cadera{sx}", None)
        hip.parent = root
        hip.location = (sx * 0.06, 0, CADERA)
        link(hip, main)
        pierna, bota = _pierna()
        _mesh(f"nena_pierna{sx}", pierna, [m_medias], main, hip, smooth=True)
        _mesh(f"nena_bota{sx}", bota, [m_botas], main, hip)
        legs.append((sx, hip))
    arms = {}
    for side in ("i", "d"):
        arm = _mesh(f"nena_brazo_{side}", _cyl(0.034, 0.03, 1.0), [m_manga], main, root, smooth=True)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.036)
        hand = _mesh(f"nena_mano_{side}", bm, [m_piel], main, root, smooth=True)
        arms[side] = (arm, hand)

    off = ctx.CFG.get("papa_brazo", {}).get("hombro", [0.24, 0.05, 0.36])
    for k in e["keys"]:
        f = k["frame"]
        at = Vector(k["at"])
        yaw = _yaw(k.get("rumbo", (0, 1)))
        root.location = at
        root.rotation_euler = (0, 0, yaw)
        root.keyframe_insert("location", frame=f)
        root.keyframe_insert("rotation_euler", frame=f)
        giro, incl = (math.radians(a) for a in k.get("cabeza", (0, 0)))
        # XYZ: primero inclina (en el cuello) y despues gira
        head.rotation_euler = Euler((incl, 0, giro), "XYZ")
        head.keyframe_insert("rotation_euler", frame=f)
        paso = math.radians(k.get("paso", 0))
        for sx, hip in legs:
            hip.rotation_euler = (sx * paso, 0, 0)
            hip.keyframe_insert("rotation_euler", frame=f)
        M = _root_matrix(at, yaw)
        Mi = M.inverted()
        # mano izquierda: a la altura de la cadera del papa, entre los dos hombros
        hp = _hombro_papa(f, off)
        hi_w = M @ HOMBRO_I
        meet = hi_w.lerp(hp, 0.42)
        meet.z = at.z + k.get("mano_z", 0.80)
        arm, hand = arms["i"]
        _aim(arm, f, HOMBRO_I, Mi @ meet)
        hand.location = Mi @ meet
        hand.keyframe_insert("location", frame=f)
        # mano derecha: colgando bajo el poncho o senalando
        arm, hand = arms["d"]
        if k.get("senala"):
            t = Mi @ Vector(k["senala"])
            tgt = HOMBRO_D + (t - HOMBRO_D).normalized() * 0.5
        else:
            tgt = HOMBRO_D + Vector((0.05, 0.03, -0.24))
        _aim(arm, f, HOMBRO_D, tgt)
        hand.location = tgt
        hand.keyframe_insert("location", frame=f)
        key_power(vis, f, 1.0 if k.get("habla") else 0.35)
        # para el brazo del papa: donde tiene que estar su mano en esta clave
        _MANOS[f] = meet.copy()


_MANOS = {}


def build_papa_brazo(e, colls):
    """Brazo derecho del papa en primera persona: manga de campera desde el
    hombro (abajo a la derecha de la camara) hasta la mano de la nena; la mano
    la envuelve."""
    col = {"campera": "#2a3044", "puno": "#1c2030", "piel": "#d9a882", **e.get("colores", {})}
    main = colls["main"]
    arm = _mesh("papa_brazo", _cyl(0.058, 0.048, 1.0, segs=12), [mat_toon("papa_campera", col["campera"])],
                main, smooth=True)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=8, radius=1.0,
                              matrix=Matrix.Diagonal((0.052, 0.045, 0.085, 1)))
    hand = _mesh("papa_mano", bm, [mat_toon("papa_piel", col["piel"])], main, smooth=True)
    off = e.get("hombro", [0.24, 0.05, 0.36])
    for f, meet in sorted(_MANOS.items()):
        hp = _hombro_papa(f, off)
        wrist = meet + (hp - meet).normalized() * 0.07
        _aim(arm, f, hp, wrist)
        hand.rotation_mode = "QUATERNION"
        hand.location = meet + (hp - meet).normalized() * 0.01
        hand.rotation_quaternion = Vector((0, 0, 1)).rotation_difference((meet - hp).normalized())
        hand.keyframe_insert("location", frame=f)
        hand.keyframe_insert("rotation_quaternion", frame=f)


PIEZAS = [("nena", build_nena), ("papa_brazo", build_papa_brazo)]
