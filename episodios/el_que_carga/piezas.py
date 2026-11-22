"""Piezas de EL QUE CARGA: la roca del laboratorio flotante (panza facetada
que termina en punta, torres arriba), el Hombre-Tanque (gaucho de silicio:
sombrero de ala, poncho en triangulo, visor, piernas de maquina, botas con
espuela) que camina de verdad y pierde aceite, y el paisaje pintado (capas de
cerros sin linea, franjas de matas y nubes de grumos).

Ejes: el Hombre-Tanque camina hacia +X; su ancho de hombros va en Y. Z arriba.

Animacion: cada parte es un objeto rigido; pose(f) calcula donde va cada una
en el cuadro f (IK de dos huesos para piernas y brazos) y se pone una clave
por cuadro. Con "ciclo" camina y avanza: el pie apoyado queda quieto en el
piso, asi que la velocidad sale de la zancada (VEL = 4 A / N por cuadro).
La roca avanza con el (cuelga de "roca_eje") y el aceite deja rastro.
"""

import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from piezas import ctx
from piezas.base import link
from piezas.materiales import mat_flat, mat_neon, mat_toon

_MATS = {}


def _mat(kind, color, **kw):
    key = (kind, color, tuple(sorted(kw.items())))
    if key not in _MATS:
        f = {"toon": mat_toon, "flat": mat_flat, "neon": mat_neon}[kind]
        _MATS[key] = f(f"m_{kind}_{color}", color, **kw)
    return _MATS[key]


def _obj(name, bm, mat, coll, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(mat)
    link(ob, coll)
    return ob


def _box(name, c, s, mat, coll, rot=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * s[0], v.co.y * s[1], v.co.z * s[2]))
    ob = _obj(name, bm, mat, coll)
    ob.location = c
    if rot:
        ob.rotation_euler = rot
    return ob


def _cyl(name, r1, r2, h, mat, coll, segs=16, smooth=True, tapas=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=tapas, segments=segs, radius1=r1, radius2=r2, depth=h)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, h / 2))
    return _obj(name, bm, mat, coll, smooth)


def _bola(name, c, r, mat, coll, escala=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=r)
    ob = _obj(name, bm, mat, coll, True)
    ob.location = c
    if escala:
        ob.scale = escala
    return ob


def _dos_huesos(S, T, L1, L2, pole):
    S, T, pole = (np.asarray(x, float) for x in (S, T, pole))
    d = T - S
    n = float(np.linalg.norm(d))
    n = min(max(n, 1e-6), L1 + L2 - 1e-4)
    u = d / np.linalg.norm(d)
    a = (L1 * L1 - L2 * L2 + n * n) / (2 * n)
    h = math.sqrt(max(L1 * L1 - a * a, 0.0))
    p = pole - np.dot(pole, u) * u
    p = p / (np.linalg.norm(p) + 1e-9)
    return S + u * a + p * h, S + u * n


def _rot_hacia(d):
    return Vector(d).to_track_quat("Z", "Y").to_euler()


def _disco(bm, cx, cy, rx, ry, z, n=10, rng=None):
    vs = []
    for k in range(n):
        a = 2 * math.pi * k / n
        j = 1.0 + (rng.uniform(-0.18, 0.18) if rng is not None else 0.0)
        vs.append(bm.verts.new((cx + rx * j * math.cos(a), cy + ry * j * math.sin(a), z)))
    bm.faces.new(vs)


# ------------------------------------------------------------------ la roca

def build_roca(e, colls):
    """Panza de la roca: anillos de radio r(z) = R (z/H)^k con ruido angular,
    punta abajo en 'punta'. Todo cuelga de 'roca_eje' (avanza con el)."""
    rng = np.random.default_rng(e.get("seed", 7))
    R, H, k = e.get("radio", 70.0), e.get("alto", 55.0), e.get("forma", 0.55)
    nz, na = e.get("anillos", 22), e.get("segmentos", 40)
    px, py, pz = e["punta"]
    eje = bpy.data.objects.new("roca_eje", None)
    link(eje)
    partes = []
    ruido = rng.normal(0, 1, (nz, na))
    for _ in range(2):
        ruido = (ruido + np.roll(ruido, 1, 1) + np.roll(ruido, -1, 1)) / 3
    bm = bmesh.new()
    rings = []
    tip = bm.verts.new((px, py, pz))
    for i in range(1, nz + 1):
        t = i / nz
        z = pz + H * t
        ring = []
        for j in range(na):
            a = 2 * math.pi * j / na
            r = R * t ** k * (1 + e.get("rugosidad", 0.18) * ruido[i - 1, j])
            ring.append(bm.verts.new((px + r * math.cos(a), py + r * math.sin(a) * e.get("achate", 1.0), z)))
        rings.append(ring)
    for j in range(na):
        bm.faces.new((tip, rings[0][(j + 1) % na], rings[0][j]))
    for i in range(nz - 1):
        for j in range(na):
            j2 = (j + 1) % na
            bm.faces.new((rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j]))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # silueta pura por defecto (como la roca del corto); "toon" marca facetas
    roca = _obj("roca", bm, _mat(e.get("material", "flat"), e.get("color", "#2a1636")), colls["main"])
    # sin tinta propia (en el corto es una mancha), pero tapa la tinta de atras
    roca.lineart.usage = e.get("tinta", "OCCLUSION_ONLY")
    partes.append(roca)
    if e.get("pasto"):
        o = _cyl("roca_pasto", R * 1.02, R * 0.98, 2.5, _mat("toon", e["pasto"]), colls["main"], 40, False)
        o.location = (px, py, pz + H)
        partes.append(o)
    # el laboratorio flotante: torres con techo en punta y franjas de ventanas cian
    lab = e.get("laboratorio")
    if lab:
        mt, mv = _mat("toon", lab.get("color", "#9db8c4")), _mat("neon", lab.get("ventanas", "#7ff7ff"), strength=3.0)
        z0 = pz + H + (2.5 if e.get("pasto") else 0.0)
        for k2, (x, y, h, r) in enumerate(lab["torres"]):
            t = _cyl(f"torre_{k2}", r, r * 0.92, h, mt, colls["main"], 8, False)
            t.location = (px + x, py + y, z0)
            p = _cyl(f"techo_{k2}", r * 1.08, 0.05, r * 1.6, mt, colls["main"], 8, False)
            p.location = (px + x, py + y, z0 + h)
            partes += [t, p]
            for j in range(int(h // 7)):
                v = _cyl(f"ventana_{k2}_{j}", r * 1.01, r * 1.01, 0.9, mv, colls["neon"], 8, False)
                v.location = (px + x, py + y, z0 + 4 + j * 7)
                partes.append(v)
    for o in partes:
        o.parent = eje


# ------------------------------------------------------------ el Hombre-Tanque

L1, L2 = 1.35, 1.3          # muslo, canilla
LB = 1.35                   # brazo y antebrazo


def ciclo_de(e):
    """(N, A, velocidad por cuadro) o None si esta quieto."""
    c = e.get("ciclo")
    if not c:
        return None
    N, A = c.get("frames", 18), c.get("zancada", 0.7)
    return N, A, (4 * A / N if c.get("avanza", True) else 0.0)


def pose(e, f):
    """Puntos del cuerpo en el cuadro f (mundo)."""
    O = np.array(e.get("at", (0, 0, 0)), float)
    lean = e.get("inclina", 0.12)
    cic = ciclo_de(e)
    piernas = {}
    if cic:
        N, A, vel = cic
        th = 2 * math.pi * (f - 1 + e["ciclo"].get("fase", 0)) / N
        O = O + np.array([vel * (f - 1), 0, 0])
        # rebote: abajo en el apoyo doble, arriba al pasar la pierna
        cad = 2.36 + 0.07 * math.cos(2 * th)
        for lado, sgn, off in (("i", 1, 0.0), ("d", -1, math.pi)):
            s = th + off
            fx = A * math.sin(s)
            lift = 0.32 * max(0.0, math.cos(s)) ** 1.5      # el pie que va adelante sube
            piernas[lado] = (sgn, fx, lift)
    else:
        paso = e.get("paso", 0.0)
        cad = 2.45 - 0.18 * paso
        for lado, sgn in (("i", 1), ("d", -1)):
            piernas[lado] = (sgn, sgn * 0.95 * paso, 0.0)
    P = {"O": O, "cad": cad, "lean": lean}
    for lado, (sgn, fx, lift) in piernas.items():
        hip = O + np.array([0.0, sgn * 0.48, cad])
        foot = O + np.array([fx, sgn * e.get("abre", 0.52), 0.42 + lift])
        knee, foot = _dos_huesos(hip, foot, L1, L2, (1, 0, 0))
        P[lado] = {"hip": hip, "knee": knee, "foot": foot, "sgn": sgn}
    tz = cad + 0.3
    P["tz"] = tz
    P["cuello"] = O + np.array([lean * 2.0, 0, tz + 1.75])
    hx = P["cuello"][0] + 0.15
    hz = P["cuello"][2] + 0.2
    P["hx"], P["hz"] = hx, hz
    mano_z = e.get("mano_z", 6.7)
    for lado, sgn in (("bi", 1), ("bd", -1)):
        sh = O + np.array([lean * 1.6, sgn * 0.95, tz + 1.45])
        hand = np.array([O[0] + lean * 2.0 + 0.25, sgn * 0.55, mano_z])
        elbow, hand = _dos_huesos(sh, hand, LB, LB, (0, sgn, -0.2))
        P[lado] = {"sh": sh, "elbow": elbow, "hand": hand}
    return P


def build_tanque(e, colls):
    C = {"metal": "#7fa6a0", "oscuro": "#2f3d45", "poncho": "#e8dcc0", "guarda": "#b5322a",
         "sombrero": "#2b2026", "faja": "#b5322a", "visor": "#7ff7ff", "aceite": "#0d0b14",
         "espuela": "#d2a53a", "cuero": "#6b3b26", "bombacha": "#d6ccb4"}
    C.update(e.get("colores", {}))
    co = colls["main"]
    m = {k: _mat("toon", v) for k, v in C.items() if k != "visor"}
    lean = e.get("inclina", 0.12)
    mov = []        # (objeto, funcion pose -> (loc, rot o None, escala o None))
    telas = []      # (objeto, z de arriba, z de abajo): se deforman por cuadro

    def rig(ob, fn):
        mov.append((ob, fn))
        return ob

    def seg(name, L, r1, r2, mat, a_fn, b_fn, segs=14, tapas=True):
        ob = _cyl(name, r1, r2, L, mat, co, segs, tapas=tapas)
        return rig(ob, lambda P: (a_fn(P), _rot_hacia(b_fn(P) - a_fn(P)), None))

    # ---- piernas, botas, vendas, aceite
    for lado in ("i", "d"):
        seg(f"muslo_{lado}", L1, 0.36, 0.30, m["metal"], lambda P, l=lado: P[l]["hip"], lambda P, l=lado: P[l]["knee"])
        rig(_bola(f"rodilla_{lado}", (0, 0, 0), 0.32, m["oscuro"], co), lambda P, l=lado: (P[l]["knee"], None, None))
        seg(f"canilla_{lado}", L2, 0.30, 0.24, m["metal"], lambda P, l=lado: P[l]["knee"], lambda P, l=lado: P[l]["foot"])
        for k in range(3):
            t = 0.55 + 0.12 * k
            ob = _cyl(f"venda_{lado}{k}", 0.31, 0.31, 0.07, m["guarda"], co, 14)
            rig(ob, lambda P, l=lado, t=t: (P[l]["knee"] + (P[l]["foot"] - P[l]["knee"]) * t,
                                            _rot_hacia(P[l]["foot"] - P[l]["knee"]), None))
        # bota: suela, caña que se ensancha, puntera redonda y espuela en el talon
        def en_pie(dx, dz, l=lado):
            return lambda P: (P[l]["foot"] + np.array([dx, 0, dz]), None, None)
        rig(_box(f"suela_{lado}", (0, 0, 0), (1.0, 0.54, 0.12), m["oscuro"], co), en_pie(0.12, -0.36))
        rig(_cyl(f"cana_{lado}", 0.34, 0.27, 0.36, m["oscuro"], co, 16), en_pie(-0.05, -0.31))
        rig(_bola(f"puntera_{lado}", (0, 0, 0), 1.0, m["oscuro"], co, (0.36, 0.26, 0.17)), en_pie(0.38, -0.26))
        esp = _cyl(f"espuela_{lado}", 0.13, 0.13, 0.03, m["espuela"], co, 8, False)
        rig(esp, lambda P, l=lado: (P[l]["foot"] + np.array([-0.44, -0.015, -0.2]), (math.pi / 2, 0, 0), None))
        rig(_box(f"talonera_{lado}", (0, 0, 0), (0.2, 0.05, 0.05), m["espuela"], co), en_pie(-0.34, -0.2))

    # ---- faja y torso
    # el torso empieza mas arriba y la faja cubre el hueco: asi la boca de la
    # bombacha, que se levanta al dar el paso, no se mete en el torso
    rig(_cyl("faja", 0.78, 0.78, 0.6, m["faja"], co, 20), lambda P: (P["O"] + np.array([0, 0, P["cad"] - 0.05]), None, None))
    rig(_box("torso", (0, 0, 0), (1.0, 1.5, 1.35), m["metal"], co),
        lambda P: (P["O"] + np.array([lean * 1.2, 0, P["tz"] + 0.92]), (0, lean, 0), None))
    # bombachas: una por muslo, la envuelve y se mueve con ella (el chiripa
    # fijo de antes lo atravesaban las piernas al dar el paso)
    for lado in ("i", "d"):
        # tubo abierto: el muslo sale por la boca, no atraviesa una tapa
        seg(f"bombacha_{lado}", 0.85, 0.46, 0.40, m["bombacha"], lambda P, l=lado: P[l]["hip"] - np.array([0, 0, 0.05]),
            lambda P, l=lado: P[l]["hip"] + (P[l]["knee"] - P[l]["hip"]) * 0.7, 18, tapas=False)

    # ---- poncho: tela abierta arriba y abajo (los hombros y los brazos salen
    # por la boca de arriba, no la atraviesan), punta adelante y atras, guarda
    # roja en la ultima franja. Se deforma cuadro por cuadro (ver _tela).
    NR, NA = 7, 32
    zs = -0.30                         # hombros, relativos al cuello
    bm = bmesh.new()
    rings = []
    for j in range(NR + 1):
        u = j / NR
        ring = []
        for i in range(NA):
            a = 2 * math.pi * i / NA
            ca, sa = math.cos(a), math.sin(a)
            # arriba: elipse que contiene hombros y torso; abajo: rombo (punta adelante)
            tx, ty, tzz = -0.4 * lean + 0.95 * ca, 1.5 * sa, zs + 0.12
            dn = abs(ca) + abs(sa)
            bx, by, bz = -0.8 * lean + 1.85 * ca / dn, 2.15 * sa / dn, -1.85
            ring.append(bm.verts.new((tx + (bx - tx) * u, ty + (by - ty) * u, tzz + (bz - tzz) * u)))
        rings.append(ring)
    for j in range(NR):
        for i in range(NA):
            i2 = (i + 1) % NA
            fc = bm.faces.new((rings[j][i], rings[j + 1][i], rings[j + 1][i2], rings[j][i2]))
            fc.material_index = 1 if j == NR - 1 else 0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    poncho = _obj("poncho", bm, m["poncho"], co, smooth=False)
    poncho.data.materials.append(m["guarda"])
    rig(poncho, lambda P: (P["cuello"], None, None))
    telas.append((poncho, zs + 0.12, -1.85))

    # ---- cabeza: caja, mandibula, remaches, tornillos de oreja, barbijo, visor
    def en_cabeza(dx, dy, dz, rot=None):
        return lambda P: (np.array([P["hx"] + dx, P["O"][1] + dy, P["hz"] + dz]), rot, None)
    rig(_box("cabeza", (0, 0, 0), (0.62, 0.56, 0.56), m["oscuro"], co), en_cabeza(0, 0, 0.38))
    rig(_box("mandibula", (0, 0, 0), (0.58, 0.62, 0.2), m["metal"], co), en_cabeza(0.04, 0, 0.06))
    for dy in (-0.21, 0.21):
        for dz in (0.2, 0.58):
            rig(_bola(f"remache_{dy}_{dz}", (0, 0, 0), 0.035, m["espuela"], co), en_cabeza(0.31, dy, dz))
        rig(_cyl(f"oreja_{dy}", 0.13, 0.13, 0.08, m["metal"], co, 12), en_cabeza(0, dy * 1.33, 0.38, (math.pi / 2 * (1 if dy < 0 else -1), 0, 0)))
    for sgn in (1, -1):
        seg(f"barbijo_{sgn}", 0.62, 0.018, 0.018, m["cuero"],
            lambda P, s=sgn: np.array([P["hx"], P["O"][1] + s * 0.3, P["hz"] + 0.66]),
            lambda P, s=sgn: np.array([P["hx"] + 0.3, P["O"][1] + s * 0.05, P["hz"] - 0.02]), 6)
    rig(_box("visor", (0, 0, 0), (0.04, 0.44, 0.1), _mat("neon", C["visor"], strength=4.0), colls["neon"]), en_cabeza(0.32, 0, 0.42))
    # errores de renderizado: pixeles sueltos al lado del visor (el canon: en sus ojos solo hay errores)
    for k, (dy, dz, col) in enumerate(((0.27, 0.45, "#ff3df0"), (-0.25, 0.36, "#7ff7ff"), (0.18, 0.31, "#ffffff"))):
        rig(_box(f"pixel_{k}", (0, 0, 0), (0.03, 0.05, 0.05), _mat("neon", col, strength=4.0), colls["neon"]),
            en_cabeza(0.33, dy, dz))
    rig(_cyl("ala", 1.2, 1.2, 0.08, m["sombrero"], co, 28), en_cabeza(0, 0, 0.66))
    rig(_cyl("copa", 0.42, 0.38, 0.34, m["sombrero"], co, 20), en_cabeza(0, 0, 0.72))

    # ---- brazos en alto
    for lado in ("bi", "bd"):
        rig(_bola(f"hombro_{lado}", (0, 0, 0), 0.42, m["oscuro"], co), lambda P, l=lado: (P[l]["sh"], None, None))
        seg(f"brazo_{lado}", LB, 0.3, 0.26, m["metal"], lambda P, l=lado: P[l]["sh"], lambda P, l=lado: P[l]["elbow"])
        rig(_bola(f"codo_{lado}", (0, 0, 0), 0.27, m["oscuro"], co), lambda P, l=lado: (P[l]["elbow"], None, None))
        seg(f"antebrazo_{lado}", LB, 0.27, 0.24, m["metal"], lambda P, l=lado: P[l]["elbow"], lambda P, l=lado: P[l]["hand"])
        rig(_box(f"mano_{lado}", (0, 0, 0), (0.55, 0.42, 0.3), m["oscuro"], co),
            lambda P, l=lado: (P[l]["hand"] + np.array([0, 0, 0.12]), None, None))

    # ---- aceite: gota colgando de cada rodilla y gotas que caen
    ac = e.get("aceite", {})
    if ac is not False:
        per = ac.get("periodo", 7)
        for lado, off in (("i", 0), ("d", 3)):
            rig(_bola(f"gota_colgada_{lado}", (0, 0, 0), 1.0, m["aceite"], co, (0.07, 0.07, 0.12)),
                lambda P, l=lado: (P[l]["knee"] + np.array([0.06, 0, -0.36]), None, None))

            def cae(P, l=lado, off=off):
                f = P["f"]
                t = ((f + off) % per) / 12.0
                k = P[l]["knee"]
                z = k[2] - 0.45 - 4.9 * t * t
                if z < 0.04:
                    return (np.array([k[0], k[1], 0.04]), None, (0.0, 0.0, 0.0))
                return (np.array([k[0] + 0.06, k[1], z]), None, (0.06, 0.06, 0.1))
            rig(_bola(f"gota_cae_{lado}", (0, 0, 0), 1.0, m["aceite"], co), cae)

    # ---- animar: una clave por cuadro (o una sola si esta quieto)
    frames = ctx.CFG["frames"]
    lista = range(1, frames + 1)        # quieto tambien: las gotas caen igual
    eje = bpy.data.objects.get("roca_eje")
    O0 = None
    for f in lista:
        P = pose(e, f)
        P["f"] = f
        O0 = P["O"] if O0 is None else O0
        for ob, fn in mov:
            loc, rot, esc = fn(P)
            ob.location = tuple(loc)
            ob.keyframe_insert("location", frame=f)
            if rot is not None:
                ob.rotation_euler = rot
                ob.keyframe_insert("rotation_euler", frame=f)
            if esc is not None:
                ob.scale = esc
                ob.keyframe_insert("scale", frame=f)
        if eje is not None:
            eje.location = (P["O"][0] - O0[0], 0, 0)
            eje.keyframe_insert("location", frame=f)
    for ob in [o for o, _ in mov] + ([eje] if eje else []):
        if ob.animation_data and ob.animation_data.action:
            _constante(ob)
    for ob, z0, z1 in telas:
        _tela(ob, e, z0, z1, lista)
    if ac is not False:
        rastro(e, colls, lista)


def _tela(ob, e, z0, z1, lista):
    """La tela se mueve por claves de forma, una por cuadro (en unos). Peso
    0 arriba (donde se apoya) y 1 en el ruedo. Tres cosas, como se anima una
    capa en 2D:
      - arrastre: al caminar el ruedo queda atras y se levanta un poco;
      - vaiven con retraso (overlap): sigue el rebote y el balanceo del paso,
        pero llega tarde (fase corrida);
      - flameo: una onda que corre alrededor del ruedo (viento), siempre,
        aunque este quieto."""
    me = ob.data
    rest = np.array([v.co[:] for v in me.vertices])
    w = np.clip((z0 - rest[:, 2]) / (z0 - z1), 0, 1) ** 1.6
    ang = np.arctan2(rest[:, 1], rest[:, 0])
    cic = ciclo_de(e)
    viento = e.get("viento", 1.0)
    ob.shape_key_add(name="base")
    for f in lista:
        if cic:
            N, A, vel = cic
            th = 2 * math.pi * (f - 1 + e["ciclo"].get("fase", 0)) / N
            drag, amp = (0.22 if vel > 0 else 0.0), 1.0
        else:
            th = 2 * math.pi * (f - 1) / 24.0
            drag, amp = 0.0, 0.35
        tw = 2 * math.pi * (f - 1) / 9.0
        dx = -drag + amp * (0.10 * np.sin(2 * th - 1.1)) + 0.03 * viento * np.sin(tw + ang)
        dy = amp * 0.07 * np.sin(th - 1.1) * np.ones_like(ang)
        dz = drag * 0.35 + amp * 0.08 * np.cos(2 * th - 1.4)             + viento * (0.06 * np.sin(3 * ang - tw) + 0.03 * np.sin(5 * ang + 1.7 * tw))
        rad = 1.0 + viento * w * (0.03 * np.sin(4 * ang - 1.3 * tw))
        nv = rest.copy()
        nv[:, 0] = rest[:, 0] * rad + w * dx
        nv[:, 1] = rest[:, 1] * rad + w * dy
        nv[:, 2] = rest[:, 2] + w * dz
        k = ob.shape_key_add(name=f"f{f}", from_mix=False)
        k.data.foreach_set("co", nv.ravel().astype(np.float32))
        for ff, val in ((f - 1, 0.0), (f, 1.0), (f + 1, 0.0)):
            if lista[0] <= ff <= lista[-1]:
                k.value = val
                k.keyframe_insert("value", frame=ff)
    sk = me.shape_keys
    if sk.animation_data and sk.animation_data.action:
        from piezas.base import action_fcurves
        for fc in action_fcurves(sk.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"


def _constante(ob):
    """Claves sin interpolar: a 12 fps cada cuadro es un dibujo (en unos)."""
    from piezas.base import action_fcurves
    for fc in action_fcurves(ob.animation_data.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"


def rastro(e, colls, lista):
    """Rastro de aceite en el piso, debajo de cada rodilla: lo que ya quedo
    atras es una sola malla; lo que va dejando en el plano aparece en el
    cuadro en que la rodilla pasa por encima."""
    ac = e.get("aceite") or {}
    rng = np.random.default_rng(ac.get("seed", 5))
    mat = _mat("toon", ac.get("color", "#0d0b14"))
    largo = ac.get("rastro", 80.0)
    P1, Pn = pose(e, lista[0]), pose(e, lista[-1])
    x_ini, x_fin = P1["O"][0], Pn["O"][0] + 0.3
    fija = bmesh.new()
    nuevas = []
    for sgn in (1, -1):
        y0 = sgn * (e.get("abre", 0.52) + 0.04)
        x = x_ini - largo
        while x < x_fin:
            x += rng.uniform(0.12, 0.3)
            r = rng.uniform(0.09, 0.2)
            cx, cy = x, y0 + rng.uniform(-0.08, 0.08)
            if rng.random() < 0.06:
                r *= 3.0         # charco donde se freno
            if x <= x_ini:
                _disco(fija, cx, cy, r * 2.2, r, 0.012, 10, rng)
            else:
                nuevas.append((cx, cy, r))
    ob = _obj("rastro", fija, mat, colls["veil"])
    ob.hide_render = False
    # las nuevas: aparecen cuando la rodilla (mas o menos el cuerpo) pasa
    xs = [(f, pose(e, f)["O"][0]) for f in lista]
    for k, (cx, cy, r) in enumerate(nuevas):
        bm = bmesh.new()
        _disco(bm, 0, 0, r * 2.2, r, 0.0, 10, rng)
        o = _obj(f"mancha_{k}", bm, mat, colls["veil"])
        o.location = (cx, cy, 0.012)
        f_aparece = next((f for f, ox in xs if ox + 0.05 >= cx), None)
        if f_aparece is None:
            o.hide_render = True
            continue
        if f_aparece > lista[0]:
            o.hide_render = True
            o.keyframe_insert("hide_render", frame=lista[0])
            o.hide_render = False
            o.keyframe_insert("hide_render", frame=f_aparece)


# ------------------------------------------------------------- el paisaje

def build_paisaje(e, colls):
    """Piso plano y capas de cerros pintadas: cada capa es una banda vertical
    en arco alrededor de 'centro' (o recta, para las matas que pasan al lado
    de la camara que acompaña), con su silueta de ruido y un color plano, sin
    linea (coleccion 'velo'). Nubes: grumos de esferas blancas."""
    rng = np.random.default_rng(e.get("seed", 3))
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=e.get("piso_radio", 1500))
    _obj("piso", bm, _mat("toon", e.get("piso", "#9cbf4a")), colls["main"])
    for n, cap in enumerate(e.get("cerros", [])):
        h, col = cap["alto"], cap["color"]
        recta = cap.get("recta")
        na = int(recta["n"]) if recta else 220
        x = np.linspace(0, 1, na)
        perfil = np.zeros(na)
        for fq, amp in cap.get("ondas", [(3, 0.5), (9, 0.3), (23, 0.15)]):
            ph = rng.uniform(0, 2 * np.pi)
            perfil += amp * (0.5 + 0.5 * np.sin(2 * np.pi * fq * x + ph))
        if cap.get("picos"):
            perfil = perfil ** 1.6
        perfil = h * perfil / max(perfil.max(), 1e-6)
        bm = bmesh.new()
        lo, hi = [], []
        for i in range(na):
            if recta:
                cx = recta["x0"] + (recta["x1"] - recta["x0"]) * x[i]
                cy = recta["y"]
            else:
                D = cap["dist"]
                a0, a1 = map(math.radians, cap.get("arco", (20, 160)))
                a = a0 + (a1 - a0) * x[i]
                ox, oy = cap.get("centro", (0.0, 0.0))
                cx, cy = ox + D * math.cos(a), oy + D * math.sin(a)
            lo.append(bm.verts.new((cx, cy, -2.0)))
            hi.append(bm.verts.new((cx, cy, cap.get("base", 0.0) + perfil[i])))
        for i in range(na - 1):
            bm.faces.new((lo[i], lo[i + 1], hi[i + 1], hi[i]))
        _obj(f"cerro_{n}", bm, _mat("flat", col), colls["veil"])
    for n, nb in enumerate(e.get("nubes", [])):
        cx, cy, cz = nb["at"]
        s = nb.get("escala", 30.0)
        col = _mat("toon", nb.get("color", "#fbfbf4"))
        for k in range(nb.get("grumos", 9)):
            u = rng.uniform(-1, 1)
            r = s * rng.uniform(0.35, 0.6) * (1 - 0.45 * abs(u))
            c = (cx + u * s * 1.3, cy + rng.uniform(-0.2, 0.2) * s, cz + r * 0.5 + rng.uniform(0, 0.25) * s)
            b = _bola(f"nube_{n}_{k}", c, r, col, colls["veil"])
            b.scale = (1.0, 0.6, 0.75)


PIEZAS = [("paisaje", build_paisaje), ("roca", build_roca), ("tanque", build_tanque)]
