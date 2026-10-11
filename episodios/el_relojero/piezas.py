"""
piezas.py - EL RELOJERO: el robot, la esfera del reloj vista desde adentro y
la sala de maquinas de la torre.

El robot es una maquina vieja de mantenimiento, sin cara: un solo ojo-luz
ambar, un torso de cobre oxidado (verdin) con ribetes de bronce, una tapa en
el pecho y, adentro, su corazon: un engranaje que brilla. Llave de cuerda en
la espalda. Piezas rigidas colgadas de pivotes (sin esqueleto): la pose es
una rotacion por articulacion, con claves en el JSON.

Ejes del robot: mira a -Y, +Z arriba. "i" = su izquierda (+X), "d" = su derecha.

    "relojero": {
        "at": [0, 0, 0], "face": 0,
        "pose": [{"frame": 1, "cintura": [8, 0, 0], "cuello": [15, 0, 0],
                  "hombro_i": [-45, 25, 0], "codo_i": [-95, 0, 0],
                  "tapa": 110, "ojo": 1.0, "corazon": 1.0}, ...],
        "corazon_mano": 18,     # desde este frame el corazon esta en la mano izquierda
        "corazon_reloj": {"gear": "rueda_rota", "frame": 44}
    }

corazon_reloj: en ese frame el corazon pasa de la mano al cubo del engranaje
(que se mueve solo hasta donde esta la mano en ese frame: no hay que calzarlo a
ojo) y desde ahi gira con el reloj, a golpes de tic.
"""

import math

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector

from piezas import ctx
from piezas.base import action_fcurves, box_mesh, lin, link, tint_light
from piezas.despiece import apply_despiece
from piezas.mecanica import gear_mesh
from piezas.materiales import _emit_out, _power, mat_beam, mat_flat, mat_neon, mat_toon, mat_wet_ground

# punto que agarra la mano, en coordenadas de la muneca (ahi va el corazon)
GRIP = (0.0, -0.1, -0.12)
ARM = (0.35, 0.33)      # hombro -> codo, codo -> muneca
LEG = (0.28, 0.28)      # cadera -> rodilla, rodilla -> tobillo (tobillo a 6 cm del piso)

JOINTS = ("cintura", "cuello", "hombro_i", "codo_i", "muneca_i",
          "hombro_d", "codo_d", "muneca_d", "tapa", "cadera_i", "cadera_d", "rodilla_i", "rodilla_d",
          "tobillo_i", "tobillo_d")

COLORS = {
    "cuerpo": "#3f7a72",     # cobre con verdin
    "bronce": "#c4923a",
    "oscuro": "#2a2733",
    "ojo": "#ffb04a",
    "corazon": "#ffcf6a",
}


# --- mallas -----------------------------------------------------------------

def _smooth(mesh):
    for p in mesh.polygons:
        p.use_smooth = True
    return mesh


def cyl(name, r1, r2, h, segs=20, z0=0.0):
    """Cono truncado sobre z, de z0 a z0 + h (h negativo = hacia abajo)."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r1, radius2=r2, depth=abs(h))
    for v in bm.verts:
        v.co.z = v.co.z * (1 if h > 0 else -1) + z0 + h / 2
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    # lados suaves, tapas planas: una tapa suavizada sale en triangulos
    for poly in mesh.polygons:
        poly.use_smooth = abs(poly.normal.z) < 0.9
    return mesh


def sphere(name, r, sz=1.0, segs=16):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=segs // 2 + 2, radius=r)
    for v in bm.verts:
        v.co.z *= sz
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return _smooth(mesh)


def annulus(name, r_in, r_out, thick, segs=64):
    """Anillo plano en xy (eje z), centrado."""
    bm = bmesh.new()
    rings = {}
    for key, r, z in (("ot", r_out, thick / 2), ("ob", r_out, -thick / 2),
                      ("it", r_in, thick / 2), ("ib", r_in, -thick / 2)):
        rings[key] = [bm.verts.new((r * math.cos(2 * math.pi * i / segs),
                                    r * math.sin(2 * math.pi * i / segs), z)) for i in range(segs)]
    ot, ob, it, ib = rings["ot"], rings["ob"], rings["it"], rings["ib"]
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new((ot[i], ot[j], it[j], it[i]))
        bm.faces.new((ob[i], ib[i], ib[j], ob[j]))
        bm.faces.new((ob[i], ob[j], ot[j], ot[i]))
        bm.faces.new((ib[i], it[i], it[j], ib[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def boxc(name, sx, sy, sz):
    """Caja centrada en el origen."""
    mesh = box_mesh(name, sx, sy, sz)
    for v in mesh.vertices:
        v.co.z -= sz / 2
    return mesh


# --- objetos ----------------------------------------------------------------

# prefijo de los objetos del robot que se esta armando: dos robots en escena
# (el viejo desplomado y el nuevo) no pueden compartir nombres
PRE = ""


def R(name):
    """Objeto del robot actual por nombre (o de la escena, si no es del robot)."""
    return bpy.data.objects.get(PRE + name) or bpy.data.objects[name]


def obj(name, data, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, coll=None):
    ob = bpy.data.objects.new(PRE + name, data)
    if mat is not None and data is not None:
        data.materials.append(mat)
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    ob.parent = parent       # sin matrix_parent_inverse: loc es relativa al padre
    link(ob, coll)
    return ob


def pivot(name, parent, loc, coll):
    return obj(name, None, parent, loc, coll=coll)


# --- el robot ---------------------------------------------------------------

def build_relojero(e, colls):
    global PRE
    PRE = e.get("prefix", "")
    try:
        _build_relojero(e, colls)
    finally:
        PRE = ""


def build_relojero_viejo(e, colls):
    """El relojero anterior, desplomado: el mismo robot con prefijo "v_"."""
    build_relojero({"prefix": "v_", **e}, colls)


def _build_relojero(e, colls):
    main, neon = colls["main"], colls["neon"]
    c = {**COLORS, **e.get("colors", {})}
    m_body = mat_toon("robot_cuerpo", c["cuerpo"])
    m_brass = mat_toon("robot_bronce", c["bronce"])
    m_dark = mat_toon("robot_oscuro", c["oscuro"])
    m_eye = mat_neon("robot_ojo", c["ojo"], strength=e.get("ojo_fuerza", 2.2), fog=False)
    m_heart = mat_neon("robot_corazon", c["corazon"], strength=2.6, fog=False)

    root = obj("relojero", None, None, e.get("at", (0, 0, 0)), (0, 0, e.get("face", 0)), coll=main)
    foco = obj("corazon_foco", None, None, coll=main)
    glow = e.get("corazon_glow", {"strength": 0.9, "falloff": 0.08})
    brillos = [glow_follow(m, foco, c["corazon"], col, glow["falloff"])
               for m, col in ((m_body, c["cuerpo"]), (m_brass, c["bronce"]), (m_dark, c["oscuro"]))]

    # piernas: cortas y rectas (camina como un robot de juguete viejo), colgadas
    # de la cadera; rodilla de bola, pie de bronce. En reposo, igual que antes.
    # cadera -> muslo -> rodilla -> canilla -> tobillo -> pie. La rodilla dobla
    # para subir escalones; el tobillo mantiene el pie plano. Tramos de LEG.
    HIP = 0.62
    for s, side in ((1, "i"), (-1, "d")):
        x = 0.13 * s
        cad = pivot(f"cadera_{side}", root, (x, 0, HIP), main)
        obj(f"muslo_{side}", cyl(f"muslo_{side}", 0.075, 0.07, -(LEG[0] - 0.07)), cad, mat=m_dark, coll=main)
        rod = pivot(f"rodilla_{side}", cad, (0, 0, -LEG[0]), main)
        obj(f"rodilla_bola_{side}", sphere(f"rodilla_bola_{side}", 0.085), rod, (0, -0.01, 0), mat=m_body, coll=main)
        obj(f"canilla_{side}", cyl(f"canilla_{side}", 0.068, 0.065, -(LEG[1] - 0.07), z0=-0.07), rod,
            mat=m_dark, coll=main)
        tob = pivot(f"tobillo_{side}", rod, (0, 0, -LEG[1]), main)
        obj(f"pie_{side}", box_mesh(f"pie_{side}", 0.15, 0.26, 0.08), tob, (0, -0.05, -0.06), mat=m_brass, coll=main)
    obj("pelvis", cyl("pelvis", 0.2, 0.22, 0.16, z0=0.6), root, mat=m_dark, coll=main)

    cintura = pivot("cintura", root, (0, 0, 0.72), main)
    # torso en barril: angosto abajo, ancho arriba; ribetes de bronce que
    # sobresalen de las tapas (caras a la misma altura = manchas y lineas sueltas)
    obj("torso", cyl("torso", 0.24, 0.31, 0.58, segs=28, z0=0.04), cintura, mat=m_body, coll=main)
    obj("ribete_bajo", cyl("ribete_bajo", 0.255, 0.255, 0.06, segs=28, z0=0.03), cintura, mat=m_brass, coll=main)
    obj("ribete_alto", cyl("ribete_alto", 0.32, 0.32, 0.075, segs=28, z0=0.555), cintura, mat=m_brass, coll=main)

    # pecho: aro de bronce, hueco oscuro, corazon y tapa
    zc, yc = 0.33, -0.272
    obj("pecho_aro", annulus("pecho_aro", 0.14, 0.175, 0.03), cintura, (0, yc, zc), (90, 0, 0), m_brass, main)
    obj("pecho_hueco", cyl("pecho_hueco", 0.142, 0.142, 0.02, segs=28), cintura, (0, yc + 0.004, zc), (90, 0, 0), m_dark, main)
    heart = obj("corazon", gear_mesh("corazon", 0.1, 10, 0.022, 0.03, r_in=0.06, spokes=4, hub=0.022),
                cintura, (0, yc - 0.02, zc), (90, 0, 0), m_heart, neon)
    # bisagra abajo, como la puerta de un horno: la mano tira de la perilla de
    # arriba y la tapa cae hacia adelante, lejos del brazo y de la cabeza
    tapa = pivot("tapa", cintura, (0, yc - 0.03, zc - 0.165), main)
    obj("tapa_disco", cyl("tapa_disco", 0.165, 0.165, 0.025, segs=28), tapa, (0, 0, 0.165), (90, 0, 0), m_body, main)
    obj("tapa_perilla", sphere("tapa_perilla", 0.022), tapa, (0, -0.02, 0.29), mat=m_brass, coll=main)
    # eje del corazon: cuando se abre la tapa, el corazon sale sobre el eje
    obj("corazon_eje", cyl("corazon_eje", 0.016, 0.016, 0.1), cintura, (0, yc, zc), (90, 0, 0), m_brass, main)
    obj("tapa_bisagra", cyl("tapa_bisagra", 0.018, 0.018, 0.12, z0=-0.06), tapa, rot=(0, 90, 0), mat=m_brass, coll=main)

    # llave de cuerda en la espalda
    llave = pivot("llave", cintura, (0, 0.3, 0.36), main)
    obj("llave_eje", cyl("llave_eje", 0.022, 0.022, 0.12), llave, rot=(-90, 0, 0), mat=m_brass, coll=main)
    for s in (1, -1):
        obj(f"llave_ala{s}", sphere(f"llave_ala{s}", 0.075, sz=0.35), llave, (0.08 * s, 0.12, 0), (90, 0, 0), m_brass, main)

    # brazos
    for s, side in ((1, "i"), (-1, "d")):
        hombro = pivot(f"hombro_{side}", cintura, (0.37 * s, 0, 0.5), main)
        obj(f"hombrera_{side}", sphere(f"hombrera_{side}", 0.1), hombro, mat=m_brass, coll=main)
        obj(f"brazo_{side}", cyl(f"brazo_{side}", 0.055, 0.05, -0.265), hombro, mat=m_dark, coll=main)
        # brazo y antebrazo no llegan al codo: la bola cubre la union y el
        # codo dobla hasta ~115 grados sin que un tramo entre en el otro
        codo = pivot(f"codo_{side}", hombro, (0, 0, -0.35), main)
        obj(f"codo_bola_{side}", sphere(f"codo_bola_{side}", 0.088), codo, mat=m_body, coll=main)
        obj(f"antebrazo_{side}", cyl(f"antebrazo_{side}", 0.065, 0.05, -0.19, z0=-0.09), codo, mat=m_body, coll=main)
        muneca = pivot(f"muneca_{side}", codo, (0, 0, -0.33), main)
        # bola de muneca y antebrazo corto: la mano dobla 90 grados sin meterse en el
        obj(f"muneca_bola_{side}", sphere(f"muneca_bola_{side}", 0.045), muneca, mat=m_dark, coll=main)
        obj(f"palma_{side}", boxc(f"palma_{side}", 0.1, 0.065, 0.09), muneca, (0, 0, -0.045), mat=m_dark, coll=main)
        # dedos colgados de su nudillo: "agarre" (0..1) los curva hacia la palma
        for k, fx in enumerate((-0.033, 0.0, 0.033)):
            nud = obj(f"nudillo_{side}{k}", None, muneca, (fx, -0.012, -0.08), (-12, 0, 0), coll=main)
            obj(f"dedo_{side}{k}", boxc(f"dedo_{side}{k}", 0.022, 0.03, 0.085), nud,
                (0, 0, -0.04), mat=m_brass, coll=main)
        obj(f"pulgar_{side}", boxc(f"pulgar_{side}", 0.022, 0.03, 0.07), muneca,
            (-0.055 * s, -0.03, -0.06), (-25, 30 * s, 0), m_brass, main)

    # cabeza: farol con un solo ojo, visera y antena torcida
    # cuello alto: al mirar hacia abajo la cabeza no se hunde en el torso
    cuello = pivot("cuello", cintura, (0, 0, 0.68), main)
    obj("cuello_eje", cyl("cuello_eje", 0.055, 0.055, 0.1, z0=-0.08), cuello, mat=m_dark, coll=main)
    obj("craneo", sphere("craneo", 0.17, sz=0.88, segs=20), cuello, (0, 0, 0.19), mat=m_body, coll=main)
    obj("visera", boxc("visera", 0.24, 0.09, 0.025), cuello, (0, -0.13, 0.27), (-12, 0, 0), m_brass, main)
    obj("ojo_aro", annulus("ojo_aro", 0.062, 0.085, 0.04, segs=32), cuello, (0, -0.15, 0.17), (90, 0, 0), m_brass, main)
    obj("ojo", cyl("ojo", 0.063, 0.063, 0.03, segs=32), cuello, (0, -0.155, 0.17), (90, 0, 0), m_eye, neon)
    obj("antena", cyl("antena", 0.012, 0.008, 0.16), cuello, (0.09, 0.03, 0.32), (0, 18, 0), m_dark, main)
    obj("antena_bola", sphere("antena_bola", 0.022), cuello, (0.14, 0.03, 0.47), mat=m_brass, coll=main)

    # corazon en la mano (cuando se lo saca)
    mano = obj("corazon_mano", heart.data, R("muneca_i"), GRIP, (90, 0, 0), None, neon)
    mano["power"] = 1.0


    if not e.get("cast_shadow", True):
        for ob in bpy.data.objects:
            if ob.type == "MESH" and _is_robot(ob, root):
                ob.visible_shadow = False

    _pose(e, heart, mano, foco, brillos, glow["strength"])

    if e.get("camino"):
        _camino(e, ctx.CFG["frames"])

    # despiece: el reloj lo arma pieza por pieza (piezas hojas, no pivotes; la
    # pose del robot tiene que estar neutra para que "from" vaya en ejes del robot)
    if e.get("despiece"):
        partes = e["despiece"]["partes"]
        if e["despiece"].get("pila"):
            _pila(e["despiece"]["pila"], partes)
        apply_despiece({n: R(n) for n in partes}, e["despiece"], ctx.CFG["frames"])


def _pila(pila, partes):
    """Las piezas sin "from" arrancan tiradas en el piso, como una pila de
    repuestos ("center", "radius", en mundo): lugar y orientacion al azar fijo.
    "from" se calcula en los ejes del padre (lo que espera el despiece).

    Llegada: el arco se elige para que el ultimo tramo sea horizontal (arc =
    caida / 4): cada pieza entra de frente a su altura y no atraviesa a las de
    arriba o abajo (el brazo es una columna). Las de "arriba" bajan en vertical
    (un anillo alrededor del torso, la visera). "grupos": piezas que viajan
    juntas sin girar, con su disposicion (los dedos: si no, se cruzan)."""
    import random
    rnd = random.Random(pila.get("seed", 3))
    bpy.context.scene.frame_set(1)
    root_rot = R("relojero").matrix_world.to_3x3().normalized()
    cx, cy = pila["center"]
    arriba = set(pila.get("arriba", []))
    quietas = set(pila.get("quietas", []))
    grupo_de = {n: g for g, ns in pila.get("grupos", {}).items() for n in ns}
    anclas = {}

    ocupado = []          # (x, y, radio) de lo que ya esta en el piso

    def punto(rad=0.1):
        """Lugar libre en la pila (al despegar no se cruza con las vecinas)."""
        best = None
        for _ in range(80):
            ang = rnd.uniform(0, 2 * math.pi)
            rr = pila["radius"] * math.sqrt(rnd.random())
            x, y = cx + rr * math.cos(ang), cy + rr * math.sin(ang)
            gap = min([math.hypot(x - ox, y - oy) - rad - orad for ox, oy, orad in ocupado] or [1.0])
            if best is None or gap > best[0]:
                best = (gap, x, y)
            if gap > 0.02:
                break
        ocupado.append((best[1], best[2], rad))
        return Vector((best[1], best[2], 0.0))

    for name, spec in partes.items():
        if "from" in spec:
            continue
        ob = R(name)
        rest = ob.matrix_world.translation.copy()
        lie = 0.5 * min(ob.dimensions) + 0.01          # apoyada sobre su lado mas chato
        g = grupo_de.get(name)
        if g:
            if g not in anclas:
                anclas[g] = (punto(0.12), rest.copy())
            p0, r0 = anclas[g]
            start = p0 + (rest - r0)
            start.z = rest.z - r0.z + 0.06
        else:
            start = punto(0.5 * max(ob.dimensions[0], ob.dimensions[1]))
            start.z = lie
        P = ob.parent.matrix_world.to_3x3().normalized().inverted() if ob.parent else Matrix.Identity(3)
        spec["from"] = [round(v, 4) for v in P @ (start - rest)]
        if name in arriba:
            spec.setdefault("arc", round((rest.z - start.z) / 4 + 0.35, 3))   # llega bajando
        else:
            # punto de paso a 45 cm de su lugar, del lado por donde no hay nada:
            # brazos y manos por su costado, la llave por atras, el resto de frente
            side = name.rsplit("_", 1)[-1][:1] if "_" in name else ""
            lado = pila.get("lados", {"i": [1.0, -0.7, 0.0], "d": [-1.0, -0.7, 0.0]})
            if name in pila.get("vias", {}):
                local = Vector(pila["vias"][name])        # metros, en ejes del robot
            elif name.startswith(("hombrera_", "brazo_", "codo_bola_", "antebrazo_", "muneca_bola_", "palma_")):
                local = Vector(lado["i" if side == "i" else "d"]).normalized() * pila.get("paso", 0.45)
            else:
                local = Vector((0.0, -1.0, 0.0)) * pila.get("paso", 0.45)
            out = root_rot @ local
            spec["via"] = [round(v, 4) for v in P @ out]
            spec.setdefault("arc", pila.get("arc", 0.3))
        if g or name in quietas:
            spec.setdefault("spin", [0, 0, 0])
        else:
            # acostada sobre su lado mas chato, girada al azar sobre el piso: el
            # giro del despiece se suma a la rotacion local, asi que se pide la
            # diferencia exacta entre la orientacion tirada y la de reposo
            W0 = ob.matrix_world.to_3x3().normalized()
            dims = list(ob.dimensions)
            thin = Vector([1.0 if i == dims.index(min(dims)) else 0.0 for i in range(3)])
            flat = (W0 @ thin).rotation_difference(Vector((0, 0, 1))).to_matrix() @ W0
            Ws = Matrix.Rotation(rnd.uniform(-math.pi, math.pi), 3, "Z") @ flat
            Pw = ob.parent.matrix_world.to_3x3().normalized() if ob.parent else Matrix.Identity(3)
            rot0 = ob.rotation_euler.copy()
            want = (Pw.inverted() @ Ws).to_euler("XYZ", rot0)
            spec.setdefault("spin", [round(math.degrees(w - r0), 2) for w, r0 in zip(want, rot0)])
        # el rebotito solo en piezas grandes: en las que van justas las mete en la vecina
        if name in pila.get("clac_en", partes):
            spec.setdefault("clac", pila.get("clac", 0.012))


def _is_robot(ob, root):
    while ob is not None:
        if ob == root:
            return True
        ob = ob.parent
    return False


def glow_follow(mat, target, color, albedo, falloff):
    """Resplandor suave (aerografo sobre el cel) de una fuente que se mueve:
    la distancia sale de las coordenadas de objeto del vacio 'target'. Una
    luz puntual real, aun sin sombra, moteaba el cel. Devuelve el socket de
    intensidad para animarlo."""
    nt = mat.node_tree
    n, L = nt.nodes, nt.links
    em = next(x for x in n if x.type == "EMISSION")
    src = em.inputs["Color"].links[0].from_socket
    tc = n.new("ShaderNodeTexCoord")
    tc.object = target
    ln = n.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    L.new(tc.outputs["Object"], ln.inputs[0])
    q = n.new("ShaderNodeMath")
    q.operation = "DIVIDE"
    L.new(ln.outputs["Value"], q.inputs[0])
    q.inputs[1].default_value = falloff
    sq = n.new("ShaderNodeMath")
    sq.operation = "MULTIPLY"
    L.new(q.outputs[0], sq.inputs[0])
    L.new(q.outputs[0], sq.inputs[1])
    one = n.new("ShaderNodeMath")
    one.operation = "ADD"
    one.inputs[0].default_value = 1.0
    L.new(sq.outputs[0], one.inputs[1])
    k = n.new("ShaderNodeValue")
    k.outputs[0].default_value = 0.0
    dv = n.new("ShaderNodeMath")
    dv.operation = "DIVIDE"
    L.new(k.outputs[0], dv.inputs[0])
    L.new(one.outputs[0], dv.inputs[1])
    tint = n.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.inputs["Factor"].default_value = 0.5
    tint.inputs[6].default_value = lin(color)
    tint.inputs[7].default_value = lin(albedo)
    sc = n.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    L.new(tint.outputs[2], sc.inputs[0])
    L.new(dv.outputs[0], sc.inputs["Scale"])
    add = n.new("ShaderNodeVectorMath")
    add.operation = "ADD"
    L.new(src, add.inputs[0])
    L.new(sc.outputs[0], add.inputs[1])
    L.new(add.outputs[0], em.inputs["Color"])
    return k.outputs[0]


def _target(k, scene):
    """Punto del mundo de una clave de IK: "to" (mundo), "rel" (en ejes del
    robot) u "obj" + "off" (en ejes de ese objeto, que puede moverse)."""
    if "obj" in k:
        ob = R(k["obj"])
        return ob.matrix_world @ Vector(k.get("off", (0, 0, 0)))
    if "rel" in k:
        return R("relojero").matrix_world @ Vector(k["rel"])
    return Vector(k["to"])


def _ik_arm(keys, side, frames):
    """Brazo de dos tramos por IK analitica: el punto de agarre (GRIP) va al
    objetivo. Entre claves el objetivo se interpola (smoothstep) entre los dos
    puntos evaluados en ese frame: si una clave apunta a un objeto que se mueve
    (la perilla de la tapa que se abre), la mano lo sigue. Pisa las claves FK
    de hombro y codo; la muneca queda en FK."""
    scene = bpy.context.scene
    hombro = R(f"hombro_{side}")
    codo = R(f"codo_{side}")
    muneca = R(f"muneca_{side}")
    cintura = R("cintura")
    root = R("relojero")
    L1, L2 = ARM
    keys = sorted(keys, key=lambda k: k["frame"])
    for f in range(1, frames + 1):
        scene.frame_set(f)
        a = max([k for k in keys if k["frame"] <= f], key=lambda k: k["frame"], default=keys[0])
        b = min([k for k in keys if k["frame"] >= f], key=lambda k: k["frame"], default=keys[-1])
        pa, pb = _target(a, scene), _target(b, scene)
        t = 0.0 if b["frame"] == a["frame"] else (f - a["frame"]) / (b["frame"] - a["frame"])
        t = t * t * (3 - 2 * t)
        T = pa.lerp(pb, t)
        pole_l = Vector(a.get("pole", (0.6, 0.5, -0.6))).lerp(Vector(b.get("pole", (0.6, 0.5, -0.6))), t)
        pole = (root.matrix_world.to_3x3() @ pole_l).normalized()
        # "palm": hacia donde mira la palma (mundo). Entre dos claves con palma
        # se interpola; si no, la muneca queda en FK
        palm = None
        if "palm" in a and "palm" in b:
            palm = Vector(a["palm"]).normalized().lerp(Vector(b["palm"]).normalized(), t).normalized()
        S = hombro.matrix_world.translation.copy()
        R_c = cintura.matrix_world.to_3x3().normalized()
        R_w = muneca.rotation_euler.to_matrix()
        W = T.copy()
        for _ in range(4):
            d = min((W - S).length, L1 + L2 - 1e-3)
            u = (W - S).normalized()
            ca = (L1 * L1 - L2 * L2 + d * d) / (2 * d)
            h = math.sqrt(max(0.0, L1 * L1 - ca * ca))
            v = (pole - u * pole.dot(u)).normalized()
            E = S + u * ca + v * h
            D1 = (E - S).normalized()
            D2 = (W - E).normalized()
            # marco del hombro: -Z = brazo; el antebrazo dobla hacia -Y local
            Z = -D1
            Y = -(D2 - D1 * D2.dot(D1))
            Y = Y.normalized() if Y.length > 1e-6 else (pole - D1 * pole.dot(D1)).normalized()
            X = Y.cross(Z)
            M = Matrix((X, Y, Z)).transposed()
            th = -math.acos(max(-1.0, min(1.0, D1.dot(D2))))
            R_codo = Matrix.Rotation(th, 3, "X")
            if palm is not None:
                # palma (-Y local) hacia "palm"; los dedos (-Z) siguen al antebrazo
                Yw = -palm
                Zw = -(D2 - palm * D2.dot(palm))
                Zw = Zw.normalized() if Zw.length > 1e-6 else Z
                Xw = Yw.cross(Zw)
                R_w = (M @ R_codo).inverted() @ Matrix((Xw, Yw, Zw)).transposed()
            # el agarre esta corrido de la muneca: corregir el objetivo
            grip = M @ R_codo @ R_w @ Vector(GRIP)
            W = T - grip
        hombro.rotation_euler = (R_c.inverted() @ M).to_euler("XYZ")
        codo.rotation_euler = (th, 0.0, 0.0)
        hombro.keyframe_insert("rotation_euler", frame=f)
        codo.keyframe_insert("rotation_euler", frame=f)
        if palm is not None:
            muneca.rotation_euler = R_w.to_euler("XYZ")
            muneca.keyframe_insert("rotation_euler", frame=f)
    for ob in (hombro, codo, muneca):
        if not (ob.animation_data and ob.animation_data.action):
            continue
        for fc in action_fcurves(ob.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


def _pose(e, heart, mano, foco, brillos, strength):
    frames = ctx.CFG["frames"]
    obs = {j: R(j) for j in JOINTS}
    eye = R("ojo")
    for k in e.get("pose", []):
        f = k["frame"]
        for j in JOINTS:
            if j not in k:
                continue
            ob = obs[j]
            if j == "tapa":
                ob.rotation_euler = (math.radians(k[j]), 0, 0)
            else:
                ob.rotation_euler = [math.radians(a) for a in k[j]]
            ob.keyframe_insert("rotation_euler", frame=f)
        if "ojo" in k:
            eye["power"] = k["ojo"]
            eye.keyframe_insert('["power"]', frame=f)
        if "agarre" in k:
            for n in range(3):
                nud = R(f"nudillo_i{n}")
                nud.rotation_euler = (math.radians(-12 - 15 * k["agarre"]), 0, 0)
                nud.keyframe_insert("rotation_euler", frame=f)
        if "corazon" in k:
            for h in (heart, mano):
                h["power"] = k["corazon"]
                h.keyframe_insert('["power"]', frame=f)

    # el corazon sale del pecho sobre su eje (resorte): [f0, f1], metros
    eje = R("corazon_eje")
    f0, f1 = e.get("corazon_sale", (frames + 1, frames + 2))
    base = heart.location.copy()
    pop = e.get("corazon_sale_m", 0.1)
    for f, k in ((1, 0.0), (f0, 0.0), (f1, 1.0)):
        if f > frames:
            continue
        heart.location = base + Vector((0, -pop * k, 0))
        heart.keyframe_insert("location", frame=f)
        eje.scale = (1, 1, 0.05 + 0.95 * k * pop / 0.1)
        eje.keyframe_insert("scale", frame=f)

    scene = bpy.context.scene
    out = e.get("corazon_mano", frames + 1)
    cr = e.get("corazon_reloj")
    put = cr["slide"][0] if cr else frames + 1
    reloj = None
    if cr:
        # el corazon se monta en el eje vacio: cuelga de un engranaje fantasma
        # (mismo giro y engrane que tenia el pinon roto) y entra deslizando
        # por el eje (+z local) hasta su lugar
        ghost = bpy.data.objects[cr["gear"]]
        reloj = obj("corazon_reloj", heart.data, ghost, coll=heart.users_collection[0])
        reloj["power"] = 1.0
        s0, s1 = cr["slide"]
        for f, z in ((s0, cr.get("slide_m", 0.12)), (s1, 0.0)):
            reloj.location = (0, 0, z)
            reloj.keyframe_insert("location", frame=f)
        for g in cr.get("glow_gears", []):
            for m in {sl.material for sl in bpy.data.objects[g].material_slots}:
                brillos.append(glow_follow(m, foco, COLORS["corazon"], "#b08a3e", 0.1))

    # IK despues de lo que la mano va a buscar (la perilla, el corazon, el eje)
    if e.get("ik_i"):
        _ik_arm(e["ik_i"], "i", frames)

    # el corazon late (gira) en el pecho; afuera del cuerpo se queda quieto
    spin = e.get("corazon_spin", 120)
    base = heart.rotation_euler.copy()
    for f in (1, frames):
        heart.rotation_euler = base
        heart.rotation_euler.rotate_axis("Z", math.radians(spin * (f - 1) / ctx.CFG["fps"]))
        heart.keyframe_insert("rotation_euler", frame=f)
    for fc in action_fcurves(heart.animation_data.action):
        if fc.data_path == "rotation_euler":
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

    # al agarrarlo, la copia en la mano toma la pose exacta del original en
    # ese frame: no salta al cambiar de dueno
    muneca = R("muneca_i")
    if out <= frames:
        _catch(mano, heart, muneca, out)
    where = {"pecho": heart, "mano": mano, "reloj": reloj}
    for f, now in ((1, "pecho"), (out, "mano"), (put, "reloj")):
        if f > frames:
            continue
        for k, ob in where.items():
            if ob is not None:
                ob.hide_render = k != now
                ob.keyframe_insert("hide_render", frame=f)

    # el pinon roto: la mano lo saca del eje, lo mira y lo suelta
    pn = e.get("pinon")
    if pn and pn["grab"] <= frames:
        src = bpy.data.objects[pn["obj"]]
        en_mano = obj(src.name + "_mano", src.data, muneca, coll=src.users_collection[0])
        _catch(en_mano, src, muneca, pn["grab"])
        suelo = obj(src.name + "_suelo", src.data, None, coll=src.users_collection[0])
        drop = pn.get("drop", frames + 1)
        if drop <= frames:
            _fall(suelo, en_mano, drop, frames, pn.get("floor", 0.016))
        for f, now in ((1, src), (pn["grab"], en_mano), (drop, suelo)):
            if f > frames:
                continue
            for ob in (src, en_mano, suelo):
                ob.hide_render = ob is not now
                ob.keyframe_insert("hide_render", frame=f)

    # el resplandor sigue al corazon visible (un poco adelante) y brilla
    # segun la tapa: cerrada, el corazon no tine nada
    tapa = R("tapa")
    for f in range(1, frames + 1):
        scene.frame_set(f)
        h = reloj if f >= put else (mano if f >= out else heart)
        foco.location = h.matrix_world @ Vector((0, 0, 0.08))
        foco.keyframe_insert("location", frame=f)
        open_ = 1.0 if f >= out else min(1.0, abs(math.degrees(tapa.rotation_euler.x)) / 60.0)
        for v in brillos:
            v.default_value = strength * float(h.get("power", 1.0)) * open_
            v.keyframe_insert("default_value", frame=f)


def _catch(copy, src, hand, f):
    """La copia (hija de la mano) queda donde estaba src en el frame f."""
    scene = bpy.context.scene
    scene.frame_set(f)
    copy.parent = hand
    copy.matrix_parent_inverse = Matrix.Identity(4)
    copy.matrix_basis = hand.matrix_world.inverted() @ src.matrix_world


def _fall(ob, src, f0, frames, floor):
    """Cae desde donde esta src en f0, girando, y queda plano en el piso."""
    scene = bpy.context.scene
    scene.frame_set(f0)
    m0 = src.matrix_world.copy()
    p0 = m0.translation.copy()
    q0 = m0.to_quaternion()
    q1 = Euler((0, 0, q0.to_euler().z)).to_quaternion()     # plano, con su giro
    fps = ctx.CFG["fps"]
    t_land = math.sqrt(max(0.0, 2 * (p0.z - floor) / 9.8))
    for f in range(1, frames + 1):
        t = max(0.0, (f - f0) / fps)
        k = min(1.0, t / t_land) if t_land > 0 else 1.0
        z = max(floor, p0.z - 4.9 * t * t)
        loc = Vector((p0.x, p0.y, z))
        q = q0.slerp(q1, k * k)
        ob.matrix_world = Matrix.Translation(loc) @ q.to_matrix().to_4x4()
        ob.keyframe_insert("location", frame=f)
        ob.keyframe_insert("rotation_euler", frame=f)
    for fc in action_fcurves(ob.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


# --- la esfera del reloj, desde adentro ------------------------------------

def mat_vidrio(name, top, bottom, strength=1.0, r=1.0, noche=None):
    """Vidrio esmerilado de la esfera, visto desde adentro de noche: degradado
    suave (aerografo) del resplandor de la ciudad abajo al cielo arriba, la
    silueta difusa de los edificios con ventanas, y lluvia sobre el vidrio
    (hilos que bajan y gotas). Afuera llueve: adentro se tiene que notar.
    Todo funcion pura del frame (el tiempo es un nodo Value animado)."""
    noche = noche or {}
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    n, L = nt.nodes, nt.links

    def m(op, a, b=None):
        node = n.new("ShaderNodeMath")
        node.operation = op
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                node.inputs[i].default_value = x
            else:
                L.new(x, node.inputs[i])
        return node.outputs[0]

    def mix(fac, c1, c2):
        node = n.new("ShaderNodeMix")
        node.data_type = "RGBA"
        for sock, x in ((node.inputs["Factor"], fac), (node.inputs[6], c1), (node.inputs[7], c2)):
            if isinstance(x, str):
                sock.default_value = lin(x)
            elif isinstance(x, (int, float)):
                sock.default_value = x
            else:
                L.new(x, sock)
        return node.outputs[2]

    def noise1(v):
        wn = n.new("ShaderNodeTexWhiteNoise")
        wn.noise_dimensions = "1D"
        L.new(v, wn.inputs["W"])
        return wn.outputs["Value"]

    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Object"], sep.inputs[0])
    x, y = sep.outputs[0], sep.outputs[1]
    # tiempo en segundos, lineal con el frame
    tv = n.new("ShaderNodeValue")
    frames, fps = ctx.CFG["frames"], ctx.CFG["fps"]
    tv.outputs[0].default_value = 0.0
    tv.outputs[0].keyframe_insert("default_value", frame=1)
    tv.outputs[0].default_value = (frames - 1) / fps
    tv.outputs[0].keyframe_insert("default_value", frame=frames)
    from piezas.base import set_interp
    set_interp(nt, "LINEAR")
    t = tv.outputs[0]

    mr = n.new("ShaderNodeMapRange")
    mr.interpolation_type = "SMOOTHSTEP"
    L.new(y, mr.inputs["Value"])
    mr.inputs["From Min"].default_value = -r
    mr.inputs["From Max"].default_value = r * 0.6
    col = mix(mr.outputs["Result"], bottom, top)

    if noche and noche.get("paisaje") == "arboles":
        # San Isidro: copas de arboles abajo (dos capas, la de atras con bruma),
        # faroles calidos que asoman entre las copas y la noche arriba
        def copa(w, seed, base, var):
            # una fila de copas redondas: medio circulo por celda de ancho w,
            # alto al azar por celda y borde de hojas (ruido fino)
            cel = m("FLOOR", m("ADD", m("DIVIDE", x, w * r), seed))
            u = m("SUBTRACT", m("FRACT", m("ADD", m("DIVIDE", x, w * r), seed)), 0.5)
            bump = m("MULTIPLY", m("SQRT", m("MAXIMUM", 0.0, m("SUBTRACT", 0.25, m("MULTIPLY", u, u)))),
                     1.6 * w * r)
            alto = m("MULTIPLY", noise1(m("ADD", cel, seed * 13.0)), var * r)
            nz = n.new("ShaderNodeTexNoise")
            nz.noise_dimensions = "2D"
            nz.inputs["Scale"].default_value = 26.0
            cmb = n.new("ShaderNodeCombineXYZ")
            L.new(m("DIVIDE", x, r), cmb.inputs[0])
            L.new(m("DIVIDE", y, r), cmb.inputs[1])
            L.new(cmb.outputs[0], nz.inputs["Vector"])
            hojas = m("MULTIPLY", m("SUBTRACT", nz.outputs["Fac"], 0.5), 0.05 * r)
            borde = m("ADD", m("ADD", m("ADD", base * r, bump), alto), hojas)
            return m("LESS_THAN", y, borde)

        lejos = copa(0.2, 0.37, -0.32, 0.12)
        col = mix(m("MULTIPLY", lejos, 0.7), col, noche.get("copa_lejos", "#2a2650"))
        cerca = copa(0.32, 0.81, -0.62, 0.16)
        col = mix(m("MULTIPLY", cerca, 0.92), col, noche.get("copa", "#14202c"))
        # faroles: luz calida que asoma entre las copas (encima, suave)
        for i, (lx, ly) in enumerate(noche.get("faroles", [(-0.5, -0.28), (0.12, -0.36), (0.6, -0.26)])):
            d2 = m("ADD", m("MULTIPLY", m("SUBTRACT", x, lx * r), m("SUBTRACT", x, lx * r)),
                   m("MULTIPLY", m("SUBTRACT", y, ly * r), m("SUBTRACT", y, ly * r)))
            g = m("DIVIDE", 0.5, m("ADD", 1.0, m("DIVIDE", d2, (0.07 * r) ** 2)))
            col = mix(g, col, noche.get("farol", "#ffcf8a"))
        # lluvia: hilos que bajan, uno por carril, con velocidad y largo propios
        lw = r / noche.get("carriles", 46)
        lane = m("FLOOR", m("DIVIDE", x, lw))
        rr = noise1(lane)
        rr2 = noise1(m("ADD", lane, 37.0))
        thin = m("LESS_THAN", m("FRACT", m("DIVIDE", x, lw)), 0.14)
        speed = m("ADD", 0.25, m("MULTIPLY", rr, 0.5))
        v = m("FRACT", m("ADD", m("ADD", m("DIVIDE", y, 2 * r), m("MULTIPLY", t, speed)), m("MULTIPLY", rr, 7.0)))
        seg = m("LESS_THAN", v, 0.16)
        head = m("SUBTRACT", 1.0, m("DIVIDE", v, 0.16))
        streak = m("MULTIPLY", m("MULTIPLY", m("MULTIPLY", thin, seg), head), m("LESS_THAN", rr2, 0.55))
        col = mix(m("MULTIPLY", streak, noche.get("lluvia_alfa", 0.45)), col, noche.get("lluvia", "#f0dcff"))
        vor = n.new("ShaderNodeTexVoronoi")
        vor.inputs["Scale"].default_value = noche.get("gotas", 9.0) / r
        L.new(tc.outputs["Object"], vor.inputs["Vector"])
        drop = m("LESS_THAN", vor.outputs["Distance"], 0.07)
        col = mix(m("MULTIPLY", drop, 0.3), col, noche.get("lluvia", "#f0dcff"))
    elif noche:
        # edificios detras del vidrio: una silueta por franja, alto al azar
        nb = noche.get("edificios", 9)
        cell = m("FLOOR", m("DIVIDE", x, 2 * r / nb))
        h = noise1(cell)
        top_y = m("ADD", -0.62 * r, m("MULTIPLY", h, 0.55 * r))
        inb = m("LESS_THAN", y, top_y)
        col = mix(m("MULTIPLY", inb, 0.72), col, noche.get("edificio", "#2a1a44"))
        # ventanas encendidas (borrosas: el vidrio es esmerilado)
        wx = m("FRACT", m("DIVIDE", x, 0.075 * r))
        wy = m("FRACT", m("DIVIDE", y, 0.095 * r))
        rect = m("MULTIPLY", m("MULTIPLY", m("GREATER_THAN", wx, 0.3), m("LESS_THAN", wx, 0.7)),
                 m("MULTIPLY", m("GREATER_THAN", wy, 0.3), m("LESS_THAN", wy, 0.7)))
        comb = n.new("ShaderNodeCombineXYZ")
        L.new(m("FLOOR", m("DIVIDE", x, 0.075 * r)), comb.inputs[0])
        L.new(m("FLOOR", m("DIVIDE", y, 0.095 * r)), comb.inputs[1])
        wn = n.new("ShaderNodeTexWhiteNoise")
        wn.noise_dimensions = "3D"
        L.new(comb.outputs[0], wn.inputs["Vector"])
        lit = m("MULTIPLY", m("MULTIPLY", rect, inb), m("LESS_THAN", wn.outputs["Value"], 0.32))
        wcol = mix(m("GREATER_THAN", wn.outputs["Value"], 0.16), noche.get("ventana_fria", "#9ff0ff"),
                   noche.get("ventana", "#ffc56b"))
        col = mix(m("MULTIPLY", lit, 0.55), col, wcol)
        # lluvia: hilos que bajan, uno por carril, con velocidad y largo propios
        lw = r / noche.get("carriles", 46)
        lane = m("FLOOR", m("DIVIDE", x, lw))
        rr = noise1(lane)
        rr2 = noise1(m("ADD", lane, 37.0))
        thin = m("LESS_THAN", m("FRACT", m("DIVIDE", x, lw)), 0.14)
        speed = m("ADD", 0.25, m("MULTIPLY", rr, 0.5))
        v = m("FRACT", m("ADD", m("ADD", m("DIVIDE", y, 2 * r), m("MULTIPLY", t, speed)), m("MULTIPLY", rr, 7.0)))
        seg = m("LESS_THAN", v, 0.16)
        head = m("SUBTRACT", 1.0, m("DIVIDE", v, 0.16))
        streak = m("MULTIPLY", m("MULTIPLY", m("MULTIPLY", thin, seg), head), m("LESS_THAN", rr2, 0.55))
        col = mix(m("MULTIPLY", streak, noche.get("lluvia_alfa", 0.45)), col, noche.get("lluvia", "#f0dcff"))
        # gotas quietas sobre el vidrio
        vor = n.new("ShaderNodeTexVoronoi")
        vor.inputs["Scale"].default_value = noche.get("gotas", 9.0) / r
        L.new(tc.outputs["Object"], vor.inputs["Vector"])
        drop = m("LESS_THAN", vor.outputs["Distance"], 0.07)
        col = mix(m("MULTIPLY", drop, 0.3), col, noche.get("lluvia", "#f0dcff"))

    sc = n.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    L.new(col, sc.inputs[0])
    k = n.new("ShaderNodeMath")
    k.operation = "MULTIPLY"
    k.inputs[0].default_value = strength
    L.new(_power(nt), k.inputs[1])
    L.new(k.outputs[0], sc.inputs["Scale"])
    _emit_out(nt, sc.outputs[0])
    mat["neon"] = True
    return mat


def build_esfera(e, colls):
    """Esfera vertical que mira a -Y, vista desde adentro: vidrio iluminado,
    marco y parteluces de hierro, marcas de las horas y agujas en silueta."""
    main, neon = colls["main"], colls["neon"]
    r = e["r"]
    m_iron = mat_toon("esfera_hierro", e.get("iron", "#1c1826"))
    root = obj("esfera", None, None, e["at"], (90, 0, 0), coll=main)
    obj("esfera_vidrio", cyl("esfera_vidrio", r, r, 0.02, segs=96), root, (0, 0, -0.03),
        mat=mat_vidrio("vidrio", e.get("top", "#9fd2ff"), e.get("bottom", "#ff5fa8"),
                       e.get("strength", 1.0), r, e.get("noche")), coll=neon)
    obj("esfera_marco", annulus("esfera_marco", r * 0.995, r * 1.08, 0.14, segs=96), root, mat=m_iron, coll=main)
    obj("esfera_aro", annulus("esfera_aro", r * 0.28, r * 0.31, 0.06, segs=64), root, mat=m_iron, coll=main)
    for k in range(12):
        a = 2 * math.pi * k / 12
        # parteluz radial y marca de la hora
        bar = obj(f"parteluz{k}", boxc(f"parteluz{k}", 0.035, r * 0.7, 0.05), root,
                  (0, 0, 0), (0, 0, math.degrees(a)), m_iron, main)
        for v in bar.data.vertices:
            v.co.y += r * 0.645
        mk = obj(f"marca{k}", boxc(f"marca{k}", r * (0.05 if k % 3 else 0.08), r * 0.12, 0.06),
                 root, (0, 0, 0), (0, 0, math.degrees(a)), m_iron, main)
        for v in mk.data.vertices:
            v.co.y += r * 0.83
    # agujas: desde adentro el reloj esta espejado (giran al reves)
    hh, mm = e.get("hora", (11, 59))
    for name, ang, ln, w in (("aguja_hora", (hh % 12 + mm / 60) * 30, 0.55, 0.07),
                             ("aguja_minuto", mm * 6, 0.86, 0.045)):
        ag = obj(name, boxc(name, r * w, r * ln, 0.05), root, (0, 0, 0.06), (0, 0, ang), m_iron, main)
        for v in ag.data.vertices:
            v.co.y += r * ln * 0.42


def build_sala(e, colls):
    """Sala de maquinas: piso de tablas y cuatro paredes oscuras (la del fondo
    tiene la esfera adelante). "room": [x0, x1, y0, y1] de las paredes."""
    main = colls["main"]
    floor = e.get("floor", "#2b1f1c")
    obj("piso", box_mesh("piso", 20, 20, 0.1), None, (0, 0, -0.1), mat=mat_toon("piso", floor), coll=main)
    m = mat_toon("pared", e.get("wall", "#1a1424"))
    w = e.get("wall_y", 2.0)
    obj("pared", box_mesh("pared", 20, 0.3, 12), None, (0, w, 0), mat=m, coll=main)
    if "room" in e:
        x0, x1, y0, _ = e["room"]
        obj("pared_izq", box_mesh("pared_izq", 0.3, 20, 12), None, (x0, 0, 0), mat=m, coll=main)
        obj("pared_der", box_mesh("pared_der", 0.3, 20, 12), None, (x1, 0, 0), mat=m, coll=main)
        obj("pared_frente", box_mesh("pared_frente", 20, 0.3, 12), None, (0, y0, 0), mat=m, coll=main)
        # el sol hace de lampara de la sala: las paredes no le pueden hacer sombra
        for n in ("pared_izq", "pared_der", "pared_frente"):
            bpy.data.objects[n].visible_shadow = False


# --- la ciudad: la torre del reloj y el pulso ---------------------------------

def build_torre(e, colls):
    """Torre del reloj vista desde la avenida, inspirada en el Palacio Barolo:
    cuerpo de piedra con ventanas, torre escalonada, esfera iluminada al
    frente (-y), linterna octogonal y faro arriba con su haz girando.
    "at": base (x, y). Todo en metros."""
    main, neon = colls["main"], colls["neon"]
    x0, y0 = e["at"]
    S = e.get("scale", 1.0)        # todo el edificio escala (y la esfera con el)
    stone = e.get("stone", "#d8c8a8")
    win = e.get("windows")
    clock_z = e.get("clock_z", 74.0) * S
    glows = [{"kind": "point", "at": (x0, y0 - 6.0 * S, clock_z), "color": e.get("clock_color", "#ffe2a8"),
              "strength": 0.9, "falloff": 9.0 * S, "prop": "glow_reloj"}]
    m_stone = mat_toon("torre_piedra", stone, windows=win, glows=glows)
    m_top = mat_toon("torre_cupula", e.get("dome", "#b9a98c"), glows=glows)
    m_iron = mat_toon("torre_hierro", "#1c1826")
    root = obj("torre", None, None, (x0, y0, 0), coll=main)
    root.scale = (S, S, S)
    root["glow_reloj"] = 1.0
    # cuerpo, torre escalonada y linterna
    for name, (sx, sy, z0, h) in {"torre_cuerpo": (34, 22, 0, 62), "torre_paso": (20, 16, 62, 6),
                                  "torre_torre": (14, 12, 68, 14), "torre_corona": (16, 14, 82, 2)}.items():
        ob = obj(name, box_mesh(name, sx, sy, h), root, (0, 0, z0), mat=m_stone if z0 < 84 else m_top, coll=main)
        ob["glow_reloj"] = 1.0
    lint = obj("torre_linterna", cyl("torre_linterna", 6.0, 4.2, 12, segs=8, z0=84), root, mat=m_top, coll=main)
    lint["glow_reloj"] = 1.0
    obj("torre_aguja", cyl("torre_aguja", 1.2, 0.5, 8, segs=8, z0=96), root, mat=m_iron, coll=main)
    # faro: lampara y haz que gira
    obj("torre_faro", sphere("torre_faro", 1.3), root, (0, 0, 104.5), mat=mat_neon("faro_m", e.get("beacon", "#fff0c0"), 2.0), coll=neon)
    haz = obj("torre_haz", None, root, (0, 0, 104.5), coll=main)
    cone = bpy.data.meshes.new("torre_haz_cono")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=16, radius1=0.6, radius2=9.0, depth=90)
    for v in bm.verts:
        v.co.z += 45
    bm.to_mesh(cone)
    bm.free()
    obj("torre_haz_cono", cone, haz, rot=(90, 0, 0), mat=mat_beam("faro_haz", e.get("beacon", "#fff0c0"), 0.07), coll=colls["veil"])
    spin = e.get("beacon_spin", 40)      # grados/s
    stop = e.get("beacon_stop")          # frame en que se traba (desincronia)
    fps = ctx.CFG["fps"]
    for f in range(1, ctx.CFG["frames"] + 1):
        ff = f if not stop or f < stop else stop + (f - stop) * 0.02
        haz.rotation_euler = (0, 0, math.radians(spin * (ff - 1) / fps + e.get("beacon_phase", 0)))
        haz.keyframe_insert("rotation_euler", frame=f)
    # esfera del reloj: vidrio calido, marco, marcas y agujas
    r = e.get("clock_r", 5.2)
    face = obj("torre_esfera", None, root, (0, -6.05, clock_z / S), (90, 0, 0), coll=main)
    m_face = mat_neon("torre_esfera_m", e.get("clock_color", "#ffe2a8"), e.get("clock_strength", 1.1))
    vid = obj("torre_vidrio", cyl("torre_vidrio", r, r, 0.1, segs=64), face, (0, 0, -0.05), mat=m_face, coll=neon)
    vid["glow_reloj"] = 1.0
    obj("torre_marco", annulus("torre_marco", r * 0.99, r * 1.12, 0.6, segs=64), face, mat=m_iron, coll=main)
    for k in range(12):
        mk = obj(f"torre_marca{k}", boxc(f"torre_marca{k}", r * 0.07, r * 0.16, 0.3), face, (0, 0, 0.1),
                 (0, 0, -30 * k), m_iron, main)
        for v in mk.data.vertices:
            v.co.y += r * 0.8
    hh, mm = e.get("hora", (23, 59))
    for name, ang, ln, w in (("torre_aguja_h", (hh % 12 + mm / 60) * 30, 0.5, 0.09),
                             ("torre_aguja_m", mm * 6, 0.82, 0.06)):
        ag = obj(name, boxc(name, r * w, r * ln, 0.3), face, (0, 0, 0.25), (0, 0, -ang), m_iron, main)
        for v in ag.data.vertices:
            v.co.y += r * ln * 0.42


def build_pulso(e, colls):
    """La ciudad late con el reloj: en cada tic todo lo que emite sube de golpe
    y decae (exponencial). "desync": desde ese frame cada luz pierde el compas
    (fase y ritmo propios), algunas titilan y se apagan."""
    import random
    rnd = random.Random(e.get("seed", 7))
    fps = ctx.CFG["fps"]
    frames = ctx.CFG["frames"]
    bps, lo, hi, decay = e.get("bps", 1.0), e.get("lo", 0.62), e.get("hi", 1.0), e.get("decay", 0.35)
    off = e.get("offset", 0.0)
    ds = e.get("desync")

    def env(t):
        dt = t - math.floor(t)
        return math.exp(-dt / bps / decay)

    targets = [o for o in list(colls["neon"].objects) + list(colls["main"].objects) + list(colls["veil"].objects)
               if o.type in ("MESH", "CURVE", "FONT") and not o.get("keep")]
    for ob in targets:
        ph, rate = rnd.random(), bps * (1 + rnd.uniform(-0.45, 0.45))
        dies = ds and rnd.random() < ds.get("die", 0.35)
        f_die = ds["frame"] + rnd.randint(4, ds.get("spread", 30)) if dies else frames + 1
        revive = ds and rnd.random() < ds.get("revive", 0.0)
        for f in range(1, frames + 1):
            t = (f - 1) / fps * bps + off
            if ds and f >= ds["frame"]:
                td = (f - ds["frame"]) / fps
                t = (ds["frame"] - 1) / fps * bps + off + td * rate + ph
                p = lo * 0.8 + (hi - lo * 0.8) * env(t)
                if f >= f_die:
                    # se apaga; algunas vuelven a titilar de a ratos ("revive")
                    p = 0.0 if (f - f_die) > 2 or rnd.random() < 0.6 else 1.0
                    if revive and rnd.random() < 0.12:
                        p = rnd.uniform(0.5, 1.0)
            else:
                p = lo + (hi - lo) * env(t)
            ob["power"] = p
            ob.keyframe_insert('["power"]', frame=f)
    # faroles y vidrieras (luces puntuales): la misma curva sobre su energia
    for lo_ob in colls["lights"].objects:
        if lo_ob.type != "LIGHT" or lo_ob.data.type == "SUN" or lo_ob.get("keep"):
            continue
        e0 = lo_ob.data.energy
        for f in range(1, frames + 1):
            t = (f - 1) / fps * bps + off
            k = lo + (hi - lo) * env(t) if not ds or f < ds["frame"] else rnd.uniform(0.2, 1.0)
            lo_ob.data.energy = e0 * k
            lo_ob.data.keyframe_insert("energy", frame=f)


# --- la subida: escalera caracol dentro de la torre --------------------------

def build_escalera(e, colls):
    """Escalera caracol (sube girando en sentido antihorario visto desde arriba):
    escalones en cuna alrededor de una columna, baranda en espiral, muro
    cilindrico con ventanas angostas (la ciudad de noche bajo la lluvia) y, arriba,
    la abertura a la sala de maquinas por donde baja la luz calida."""
    main, neon = colls["main"], colls["neon"]
    cx, cy = e.get("center", (0.0, 0.0))
    r_in, r_out = e.get("r_in", 0.25), e.get("r_out", 1.15)
    rise, per_turn, n = e.get("rise", 0.2), e.get("per_turn", 16), e.get("steps", 34)
    th = e.get("thick", 0.07)
    m_step = mat_toon("escalon", e.get("step", "#5a4636"))
    m_iron = mat_toon("escalera_hierro", e.get("iron", "#1c1826"))
    m_wall = mat_toon("torre_muro", e.get("wall", "#2a2234"))
    dth = 2 * math.pi / per_turn
    root = obj("escalera", None, None, (cx, cy, 0), coll=main)
    for k in range(n):
        a0, z = k * dth + e.get("phase", 0.0), k * rise
        bm = bmesh.new()
        segs = 4
        ring = [(r_in, a0 + dth * i / segs) for i in range(segs + 1)] +                [(r_out, a0 + dth * i / segs) for i in reversed(range(segs + 1))]
        top = [bm.verts.new((rr * math.cos(a), rr * math.sin(a), z)) for rr, a in ring]
        bot = [bm.verts.new((rr * math.cos(a), rr * math.sin(a), z - th)) for rr, a in ring]
        bm.faces.new(top)
        bm.faces.new(list(reversed(bot)))
        for i in range(len(ring)):
            j = (i + 1) % len(ring)
            bm.faces.new((bot[i], bot[j], top[j], top[i]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        mesh = bpy.data.meshes.new(f"escalon{k}")
        bm.to_mesh(mesh)
        bm.free()
        obj(f"escalon{k}", mesh, root, mat=m_step, coll=main)
        # parante de la baranda en el borde de afuera
        am = a0 + dth * 0.5
        # el pasamanos pasa por aca medio escalon mas arriba (0,9 + rise/2): el parante llega
        obj(f"parante{k}", cyl(f"parante{k}", 0.015, 0.015, 0.9 + rise * 0.5, segs=8), root,
            ((r_out - 0.05) * math.cos(am), (r_out - 0.05) * math.sin(am), z), mat=m_iron, coll=main)
    h_total = n * rise + 1.5
    obj("columna", cyl("columna", r_in, r_in, h_total, segs=24, z0=-0.2), root, mat=m_iron, coll=main)
    # pasamanos: tubo en espiral a 0,9 m sobre cada escalon
    bm = bmesh.new()
    pts = [((r_out - 0.05) * math.cos(t), (r_out - 0.05) * math.sin(t), (t - e.get("phase", 0.0)) / dth * rise + 0.9)
           for t in [e.get("phase", 0.0) + dth * 0.5 + i * dth / 4 for i in range((n - 1) * 4 + 1)]]
    rings = []
    for (x, y, z) in pts:
        rad = Vector((x, y, 0)).normalized()
        rings.append([bm.verts.new(Vector((x, y, z)) + rad * 0.02 * math.cos(2 * math.pi * j / 6)
                                   + Vector((0, 0, 0.02 * math.sin(2 * math.pi * j / 6)))) for j in range(6)])
    for a, b in zip(rings, rings[1:]):
        for j in range(6):
            bm.faces.new((a[j], a[(j + 1) % 6], b[(j + 1) % 6], b[j]))
    mesh = bpy.data.meshes.new("pasamanos")
    bm.to_mesh(mesh)
    bm.free()
    obj("pasamanos", mesh, root, mat=m_iron, coll=main)
    # muro de la torre, con la cara hacia adentro
    R = e.get("r_wall", 1.6)
    # corte: el muro mira hacia adentro y se dibuja de un solo lado, asi desde
    # afuera la mitad cercana no se ve y la de atras hace de fondo. Sin tinta
    # (Line Art dibujaria la mitad cercana igual): va en la coleccion "velo".
    m_wall.use_backface_culling = True
    wall = obj("muro", cyl("muro", R, R, h_total + 1, segs=48, z0=-0.5), root, mat=m_wall, coll=colls["veil"])
    for poly in wall.data.polygons:
        poly.flip()
    wall.visible_shadow = False
    # ventanas angostas: la noche de afuera (mismo vidrio que la esfera)
    m_win = mat_vidrio("ventana_torre", "#1d1c4c", "#c4428f", 0.9, 0.6, e.get("noche"))
    for k in range(e.get("ventanas", 6)):
        a = math.radians(e.get("ventana_ang", 200)) + k * math.radians(e.get("ventana_paso", 70))
        z = 1.2 + k * e.get("ventana_dz", 1.1)
        obj(f"ventana{k}", boxc(f"ventana{k}", 0.05, 0.22, 0.9), root,
                ((R - 0.02) * math.cos(a), (R - 0.02) * math.sin(a), z), (0, 0, math.degrees(a)), m_win, neon)
    # la abertura de arriba: luz calida de la sala de maquinas
    obj("abertura", cyl("abertura", R * 0.95, R * 0.95, 0.05, segs=48, z0=h_total - 0.2), root,
        mat=mat_neon("abertura_m", e.get("luz", "#ffd9a0"), e.get("luz_fuerza", 1.4)), coll=neon)


def _two_bone(S, T, pole, L1, L2, R_parent):
    """IK de dos tramos (como el brazo). Devuelve (rotacion local del primer
    pivote, angulo del segundo sobre su X, matriz de mundo del segundo tramo)."""
    d = min(max((T - S).length, 1e-4), L1 + L2 - 1e-4)
    u = (T - S).normalized()
    ca = (L1 * L1 - L2 * L2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, L1 * L1 - ca * ca))
    v = (pole - u * pole.dot(u)).normalized()
    E = S + u * ca + v * h
    D1 = (E - S).normalized()
    D2 = (T - E).normalized()
    Z = -D1
    Y = -(D2 - D1 * D2.dot(D1))
    Y = Y.normalized() if Y.length > 1e-6 else (pole - D1 * pole.dot(D1)).normalized()
    X = Y.cross(Z)
    M = Matrix((X, Y, Z)).transposed()
    th = -math.acos(max(-1.0, min(1.0, D1.dot(D2))))
    return (R_parent.inverted() @ M).to_euler("XYZ"), th, M @ Matrix.Rotation(th, 3, "X")


def _camino(e, frames):
    """Sube la escalera caracol como se sube una escalera: los pies apoyan en
    escalones reales y la rodilla dobla. Un escalon por tic: en cada tic el pie
    de atras se levanta en arco y se planta dos escalones mas arriba (alternan).
    El cuerpo sube y gira continuo, con un vaiven chico; el tobillo deja el pie
    plano. Mira en la direccion de la helice (sentido antihorario)."""
    c = e["camino"]
    root = R("relojero")
    cx, cy = c.get("center", (0.0, 0.0))
    r, rise, per_turn = c["r"], c["rise"], c.get("per_turn", 16)
    dth = 2 * math.pi / per_turn
    fs, k0, f0 = c.get("frames_step", 6), c.get("step0", 0), c.get("start", 1)
    ph = c.get("phase", 0.0) + dth * 0.5
    z0 = c.get("z0", 0.0)
    scene = bpy.context.scene
    cint = R("cintura")
    lado = {"i": -1.0, "d": 1.0}             # va antihorario: su izquierda mira al centro

    def ss(t):
        t = min(1.0, max(0.0, t))
        return t * t * (3 - 2 * t)

    def en_helice(rr, ang, z):
        return Vector((cx + rr * math.cos(ang), cy + rr * math.sin(ang), z))

    def pie(side, j):
        """Tobillo apoyado en el escalon j (6 cm sobre la huella), un poco hacia
        atras en la huella: si no, la canilla inclinada roza el borde del siguiente."""
        ang = ph + (j - c.get("atras", 0.15)) * dth
        return en_helice(r + 0.13 * lado[side], ang, j * rise + 0.06 + z0)

    def progreso(f):
        t = max(0.0, (f - f0) / fs)
        k, u = int(t), t - int(t)
        return k, u, k + ss(u)               # el cuerpo avanza con el tic, sin saltos

    for f in range(1, frames + 1):
        k, u, sp = progreso(f)
        # el cuerpo va medio escalon detras del pie de adelante y 15 cm mas abajo:
        # asi la pierna de atras (a 20 cm en horizontal) no se estira de mas (56 cm)
        ang = ph + (k0 + sp - 0.5) * dth
        bob = 0.02 * math.sin(math.pi * u)
        root.location = en_helice(r, ang, (k0 + sp - 0.5) * rise - 0.15 + z0 + bob)
        root.rotation_euler = (0, math.radians(2.5 * math.sin(math.pi * (k + u))), ang + math.pi)
        root.keyframe_insert("location", frame=f)
        root.keyframe_insert("rotation_euler", frame=f)
        cint.rotation_euler = (math.radians(8 + 2 * math.sin(math.pi * u)), 0,
                               math.radians(3 * math.sin(math.pi * (k + u))))
        cint.keyframe_insert("rotation_euler", frame=f)
        # en el tic k se mueve un pie (alternan): sube del escalon k0+k-1 al k0+k+1;
        # el otro queda apoyado en el k0+k (ahi lo dejo el tic anterior)
        mueve = "i" if k % 2 == 0 else "d"
        for side in ("i", "d"):
            if side == mueve:
                w = ss(u)
                z = (pie(side, k0 + k - 1).z * (1 - w) + pie(side, k0 + k + 1).z * w
                     + (0.16 + rise) * 0.6 * math.sin(math.pi * w))     # arco sobre el escalon del medio
                # sigue la helice (radio constante), no la cuerda
                T = en_helice(r + 0.13 * lado[side], ph + (k0 + k - 1 + 2 * w - c.get("atras", 0.15)) * dth, z)
            else:
                T = pie(side, k0 + k)
            scene.frame_set(f)
            cad = R(f"cadera_{side}")
            rod = R(f"rodilla_{side}")
            tob = R(f"tobillo_{side}")
            S = cad.matrix_world.translation.copy()
            R_root = root.matrix_world.to_3x3().normalized()
            fwd = R_root @ Vector((0, -1, 0))
            rot_cad, th, M_shin = _two_bone(S, T, (fwd + Vector((0, 0, 0.2))).normalized(), LEG[0], LEG[1], R_root)
            cad.rotation_euler = rot_cad
            rod.rotation_euler = (th, 0, 0)
            # pie plano: la orientacion de mundo del pie = la del cuerpo (solo el giro)
            tob.rotation_euler = (M_shin.inverted() @ R_root).to_euler("XYZ")
            for ob in (cad, rod, tob):
                ob.keyframe_insert("rotation_euler", frame=f)
            # brazos: acompanan al reves que las piernas
            hom = R(f"hombro_{side}")
            sw = math.sin(math.pi * u) * (1 if side == mueve else -1)
            hom.rotation_euler = (math.radians(14 * sw), 0, math.radians(6 if side == "i" else -6))
            hom.keyframe_insert("rotation_euler", frame=f)
    for name in ("relojero", "cintura", "cadera_i", "cadera_d", "rodilla_i", "rodilla_d", "tobillo_i", "tobillo_d",
                 "hombro_i", "hombro_d"):
        ob = R(name)
        for fc in action_fcurves(ob.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


# --- la Catedral de San Isidro ------------------------------------------------

def mat_franjas(name, base, band, pitch=2.6, width=0.3):
    """Ladrillo con franjas horizontales de piedra crema (por altura de mundo),
    como la catedral: toon de mat_toon con el color base reemplazado."""
    mat = mat_toon(name, base)
    nt = mat.node_tree
    n, L = nt.nodes, nt.links
    mul = next(x for x in n if x.type == "MIX" and x.blend_type == "MULTIPLY" and not x.inputs[6].is_linked)
    geo = n.new("ShaderNodeNewGeometry")
    sep = n.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])
    d = n.new("ShaderNodeMath")
    d.operation = "DIVIDE"
    L.new(sep.outputs[2], d.inputs[0])
    d.inputs[1].default_value = pitch
    fr = n.new("ShaderNodeMath")
    fr.operation = "FRACT"
    L.new(d.outputs[0], fr.inputs[0])
    lt = n.new("ShaderNodeMath")
    lt.operation = "LESS_THAN"
    L.new(fr.outputs[0], lt.inputs[0])
    lt.inputs[1].default_value = width / pitch
    mx = n.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    L.new(lt.outputs[0], mx.inputs["Factor"])
    mx.inputs[6].default_value = lin(base)
    mx.inputs[7].default_value = lin(band)
    L.new(mx.outputs[2], mul.inputs[6])
    return mat


def ojival(name, w, h, depth, segs=6):
    """Arco ojival (equilatero) plano en el plano local xz, extruido en y:
    rectangulo de ancho w y alto h hasta el arranque, mas la punta."""
    # punta: dos arcos de radio w con centro en los arranques opuestos
    pts = [(-w / 2, 0.0), (w / 2, 0.0)]
    for i in range(segs + 1):
        th = math.radians(60 * i / segs)              # arco derecho: centro (-w/2, h), de 0 a 60 grados
        pts.append((-w / 2 + w * math.cos(th), h + w * math.sin(th)))
    for i in range(1, segs + 1):
        th = math.radians(120 + 60 * i / segs)        # arco izquierdo: centro (w/2, h), de 120 a 180
        pts.append((w / 2 + w * math.cos(th), h + w * math.sin(th)))
    bm = bmesh.new()
    front = [bm.verts.new((x, -depth / 2, z)) for x, z in pts]
    back = [bm.verts.new((x, depth / 2, z)) for x, z in pts]
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        bm.faces.new((front[i], front[j], back[j], back[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def piramide(name, r, h, segs=4, z0=0.0):
    return cyl(name, r, 0.001, h, segs=segs, z0=z0)


def build_catedral(e, colls):
    """Catedral de San Isidro, neogotica: torre de base cuadrada con
    contrafuertes y portal ojival, el reloj en la etapa del medio, campanario con
    pinaculos y aguja octogonal con cruz; la nave al costado con contrafuertes,
    vitrales y techo a dos aguas. Ladrillo rosado con franjas crema. La fachada
    de la torre mira a -x (la calle). Sin padres: el piso mojado espeja solo
    objetos sueltos."""
    main, neon = colls["main"], colls["neon"]
    tx, ty = e["torre"]
    W = e.get("ancho", 9.0)
    m_lad = mat_franjas("ladrillo", e.get("ladrillo", "#b8655c"), e.get("piedra", "#e6d3b3"))
    m_pie = mat_toon("piedra", e.get("piedra", "#e6d3b3"))
    m_osc = mat_toon("hueco", "#1a1424")
    m_techo = mat_toon("pizarra", e.get("techo", "#3a3a52"))
    m_vit = [mat_neon(f"vitral{i}", c, 0.95) for i, c in enumerate(e.get("vitrales", ["#ffb860", "#5aa8ff", "#ff6ab0"]))]
    m_reloj = mat_neon("reloj_catedral", e.get("reloj", "#ffe7b8"), 1.15)
    m_iron = mat_toon("reloj_hierro", "#1c1826")

    def box(name, sx, sy, sz, x, y, z, mat):
        return obj(name, box_mesh(name, sx, sy, sz), None, (x, y, z), mat=mat, coll=main)

    front_x = tx - W / 2
    # torre: tres etapas que se angostan
    etapas = [(0.0, 19.0, W), (19.0, 12.0, W - 0.6), (31.0, 9.0, W - 2.2)]
    for i, (z0, h, w) in enumerate(etapas):
        box(f"torre_etapa{i}", w, w, h, tx, ty, z0, m_lad)
        box(f"torre_cornisa{i}", w + 0.5, w + 0.5, 0.5, tx, ty, z0 + h - 0.25, m_pie)
        # contrafuertes en las esquinas
        for sx in (-1, 1):
            for sy in (-1, 1):
                cx, cy = tx + sx * (w / 2 - 0.2), ty + sy * (w / 2 - 0.2)
                box(f"contrafuerte{i}{sx}{sy}", 1.0, 1.0, h, cx, cy, z0, m_lad)
                obj(f"pinaculo{i}{sx}{sy}", piramide(f"pinaculo{i}{sx}{sy}", 0.75, 3.2 if i == 2 else 2.0, 4,
                                                    z0 + h), None, (cx, cy, 0), (0, 0, 45), m_pie, main)
    # portal ojival y rosetón, en la fachada (-x)
    obj("portal", ojival("portal", 3.6, 4.2, 0.6), None, (front_x - 0.05, ty, 0.0), (0, 0, 90), m_osc, main)
    obj("portal_luz", ojival("portal_luz", 2.6, 3.4, 0.3), None, (front_x - 0.2, ty, 0.0), (0, 0, 90),
        mat_neon("portal_m", "#ffcf8a", 0.55), neon)
    obj("ventanal", ojival("ventanal", 2.4, 3.0, 0.4), None, (front_x - 0.05, ty, 8.5), (0, 0, 90), m_vit[0], neon)
    # el reloj: esfera crema iluminada con marco, marcas y agujas
    zc, rc = e.get("reloj_z", 25.0), e.get("reloj_r", 1.7)
    fx = front_x - 0.3 - 0.05
    obj("catedral_esfera", cyl("catedral_esfera", rc, rc, 0.1, segs=48), None, (fx, ty, zc), (0, -90, 0), m_reloj, neon)
    obj("catedral_marco", annulus("catedral_marco", rc * 0.98, rc * 1.15, 0.3, segs=48), None, (fx, ty, zc),
        (0, -90, 0), m_pie, main)
    hh, mm = e.get("hora", (23, 59))
    for name, ang, ln, w in (("cat_aguja_h", (hh % 12 + mm / 60) * 30, 0.5, 0.09), ("cat_aguja_m", mm * 6, 0.82, 0.06)):
        # con la esfera girada (0, -90, 0) el x local apunta arriba: las 12
        ag = obj(name, boxc(name, rc * ln, rc * w, 0.15), None, (fx - 0.12, ty, zc), (0, -90, 0), m_iron, main)
        # mira a -x: girar sobre su z local (hacia el que mira) en negativo = sentido horario
        ag.rotation_euler.rotate_axis("Z", math.radians(-ang))
        for v in ag.data.vertices:
            v.co.x += rc * ln * 0.42
    # campanario: aberturas ojivales en las cuatro caras
    zb = etapas[2][0] + 1.5
    for k, (dx, dy, rz) in enumerate(((-1, 0, 90), (1, 0, 90), (0, -1, 0), (0, 1, 0))):
        wb = etapas[2][2] / 2 + 0.05
        obj(f"campanario{k}", ojival(f"campanario{k}", 1.6, 4.0, 0.5), None,
            (tx + dx * wb, ty + dy * wb, zb), (0, 0, rz), m_osc, main)
    # aguja octogonal y cruz
    zs = etapas[2][0] + etapas[2][1]
    obj("aguja", piramide("aguja", e.get("aguja_r", 3.3), e.get("aguja_h", 26.0), 8, zs), None, (tx, ty, 0),
        (0, 0, 22.5), m_lad, main)
    zt = zs + e.get("aguja_h", 26.0)
    box("cruz_v", 0.25, 0.25, 2.4, tx, ty, zt - 0.3, m_pie)
    box("cruz_h", 0.25, 1.3, 0.25, tx, ty, zt + 1.2, m_pie)
    # la nave: detras de la torre, a lo largo de y. Hacia la calle, una nave
    # lateral baja (techo a un agua, ventanales, contrafuertes con pinaculo) y
    # arriba la nave principal con su hilera de ventanas (claristorio).
    nl, nw, nh = e.get("nave_largo", 40.0), e.get("nave_ancho", 15.0), e.get("nave_alto", 24.0)
    aw, ah = e.get("lateral_ancho", 5.0), e.get("lateral_alto", 11.0)
    ax0 = tx - W / 2 + 0.6               # frente de la nave lateral (hacia la calle)
    nx0 = ax0 + aw                       # frente de la nave principal
    ny0 = ty + W / 2

    def prisma(name, pts, y0, y1, mat):
        bm = bmesh.new()
        f0 = [bm.verts.new((x, y0, z)) for x, z in pts]
        f1 = [bm.verts.new((x, y1, z)) for x, z in pts]
        bm.faces.new(f0)
        bm.faces.new(list(reversed(f1)))
        for i in range(len(pts)):
            j = (i + 1) % len(pts)
            bm.faces.new((f0[i], f0[j], f1[j], f1[i]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        bm.free()
        return obj(name, mesh, None, mat=mat, coll=main)

    box("nave", nw, nl, nh, nx0 + nw / 2, ny0 + nl / 2, 0.0, m_lad)
    box("nave_cornisa", nw + 0.6, nl, 0.5, nx0 + nw / 2, ny0 + nl / 2, nh - 0.25, m_pie)
    prisma("techo", [(nx0 - 0.3, nh), (nx0 + nw + 0.3, nh), (nx0 + nw / 2, nh + nw * 0.55)], ny0, ny0 + nl, m_techo)
    box("lateral", aw, nl, ah, ax0 + aw / 2, ny0 + nl / 2, 0.0, m_lad)
    box("lateral_cornisa", aw + 0.5, nl, 0.4, ax0 + aw / 2, ny0 + nl / 2, ah - 0.2, m_pie)
    prisma("lateral_techo", [(ax0 - 0.3, ah), (nx0 + 0.1, ah), (nx0 + 0.1, ah + aw * 0.5)], ny0, ny0 + nl, m_techo)
    paso = e.get("nave_paso", 4.4)
    nb = int(nl / paso)
    for k in range(nb + 1):
        yy = ny0 + 0.6 + k * paso
        box(f"lat_contrafuerte{k}", 1.3, 0.9, ah - 1.0, ax0 - 0.5, yy, 0.0, m_lad)
        obj(f"lat_pinaculo{k}", piramide(f"lat_pinaculo{k}", 0.65, 2.4, 4, ah - 1.0), None, (ax0 - 0.5, yy, 0),
            (0, 0, 45), m_pie, main)
        # pinaculos sobre la nave principal, encima de cada contrafuerte
        box(f"nave_contrafuerte{k}", 1.0, 0.8, nh - ah + 1.0, nx0 - 0.3, yy, ah, m_lad)
        obj(f"nave_pinaculo{k}", piramide(f"nave_pinaculo{k}", 0.6, 2.8, 4, nh + 0.5), None, (nx0 - 0.3, yy, 0),
            (0, 0, 45), m_pie, main)
        if k < nb:
            ym = yy + paso / 2
            obj(f"vitral{k}", ojival(f"vitral{k}", 1.7, 5.0, 0.3), None, (ax0 - 0.05, ym, 1.6),
                (0, 0, 90), m_vit[k % len(m_vit)], neon)
            obj(f"claristorio{k}", ojival(f"claristorio{k}", 1.5, 5.2, 0.3), None, (nx0 - 0.05, ym, ah + 2.4),
                (0, 0, 90), m_vit[(k + 1) % len(m_vit)], neon)
    # cerco verde a lo largo de la vereda, como en la foto
    if e.get("cerco"):
        cx0, cy0, cy1 = e["cerco"]
        box("cerco", 1.1, cy1 - cy0, 1.1, cx0, (cy0 + cy1) / 2, 0.0, mat_toon("cerco_m", e.get("cerco_color", "#1d3a30")))
    # nubes de noche teñidas por la ciudad (sin tinta, en el velo)
    # cada nube es un cumulo: varias esferas achatadas, la de abajo mas clara
    # (la ciudad la ilumina desde abajo)
    import random
    rnd = random.Random(e.get("seed_nubes", 5))
    m_nube = mat_flat("nube", e.get("nube_color", "#3a2a5e"))
    m_nube_b = mat_flat("nube_base", e.get("nube_base", "#5a3a78"))
    for k, (x, y, z, sx, sy, sz) in enumerate(e.get("nubes", [])):
        for j in range(5):
            ox, oy = rnd.uniform(-0.45, 0.45) * sx, rnd.uniform(-0.3, 0.3) * sy
            oz = rnd.uniform(0.0, 0.9) * sz
            f = rnd.uniform(0.45, 0.7)
            nb_ = obj(f"nube{k}_{j}", sphere(f"nube{k}_{j}", 1.0, segs=20), None, (x + ox, y + oy, z + oz),
                      mat=m_nube if j else m_nube_b, coll=colls["veil"])
            nb_.scale = (sx * f, sy * f, sz * (1.4 if j else 0.8))
            nb_.visible_shadow = False
    # piso mojado de la plaza y vereda (el nombre "calle" evita que el espejo se copie a si mismo)
    pz = e.get("piso", {})
    m_piso = mat_wet_ground("plaza_piso", pz.get("color", "#2a2d48"),
                            pz.get("puddles", {"scale": 2.4, "threshold": 0.56, "stretch": 0.35}))
    obj("calle_plaza", box_mesh("calle_plaza", 80, 160, 0.1), None, (0, 40, -0.1), mat=m_piso, coll=main)
    box("calle_cordon", 0.4, 160, 0.16, e.get("cordon_x", -0.6), 40, -0.02, m_pie)
    # faroles de la vereda: poste, farol y cono de luz que tine el piso
    m_poste = mat_toon("poste", "#1c1826")
    m_luz = mat_neon("farol_luz", "#ffcf8a", 1.6)
    m_cono = mat_beam("farol_cono", "#ffcf8a", 0.05)
    for k, (fx_, fy_) in enumerate(e.get("faroles", [])):
        box(f"farol_poste{k}", 0.16, 0.16, 4.2, fx_, fy_, 0.0, m_poste)
        obj(f"farol{k}", sphere(f"farol{k}", 0.28), None, (fx_, fy_, 4.4), mat=m_luz, coll=neon)
        cm = bpy.data.meshes.new(f"farol_cono{k}")
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=False, segments=16, radius1=2.2, radius2=0.2, depth=4.2)
        for v in bm.verts:
            v.co.z += 2.1
        bm.to_mesh(cm)
        bm.free()
        obj(f"farol_cono{k}", cm, None, (fx_, fy_, 0.0), mat=m_cono, coll=colls["veil"])
        tint_light(f"farol_tinte{k}", "#ffcf8a", e.get("farol_energia", 900), (fx_, fy_, 4.0), colls)


PIEZAS = [
    ("sala", build_sala),
    ("esfera", build_esfera),
    ("relojero", build_relojero),
    ("relojero_viejo", build_relojero_viejo),
    ("escalera", build_escalera),
    ("torre", build_torre),
    ("catedral", build_catedral),
    ("pulso", build_pulso),       # al final: modula todo lo que ya esta armado
]
