"""
piezas.py - LA BANDERA: una mariposa mecanica basada en la "bandera argentina"
(Morpho epistrophus argentinus), la Morpho celeste y blanca de la ribera
portena, y el fondo de ciudad hecho bokeh.

Ejes de la mariposa: el cuerpo sobre +y (la cabeza adelante), el ala derecha
hacia +x, el dorso hacia +z. "escala" es el largo del ala anterior en metros
(la real mide ~5 cm). Todo el movimiento se calcula cuadro por cuadro (claves
LINEAR en cada cuadro): no hay simulacion.

    "mariposa": {
      "escala": 0.05,
      "keys": [[frame, [x, y, z], yaw_deg, pitch_deg], ...],   # trayectoria
      "aleteo": [[frame, ciclo_frames, amplitud_deg, media_deg], ...],
      "vaiven": 0.004                                            # flotar (m)
    }

El aleteo (lo que tiene que leerse como mariposa y no como bisagra):
  - la bajada dura el 42 % del ciclo y la subida el resto (la fuerza baja);
  - el ala de atras llega tarde (desfase) y con menos recorrido;
  - la punta del ala se dobla contra el movimiento (shape key, segun la
    velocidad un poco atrasada): la membrana pesa;
  - el borde de ataque baja en la bajada (torsion) y el ala se adelanta;
  - el cuerpo sube con cada golpe, cabecea, y el abdomen y las antenas
    siguen con retraso.
amplitud 0 = planeo con las alas quietas en "media" grados.

Alas: una malla en abanico desde la bisagra, con UV (u = 0 en la bisagra, 1 en
el borde; v a lo largo del contorno). Las nervaduras son lineas de v constante
(salen de la base, como en las alas reales) y las escamas una grilla en (u, v):
cada escama es un pixel. El dorso es iridiscente en bandas duras (el color
cambia con el angulo, como la Morpho real, pero en escalones de cel); el
reverso es bronce oscuro con ocelos de neon.
"""

import math
import random

import bmesh
import bpy
from mathutils import Euler, Vector

from piezas import ctx
from piezas.base import action_fcurves, lin, link
from piezas.materiales import _borde_neon, _emit_out, _power, _toon_light, mat_neon, mat_toon

TINTA = "#0d0b24"


# --- nodos --------------------------------------------------------------------

def _m(nt, op, a, b=None, clamp=False):
    node = nt.nodes.new("ShaderNodeMath")
    node.operation = op
    node.use_clamp = clamp
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


def _escalar(nt, col, k):
    sc = nt.nodes.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    if isinstance(col, str):
        c = lin(col)
        rgb = nt.nodes.new("ShaderNodeRGB")
        rgb.outputs[0].default_value = c
        col = rgb.outputs[0]
    nt.links.new(col, sc.inputs[0])
    if isinstance(k, (int, float)):
        sc.inputs["Scale"].default_value = k
    else:
        nt.links.new(k, sc.inputs["Scale"])
    return sc.outputs[0]


def _sumar(nt, a, b):
    add = nt.nodes.new("ShaderNodeVectorMath")
    add.operation = "ADD"
    nt.links.new(a, add.inputs[0])
    nt.links.new(b, add.inputs[1])
    return add.outputs[0]


def _suave(nt, x, a, b):
    """smoothstep(a, b, x)"""
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.interpolation_type = "SMOOTHSTEP"
    mr.inputs["From Min"].default_value = a
    mr.inputs["From Max"].default_value = b
    nt.links.new(x, mr.inputs["Value"])
    return mr.outputs["Result"]


def _attr(nt, name):
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_type = "OBJECT"
    at.attribute_name = name
    return at.outputs["Fac"]


def _ruido(nt, a, b, c):
    cb = nt.nodes.new("ShaderNodeCombineXYZ")
    for i, x in enumerate((a, b, c)):
        if isinstance(x, (int, float)):
            cb.inputs[i].default_value = x
        else:
            nt.links.new(x, cb.inputs[i])
    wn = nt.nodes.new("ShaderNodeTexWhiteNoise")
    wn.noise_dimensions = "3D"
    nt.links.new(cb.outputs[0], wn.inputs["Vector"])
    return wn.outputs["Value"]


def _largo2(nt, a, b):
    """sqrt(a^2 + b^2)"""
    return _m(nt, "SQRT", _m(nt, "ADD", _m(nt, "MULTIPLY", a, a), _m(nt, "MULTIPLY", b, b)))


# --- material del ala ---------------------------------------------------------

DORSO = [[0.0, "#f2fcff"], [0.30, "#9fe9ff"], [0.48, "#4fb6ff"], [0.62, "#3a6cff"],
         [0.76, "#8f5cff"], [0.88, "#ff4fd8"]]


def mat_ala(name, A, costa):
    """A: config de la mariposa. costa: el ala de adelante tiene el borde de
    ataque oscuro (como la real); la de atras no."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    n = nt.nodes
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["UV"], sep.inputs[0])
    u, v = sep.outputs[0], sep.outputs[1]
    t = _attr(nt, "t")
    pw = _power(nt)
    geo = n.new("ShaderNodeNewGeometry")
    luz = _toon_light(nt)
    # despliegue (0..1, por objeto): la luz inunda el ala desde la base; lo que
    # todavia no llego es membrana opaca y humeda, y el frente es una onda blanca
    d = _attr(nt, "despl")
    frente = _m(nt, "SUBTRACT", u, _m(nt, "MULTIPLY", d, 1.08))
    lleno = _m(nt, "SUBTRACT", 1.0, _suave(nt, frente, -0.03, 0.0))
    onda = _m(nt, "MULTIPLY", _m(nt, "SUBTRACT", 1.0, _suave(nt, _m(nt, "ABSOLUTE", frente), 0.0, 0.05)),
              _m(nt, "MULTIPLY", _m(nt, "LESS_THAN", d, 0.999), _attr(nt, "onda")))

    # nervaduras: lineas de v constante que se curvan un poco hacia el borde
    NV = A.get("nervaduras", 9)
    vv = _m(nt, "ADD", _m(nt, "MULTIPLY", v, NV), _m(nt, "MULTIPLY", _m(nt, "MULTIPLY", u, u), 0.35))
    fr = _m(nt, "FRACT", vv)
    lado = _m(nt, "SUBTRACT", 0.5, _m(nt, "ABSOLUTE", _m(nt, "SUBTRACT", fr, 0.5)))  # 0 en la vena
    ancho = _m(nt, "SUBTRACT", 0.075, _m(nt, "MULTIPLY", u, 0.04))
    vena = _m(nt, "SUBTRACT", 1.0, _suave(nt, _m(nt, "DIVIDE", lado, ancho), 0.4, 1.0))
    # la celda discal: una nervadura que cruza
    cruz = _m(nt, "ABSOLUTE", _m(nt, "SUBTRACT", u, _m(nt, "ADD", 0.42, _m(nt, "MULTIPLY", _m(nt, "SINE", _m(nt, "MULTIPLY", v, 7.0)), 0.04))))
    vena = _m(nt, "MAXIMUM", vena, _m(nt, "SUBTRACT", 1.0, _suave(nt, cruz, 0.006, 0.014)))
    # sin nervaduras en la base peluda ni pasado el borde oscuro
    vena = _m(nt, "MULTIPLY", vena, _m(nt, "MULTIPLY", _suave(nt, u, 0.10, 0.16), _m(nt, "SUBTRACT", 1.0, _suave(nt, u, 0.84, 0.87))))

    # escamas: una grilla de pixeles en (u, v)
    cu = _m(nt, "FLOOR", _m(nt, "MULTIPLY", u, A.get("escamas_u", 34)))
    cv = _m(nt, "FLOOR", _m(nt, "MULTIPLY", v, A.get("escamas_v", 52)))
    tono = _m(nt, "ADD", 0.88, _m(nt, "MULTIPLY", _ruido(nt, cu, cv, 0.0), 0.22))
    # junta entre escamas, apenas mas oscura
    ju = _m(nt, "LESS_THAN", _m(nt, "FRACT", _m(nt, "MULTIPLY", u, A.get("escamas_u", 34))), 0.10)
    jv = _m(nt, "LESS_THAN", _m(nt, "FRACT", _m(nt, "MULTIPLY", v, A.get("escamas_v", 52))), 0.10)
    tono = _m(nt, "MULTIPLY", tono, _m(nt, "SUBTRACT", 1.0, _m(nt, "MULTIPLY", _m(nt, "MAXIMUM", ju, jv), 0.12)))
    # destellos: algunas escamas se encienden un instante (glitch como poesia)
    salto = _m(nt, "FLOOR", _m(nt, "MULTIPLY", t, A.get("destellos_hz", 8)))
    destello = _m(nt, "GREATER_THAN", _ruido(nt, cu, cv, salto), 1.0 - A.get("destellos", 0.018))

    # --- dorso: iridiscencia en bandas segun el angulo de vista
    lw = n.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    fac = _m(nt, "ADD", _m(nt, "MULTIPLY", lw.outputs["Facing"], 0.9), _m(nt, "MULTIPLY", _m(nt, "SUBTRACT", 1.0, u), 0.32))
    fac = _m(nt, "ADD", fac, _attr(nt, "iris"))   # corrimiento animable
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    dorso = A.get("dorso", DORSO)
    while len(els) < len(dorso):
        els.new(0.5)
    for el, (p, c) in zip(els, dorso):
        el.position = p
        el.color = lin(c)
    nt.links.new(_m(nt, "FRACT", _m(nt, "MULTIPLY", fac, 0.999)), ramp.inputs["Fac"])
    base = _escalar(nt, ramp.outputs["Color"], _m(nt, "MULTIPLY", tono, A.get("dorso_k", 1.0)))
    # borde oscuro con lunares de neon, costa y base oscuras
    ola = _m(nt, "MULTIPLY", _m(nt, "SINE", _m(nt, "MULTIPLY", v, 60.0)), 0.012)
    margen = _m(nt, "GREATER_THAN", u, _m(nt, "ADD", 0.86, ola))
    oscuro = margen
    if costa:
        oscuro = _m(nt, "MAXIMUM", oscuro, _m(nt, "LESS_THAN", v, _m(nt, "SUBTRACT", 0.07, _m(nt, "MULTIPLY", u, 0.03))))
    oscuro = _m(nt, "MAXIMUM", oscuro, _m(nt, "LESS_THAN", u, 0.12))
    base = _mix(nt, oscuro, base, A.get("margen", "#10142e"))
    base = _mix(nt, _m(nt, "SUBTRACT", 1.0, lleno), base, A.get("humeda", "#2c3148"))
    lit_d = _sumar(nt, _mix(nt, 1.0, base, luz, "MULTIPLY"), _escalar(nt, base, A.get("autoluz", 0.45)))
    # lunares del borde: uno por celda de nervadura
    du = _m(nt, "SUBTRACT", u, 0.93)
    dv = _m(nt, "MULTIPLY", _m(nt, "SUBTRACT", fr, 0.5), 2.4 / NV)
    lunar = _m(nt, "LESS_THAN", _largo2(nt, du, dv), A.get("lunar", 0.022))

    # --- reverso: bronce oscuro con ocelos
    rev = _mix(nt, 1.0, _escalar(nt, A.get("reverso", "#3a2a3e"), tono), luz, "MULTIPLY")
    rev = _sumar(nt, rev, _escalar(nt, A.get("reverso", "#3a2a3e"), 0.25))
    ocelo_em = None
    for (u0, v0, r) in A.get("ocelos_" + ("ant" if costa else "pos"), []):
        d = _m(nt, "DIVIDE", _largo2(nt, _m(nt, "SUBTRACT", u, u0), _m(nt, "MULTIPLY", _m(nt, "SUBTRACT", v, v0), 1.15)), r)
        anillo = _m(nt, "MULTIPLY", _m(nt, "GREATER_THAN", d, 0.55), _m(nt, "LESS_THAN", d, 0.82))
        negro = _m(nt, "LESS_THAN", d, 0.55)
        pupila = _m(nt, "LESS_THAN", d, 0.2)
        oro = _m(nt, "MULTIPLY", _m(nt, "GREATER_THAN", d, 0.82), _m(nt, "LESS_THAN", d, 1.0))
        rev = _mix(nt, negro, rev, "#07060f")
        rev = _mix(nt, oro, rev, "#6b4a22")
        em = _sumar(nt, _escalar(nt, A.get("ocelo", "#ff8a2a"), _m(nt, "MULTIPLY", anillo, 2.2)),
                    _escalar(nt, "#ffffff", _m(nt, "MULTIPLY", pupila, 1.6)))
        ocelo_em = em if ocelo_em is None else _sumar(nt, ocelo_em, em)
    if ocelo_em is not None:
        rev = _sumar(nt, rev, _escalar(nt, ocelo_em, _m(nt, "MULTIPLY", pw, lleno)))

    col = _mix(nt, geo.outputs["Backfacing"], lit_d, rev)

    # --- lo que emite: nervaduras con un pulso que viaja de la base al borde,
    # lunares, destellos y el filo
    q = _m(nt, "FRACT", _m(nt, "SUBTRACT", _m(nt, "MULTIPLY", t, A.get("pulso_vel", 0.9)), u))
    pulso = _m(nt, "POWER", _m(nt, "SUBTRACT", 1.0, q), 9.0)
    k_vena = _m(nt, "MULTIPLY", vena, _m(nt, "ADD", A.get("vena_base", 0.35), _m(nt, "MULTIPLY", pulso, A.get("vena_pulso", 2.6))))
    k_vena = _m(nt, "MULTIPLY", k_vena, lleno)
    destello = _m(nt, "MULTIPLY", destello, lleno)
    lunar = _m(nt, "MULTIPLY", lunar, lleno)
    dorsal = _m(nt, "SUBTRACT", 1.0, geo.outputs["Backfacing"])
    em = _escalar(nt, A.get("vena", "#bff6ff"), _m(nt, "MULTIPLY", k_vena, _m(nt, "ADD", 0.35, _m(nt, "MULTIPLY", dorsal, 0.65))))
    em = _sumar(nt, em, _escalar(nt, A.get("lunar_color", "#7fe8ff"), _m(nt, "MULTIPLY", _m(nt, "MULTIPLY", lunar, margen), _m(nt, "MULTIPLY", dorsal, 1.8))))
    em = _sumar(nt, em, _escalar(nt, "#ffffff", _m(nt, "MULTIPLY", destello, _m(nt, "MULTIPLY", _m(nt, "SUBTRACT", 1.0, oscuro), 1.4))))
    filo = _m(nt, "MULTIPLY", _m(nt, "GREATER_THAN", u, 0.972), _m(nt, "LESS_THAN", u, 0.992))
    em = _sumar(nt, em, _escalar(nt, A.get("filo", "#ff4fd8"), _m(nt, "MULTIPLY", filo, _m(nt, "ADD", 0.4, _m(nt, "MULTIPLY", lleno, 1.1)))))
    em = _sumar(nt, em, _escalar(nt, A.get("onda", "#e8fbff"), _m(nt, "MULTIPLY", onda, A.get("onda_k", 2.6))))
    col = _sumar(nt, col, _escalar(nt, em, pw))
    _emit_out(nt, col)
    return mat


def mat_cuerpo(name, color, rim):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    col = _mix(nt, 1.0, color, _toon_light(nt), "MULTIPLY")
    col = _borde_neon(nt, col, {"color": rim, "ancho": 0.28, "fuerza": 0.9})
    _emit_out(nt, col)
    return mat


def mat_ojo(name, color):
    """Ojo compuesto: celdas de voronoi encendidas, con la junta oscura."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    vo = nt.nodes.new("ShaderNodeTexVoronoi")
    vo.feature = "DISTANCE_TO_EDGE"
    vo.inputs["Scale"].default_value = 1.0 / max(1e-4, ctx_escala() * 0.012)
    nt.links.new(geo.outputs["Position"], vo.inputs["Vector"])
    celda = _m(nt, "GREATER_THAN", vo.outputs["Distance"], 0.08)
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    centro = _m(nt, "SUBTRACT", 1.0, lw.outputs["Facing"])
    k = _m(nt, "MULTIPLY", celda, _m(nt, "ADD", 0.6, _m(nt, "MULTIPLY", centro, 1.4)))
    _emit_out(nt, _escalar(nt, _escalar(nt, color, k), _power(nt)))
    return mat


_ESCALA = [0.05]


def ctx_escala():
    return _ESCALA[0]


# --- mallas -------------------------------------------------------------------

def _contorno(ctrl, th):
    """Radio del ala en el angulo th (grados) por Catmull-Rom sobre los puntos
    de control [(grados, radio)]."""
    if th <= ctrl[0][0]:
        return ctrl[0][1]
    if th >= ctrl[-1][0]:
        return ctrl[-1][1]
    for i in range(len(ctrl) - 1):
        a0, r1 = ctrl[i]
        a1, r2 = ctrl[i + 1]
        if a0 <= th <= a1:
            r0 = ctrl[max(0, i - 1)][1]
            r3 = ctrl[min(len(ctrl) - 1, i + 2)][1]
            s = (th - a0) / (a1 - a0)
            return 0.5 * ((2 * r1) + (-r0 + r2) * s + (2 * r0 - 5 * r1 + 4 * r2 - r3) * s * s
                          + (-r0 + 3 * r1 - 3 * r2 + r3) * s * s * s)
    return ctrl[-1][1]


# contornos de Morpho epistrophus (radio en largos de ala anterior, angulo
# desde la cabeza hacia el costado y atras)
ALA_ANT = [(52, 0.28), (57, 0.72), (63, 0.95), (71, 1.0), (80, 0.95), (94, 0.84),
           (110, 0.74), (124, 0.66), (138, 0.56), (152, 0.42), (166, 0.26)]
ALA_POS = [(82, 0.40), (96, 0.58), (114, 0.68), (132, 0.72), (150, 0.70), (166, 0.62),
           (180, 0.50), (193, 0.34), (202, 0.20)]


def _ala(name, ctrl, L, lado, mat, feston=0.0, camber=0.05, NA=56, NR=16):
    """Abanico desde la bisagra (origen local). lado = 1 derecha, -1 izquierda
    (espejada en x, con el giro de las caras invertido)."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UV")
    a0, a1 = ctrl[0][0], ctrl[-1][0]
    filas = []
    for i in range(NR + 1):
        uu = 0.03 + 0.97 * i / NR
        fila = []
        for j in range(NA + 1):
            th = a0 + (a1 - a0) * j / NA
            r = _contorno(ctrl, th)
            if feston:
                r *= 1.0 - feston * abs(math.sin(math.radians(th) * 9.0)) * (1 if 100 < th < 190 else 0)
            rr = uu * r * L
            x = math.sin(math.radians(th)) * rr * lado
            y = math.cos(math.radians(th)) * rr
            # comba: la membrana no es plana
            z = camber * L * math.sin(math.pi * uu) * (0.6 + 0.4 * math.sin(math.pi * j / NA))
            fila.append((bm.verts.new((x, y, z)), uu, j / NA))
        filas.append(fila)
    for i in range(NR):
        for j in range(NA):
            q = [filas[i][j], filas[i][j + 1], filas[i + 1][j + 1], filas[i + 1][j]]
            if lado < 0:
                q = q[::-1]
            f = bm.faces.new([p[0] for p in q])
            for loop, p in zip(f.loops, q):
                loop[uvl].uv = (p[1], p[2])
    mesh = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    mesh.materials.append(mat)
    ob = bpy.data.objects.new(name, mesh)
    # shape key: la punta se dobla hacia el dorso (valor negativo = hacia abajo)
    ob.shape_key_add(name="base")
    sk = ob.shape_key_add(name="flex")
    sk.slider_min = -1.0
    sk.slider_max = 1.0
    for vtx, kd in zip(mesh.vertices, sk.data):
        d = abs(vtx.co.x) / L
        kd.co = (vtx.co.x, vtx.co.y, vtx.co.z + 0.42 * L * d * d)
    # shape key: el ala recien salida, arrugada y encogida hacia la bisagra
    sk = ob.shape_key_add(name="arruga", from_mix=False)
    sk.value = 0.0      # nace en 1: sin esto toda mariposa sale arrugada
    for i in range(NR + 1):
        uu = 0.03 + 0.97 * i / NR
        for j in range(NA + 1):
            vt = mesh.vertices[i * (NA + 1) + j]
            vv = j / NA
            pl = Vector((vt.co.x, vt.co.y, 0.0)) * (1.0 - 0.3 * uu)
            z = vt.co.z + 0.07 * L * uu * math.sin(uu * 23.0 + vv * 11.0) * math.sin(vv * 29.0 + uu * 5.0) \
                + 0.10 * L * uu * uu
            sk.data[i * (NA + 1) + j].co = (pl.x, pl.y, z)
    return ob


def _elipsoide(name, r, at, mat, segs=20, rings=12):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0)
    for vt in bm.verts:
        vt.co = Vector((vt.co.x * r[0], vt.co.y * r[1], vt.co.z * r[2])) + Vector(at)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    mesh.materials.append(mat)
    return bpy.data.objects.new(name, mesh)


def _anillo(name, r, w, at, mat, segs=24):
    """Aro fino alrededor del eje y (las juntas de neon del abdomen)."""
    bm = bmesh.new()
    vs = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        for k in (-1, 1):
            vs.append(bm.verts.new((r[0] * math.cos(a) + at[0], at[1] + k * w, r[1] * math.sin(a) + at[2])))
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new([vs[2 * i], vs[2 * j], vs[2 * j + 1], vs[2 * i + 1]])
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    return bpy.data.objects.new(name, mesh)


def _curva(name, pts, radio, mat, afinar=True):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radio
    cu.bevel_resolution = 2
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p[0], p[1], p[2], 1.0)
        sp.points[i].radius = (1.0 - 0.6 * i / max(1, len(pts) - 1)) if afinar else 1.0
    cu.materials.append(mat)
    return bpy.data.objects.new(name, cu)


# --- movimiento ---------------------------------------------------------------

def _golpe(p):
    """Posicion del ala en el ciclo: 1 arriba, -1 abajo. La bajada es mas
    corta que la subida."""
    p %= 1.0
    d = 0.42
    if p < d:
        return math.cos(math.pi * p / d)
    return -math.cos(math.pi * (p - d) / (1 - d))


def _vel(p):
    """Velocidad normalizada del golpe (-1 bajando a fondo, +1 subiendo)."""
    h = 1e-3
    return (_golpe(p + h) - _golpe(p - h)) / (2 * h) / (math.pi / 0.42)


def _tramo(keys, f):
    """Interpola claves [[frame, valores...]] linealmente (suavizado)."""
    if f <= keys[0][0]:
        return keys[0][1:]
    for k0, k1 in zip(keys, keys[1:]):
        if k0[0] <= f <= k1[0]:
            s = (f - k0[0]) / max(1e-6, k1[0] - k0[0])
            s = s * s * (3 - 2 * s)
            return [a + (b - a) * s for a, b in zip(k0[1:], k1[1:])]
    return keys[-1][1:]


def _camino(keys, f):
    """Catmull-Rom sobre las posiciones de "keys" (frame, pos, yaw, pitch)."""
    fs = [k[0] for k in keys]
    P = [Vector(k[1]) for k in keys]
    if f <= fs[0]:
        i, s = 0, 0.0
    elif f >= fs[-1]:
        i, s = len(fs) - 2, 1.0
    else:
        i = max(j for j in range(len(fs) - 1) if fs[j] <= f)
        s = (f - fs[i]) / (fs[i + 1] - fs[i])
    if len(P) == 1:
        return P[0]
    p0, p1 = P[max(0, i - 1)], P[i]
    p2, p3 = P[i + 1], P[min(len(P) - 1, i + 2)]
    return 0.5 * ((2 * p1) + (-p0 + p2) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s * s
                  + (-p0 + 3 * p1 - 3 * p2 + p3) * s * s * s)


def _clave(ob, path, frame):
    ob.keyframe_insert(path, frame=frame)


# --- la mariposa --------------------------------------------------------------

_MATS = {}


def build_mariposa(A, colls):
    """Una mariposa (dict) o varias (lista); "nombre" es el del objeto raiz
    (el foco de la camara busca "mariposa")."""
    for a in (A if isinstance(A, list) else [A]):
        _una_mariposa(a, colls)


def _materiales(A):
    """Los materiales de una mariposa; las de un mismo "grupo" (el enjambre)
    los comparten: menos shaders que compilar."""
    g = A.get("grupo")
    if g and g in _MATS:
        return _MATS[g]
    m = {"ant": mat_ala("ala_ant", A, costa=True), "pos": mat_ala("ala_pos", A, costa=False),
         "cuerpo": mat_cuerpo("quitina", A.get("cuerpo", "#161a36"), A.get("rim", "#7fe8ff")),
         "neon": mat_neon("mariposa_neon", A.get("neon", "#7fe8ff"), A.get("neon_k", 2.0), fog=False),
         "ojo": mat_ojo("ojo", A.get("ojo", "#7fe8ff")),
         "blanco": mat_neon("franja_blanca", "#eefcff", 1.6, fog=False)}
    if g:
        _MATS[g] = m
    return m


def _una_mariposa(A, colls):
    L = A.get("escala", 0.05)
    _ESCALA[0] = L
    lejos = A.get("lejos", False)
    # "sin_tinta": en un plano de escala de ciudad la tinta va en metros y a
    # 40 cm de la camara la mariposa saldria como una mancha negra
    main = colls["neon"] if A.get("sin_tinta") else colls["main"]
    raiz = bpy.data.objects.new(A.get("nombre", "mariposa"), None)
    raiz.rotation_mode = "XYZ"
    if A.get("ancla"):
        raiz["ancla"] = 1
    link(raiz, main)
    cuerpo_pivote = bpy.data.objects.new("mariposa_cuerpo", None)
    cuerpo_pivote.parent = raiz
    cuerpo_pivote.rotation_mode = "XYZ"
    link(cuerpo_pivote, main)

    M = _materiales(A)
    m_ant, m_pos, m_cuerpo, m_neon, m_ojo = M["ant"], M["pos"], M["cuerpo"], M["neon"], M["ojo"]
    detalle = {"NA": 24, "NR": 8} if lejos else {}

    alas = {}
    for lado, s in (("d", 1), ("i", -1)):
        for nom, ctrl, mat, piv, fest in (("ant", ALA_ANT, m_ant, (0.035, 0.06, 0.012), 0.0),
                                          ("pos", ALA_POS, m_pos, (0.035, -0.03, 0.0), 0.035)):
            bis = bpy.data.objects.new(f"bisagra_{nom}_{lado}", None)
            bis.parent = cuerpo_pivote
            bis.location = (piv[0] * L * s, piv[1] * L, piv[2] * L)
            bis.rotation_mode = "XZY"
            link(bis, main)
            ob = _ala(f"ala_{nom}_{lado}", ctrl, L, s, mat, feston=fest, **detalle)
            ob.parent = bis
            ob["t"] = 0.0
            ob["iris"] = 0.0
            ob["despl"] = 1.0
            ob["onda"] = 0.0 if A.get("apaga") else 1.0     # la onda blanca es del despliegue
            link(ob, main)
            alas[(nom, lado)] = (bis, ob)

    # cuerpo: torax blindado con la franja de la bandera, collar de neon,
    # cabeza con ojos compuestos grandes, abdomen en segmentos con juntas de neon
    C = A.get("cuerpo_k", 1.0)
    m_blanco = M["blanco"]
    partes = [_elipsoide("torax", (0.10 * L * C, 0.16 * L, 0.095 * L * C), (0, 0.02 * L, 0), m_cuerpo, 24, 14),
              _elipsoide("escudo", (0.075 * L * C, 0.11 * L, 0.05 * L * C), (0, 0.0, 0.06 * L * C), m_cuerpo, 20, 10),
              _elipsoide("cabeza", (0.07 * L * C, 0.06 * L, 0.065 * L * C), (0, 0.2 * L, 0.012 * L), m_cuerpo)]
    for s in (1, -1):
        partes.append(_elipsoide(f"ojo_{s}", (0.05 * L * C,) * 3, (0.05 * L * C * s, 0.225 * L, 0.025 * L), m_ojo, 18, 12))
    for ob in partes:
        ob.parent = cuerpo_pivote
        link(ob, main)
    # franja celeste-blanca-celeste sobre el escudo del torax
    for k, (dx, mat) in enumerate(() if lejos else ((-0.022, m_neon), (0.0, m_blanco), (0.022, m_neon))):
        pts = [(dx * L * C, (0.09 - 0.18 * i / 8) * L,
                0.06 * L * C + 0.05 * L * C * math.sqrt(max(0.0, 1 - ((0.09 - 0.18 * i / 8) / 0.11) ** 2)) + 0.002 * L)
               for i in range(9)]
        fr = _curva(f"franja_{k}", pts, 0.006 * L, mat, afinar=False)
        fr.parent = cuerpo_pivote
        link(fr, colls["neon"])
    collar = _anillo("collar", (0.068 * L * C, 0.062 * L * C), 0.007 * L, (0, 0.155 * L, 0.005 * L), m_neon)
    collar.parent = cuerpo_pivote
    link(collar, colls["neon"])
    abd = bpy.data.objects.new("abdomen", None)
    abd.parent = cuerpo_pivote
    abd.location = (0, -0.13 * L, 0)
    abd.rotation_mode = "XYZ"
    link(abd, main)
    n_seg = 4 if lejos else 7
    for i in range(n_seg):
        k = 1.0 - 0.5 * (i / (n_seg - 1)) ** 1.4
        y = -0.068 * L * i
        seg = _elipsoide(f"abd_{i}", (0.068 * L * k * C, 0.05 * L, 0.064 * L * k * C), (0, y, 0), m_cuerpo, 18, 10)
        seg.parent = abd
        link(seg, main)
        if i < n_seg - 1:
            ring = _anillo(f"junta_{i}", (0.062 * L * k * C, 0.058 * L * k * C), 0.0035 * L, (0, y - 0.036 * L, 0), m_neon)
            ring.parent = abd
            link(ring, colls["neon"])
    # antenas con maza de luz
    antenas = []
    for s in (1, -1):
        piv = bpy.data.objects.new(f"antena_piv_{s}", None)
        piv.parent = cuerpo_pivote
        piv.location = (0.025 * L * s, 0.235 * L, 0.05 * L)
        piv.rotation_mode = "XYZ"
        link(piv, main)
        pts = [(0.12 * L * s * (i / 8) ** 1.1, 0.55 * L * (i / 8), 0.18 * L * math.sin(math.pi * 0.5 * i / 8)) for i in range(9)]
        an = _curva(f"antena_{s}", pts, 0.009 * L, m_cuerpo)
        an.parent = piv
        link(an, main)
        maza = _elipsoide(f"maza_{s}", (0.011 * L, 0.026 * L, 0.011 * L), pts[-1], m_neon, 12, 8)
        maza.parent = piv
        link(maza, colls["neon"])
        piv["lado"] = s
        antenas.append(piv)
    # espiritrompa enrollada, de neon
    esp = [(0, 0.235 * L + 0.035 * L * math.cos(a) * (1 - a / 14), -0.06 * L - 0.035 * L * math.sin(a) * (1 - a / 14))
           for a in [i * 0.35 for i in range(36)]]
    if not lejos:
        trompa = _curva("trompa", esp, 0.004 * L, m_neon, afinar=False)
        trompa.parent = cuerpo_pivote
        link(trompa, colls["neon"])
    # patas recogidas
    for i, yy in enumerate(() if lejos else (0.09, 0.03, -0.03)):
        for s in (1, -1):
            if A.get("agarre"):
                # colgada: las patas se estiran hacia adelante, a la cascara
                pts = [(0.04 * L * s, yy * L, -0.07 * L), (0.10 * L * s, (yy + 0.10) * L, -0.12 * L),
                       (0.045 * L * s, (0.33 + 0.02 * i) * L, -0.05 * L)]
            else:
                pts = [(0.04 * L * s, yy * L, -0.07 * L), (0.11 * L * s, (yy + 0.03) * L, -0.12 * L),
                       (0.07 * L * s, (yy - 0.05) * L, -0.17 * L)]
            pata = _curva(f"pata_{i}_{s}", pts, 0.006 * L, m_cuerpo)
            pata.parent = cuerpo_pivote
            link(pata, main)
    # la luz que las alas tiran sobre lo que tienen cerca
    if A.get("luz", 0):
        li = bpy.data.lights.new("luz_alas", "POINT")
        li.color = lin(A.get("luz_color", "#7fe8ff"))[:3]
        li.energy = A["luz"]
        li.shadow_soft_size = L * 0.5
        li.use_shadow = False
        lo = bpy.data.objects.new("luz_alas", li)
        lo.parent = cuerpo_pivote
        lo.location = (0, 0, 0.15 * L)
        link(lo, colls["lights"])

    if A.get("halo"):
        # en un plano general la mariposa mide un pixel: un punto de luz que la marca
        r = A["halo"]
        h = _elipsoide("halo", (r, r, r), (0, 0, 0), mat_neon("halo", A.get("neon", "#bff6ff"), 1.4, fog=False), 12, 8)
        h.parent = cuerpo_pivote
        link(h, colls["neon"])
        if A.get("halo_desde"):
            for fr, oculto in ((0, True), (A["halo_desde"], False)):
                h.hide_render = oculto
                h.keyframe_insert("hide_render", frame=fr)
    neones = [ob for ob in raiz.children_recursive if ob.name in colls["neon"].objects]
    # "aparece"/"desaparece": cuadros en que se muestra (las del enjambre nacen
    # cuando revienta su crisalida)
    if A.get("aparece") or A.get("desaparece"):
        a0, a1 = A.get("aparece", 0), A.get("desaparece", 10 ** 6)
        for ob in raiz.children_recursive:
            if ob.type in ("MESH", "CURVE", "LIGHT"):
                for fr, oculto in ((0, a0 > 0), (a0, False), (a1, True)):
                    if fr >= 0 and fr < 10 ** 6:
                        ob.hide_render = oculto
                        ob.keyframe_insert("hide_render", frame=fr)

    # --- el movimiento, cuadro por cuadro
    frames = ctx.CFG["frames"]
    fps = ctx.CFG.get("fps", 24)
    keys = A.get("keys", [[1, [0, 0, 1], 0, 0]])
    aleteo = A.get("aleteo", [[1, 12, 60, 22]])
    vaiven = A.get("vaiven", 0.0)
    rnd = random.Random(A.get("seed", 5))
    fase_r = [rnd.random() * 6.28 for _ in range(3)]
    p = A.get("fase0", 0.0)
    despl = A.get("despliegue")
    golpes = {}     # por cuadro: cuanto empuja el ala hacia abajo (para la estela)
    for f in range(1, frames + 1):
        ciclo, amp, media = _tramo(aleteo, f)
        dd = _tramo(despl, f)[0] if despl else 1.0
        pliegue = _tramo(A["pliegue"], f)[0] if A.get("pliegue") else 0.0
        if f > 1:
            p += 1.0 / max(1.0, ciclo)
        pos = _camino(keys, f)
        yaw, pitch = _tramo([[k[0], k[2], k[3] if len(k) > 3 else 0.0] for k in keys], f)
        g_amp = amp / 60.0      # cuanto empuja este aleteo (0 = planeo)
        tt = f / fps
        flot = Vector((math.sin(tt * 1.3 + fase_r[0]), math.sin(tt * 0.9 + fase_r[1]), math.sin(tt * 1.7 + fase_r[2]))) * vaiven
        sube = A.get("rebote", 0.10) * L * g_amp * -_golpe(p - 0.18)
        raiz.location = pos + flot + Vector((0, 0, sube))
        raiz.rotation_euler = (math.radians(pitch), 0.0, math.radians(yaw))
        _clave(raiz, "location", f)
        _clave(raiz, "rotation_euler", f)
        cuerpo_pivote.rotation_euler = (math.radians(7.0 * g_amp * -_golpe(p - 0.10)), 0.0,
                                        math.radians(2.0 * math.sin(tt * 2.1)))
        _clave(cuerpo_pivote, "rotation_euler", f)
        abd.rotation_euler = (math.radians(-9.0 * g_amp * _golpe(p - 0.22) - 4.0), 0.0, 0.0)
        _clave(abd, "rotation_euler", f)
        # "antenas": [grados hacia atras, apertura] (colgada, para que no entren en la cascara)
        an_x, an_z = _tramo(A["antenas"], f) if A.get("antenas") else (0.0, 0.0)
        for piv in antenas:
            piv.rotation_euler = (math.radians(6.0 * g_amp * _golpe(p - 0.32) - an_x), 0.0,
                                  math.radians(-an_z * piv["lado"]))
            _clave(piv, "rotation_euler", f)
        for (nom, lado), (bis, ob) in alas.items():
            s = 1 if lado == "d" else -1
            atraso = 0.0 if nom == "ant" else A.get("atraso_pos", 0.06)
            k_amp = 1.0 if nom == "ant" else 0.9
            pp = p - atraso
            g = _golpe(pp)
            vlag = _vel(pp - 0.05)
            ang = min(A.get("tope", 87.0), media + amp * k_amp * g)   # + = punta arriba
            twist = A.get("torsion", 12.0) * g_amp * _vel(pp)
            barrido = -A.get("barrido", 7.0) * g_amp * g + (4.0 if nom == "ant" else -3.0)                 - pliegue * (1.0 if nom == "ant" else 0.75)
            bis.rotation_euler = (math.radians(twist), math.radians(-ang * s), math.radians(barrido * s))
            _clave(bis, "rotation_euler", f)
            sk = ob.data.shape_keys.key_blocks["flex"]
            sk.value = max(-1.0, min(1.0, -A.get("flex", 0.85) * g_amp * vlag))
            sk.keyframe_insert("value", frame=f)
            ob["t"] = tt
            _clave(ob, '["t"]', f)
            if despl:
                # el ala crece desde la bisagra mientras se estira la arruga
                e = dd * dd * (3 - 2 * dd)
                ob.scale = (0.55 + 0.45 * e,) * 3
                _clave(ob, "scale", f)
                ar = ob.data.shape_keys.key_blocks["arruga"]
                ar.value = 1.0 - e
                ar.keyframe_insert("value", frame=f)
                ob["despl"] = dd
                _clave(ob, '["despl"]', f)
            if A.get("apaga"):
                # la luz que se va: el color se retira del borde hacia la base
                ob["despl"] = _tramo(A["apaga"], f)[0]
                _clave(ob, '["despl"]', f)
        if A.get("apaga"):
            k_neon = 0.2 + 0.8 * _tramo(A["apaga"], f)[0]
            for ob in neones:
                ob["power"] = k_neon
                _clave(ob, '["power"]', f)
        golpes[f] = max(0.0, -_vel(p)) * g_amp * (1.0 if dd >= 0.999 else 0.0)
    propios = [raiz] + list(raiz.children_recursive)
    for ob in propios:
        ad = ob.animation_data
        if ad and ad.action:
            for fc in action_fcurves(ad.action):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
        sk = getattr(getattr(ob, "data", None), "shape_keys", None)
        if sk and sk.animation_data and sk.animation_data.action:
            for fc in action_fcurves(sk.animation_data.action):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
    for ob in propios:
        ad = ob.animation_data
        if ad and ad.action:
            for fc in action_fcurves(ad.action):
                if fc.data_path == "hide_render":
                    for kp in fc.keyframe_points:
                        kp.interpolation = "CONSTANT"
    if A.get("estela") and not lejos:
        _estela(A["estela"], alas, golpes, colls, L)


def mat_escamas(name):
    """Emisivo con el color (y el brillo) de cada escama en el atributo "col"."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_type = "GEOMETRY"
    at.attribute_name = "col"
    _emit_out(nt, _escalar(nt, at.outputs["Color"], _power(nt)))
    mat["neon"] = True
    return mat


def _estela(E, alas, golpes, colls, L):
    """Escamas que se desprenden del borde de las alas con cada golpe: cubitos
    de luz (pixeles) que salen con la velocidad del ala, frenan, giran, caen
    despacio y se apagan. Se simula en Python y se arma una malla por cuadro
    (visible solo en su cuadro): determinista, sin particulas de Blender.
    E: {"por_golpe": 14, "base": 0.4, "vida": [10, 26], "tam": 0.012,
        "arrastre": 0.3, "caida": 0.006, "brillo": 3.0, "colores": [...]}"""
    from mathutils import noise
    scene = bpy.context.scene
    frames = ctx.CFG["frames"]
    rnd = random.Random(E.get("seed", 11))
    pal = [lin(c) for c in E.get("colores", ["#bff6ff", "#7fe8ff", "#ffffff", "#ffffff", "#ff4fd8", "#a35cff"])]
    NA, NR = 56, 16
    borde = [i * (NA + 1) + j for i in range(int(NR * 0.7), NR + 1) for j in range(NA + 1)]
    muestra = {k: rnd.sample(borde, 70) for k in alas}
    mat = mat_escamas("escamas")
    vivos = []
    prev = None
    cubo = [Vector(v) for v in ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
                                (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))]
    caras = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    for f in range(1, frames + 1):
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        pts = {}
        for k, (bis, ob) in alas.items():
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            mw = ev.matrix_world.copy()
            pts[k] = [mw @ me.vertices[i].co for i in muestra[k]]
            ev.to_mesh_clear()
        n = E.get("por_golpe", 14) * golpes.get(f, 0.0) + E.get("base", 0.4)
        if f > E.get("hasta", 10 ** 6):
            n = 0
        n = int(n) + (1 if rnd.random() < n - int(n) else 0)
        for _ in range(n):
            k = rnd.choice(list(alas))
            i = rnd.randrange(70)
            pos = pts[k][i].copy()
            vel = (pos - prev[k][i]) * E.get("arrastre", 0.3) if prev else Vector()
            vel += Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))) * 0.01 * L
            vivos.append({"p": pos, "v": vel, "f0": f, "vida": rnd.randint(*E.get("vida", (10, 26))),
                          "c": rnd.choice(pal), "t": E.get("tam", 0.012) * L * rnd.uniform(0.6, 1.4),
                          "r": Vector((rnd.random(), rnd.random(), rnd.random())) * 6.28,
                          "w": Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))) * 0.35})
        prev = pts
        verts, faces, cols = [], [], []
        quedan = []
        for q in vivos:
            edad = f - q["f0"]
            if edad > q["vida"]:
                continue
            quedan.append(q)
            if edad > 0:
                q["v"] = q["v"] * E.get("freno", 0.86)
                q["v"].z -= E.get("caida", 0.006) * L
                q["v"] += noise.noise_vector(q["p"] / (0.6 * L) + Vector((0, 0, f * 0.05))) * 0.004 * L
                q["p"] = q["p"] + q["v"]
                q["r"] = q["r"] + q["w"]
            x = edad / q["vida"]
            tam = q["t"] * (1.0 - x) ** 0.6
            k_luz = E.get("brillo", 3.0) * (1.0 - x) ** 0.5 * (1.7 if (edad + int(q["r"].x * 10)) % 4 == 0 else 1.0)
            m = Euler(q["r"]).to_matrix()
            base = len(verts)
            for c in cubo:
                verts.append(q["p"] + m @ (c * tam))
                cols.append((q["c"][0] * k_luz, q["c"][1] * k_luz, q["c"][2] * k_luz, 1.0))
            faces += [tuple(base + i for i in fc) for fc in caras]
        vivos = quedan
        if not verts:
            continue
        me = bpy.data.meshes.new(f"escamas_{f:04d}")
        me.from_pydata([tuple(v) for v in verts], [], faces)
        at = me.color_attributes.new("col", "FLOAT_COLOR", "POINT")
        for i, c in enumerate(cols):
            at.data[i].color = c
        me.materials.append(mat)
        ob = bpy.data.objects.new(f"escamas_{f:04d}", me)
        link(ob, colls["neon"])
        for fr, oculto in ((0, True), (f, False), (f + 1, True)):
            ob.hide_render = oculto
            ob.keyframe_insert("hide_render", frame=fr)
        for fc in action_fcurves(ob.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
    scene.frame_set(1)


# --- la ciudad hecha bokeh -----------------------------------------------------

def build_bokeh(B, colls):
    """Luces de ciudad detras del foco: ventanas, carteles y balizas como
    rectangulos emisivos; con la profundidad de campo se vuelven discos.
    Siluetas oscuras de torres entre ellas para que no sea un fondo plano.
    B: {"centro": [x, y, z], "dir": [0, 1, 0], "dist": [6, 40], "count": 160,
        "ancho": 1.0, "colores": [...], "torres": 9}"""
    rnd = random.Random(B.get("seed", 7))
    c0 = Vector(B.get("centro", (0, 0, 1)))
    fw = Vector(B.get("dir", (0, 1, 0))).normalized()
    der = fw.cross(Vector((0, 0, 1))).normalized()
    arr = der.cross(fw).normalized()
    cols = B.get("colores", ["#7fe8ff", "#ff4fd8", "#ffb347", "#4f7cff", "#ffffff"])
    mats = [mat_neon(f"bokeh_{i}", c, B.get("fuerza", 2.2), fog=True) for i, c in enumerate(cols)]
    d0, d1 = B.get("dist", (6, 40))
    for i in range(B.get("count", 160)):
        d = d0 + (d1 - d0) * rnd.random() ** 1.6
        x = (rnd.random() - 0.5) * 2 * d * B.get("ancho", 0.9)
        z = (rnd.random() - 0.35) * 2 * d * B.get("alto", 1.1)
        w = d * rnd.uniform(0.004, 0.02)
        h = w * rnd.choice((0.5, 1.0, 1.0, 3.0))
        ctr = c0 + fw * d + der * x + arr * z
        bm = bmesh.new()
        vs = [bm.verts.new(ctr + der * a * w + arr * b * h) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        bm.faces.new(vs)
        me = bpy.data.meshes.new(f"bokeh_{i}")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(rnd.choice(mats))
        ob = bpy.data.objects.new(f"bokeh_{i}", me)
        link(ob, colls["neon"])
    # torres oscuras recortadas contra el resplandor
    m_t = mat_toon("torre_bokeh", B.get("torre", "#0c0f24"))
    for i in range(B.get("torres", 9)):
        d = rnd.uniform(d1 * 0.5, d1)
        x = (rnd.random() - 0.5) * 2 * d * 0.8
        w = rnd.uniform(0.04, 0.09) * d
        h = rnd.uniform(0.8, 1.8) * d
        ctr = c0 + fw * d + der * x - arr * d * 0.5
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for vt in bm.verts:
            vt.co = ctr + der * vt.co.x * w + fw * vt.co.y * w + arr * (vt.co.z + 0.5) * h
        me = bpy.data.meshes.new(f"torre_bokeh_{i}")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(m_t)
        ob = bpy.data.objects.new(f"torre_bokeh_{i}", me)
        link(ob, colls["neon"])


# --- el cable de la grua y la crisalida ---------------------------------------

def build_cable(K, colls):
    """Cable de acero entre dos puntos, con una catenaria suave.
    K: {"desde": [x, y, z], "hasta": [x, y, z], "radio": 0.006, "flecha": 0.02}"""
    a, b = Vector(K["desde"]), Vector(K["hasta"])
    pts = []
    for i in range(41):
        s = i / 40
        pts.append(tuple(a.lerp(b, s) - Vector((0, 0, 4 * K.get("flecha", 0.02) * s * (1 - s)))))
    ob = _curva("cable", pts, K.get("radio", 0.006), mat_toon("acero_cable", K.get("color", "#2a2c44")), afinar=False)
    ob.data.bevel_resolution = 4
    link(ob, colls["main"])


def mat_crisalida(name, C):
    """Cascara de jade oscuro con costuras de neon. Por dentro (la cara de
    atras) brilla. Atributos por objeto: "latido" (la luz de adentro que se
    transparenta) y "grieta" (0..1: la raja que sube desde la punta)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    n = nt.nodes
    lg = C.get("largo", 0.026)
    geo = n.new("ShaderNodeNewGeometry")
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    x, y, z = sep.outputs[0], sep.outputs[1], sep.outputs[2]
    t = _m(nt, "DIVIDE", z, -lg)          # el origen esta arriba: 0 arriba, 1 en la punta
    pw = _power(nt)
    afuera = _mix(nt, 1.0, C.get("color", "#0b4d3d"), _toon_light(nt), "MULTIPLY")
    afuera = _borde_neon(nt, afuera, {"color": C.get("rim", "#7fe8ff"), "ancho": 0.18, "fuerza": 0.55})
    # dos costuras finas (las vainas de las alas que se adivinan debajo)
    cos = _m(nt, "LESS_THAN", _m(nt, "ABSOLUTE", _m(nt, "SUBTRACT", t, _m(nt, "ADD", 0.38,
             _m(nt, "MULTIPLY", _m(nt, "ABSOLUTE", y), 18.0 / lg * 0.01)))), 0.012)
    cos = _m(nt, "MAXIMUM", cos, _m(nt, "LESS_THAN", _m(nt, "ABSOLUTE", _m(nt, "SUBTRACT", t, 0.16)), 0.01))
    lat = _attr(nt, "latido")
    lw = n.new("ShaderNodeLayerWeight")
    centro = _m(nt, "SUBTRACT", 1.0, lw.outputs["Facing"])
    em = _escalar(nt, C.get("neon", "#7fe8ff"), _m(nt, "MULTIPLY", cos, _m(nt, "ADD", 0.5, _m(nt, "MULTIPLY", lat, 2.0))))
    em = _sumar(nt, em, _escalar(nt, C.get("adentro", "#bff6ff"), _m(nt, "MULTIPLY", _m(nt, "MULTIPLY", centro, centro), _m(nt, "MULTIPLY", lat, 0.32))))
    # la raja: zigzag sobre el frente (x > 0) que sube desde la punta
    phi = _m(nt, "ARCTAN2", y, x)
    def _tri(k, a):
        # onda triangular: quiebres con esquina, no curvas
        fr_ = _m(nt, "FRACT", _m(nt, "MULTIPLY", t, k))
        return _m(nt, "MULTIPLY", _m(nt, "SUBTRACT", _m(nt, "MULTIPLY", _m(nt, "ABSOLUTE", _m(nt, "SUBTRACT", fr_, 0.5)), 4.0), 1.0), a)
    zig = _m(nt, "ADD", _tri(7.3, 0.16), _tri(19.0, 0.06))
    dphi = _m(nt, "ABSOLUTE", _m(nt, "SUBTRACT", phi, zig))
    gr = _attr(nt, "grieta")
    abierto = _m(nt, "GREATER_THAN", t, _m(nt, "SUBTRACT", 1.02, _m(nt, "MULTIPLY", gr, 1.05)))
    raja = _m(nt, "MULTIPLY", _m(nt, "LESS_THAN", dphi, 0.035), abierto)
    fuga = _m(nt, "MULTIPLY", _m(nt, "SUBTRACT", 1.0, _suave(nt, dphi, 0.04, 0.7)), _m(nt, "MULTIPLY", abierto, gr))
    em = _sumar(nt, em, _escalar(nt, "#f2fdff", _m(nt, "MULTIPLY", raja, 4.0)))
    em = _sumar(nt, em, _escalar(nt, C.get("neon", "#7fe8ff"), _m(nt, "MULTIPLY", fuga, 0.9)))
    afuera = _sumar(nt, afuera, _escalar(nt, em, pw))
    adentro = _escalar(nt, C.get("adentro", "#bff6ff"), _m(nt, "MULTIPLY", pw, C.get("adentro_k", 1.6)))
    _emit_out(nt, _mix(nt, geo.outputs["Backfacing"], afuera, adentro))
    return mat


def _cascara(C, abierta, rnd):
    """Malla de la crisalida con el origen en el enganche (arriba)."""
    lg = C.get("largo", 0.026)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=36, v_segments=24, radius=1.0)
    for vt in bm.verts:
        tt = (1.0 - vt.co.z) / 2.0
        # fina arriba (el cremaster), rolliza, y la punta de abajo redonda
        if tt < 0.62:
            w = math.sin(0.5 * math.pi * (0.06 + 0.94 * tt / 0.62)) ** 0.8
        else:
            w = math.sqrt(max(0.0, 1.0 - ((tt - 0.62) / 0.38) ** 2)) ** 0.9
        w *= C.get("ancho", 0.33)
        r = math.hypot(vt.co.x, vt.co.y)
        if r > 1e-6:
            vt.co = Vector((vt.co.x / r * w * lg, vt.co.y / r * w * 0.92 * lg, -tt * lg))
        else:
            vt.co = Vector((0.0, 0.0, -tt * lg))
    if abierta:
        corte = []
        for vt in bm.verts:
            tt = -vt.co.z / lg
            ang = math.atan2(vt.co.y, vt.co.x)
            borde = C.get("ventana", 0.32) + 0.08 * math.sin(ang * 7 + rnd.random())
            punta = tt > C.get("punta", 2.0) + 0.04 * math.sin(ang * 9)
            if punta or (tt > borde and abs(ang) < 1.25 + 0.2 * math.sin(tt * 30)):
                corte.append(vt)
        bmesh.ops.delete(bm, geom=corte, context="VERTS")
    me = bpy.data.meshes.new("crisalida")
    bm.to_mesh(me)
    bm.free()
    for pl in me.polygons:
        pl.use_smooth = True
    return me


_MAT_CRIS = {}


def build_crisalida(C, colls):
    """Una crisalida (dict) o varias (lista)."""
    for c in (C if isinstance(C, list) else [C]):
        _una_crisalida(c, colls)


def _una_crisalida(C, colls):
    """Crisalida de Morpho colgada por el cremaster: gota rolliza, fina arriba
    y redonda abajo. "abierta": la cascara vacia (ventana del lado +x y la
    punta). "abre": cuadro en que la cerrada se cambia por la abierta (revienta).
    Animable: "latido", "grieta" (0..1), "sacude" (grados), "power" (0 = apagada,
    gris), "forma" (0..1: crece desde el enganche, el capullo que se teje).
    C: {"at": [x, y, z], "largo": 0.026, "nombre": "crisalida", "luz": 0.004, ...}"""
    lg = C.get("largo", 0.026)
    nm = C.get("nombre", "crisalida")
    rnd = random.Random(C.get("seed", 3))
    piv = bpy.data.objects.new(f"{nm}_piv", None)
    piv.location = Vector(C["at"])
    piv.rotation_mode = "XYZ"
    piv.rotation_euler = (0, 0, math.radians(C.get("rumbo", 0.0)))
    link(piv, colls["main"])
    clave_mat = C.get("grupo")
    if clave_mat and clave_mat in _MAT_CRIS:
        mat = _MAT_CRIS[clave_mat]
    else:
        mat = mat_crisalida(nm, C)
        if clave_mat:
            _MAT_CRIS[clave_mat] = mat
    tallo_l = C.get("tallo", 0.003)
    abre = C.get("abre")
    cascaras = []
    for abierta in ((False, True) if abre else (C.get("abierta", False),)):
        me = _cascara(C, abierta, rnd)
        me.materials.append(mat)
        ob = bpy.data.objects.new(nm + ("_abierta" if abierta and abre else ""), me)
        ob.parent = piv
        ob.location = (0, 0, -tallo_l)
        link(ob, colls["main"])
        if abre:
            for fr, oculto in ((0, abierta), (abre, not abierta)):
                ob.hide_render = oculto
                ob.keyframe_insert("hide_render", frame=fr)
        cascaras.append(ob)
    tallo = _curva(f"{nm}_cremaster", [(0, 0, 0), (0, 0, -(tallo_l + 0.02 * lg))],
                   0.0012 * lg / 0.026, mat_toon("cremaster", "#1d2a3a"), afinar=False)
    tallo.parent = piv
    link(tallo, colls["main"])
    li = None
    if C.get("luz"):
        ld = bpy.data.lights.new(f"{nm}_luz", "POINT")
        ld.color = lin(C.get("adentro", "#bff6ff"))[:3]
        ld.shadow_soft_size = lg * 0.3
        ld.use_shadow = False
        li = bpy.data.objects.new(f"{nm}_luz", ld)
        li.parent = piv
        li.location = (0.25 * lg, 0, -0.7 * lg)
        link(li, colls["lights"])
    frames = ctx.CFG["frames"]
    fps = ctx.CFG.get("fps", 24)
    fase = rnd.random() * 6.0
    for f in range(1, frames + 1):
        lat = _tramo(C["latido"], f)[0] if C.get("latido") else (0.0 if not C.get("abierta") else 0.3)
        gr = _tramo(C["grieta"], f)[0] if C.get("grieta") else 0.0
        amp = _tramo(C["sacude"], f)[0] if C.get("sacude") else 0.0
        tt = f / fps + fase
        piv.rotation_euler = (math.radians(amp * math.sin(tt * 19.0)), math.radians(amp * 0.6 * math.sin(tt * 13.0 + 1.1)),
                              math.radians(C.get("rumbo", 0.0) + amp * 0.4 * math.sin(tt * 7.0)))
        piv.keyframe_insert("rotation_euler", frame=f)
        for ob in cascaras:
            ob["latido"] = lat
            ob["grieta"] = gr
            ob.keyframe_insert('["latido"]', frame=f)
            ob.keyframe_insert('["grieta"]', frame=f)
            if C.get("power"):
                ob["power"] = _tramo(C["power"], f)[0]
                ob.keyframe_insert('["power"]', frame=f)
            if C.get("forma"):
                k = max(0.001, _tramo(C["forma"], f)[0])
                ob.scale = (0.4 + 0.6 * k, 0.4 + 0.6 * k, k)
                ob.keyframe_insert("scale", frame=f)
        if li:
            li.data.energy = C["luz"] * (0.15 * lat + gr)
            li.data.keyframe_insert("energy", frame=f)
    for idb in [piv] + cascaras + ([li.data] if li else []):
        for fc in action_fcurves(idb.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT" if fc.data_path == "hide_render" else "LINEAR"


# --- la Reserva: ramas secas, crisalidas apagadas, el despertar y el enjambre --

def _arbol_mod():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("arbol_ep", Path(__file__).resolve().parent / "arbol.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_reserva(R, colls):
    """Un arbol seco de la Reserva con crisalidas colgadas (arbol.py), apagadas.
    R: {"base", "alto", "niveles", "seed", "crisalidas", "largo",
        "intentos": [[i, frame, "nada" | "parpadeo"]],      # ella prueba y no puede
        "despierta": {"desde": [x, y, z], "frame": f0, "vel": m_por_cuadro,
                      "revienta": cuadros},                  # la luz baja por las ramas
        "enjambre": {"destino": [x, y, z], "radio": 0.4, "max": 30, "escala": 0.05}}
    Con "despierta", la luz recorre cada rama desde el punto mas cercano a
    "desde" (una vena de neon que se enciende) y cada crisalida late, se raja y
    revienta en orden de distancia; de cada una sale una mariposa del enjambre."""
    AM = _arbol_mod()
    A = AM.arbol(R)
    madera = mat_toon("madera_seca", R.get("madera", "#3a2c3e"))
    vena_m = mat_neon("vena_rama", R.get("vena", "#bff6ff"), 2.2, fog=True)
    D = R.get("despierta")
    frames = ctx.CFG["frames"]
    for k, rama in enumerate(A["ramas"]):
        ob = _curva(f"rama_{k}", rama["pts"], rama["radio"], madera)
        link(ob, colls["main"])
        if D:
            # la vena se enciende tramo a tramo cuando llega la luz
            d0 = Vector(D["desde"])
            for i in range(len(rama["pts"]) - 1):
                pa, pb = Vector(rama["pts"][i]), Vector(rama["pts"][i + 1])
                f_on = D["frame"] + ((pa + pb) / 2 - d0).length / D.get("vel", 0.02)
                if f_on > frames:
                    continue
                arriba = Vector((0, 0, rama["radio"] * 0.7))
                v = _curva(f"vena_{k}_{i}", [tuple(pa + arriba), tuple(pb + arriba)], rama["radio"] * 0.28, vena_m, afinar=False)
                link(v, colls["neon"])
                # se enciende al pasar la luz y se apaga cuando la luz sigue de largo
                for fr, pw in ((0, 0.0), (int(f_on), 0.0), (int(f_on) + 3, 1.0), (int(f_on) + 14, 0.55),
                               (int(f_on) + 70, 0.08)):
                    v["power"] = pw
                    v.keyframe_insert('["power"]', frame=max(0, fr))
    intentos = {i: (f, modo) for i, f, modo in R.get("intentos", [])}
    E = R.get("enjambre")
    rnd = random.Random(R.get("seed", 4) + 7)
    swarm = []
    for i, c in enumerate(A["colgadas"]):
        C = {"at": list(c["at"]), "largo": c["largo"], "nombre": f"cris_{i:02d}", "grupo": "reserva",
             "color": R.get("cris_color", "#2b3a3a"), "seed": i, "rumbo": rnd.uniform(0, 360),
             "power": [[1, 0.0]]}
        if i in intentos:
            f, modo = intentos[i]
            if modo == "nada":
                C["latido"] = [[1, 0], [f, 0], [f + 2, 0.25], [f + 7, 0]]
                C["power"] = [[1, 0], [f, 0], [f + 2, 0.5], [f + 7, 0]]
            else:
                C["latido"] = [[1, 0], [f, 0], [f + 2, 0.9], [f + 5, 0.1], [f + 8, 0.6], [f + 14, 0]]
                C["power"] = [[1, 0], [f, 0], [f + 2, 1], [f + 5, 0.2], [f + 8, 0.8], [f + 14, 0]]
                C["sacude"] = [[1, 0], [f, 0], [f + 3, 2.0], [f + 10, 0]]
        if D:
            w = D["frame"] + (Vector(c["at"]) - Vector(D["desde"])).length / D.get("vel", 0.02) + rnd.uniform(0, 4)
            b = w + D.get("revienta", 30) + rnd.uniform(-4, 8)
            if w < frames:
                C["power"] = [[1, 0], [w, 0], [w + 2, 1]]
                C["latido"] = [[1, 0], [w, 0], [w + 2, 1.0], [w + 7, 0.3], [b - 10, 0.5], [b, 1.0]]
                C["grieta"] = [[1, 0], [b - 10, 0], [b, 1]]
                C["sacude"] = [[1, 0], [b - 12, 0], [b - 5, 4], [b, 7], [b + 2, 0]]
                C["ventana"] = 0.45
                C["punta"] = 0.8
                if b < frames:
                    C["abre"] = int(b)
                    swarm.append((int(b), c))
        _una_crisalida(C, colls)
    if E and swarm:
        swarm.sort(key=lambda x: x[0])
        dest = Vector(E["destino"])
        tronco = Vector(R["base"])
        lista = swarm[:E.get("max", 30)]
        for n, (b, c) in enumerate(lista):
            # cae un poco, sale de la copa hacia afuera (lejos del tronco) y recien
            # ahi sube: subir derecho la cruza contra las ramas. Cada una va a su
            # lugar en una esfera alrededor del destino: no convergen a un punto.
            # nace debajo de la cascara, con aire para las alas
            p0 = Vector(c["at"]) - Vector((0, 0, c["largo"] + 0.045))
            afuera = Vector((p0.x - tronco.x, p0.y - tronco.y, 0))
            afuera = afuera.normalized() if afuera.length > 1e-6 else Vector((1, 0, 0))
            for baja in (0.06, 0.12, 0.2, 0.3, 0.45):
                cae = p0 - Vector((0, 0, baja))
                sale = cae + afuera * E.get("sale", 0.45)
                if AM.camino_libre(A, list(p0), list(cae), 0.05, sin=(c["rama"],))                         and AM.camino_libre(A, list(cae), list(sale), 0.06):
                    break
            k = (n + 0.5) / len(lista)
            th = math.acos(1 - 2 * k)
            ph = math.pi * (1 + 5 ** 0.5) * n
            esfera = Vector((math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th) * 0.6))
            fin = dest + esfera * E.get("radio", 0.4)
            medio = sale.lerp(fin, 0.5) + Vector((0, 0, 0.1))
            rumbo = math.degrees(math.atan2(-(fin - p0).x, (fin - p0).y))
            dur = E.get("vuelo", 90)
            keys = [[b, list(p0), rumbo, 30], [b + 6, list(cae), rumbo, 10], [b + 24, list(sale), rumbo, 0],
                    [b + dur * 0.6, list(medio), rumbo, 10], [b + dur, list(fin), rumbo, 5]]
            _una_mariposa({"nombre": f"enjambre_{n:02d}", "grupo": "enjambre", "lejos": True,
                           "escala": E.get("escala", 0.05) * rnd.uniform(0.8, 1.1), "keys": keys,
                           "aleteo": [[1, rnd.uniform(8, 11), 62, 18]], "fase0": rnd.random(),
                           "despliegue": [[1, 0.35], [b, 0.35], [b + 8, 1.0]], "aparece": b,
                           "vaiven": 0.01, "dorso_k": 0.8, "seed": n}, colls)


# --- Puerto Madero: el dique, los docks, las gruas, las torres y el puente -------

def _caja(name, c, tam, mat, rot=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    m = Euler((0, 0, math.radians(rot))).to_matrix()
    for vt in bm.verts:
        vt.co = Vector(c) + m @ Vector((vt.co.x * tam[0], vt.co.y * tam[1], vt.co.z * tam[2]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    return bpy.data.objects.new(name, me)


def _viga(name, a, b, grosor, mat):
    """Caja larga de a a b (la pluma de la grua, patas, el mastil del puente)."""
    a, b = Vector(a), Vector(b)
    d = b - a
    ob = _caja(name, (0, 0, 0), (grosor, grosor, d.length), mat)
    ob.location = (a + b) / 2
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    return ob


def build_puerto(P, colls):
    """El dique de Puerto Madero de noche, a escala real (m). El agua corre por
    y entre x = -ancho/2 y +ancho/2 (z = 0); los muelles a z = 2.
    P: {"ancho": 60, "largo": 500, "docks": {...}, "gruas": [{"at": [x, y], "rumbo": deg}],
        "torres": [{"at": [x, y], "tam": [w, d], "alto": h}], "puente": {"y": 60}}"""
    main = colls["main"]
    antes = set(bpy.data.objects)
    W, Lg = P.get("ancho", 60), P.get("largo", 500)
    agua = _caja("agua", (0, Lg / 2 - 100, -0.5), (W + 4, Lg, 1.0), mat_agua("agua", P))
    link(agua, main)
    piso = mat_toon("muelle", P.get("muelle", "#2a2a40"))
    for s in (-1, 1):
        link(_caja(f"muelle_{s}", (s * (W / 2 + 40), Lg / 2 - 100, 1.0), (80, Lg, 2.0), piso), main)
    # docks de ladrillo (los galpones del puerto viejo) sobre el muelle oeste
    D = P.get("docks", {})
    ven = {"pitch_x": 3.2, "pitch_z": 3.6, "base": 3.0, "margin_x": 0.3, "margin_z": 0.28, "lit": 0.55,
           "cold_ratio": 0.7, "cold": "#9fd8ff", "warm": "#ffb066", "dark": "#1a1424"}
    m_dock = mat_toon("ladrillo", D.get("color", "#6e2f2a"), ven)
    y = D.get("desde", -60)
    while y < D.get("hasta", 380):
        largo = 70
        link(_caja(f"dock_{int(y)}", (-W / 2 - 22, y + largo / 2, 2 + 8), (22, largo - 6, 16), m_dock), main)
        y += largo
    # gruas portico, oxido rojo
    m_g = mat_toon("grua", P.get("grua_color", "#8c2e24"))
    for k, G in enumerate(P.get("gruas", [])):
        x0, y0 = G["at"]
        r = math.radians(G.get("rumbo", 90))
        fw = Vector((math.cos(r), math.sin(r), 0))
        lat = Vector((-fw.y, fw.x, 0))
        base = Vector((x0, y0, 2.0))
        h = G.get("alto", 12)
        for a in (-1, 1):
            for b2 in (-1, 1):
                pie = base + fw * a * 3.5 + lat * b2 * 3.0
                link(_viga(f"grua{k}_pata", pie, base + Vector((0, 0, h)) + (pie - base) * 0.25, 0.7, m_g), main)
        cab = base + Vector((0, 0, h + 3))
        link(_caja(f"grua{k}_cabina", cab, (5, 4, 6), m_g, math.degrees(r)), main)
        ang = math.radians(G.get("angulo", 38))
        punta = cab + fw * G.get("pluma", 32) * math.cos(ang) + Vector((0, 0, G.get("pluma", 32) * math.sin(ang)))
        link(_viga(f"grua{k}_pluma", cab + fw * 2, punta, 1.0, m_g), main)
        apice = cab + Vector((0, 0, 9)) - fw * 1.5
        link(_viga(f"grua{k}_torre", cab, apice, 0.8, m_g), main)
        contra = cab - fw * 9 + Vector((0, 0, 1))
        link(_viga(f"grua{k}_contra", cab - fw * 1, contra, 1.2, m_g), main)
        for q, dst in enumerate((punta, contra)):
            link(_curva(f"grua{k}_tirante{q}", [tuple(apice), tuple(dst)], 0.06, m_g, afinar=False), main)
        # el cable que cuelga de la punta (donde nacen las crisalidas)
        link(_curva(f"grua{k}_cable", [tuple(punta), tuple(punta - Vector((0, 0, G.get("cuelga", 14))))], 0.05,
                    m_g, afinar=False), main)
    # torres de vidrio de Madero Este
    vt = {"pitch_x": 2.4, "pitch_z": 3.4, "base": 4.0, "margin_x": 0.12, "margin_z": 0.2, "lit": 0.38,
          "cold_ratio": 0.35, "cold": "#8fd6ff", "warm": "#ffc68a", "dark": "#121a33"}
    m_t = mat_toon("torre_vidrio", P.get("torre_color", "#1c2442"), vt)
    m_bz = mat_neon("baliza", "#ff3355", 3.0)
    for k, T in enumerate(P.get("torres", [])):
        x0, y0 = T["at"]
        w, d = T.get("tam", (30, 30))
        h = T["alto"]
        link(_caja(f"torre_{k}", (x0, y0, 2 + h / 2), (w, d, h), m_t, T.get("rumbo", 0)), main)
        if T.get("baliza", True):
            link(_elipsoide(f"baliza_{k}", (0.8, 0.8, 0.8), (x0, y0, 2 + h + 1.5), m_bz), colls["neon"])
    # Puente de la Mujer: tablero sobre el agua y el mastil blanco inclinado con tirantes
    B = P.get("puente")
    if B:
        yb = B.get("y", 60)
        m_b = mat_toon("puente", B.get("color", "#8e94ad"))
        link(_caja("puente_tablero", (0, yb, 4.0), (W + 10, 6, 0.8), m_b), main)
        pie = Vector((B.get("pie_x", 8), yb, 4.0))
        inc = math.radians(B.get("inclina", 39))
        tope = pie + Vector((-34 * math.cos(inc), 0, 34 * math.sin(inc)))
        link(_viga("puente_mastil", pie, tope, 1.6, m_b), main)
        for i in range(1, 9):
            ancla = Vector((pie.x - (pie.x + W / 2) * i / 9.5, yb, 4.4))
            mm = pie.lerp(tope, 0.25 + 0.75 * i / 9)
            link(_curva(f"puente_tirante{i}", [tuple(mm), tuple(ancla)], 0.08, m_b, afinar=False), main)
        luces = mat_neon("puente_luz", "#bff6ff", 2.0)
        link(_viga("puente_borde", (-W / 2 - 5, yb - 3, 4.45), (W / 2 + 5, yb - 3, 4.45), 0.15, luces), colls["neon"])
    # el reflejo: todo lo del dique espejado bajo el agua, con sus materiales
    # (las ventanas encendidas se reflejan); el agua semitransparente lo deja ver
    espejo = bpy.data.objects.new("espejo_dique", None)
    espejo.scale = (1, 1, -1)
    link(espejo, colls["refl"])
    for ob in set(bpy.data.objects) - antes:
        if ob.type not in ("MESH", "CURVE") or ob.name == "agua" or ob.name.startswith("muelle"):
            continue
        cp = ob.copy()
        cp.parent = espejo
        link(cp, colls["refl"])


def mat_agua(name, P):
    """Agua del dique: oscura, con franjas de onda (ruido estirado a lo ancho),
    y transparente en parte para que se vea el mundo espejado de abajo."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    n = nt.nodes
    col = _mix(nt, 1.0, P.get("agua", "#0b0e26"), _toon_light(nt), "MULTIPLY")
    em = _emit_out(nt, col)
    out = next(x for x in n if x.type == "OUTPUT_MATERIAL")
    geo = n.new("ShaderNodeNewGeometry")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.12, 2.2, 1.0)
    nt.links.new(geo.outputs["Position"], mp.inputs["Vector"])
    nz = n.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 1.0
    nz.inputs["Detail"].default_value = 3.0
    nt.links.new(mp.outputs[0], nz.inputs["Vector"])
    onda = _m(nt, "GREATER_THAN", nz.outputs["Fac"], P.get("onda_umbral", 0.47))
    refleja = _m(nt, "SUBTRACT", P.get("refleja", 0.8), _m(nt, "MULTIPLY", onda, 0.45))
    tr = n.new("ShaderNodeBsdfTransparent")
    mix = n.new("ShaderNodeMixShader")
    nt.links.new(refleja, mix.inputs[0])
    nt.links.new(em.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    return mat


PIEZAS = [("puerto", build_puerto), ("reserva", build_reserva), ("mariposa", build_mariposa),
          ("bokeh", build_bokeh), ("cable", build_cable), ("crisalida", build_crisalida)]
