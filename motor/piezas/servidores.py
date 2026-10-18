"""Servidores que llenan la Catedral de San Isidro: filas de racks en la
nave, las naves laterales y los brazos del crucero; un nucleo en el centro
del crucero; cables que cuelgan de las columnas, cruzan la nave desde el
triforio y suben del nucleo a la boveda.

La disposicion sale de las medidas de piezas/catedral.py (tramos, columnas,
crucero). El look (colores, leds, luces) lo pone el estilo del plano.

Los racks van todos en dos mallas (cuerpos y frentes) con un atributo
"rack" por cara: el shader de leds lo usa para que cada rack sea distinto.
"""

import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from .base import key_power, lin, tint_light
from .catedral import AI, BAY, NB, XC, XW, Y_CR0, Y_CR1, Z_TRI0, Z_V, Pieza
from .materiales import _fog, _toon_light, mat_neon, mat_toon

RW, RD, RH = 0.6, 1.1, 2.2         # rack: ancho (a lo largo de la fila), fondo, alto
CORE = (0.0, 35.6)                 # nucleo, en el crucero (antes de las gradas del presbiterio)


# ---------------------------------------------------------------- disposicion
def filas_catedral():
    """Filas: (x, y) del centro del primer rack, direccion de la fila, cuantos
    racks y hacia donde mira el frente. Bloques centrados en cada tramo, con
    pasillo a la altura de las columnas."""
    filas = []
    n_nave = 7
    for k in range(NB):
        yc = (k + 0.5) * BAY
        y0 = yc - (n_nave - 1) * RW / 2
        for sx in (-1, 1):
            # doble fila espalda con espalda en la nave central
            for face, xx in ((-sx, 1.35 + RD / 2), (sx, 1.35 + RD * 1.5)):
                filas.append({"at": (sx * xx, y0), "dir": (0, 1), "n": n_nave, "front": (face, 0)})
            # fila simple contra el muro de la nave lateral
            n_lat = 6
            filas.append({"at": (sx * (XW - 0.1 - RD / 2), yc - (n_lat - 1) * RW / 2), "dir": (0, 1),
                          "n": n_lat, "front": (-sx, 0)})
    # brazos del crucero: dos filas dobles a lo largo de x
    n_arm = 12
    for sx in (-1, 1):
        x0 = sx * 6.3
        for yc in (33.6, 38.6):
            for face, dy in ((-1, -RD / 2), (1, RD / 2)):
                filas.append({"at": (x0, yc + dy), "dir": (sx, 0), "n": n_arm, "front": (0, face)})
    return filas


def rack_centers(filas):
    out = []
    for f in filas:
        d = Vector(f["dir"] + (0,))
        for i in range(f["n"]):
            c = Vector(f["at"] + (0,)) + d * RW * i
            out.append((c, d, Vector(f["front"] + (0,))))
    return out


# ---------------------------------------------------------------- materiales
def _driver_frame(nt):
    """Valor que sigue al frame (para el parpadeo). Expresion simple: Blender
    la evalua sin Python, tambien en background."""
    val = nt.nodes.new("ShaderNodeValue")
    fc = val.outputs[0].driver_add("default_value")
    fc.driver.type = "SCRIPTED"
    fc.driver.expression = "frame"
    return val.outputs[0]


def mat_leds(name, frente, leds):
    """Frente de rack: panel oscuro con sombreado toon y, encima, unidades de
    1U con leds puntuales (densidad por rack y por unidad), una franja de
    estado y una fraccion que parpadea con el frame."""
    colors = leds.get("colores", ["#3cf2ff"])
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

    uv = n.new("ShaderNodeUVMap")
    sep = n.new("ShaderNodeSeparateXYZ")
    L.new(uv.outputs[0], sep.inputs[0])
    at = n.new("ShaderNodeAttribute")
    at.attribute_type = "GEOMETRY"
    at.attribute_name = "rack"
    rack = at.outputs["Fac"]
    units, cols = leds.get("unidades", 30), leds.get("columnas", 7)
    a = m("MULTIPLY", sep.outputs[0], cols)
    b = m("MULTIPLY", sep.outputs[1], units)
    cell = n.new("ShaderNodeCombineXYZ")
    L.new(m("FLOOR", a), cell.inputs[0])
    L.new(m("FLOOR", b), cell.inputs[1])
    L.new(rack, cell.inputs[2])
    row = n.new("ShaderNodeCombineXYZ")
    L.new(m("FLOOR", b), row.inputs[1])
    L.new(rack, row.inputs[2])

    def noise(vec, w=None):
        nz = n.new("ShaderNodeTexWhiteNoise")
        nz.noise_dimensions = "4D" if w is not None else "3D"
        L.new(vec, nz.inputs["Vector"])
        if isinstance(w, (int, float)):
            nz.inputs["W"].default_value = w
        elif w is not None:
            L.new(w, nz.inputs["W"])
        return nz

    # led: punto en el centro de la celda
    du = m("ABSOLUTE", m("SUBTRACT", m("FRACT", a), 0.5))
    dv = m("ABSOLUTE", m("SUBTRACT", m("FRACT", b), 0.5))
    dot = m("MULTIPLY", m("LESS_THAN", du, 0.22), m("LESS_THAN", dv, 0.28))
    # unidad ocupada (algunas vacias) y led encendido
    occ = m("GREATER_THAN", noise(row.outputs[0]).outputs["Value"], leds.get("vacias", 0.25))
    dens = leds.get("densidad", 0.45)
    on = m("LESS_THAN", noise(cell.outputs[0]).outputs["Value"], dens)
    # parpadeo: parte de los leds cambia cada `periodo` frames
    frame = _driver_frame(nt)
    step = m("FLOOR", m("DIVIDE", frame, leds.get("periodo", 2)))
    blink_sel = m("LESS_THAN", noise(cell.outputs[0], 7.0).outputs["Value"], leds.get("parpadeo", 0.3))
    blink_on = m("GREATER_THAN", noise(cell.outputs[0], step).outputs["Value"], 0.5)
    on = m("MAXIMUM", m("MULTIPLY", on, m("SUBTRACT", 1.0, blink_sel)), m("MULTIPLY", blink_sel, blink_on))
    mask = m("MULTIPLY", m("MULTIPLY", dot, occ), on)
    # franja de estado a un costado
    strip = m("MULTIPLY", m("GREATER_THAN", sep.outputs[0], 0.9), m("LESS_THAN", sep.outputs[0], 0.95))
    strip = m("MULTIPLY", strip, m("GREATER_THAN", sep.outputs[1], 0.04))
    mask = m("MAXIMUM", mask, strip)
    # latido: la propiedad "latido" del objeto (0..1, animable) prende todos
    # los leds de todas las unidades a la vez, del mismo color
    lt = n.new("ShaderNodeAttribute")
    lt.attribute_type = "OBJECT"
    lt.attribute_name = "latido"
    lat = lt.outputs["Fac"]
    mask = m("ADD", m("MULTIPLY", mask, m("SUBTRACT", 1.0, lat)), m("MULTIPLY", dot, lat))
    # color: un color dominante por rack y algunos leds de otro
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    while len(els) < len(colors):
        els.new(0.5)
    for k, (el, c) in enumerate(zip(els, colors)):
        el.position = k / len(colors)
        el.color = lin(c)
    rk = n.new("ShaderNodeCombineXYZ")
    L.new(rack, rk.inputs[0])
    pick = m("ADD", m("MULTIPLY", noise(rk.outputs[0]).outputs["Value"], 0.8),
             m("MULTIPLY", noise(cell.outputs[0], 3.0).outputs["Value"], 0.35))
    L.new(m("FRACT", pick), ramp.inputs["Fac"])
    unico = n.new("ShaderNodeMix")
    unico.data_type = "RGBA"
    L.new(lat, unico.inputs["Factor"])
    L.new(ramp.outputs["Color"], unico.inputs[6])
    unico.inputs[7].default_value = lin(leds.get("latido_color", "#dffbff"))
    led_col = n.new("ShaderNodeVectorMath")
    led_col.operation = "SCALE"
    L.new(unico.outputs[2], led_col.inputs[0])
    L.new(m("MULTIPLY", m("MULTIPLY", mask, leds.get("fuerza", 3.0)), m("ADD", 1.0, m("MULTIPLY", lat, 0.8))),
          led_col.inputs["Scale"])
    # panel con toon
    base = n.new("ShaderNodeMix")
    base.data_type = "RGBA"
    base.blend_type = "MULTIPLY"
    base.inputs["Factor"].default_value = 1.0
    base.inputs[6].default_value = lin(frente)
    L.new(_toon_light(nt), base.inputs[7])
    add = n.new("ShaderNodeVectorMath")
    add.operation = "ADD"
    L.new(base.outputs[2], add.inputs[0])
    L.new(led_col.outputs[0], add.inputs[1])
    em = n.new("ShaderNodeEmission")
    L.new(_fog(nt, add.outputs[0]), em.inputs["Color"])
    out = n.new("ShaderNodeOutputMaterial")
    L.new(em.outputs[0], out.inputs["Surface"])
    return mat


# ---------------------------------------------------------------- geometria
def _racks(centers, rnd):
    body = Pieza("servidores_racks")
    front = Pieza("servidores_frentes")
    lay_b = body.bm.faces.layers.float.new("rack")
    lay_f = front.bm.faces.layers.float.new("rack")
    uv = front.bm.loops.layers.uv.new("UVMap")
    for idx, (c, d, f) in enumerate(centers):
        rid = rnd.random() * 100
        h = RH * (1.0 if rnd.random() > 0.15 else 0.82)
        side = d.cross(Vector((0, 0, 1)))       # ancho del rack = d; fondo = side
        # cuerpo
        nf = len(body.bm.faces)
        corners = []
        for sz in (0, 1):
            for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                corners.append(c + d * (su * RW / 2 * 0.96) + side * (sv * RD / 2) + Vector((0, 0, h * sz)))
        vs = [body.bm.verts.new(p) for p in corners]
        for q in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            body.bm.faces.new([vs[i] for i in q])
        for face in list(body.bm.faces)[nf:]:
            face[lay_b] = rid
        # frente: plano apenas delante de la cara que mira a f
        s = 1 if side.dot(f) > 0 else -1
        o = c + side * s * (RD / 2 + 0.012)
        uax = d * (RW / 2 * 0.88) * (-s)
        pts = [o - uax + Vector((0, 0, 0.08)), o + uax + Vector((0, 0, 0.08)),
               o + uax + Vector((0, 0, h - 0.06)), o - uax + Vector((0, 0, h - 0.06))]
        fv = [front.bm.verts.new(p) for p in pts]
        face = front.bm.faces.new(fv)
        face[lay_f] = rid
        for loop, (u, v) in zip(face.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
            loop[uv].uv = (u, v)
    return body, front


def _catenary(p0, p1, sag, n=14):
    p0, p1 = Vector(p0), Vector(p1)
    return [tuple(p0.lerp(p1, t) - Vector((0, 0, sag * 4 * t * (1 - t)))) for t in (i / n for i in range(n + 1))]


def _cable(pc, pts, r):
    """Cable redondo (6 lados) por una polilinea."""
    pts = [Vector(p) for p in pts]
    rings = []
    for i, p in enumerate(pts):
        T = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        S = T.cross(Vector((0, 0, 1)))
        if S.length < 1e-4:
            S = T.cross(Vector((1, 0, 0)))
        S.normalize()
        Nn = S.cross(T)
        rings.append([pc.bm.verts.new(p + (S * math.cos(a) + Nn * math.sin(a)) * r)
                      for a in (2 * math.pi * k / 6 for k in range(6))])
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(6):
            j = (k + 1) % 6
            pc.bm.faces.new([r0[k], r0[j], r1[j], r1[k]])


def _cables(pc, filas, rnd):
    # de cada bloque de la nave central a las columnas de sus extremos
    for f in filas:
        if f["dir"] != (0, 1) or abs(f["at"][0]) > 4.0:
            continue
        x = f["at"][0]
        y_end = f["at"][1] + RW * (f["n"] - 1)
        for y_top, y_col in ((f["at"][1], round(f["at"][1] / BAY) * BAY), (y_end, round(y_end / BAY) * BAY)):
            if y_col <= 0 or y_col >= Y_CR0:
                continue
            col = (math.copysign(XC, x), y_col, 7.4)
            for j in range(3):
                off = Vector((rnd.uniform(-0.15, 0.15), rnd.uniform(-0.2, 0.2), 0))
                _cable(pc, _catenary(Vector((x, y_top, RH)) + off, Vector(col) + off * 0.5,
                                     rnd.uniform(0.6, 1.4)), rnd.uniform(0.025, 0.05))
    # telaranas: del triforio de un lado al otro, colgando sobre la nave
    for k in range(NB):
        for j in range(3):
            y0 = k * BAY + rnd.uniform(0.8, BAY - 0.8)
            y1 = y0 + rnd.uniform(-1.5, 1.5)
            _cable(pc, _catenary((-AI + 0.2, y0, Z_TRI0 - 0.3), (AI - 0.2, y1, Z_TRI0 - 0.3),
                                 rnd.uniform(2.0, 4.5), n=20), rnd.uniform(0.03, 0.07))
    # del nucleo a los pilares del crucero y a la clave
    cx, cy = CORE
    for sx in (-1, 1):
        for y in (Y_CR0, Y_CR1):
            for j in range(4):
                o = Vector((rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), 0))
                _cable(pc, _catenary(Vector((cx, cy, 6.0)) + o, (sx * XC, y, Z_V - 0.8),
                                     rnd.uniform(1.0, 2.5)), rnd.uniform(0.04, 0.08))
    for j in range(7):
        a = 2 * math.pi * j / 7
        p0 = (cx + 0.5 * math.cos(a), cy + 0.5 * math.sin(a), 6.2)
        p1 = (cx + 0.15 * math.cos(a), (Y_CR0 + Y_CR1) / 2 + 0.15 * math.sin(a), 18.9)
        _cable(pc, _catenary(p0, p1, 0.0, n=6), 0.07)
    # bandejas portacables sobre los bloques
    for f in filas:
        d = Vector(f["dir"] + (0,))
        a = Vector(f["at"] + (0,)) - d * RW / 2
        b = a + d * RW * f["n"]
        lo = Vector((min(a.x, b.x), min(a.y, b.y), 0))
        hi = Vector((max(a.x, b.x), max(a.y, b.y), 0))
        w = 0.2
        if f["dir"][0] == 0:
            lo.x -= w
            hi.x += w
        else:
            lo.y -= w
            hi.y += w
        pc.box(lo.x, hi.x, lo.y, hi.y, RH + 0.35, RH + 0.42)


def _nucleo(pc, glow_pc):
    """El nucleo: base escalonada, cuerpo con aletas y anillos que brillan."""
    cx, cy = CORE
    pc.cyl(cx, cy, 0.0, 0.3, 2.3, segs=8, rot=math.pi / 8)
    pc.cyl(cx, cy, 0.3, 0.6, 1.9, segs=8, rot=math.pi / 8)
    pc.cyl(cx, cy, 0.6, 5.6, 1.3, 1.1, segs=16)
    pc.cyl(cx, cy, 5.6, 6.2, 1.5, 0.7, segs=16)
    for k in range(8):
        a = 2 * math.pi * k / 8
        x, y = cx + 1.35 * math.cos(a), cy + 1.35 * math.sin(a)
        # aleta radial
        bmesh.ops.create_cube(pc.bm, size=1.0, matrix=(
            Matrix.Translation((x + math.cos(a) * 0.2, y + math.sin(a) * 0.2, 2.9))
            @ Matrix.Rotation(a, 4, "Z") @ Matrix.Diagonal((0.45, 0.12, 4.6, 1))))
    for z in (1.6, 3.0, 4.4):
        glow_pc.cyl(cx, cy, z, z + 0.16, 1.32, segs=24)
    glow_pc.cyl(cx, cy, 6.2, 6.5, 0.5, segs=16)


# ---------------------------------------------------------------- armado
def build_servidores(e, colls):
    """e: {"colores": {"cuerpo", "frente", "cable"}, "leds": {...}, "latido": [[frame, 0..1], ...],
    "nucleo": "#...", "luces": {"energia": 60} o false, "seed": 7}"""
    rnd = random.Random(e.get("seed", 7))
    col = {"cuerpo": "#9a9da3", "frente": "#6e7178", "cable": "#55585e", **e.get("colores", {})}
    leds = e.get("leds", {})
    filas = e.get("filas") or filas_catedral()
    centers = rack_centers(filas)
    main = colls["main"]

    body, front = _racks(centers, rnd)
    body.done(mat_toon("servidores_cuerpo", col["cuerpo"]), main, weld=False)
    if leds.get("modo") == "toon":
        mf = mat_toon("servidores_frente", leds.get("colores", [col["frente"]])[0])
    else:
        mf = mat_leds("servidores_frente", col["frente"], leds)
    ob = front.done(mf, main, weld=False)
    latido = e.get("latido", [[1, 0.0]])
    for f, v in latido:
        ob["latido"] = float(v)
        ob.keyframe_insert('["latido"]', frame=f)
    ob.lineart.usage = "EXCLUDE"

    pc = Pieza("servidores_cables")
    _cables(pc, filas, rnd)
    pc.done(mat_toon("servidores_cable", col["cable"]), main, weld=False)

    pc = Pieza("servidores_nucleo")
    gl = Pieza("servidores_nucleo_luz")
    _nucleo(pc, gl)
    pc.done(mat_toon("servidores_nucleo", col["cuerpo"]), main)
    nuc = e.get("nucleo", col["cuerpo"])
    if leds.get("modo") == "toon":
        gl.done(mat_toon("servidores_nucleo_luz", nuc), main)
    else:
        glo = gl.done(mat_neon("servidores_nucleo_luz", nuc, e.get("nucleo_fuerza", 2.5)), colls["neon"])
        # con el latido el nucleo sube a la vez que los leds
        for f, v in latido:
            key_power(glo, f, 1.0 + 1.2 * float(v))

    luces = e.get("luces", {})
    if luces:
        cols = leds.get("colores", ["#3cf2ff"])
        en = luces.get("energia", 60)
        k = 0
        for f in filas:
            d = Vector(f["dir"] + (0,))
            mid = Vector(f["at"] + (0,)) + d * RW * (f["n"] - 1) / 2
            fr = Vector(f["front"] + (0,))
            # una luz por bloque, delante del frente: el pasillo se tine
            if k % 2 == 0:
                p = mid + fr * 0.9 + Vector((0, 0, 1.3))
                tint_light(f"servidores_luz{k}", cols[k // 2 % len(cols)], en, tuple(p), colls)
            k += 1
        tint_light("servidores_luz_nucleo", nuc, luces.get("nucleo", 400), (CORE[0], CORE[1], 4.0), colls)
        tint_light("servidores_luz_nucleo_alta", nuc, luces.get("nucleo", 400) * 0.6,
                   (CORE[0], CORE[1], 12.0), colls)
