"""Materiales: todo termina en Emission. Toon por nodos, neon, pantallas,
piso mojado con charcos, velos y conos de luz."""

import math

import bpy
from mathutils import Euler, Vector

from . import ctx
from .base import lin, set_interp


def _fog(nt, color_socket):
    """Mezcla hacia el color de niebla segun la distancia a camara."""
    n = nt.nodes
    cam = n.new("ShaderNodeCameraData")
    k = n.new("ShaderNodeMath")
    k.operation = "DIVIDE"
    nt.links.new(cam.outputs["View Distance"], k.inputs[0])
    k.inputs[1].default_value = -ctx.FOG["dist"]
    e = n.new("ShaderNodeMath")
    e.operation = "EXPONENT"
    nt.links.new(k.outputs[0], e.inputs[0])
    f = n.new("ShaderNodeMath")
    f.operation = "SUBTRACT"
    f.inputs[0].default_value = 1.0
    nt.links.new(e.outputs[0], f.inputs[1])
    mix = n.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(f.outputs[0], mix.inputs["Factor"])
    nt.links.new(color_socket, mix.inputs[6])
    mix.inputs[7].default_value = lin(ctx.FOG["color"])
    return mix.outputs[2]


def _emit_out(nt, color_socket):
    n = nt.nodes
    em = n.new("ShaderNodeEmission")
    nt.links.new(color_socket, em.inputs["Color"])
    out = n.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return em


def _power(nt):
    """Propiedad 'power' del objeto (0..1, animable). Todo lo que emite la
    multiplica: asi el apagon se programa por objeto, no por material."""
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_type = "OBJECT"
    at.attribute_name = "power"
    return at.outputs["Fac"]


def _matas(nt, lum, F):
    """Follaje de fondo de anime: la luz se perturba con celdas de Voronoi
    (una mata por celda, mas iluminada en el centro), asi el corte de sombra
    de la copa sale en grumos y no en una curva lisa. F: {"escala": m,
    "fuerza": 0..1}."""
    n = nt.nodes
    geo = n.new("ShaderNodeNewGeometry")
    vo = n.new("ShaderNodeTexVoronoi")
    vo.feature = "F1"
    vo.inputs["Scale"].default_value = 1.0 / F.get("escala", 1.6)
    nt.links.new(geo.outputs["Position"], vo.inputs["Vector"])
    # 1 en el centro de la mata, ~0 en el borde
    k = n.new("ShaderNodeMapRange")
    k.inputs["From Min"].default_value = 0.0
    k.inputs["From Max"].default_value = 1.0
    k.inputs["To Min"].default_value = 1.0 + F.get("fuerza", 0.6)
    k.inputs["To Max"].default_value = 1.0 - F.get("fuerza", 0.6)
    nt.links.new(vo.outputs["Distance"], k.inputs["Value"])
    mul = n.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    nt.links.new(lum, mul.inputs[0])
    nt.links.new(k.outputs["Result"], mul.inputs[1])
    return mul.outputs[0]


def _borde_matas(nt, col, F):
    """El borde de cada mata pintado mas oscuro (las mismas celdas que
    _matas): del lado del sol la copa no cambia de escalon, y sin esto se ve
    plana. F["borde"]: ancho del borde en m; F["borde_tono"]: cuanto oscurece."""
    n = nt.nodes
    geo = n.new("ShaderNodeNewGeometry")
    vo = n.new("ShaderNodeTexVoronoi")
    vo.feature = "DISTANCE_TO_EDGE"
    vo.inputs["Scale"].default_value = 1.0 / F.get("escala", 1.6)
    nt.links.new(geo.outputs["Position"], vo.inputs["Vector"])
    lt = n.new("ShaderNodeMath")
    lt.operation = "LESS_THAN"
    nt.links.new(vo.outputs["Distance"], lt.inputs[0])
    lt.inputs[1].default_value = F["borde"] / F.get("escala", 1.6)
    k = n.new("ShaderNodeMapRange")
    k.inputs["From Min"].default_value = 0.0
    k.inputs["From Max"].default_value = 1.0
    k.inputs["To Min"].default_value = 1.0
    k.inputs["To Max"].default_value = F.get("borde_tono", 0.72)
    nt.links.new(lt.outputs[0], k.inputs["Value"])
    sc = n.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    nt.links.new(col, sc.inputs[0])
    nt.links.new(k.outputs["Result"], sc.inputs["Scale"])
    return sc.outputs[0]


def _borde_neon(nt, col, N):
    """Borde de luz de neon (rim): lo que la camara ve de canto se enciende
    de un color, en un escalon duro como el cel. N: {"color", "ancho", "fuerza"}."""
    n = nt.nodes
    lw = n.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    gt = n.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    nt.links.new(lw.outputs["Facing"], gt.inputs[0])
    gt.inputs[1].default_value = 1.0 - N.get("ancho", 0.22)
    mx = n.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    k = n.new("ShaderNodeMath")
    k.operation = "MULTIPLY"
    nt.links.new(gt.outputs[0], k.inputs[0])
    k.inputs[1].default_value = N.get("fuerza", 0.85)
    nt.links.new(k.outputs[0], mx.inputs["Factor"])
    nt.links.new(col, mx.inputs[6])
    mx.inputs[7].default_value = lin(N["color"])
    return mx.outputs[2]


def _toon_light(nt, matas=None):
    """Luz que recibe la superficie, cuantizada en escalones de luminancia
    pero conservando el tono (cuantizar por canal mete colores fuera de
    paleta: ver shaders/README.md). matas: follaje en grumos (ver _matas)."""
    n = nt.nodes
    dif = n.new("ShaderNodeBsdfDiffuse")
    dif.inputs["Color"].default_value = (1, 1, 1, 1)
    s2r = n.new("ShaderNodeShaderToRGB")
    nt.links.new(dif.outputs[0], s2r.inputs[0])
    bw = n.new("ShaderNodeRGBToBW")
    nt.links.new(s2r.outputs["Color"], bw.inputs[0])
    lum = _matas(nt, bw.outputs[0], matas) if matas else bw.outputs[0]
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    steps = ctx.TOON["steps"]
    while len(els) < len(steps):
        els.new(0.5)
    for el, (pos, val) in zip(els, steps):
        el.position = pos
        el.color = (val, val, val, 1)
    nt.links.new(lum, ramp.inputs["Fac"])
    q = n.new("ShaderNodeRGBToBW")
    nt.links.new(ramp.outputs["Color"], q.inputs[0])
    mx = n.new("ShaderNodeMath")
    mx.operation = "MAXIMUM"
    nt.links.new(bw.outputs[0], mx.inputs[0])
    mx.inputs[1].default_value = 0.004
    div = n.new("ShaderNodeMath")
    div.operation = "DIVIDE"
    nt.links.new(q.outputs[0], div.inputs[0])
    nt.links.new(mx.outputs[0], div.inputs[1])
    sc = n.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    nt.links.new(s2r.outputs["Color"], sc.inputs[0])
    nt.links.new(div.outputs[0], sc.inputs["Scale"])
    if ctx.CFG.get("gobo") and sol_dir():
        return _gobo(nt, sc.outputs[0], bw.outputs[0], ctx.CFG["gobo"])
    return sc.outputs[0]


def sol_dir():
    """Direccion en que viaja la luz del primer sol con sombra (unitaria), o
    None si no hay. Lee "rot" (grados) o "hacia" como build_lights."""
    for i, l in enumerate(ctx.CFG.get("lights", [])):
        if l.get("kind") != "SUN" or not l.get("shadow", i == 0):
            continue
        if "hacia" in l:
            return -Vector(l["hacia"]).normalized()
        d = Vector((0, 0, -1))
        d.rotate(Euler([math.radians(a) for a in l.get("rot", (0, 0, 0))]))
        return d
    return None


def _gobo(nt, light, lum, g):
    """Sol que cruza un vitral: donde la superficie recibe el sol (luz por
    encima de g["umbral"]: el ambiente no llega), la luz se tine con un
    mosaico de celdas de color y plomo oscuro. Cada punto se proyecta contra
    la direccion del sol sobre el plano x=0, asi una columna de luz conserva
    su color de punta a punta (en el piso, en un rack, en el aire). Sin
    sombra en los vidrios (vidrios.sombra=false) es lo que pinta las manchas;
    el contorno lo dan los muros y la traceria, que si hacen sombra.
    g: {"colores", "celda": [ancho, alto], "plomo", "plomo_ancho", "umbral":
    [desde, hasta], "fuerza"}."""
    n, L = nt.nodes, nt.links
    d = sol_dir()

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

    geo = n.new("ShaderNodeNewGeometry")
    sep = n.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])
    t = m("DIVIDE", sep.outputs[0], d.x if abs(d.x) > 1e-3 else 1e-3)
    qy = m("SUBTRACT", sep.outputs[1], m("MULTIPLY", t, d.y))
    qz = m("SUBTRACT", sep.outputs[2], m("MULTIPLY", t, d.z))
    cw, ch = g.get("celda", [0.9, 1.2])
    a = m("DIVIDE", qy, cw)
    b = m("DIVIDE", qz, ch)
    cell = n.new("ShaderNodeCombineXYZ")
    L.new(m("FLOOR", a), cell.inputs[0])
    L.new(m("FLOOR", b), cell.inputs[1])
    noise = n.new("ShaderNodeTexWhiteNoise")
    noise.noise_dimensions = "3D"
    L.new(cell.outputs[0], noise.inputs["Vector"])
    colors = g.get("colores", ["#ffffff"])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    while len(els) < len(colors):
        els.new(0.5)
    for k, (el, c) in enumerate(zip(els, colors)):
        el.position = k / len(colors)
        el.color = lin(c)
    L.new(noise.outputs["Value"], ramp.inputs["Fac"])
    lead = g.get("plomo_ancho", 0.08)
    plomo = m("MAXIMUM", m("LESS_THAN", m("FRACT", a), lead), m("LESS_THAN", m("FRACT", b), lead))
    vid = n.new("ShaderNodeMix")
    vid.data_type = "RGBA"
    L.new(plomo, vid.inputs["Factor"])
    L.new(ramp.outputs["Color"], vid.inputs[6])
    vid.inputs[7].default_value = lin(g.get("plomo", "#3a3040"))
    sc = n.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    L.new(vid.outputs[2], sc.inputs[0])
    sc.inputs["Scale"].default_value = g.get("fuerza", 1.0)
    u0, u1 = g.get("umbral", [0.25, 0.4])
    sol = n.new("ShaderNodeMapRange")
    sol.interpolation_type = "SMOOTHSTEP"
    sol.inputs["From Min"].default_value = u0
    sol.inputs["From Max"].default_value = u1
    L.new(lum, sol.inputs["Value"])
    tint = n.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    L.new(sol.outputs["Result"], tint.inputs["Factor"])
    tint.inputs[6].default_value = (1, 1, 1, 1)
    L.new(sc.outputs[0], tint.inputs[7])
    mul = n.new("ShaderNodeVectorMath")
    mul.operation = "MULTIPLY"
    L.new(light, mul.inputs[0])
    L.new(tint.outputs[2], mul.inputs[1])
    return mul.outputs[0]


def _glow(nt, g, albedo):
    """Resplandor suave de una fuente emisiva sobre la superficie, como el
    aerografo que se pinta encima del cel en el anime: 1/(1+(d/f)^2), sin
    escalones. g["kind"]: "point" (cristal) o "ring" (anillo horizontal).
    Su intensidad sigue a una propiedad del objeto (g["prop"]), que se anima
    con el apagon igual que la fuente."""
    n = nt.nodes
    L = nt.links

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

    geo = n.new("ShaderNodeNewGeometry")
    sep = n.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])
    cx, cy, cz = g["at"]
    dx = m("SUBTRACT", sep.outputs[0], cx)
    dy = m("SUBTRACT", sep.outputs[1], cy)
    dz = m("SUBTRACT", sep.outputs[2], cz)
    if g["kind"] == "ring":
        rho = m("SQRT", m("ADD", m("MULTIPLY", dx, dx), m("MULTIPLY", dy, dy)))
        dr = m("SUBTRACT", rho, g["r"])
        d2 = m("ADD", m("MULTIPLY", dr, dr), m("MULTIPLY", dz, dz))
    else:
        d2 = m("ADD", m("ADD", m("MULTIPLY", dx, dx), m("MULTIPLY", dy, dy)), m("MULTIPLY", dz, dz))
    k = m("DIVIDE", g["strength"], m("ADD", 1.0, m("DIVIDE", d2, g["falloff"] ** 2)))
    at = n.new("ShaderNodeAttribute")
    at.attribute_type = "OBJECT"
    at.attribute_name = g["prop"]
    k = m("MULTIPLY", k, at.outputs["Fac"])
    tint = n.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.inputs["Factor"].default_value = 0.6      # la luz toma algo del color de la piedra
    tint.inputs[6].default_value = lin(g["color"])
    tint.inputs[7].default_value = lin(albedo)
    sc = n.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    L.new(tint.outputs[2], sc.inputs[0])
    L.new(k, sc.inputs["Scale"])
    return sc.outputs[0]


def _franjas(nt, color, F):
    """Paños de ladrillo con franjas de piedra cada tanto en altura (la fabrica
    de la catedral de San Isidro): en las caras verticales el color es el
    ladrillo salvo una banda de piedra cada "paso" metros; las horizontales
    (cornisas, albardillas) quedan de piedra. F: {"color", "paso", "banda",
    "z", "esquinas", "aguja"} (ver abajo)."""
    n = nt.nodes
    L = nt.links
    geo = n.new("ShaderNodeNewGeometry")
    sp = n.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sp.inputs[0])
    sn = n.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Normal"], sn.inputs[0])

    def m(op, a, b):
        node = n.new("ShaderNodeMath")
        node.operation = op
        for i, x in enumerate((a, b)):
            if isinstance(x, (int, float)):
                node.inputs[i].default_value = x
            else:
                L.new(x, node.inputs[i])
        return node.outputs[0]
    x, y, z = sp.outputs[0], sp.outputs[1], sp.outputs[2]
    fr = m("FRACT", m("DIVIDE", z, F.get("paso", 1.2)), 0.0)
    ladrillo = m("GREATER_THAN", fr, F.get("banda", 0.22) / F.get("paso", 1.2))
    k = m("MULTIPLY", ladrillo, m("LESS_THAN", m("ABSOLUTE", sn.outputs[2], 0.0), 0.5))
    # "z": [desde, hasta]: el zocalo y lo alto van lisos, de piedra
    if "z" in F:
        z0, z1 = F["z"]
        k = m("MULTIPLY", k, m("MULTIPLY", m("GREATER_THAN", z, z0), m("LESS_THAN", z, z1)))
    # "esquinas": {"centro": [x, y], "desde": d}: solo los paños cerca de las
    # esquinas (foto 74: portada, gablete y rosetón son de piedra). La distancia
    # se mide sobre la cara: |y - cy| en las que miran a x, |x - cx| en las otras
    if "esquinas" in F:
        cx, cy = F["esquinas"]["centro"]
        dx = m("ABSOLUTE", m("SUBTRACT", x, cx), 0.0)
        dy = m("ABSOLUTE", m("SUBTRACT", y, cy), 0.0)
        u = m("ADD", m("MULTIPLY", m("ABSOLUTE", sn.outputs[0], 0.0), dy),
              m("MULTIPLY", m("ABSOLUTE", sn.outputs[1], 0.0), dx))
        k = m("MULTIPLY", k, m("GREATER_THAN", u, F["esquinas"]["desde"]))
    mix = n.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    L.new(k, mix.inputs["Factor"])
    mix.inputs[6].default_value = lin(color)
    mix.inputs[7].default_value = lin(F["color"])
    out = mix.outputs[2]
    # "aguja": {"centro": [x, y], "radio": r, "z": z, "color"}: lo que esta
    # arriba de z y cerca del eje (la aguja de pizarra) va de ese color
    if "aguja" in F:
        A = F["aguja"]
        vx = m("SUBTRACT", x, A["centro"][0])
        vy = m("SUBTRACT", y, A["centro"][1])
        r = m("SQRT", m("ADD", m("MULTIPLY", vx, vx), m("MULTIPLY", vy, vy)), 0.0)
        ka = m("MULTIPLY", m("GREATER_THAN", z, A["z"]), m("LESS_THAN", r, A["radio"]))
        mx2 = n.new("ShaderNodeMix")
        mx2.data_type = "RGBA"
        L.new(ka, mx2.inputs["Factor"])
        L.new(out, mx2.inputs[6])
        mx2.inputs[7].default_value = lin(A["color"])
        out = mx2.outputs[2]
    return out


def mat_toon(name, color, windows=None, glows=None, franjas=None, matas=None, dibujo=None):
    """Superficie opaca con sombreado toon. windows: dict opcional para
    grilla de ventanas por shader (sin geometria, sin linea). glows: lista de
    resplandores suaves que se suman encima del cel (ver _glow). franjas:
    paños de ladrillo con bandas del color base (ver _franjas). matas:
    follaje en grumos (ver _matas). dibujo: lo pintado en el piso (ver
    _dibujo: baldosas, marcas de la calle, charcos)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    n = nt.nodes
    light = _toon_light(nt, matas)
    mul = n.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    if franjas:
        nt.links.new(_franjas(nt, color, franjas), mul.inputs[6])
    elif dibujo and ("baldosas" in dibujo or "marcas" in dibujo):
        nt.links.new(_dibujo(nt, color, dibujo), mul.inputs[6])
    else:
        mul.inputs[6].default_value = lin(color)
    nt.links.new(light, mul.inputs[7])
    col = mul.outputs[2]
    if dibujo and dibujo.get("charcos"):
        col = _charcos(nt, col, dibujo["charcos"])
    if matas and matas.get("borde"):
        col = _borde_matas(nt, col, matas)
    if matas and matas.get("neon"):
        col = _borde_neon(nt, col, matas["neon"])
    if windows:
        col = _windows(nt, col, windows)
    for g in glows or []:
        add = n.new("ShaderNodeVectorMath")
        add.operation = "ADD"
        nt.links.new(col, add.inputs[0])
        nt.links.new(_glow(nt, g, color), add.inputs[1])
        col = add.outputs[0]
    _emit_out(nt, _fog(nt, col))
    return mat


def _dibujo(nt, color, D):
    """Color base de un piso con lo pintado encima, sin geometria:
    "baldosas": {"paso", "junta", "color"}: juntas en grilla (en x, y);
    "marcas": {"color", "ancho", "paso", "lleno"}: linea central discontinua
    de la calle, leida del UV "calle" (u = metros a lo largo, v = metros
    desde el eje; las calles angostas traen v lejos y no la llevan)."""
    n = nt.nodes
    L = nt.links

    def m(op, a, b=0.0):
        node = n.new("ShaderNodeMath")
        node.operation = op
        for i, x in enumerate((a, b)):
            if isinstance(x, (int, float)):
                node.inputs[i].default_value = x
            else:
                L.new(x, node.inputs[i])
        return node.outputs[0]

    def mezcla(base, c, k):
        mx = n.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        L.new(k, mx.inputs["Factor"])
        if isinstance(base, tuple):
            mx.inputs[6].default_value = base
        else:
            L.new(base, mx.inputs[6])
        mx.inputs[7].default_value = lin(c)
        return mx.outputs[2]

    out = lin(color)
    if "baldosas" in D:
        B = D["baldosas"]
        geo = n.new("ShaderNodeNewGeometry")
        sp = n.new("ShaderNodeSeparateXYZ")
        L.new(geo.outputs["Position"], sp.inputs[0])
        j = B.get("junta", 0.06) / B.get("paso", 0.8)
        jx = m("LESS_THAN", m("FRACT", m("DIVIDE", sp.outputs[0], B.get("paso", 0.8))), j)
        jy = m("LESS_THAN", m("FRACT", m("DIVIDE", sp.outputs[1], B.get("paso", 0.8))), j)
        out = mezcla(out, B["color"], m("MAXIMUM", jx, jy))
    if "marcas" in D:
        M = D["marcas"]
        uv = n.new("ShaderNodeUVMap")
        uv.uv_map = "calle"
        sp = n.new("ShaderNodeSeparateXYZ")
        L.new(uv.outputs["UV"], sp.inputs[0])
        enlinea = m("LESS_THAN", m("ABSOLUTE", sp.outputs[1]), M.get("ancho", 0.12) / 2)
        trazo = m("LESS_THAN", m("FRACT", m("DIVIDE", sp.outputs[0], M.get("paso", 6.0))), M.get("lleno", 0.5))
        out = mezcla(out, M["color"], m("MULTIPLY", enlinea, trazo))
    return out


def _charcos(nt, col, C):
    """Piso mojado pintado: manchas (ruido en x, y) que no reciben luz sino
    que muestran el reflejo, del color del cielo o del neon.
    C: {"color", "escala", "umbral", "fuerza"}."""
    n = nt.nodes
    L = nt.links
    geo = n.new("ShaderNodeNewGeometry")
    sp = n.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sp.inputs[0])
    xy = n.new("ShaderNodeCombineXYZ")
    L.new(sp.outputs[0], xy.inputs[0])
    L.new(sp.outputs[1], xy.inputs[1])
    no = n.new("ShaderNodeTexNoise")
    no.inputs["Scale"].default_value = 1.0 / C.get("escala", 6.0)
    no.inputs["Detail"].default_value = 3.0
    L.new(xy.outputs[0], no.inputs["Vector"])
    gt = n.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    L.new(no.outputs["Fac"], gt.inputs[0])
    gt.inputs[1].default_value = C.get("umbral", 0.6)
    k = n.new("ShaderNodeMath")
    k.operation = "MULTIPLY"
    L.new(gt.outputs[0], k.inputs[0])
    k.inputs[1].default_value = C.get("fuerza", 0.8)
    mx = n.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    L.new(k.outputs[0], mx.inputs["Factor"])
    L.new(col, mx.inputs[6])
    mx.inputs[7].default_value = lin(C["color"])
    out = mx.outputs[2]
    R = C.get("reflejos")
    if not R:
        return out
    # reflejos de las luces de la ciudad: trazos verticales de color en el
    # charco, ubicados por la x de pantalla (el reflejo de una luz cae debajo
    # de ella) y ondulados por el agua
    tc = n.new("ShaderNodeTexCoord")
    sw = n.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Window"], sw.inputs[0])
    on = n.new("ShaderNodeTexNoise")
    on.inputs["Scale"].default_value = 1.2
    L.new(xy.outputs[0], on.inputs["Vector"])

    def m(op, a, b=0.0):
        node = n.new("ShaderNodeMath")
        node.operation = op
        for i, x in enumerate((a, b)):
            if isinstance(x, (int, float)):
                node.inputs[i].default_value = x
            else:
                L.new(x, node.inputs[i])
        return node.outputs[0]
    xw = m("ADD", sw.outputs[0], m("MULTIPLY", m("SUBTRACT", on.outputs["Fac"], 0.5), R.get("onda", 0.012)))
    barra = m("FLOOR", m("MULTIPLY", xw, R.get("barras", 90)))
    wn = n.new("ShaderNodeTexWhiteNoise")
    wn.noise_dimensions = "1D"
    L.new(barra, wn.inputs["W"])
    hay = m("GREATER_THAN", wn.outputs["Value"], 1.0 - R.get("densidad", 0.3))
    # color de la barra: uno de la paleta, elegido por otro azar de la barra
    wn2 = n.new("ShaderNodeTexWhiteNoise")
    wn2.noise_dimensions = "1D"
    L.new(m("ADD", barra, 17.3), wn2.inputs["W"])
    cols = R.get("colores", ["#ffb347", "#3ee8ff", "#ff3fb0"])
    cb = lin(cols[0])
    cur = None
    for i, c in enumerate(cols[1:], 1):
        sel = m("GREATER_THAN", wn2.outputs["Value"], i / len(cols))
        mxc = n.new("ShaderNodeMix")
        mxc.data_type = "RGBA"
        L.new(sel, mxc.inputs["Factor"])
        if cur is None:
            mxc.inputs[6].default_value = cb
        else:
            L.new(cur, mxc.inputs[6])
        mxc.inputs[7].default_value = lin(c)
        cur = mxc.outputs[2]
    fin = n.new("ShaderNodeMix")
    fin.data_type = "RGBA"
    L.new(m("MULTIPLY", m("MULTIPLY", hay, gt.outputs[0]), R.get("fuerza", 0.9)), fin.inputs["Factor"])
    L.new(out, fin.inputs[6])
    if cur is None:
        fin.inputs[7].default_value = cb
    else:
        L.new(cur, fin.inputs[7])
    return fin.outputs[2]


def _windows(nt, base_socket, w):
    """Grilla de ventanas en las fachadas. u = coordenada horizontal sobre la
    cara (y para caras que miran a +-x, x para las que miran a +-y)."""
    n = nt.nodes
    L = nt.links
    geo = n.new("ShaderNodeNewGeometry")
    sep_p = n.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep_p.inputs[0])
    sep_n = n.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Normal"], sep_n.inputs[0])

    def m(op, a, b=None, val=None):
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

    nx = m("ABSOLUTE", sep_n.outputs[0])
    ny = m("ABSOLUTE", sep_n.outputs[1])
    nz = m("ABSOLUTE", sep_n.outputs[2])
    u = m("ADD", m("MULTIPLY", sep_p.outputs[1], nx), m("MULTIPLY", sep_p.outputs[0], ny))
    z = sep_p.outputs[2]
    cu = m("DIVIDE", u, w["pitch_x"])
    cz = m("DIVIDE", m("SUBTRACT", z, w["base"]), w["pitch_z"])
    fu = m("FRACT", cu)
    fz = m("FRACT", cz)
    # ventana = dentro del rectangulo en ambos ejes, no en techos, arriba de la planta baja
    in_u = m("MULTIPLY", m("GREATER_THAN", fu, w["margin_x"]), m("LESS_THAN", fu, 1 - w["margin_x"]))
    in_z = m("MULTIPLY", m("GREATER_THAN", fz, w["margin_z"]), m("LESS_THAN", fz, 1 - w["margin_z"] * 0.6))
    mask = m("MULTIPLY", in_u, in_z)
    mask = m("MULTIPLY", mask, m("LESS_THAN", nz, 0.5))
    mask = m("MULTIPLY", mask, m("GREATER_THAN", z, w["base"]))

    # celda -> azar fijo: encendida o no, calida o fria
    comb = n.new("ShaderNodeCombineXYZ")
    L.new(m("FLOOR", cu), comb.inputs[0])
    L.new(m("FLOOR", cz), comb.inputs[1])
    # la normal interpolada varia en el ultimo decimal entre pixeles: sin
    # redondear, el hash da otro azar por pixel y la ventana sale rayada
    L.new(m("ROUND", m("ADD", m("MULTIPLY", sep_n.outputs[0], 3.0), sep_n.outputs[1])), comb.inputs[2])
    noise = n.new("ShaderNodeTexWhiteNoise")
    noise.noise_dimensions = "3D"
    L.new(comb.outputs[0], noise.inputs["Vector"])
    sep_c = n.new("ShaderNodeSeparateColor")
    L.new(noise.outputs["Color"], sep_c.inputs[0])
    lit = m("MULTIPLY", m("LESS_THAN", noise.outputs["Value"], w["lit"]), _power(nt))
    warm = m("GREATER_THAN", sep_c.outputs[0], w.get("cold_ratio", 0.45))

    pick = n.new("ShaderNodeMix")
    pick.data_type = "RGBA"
    L.new(warm, pick.inputs["Factor"])
    pick.inputs[6].default_value = lin(w["cold"])
    pick.inputs[7].default_value = lin(w["warm"])

    glass = n.new("ShaderNodeMix")
    glass.data_type = "RGBA"
    L.new(lit, glass.inputs["Factor"])
    glass.inputs[6].default_value = lin(w["dark"])
    L.new(pick.outputs[2], glass.inputs[7])

    out = n.new("ShaderNodeMix")
    out.data_type = "RGBA"
    L.new(mask, out.inputs["Factor"])
    L.new(base_socket, out.inputs[6])
    L.new(glass.outputs[2], out.inputs[7])
    return out.outputs[2]


def mat_neon(name, color, strength=1.0, fog=True):
    """Emisivo puro. La niebla lo afecta menos: la luz atraviesa la bruma."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    rgb = nt.nodes.new("ShaderNodeRGB")
    c = lin(color)
    rgb.outputs[0].default_value = (c[0] * strength, c[1] * strength, c[2] * strength, 1)
    sc = nt.nodes.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    nt.links.new(rgb.outputs[0], sc.inputs[0])
    nt.links.new(_power(nt), sc.inputs["Scale"])
    sock = sc.outputs[0]
    if fog:
        saved = ctx.FOG["dist"]
        ctx.FOG["dist"] = saved * 2.5
        sock = _fog(nt, sock)
        ctx.FOG["dist"] = saved
    _emit_out(nt, sock)
    mat["neon"] = True
    return mat


def mat_screen(name, c1, c2, freq=0.9, speed=2.0, axis=2):
    """Pantalla con contenido: barras que corren, dos tonos planos (nada de
    gradiente: es una pantalla de anime). El tiempo es un nodo Value animado
    linealmente, asi el patron es funcion pura del frame."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    n = nt.nodes
    L = nt.links
    t = n.new("ShaderNodeValue")
    t.outputs[0].default_value = 0.0
    t.outputs[0].keyframe_insert("default_value", frame=1)
    t.outputs[0].default_value = speed * ctx.CFG["frames"] / ctx.CFG["fps"]
    t.outputs[0].keyframe_insert("default_value", frame=ctx.CFG["frames"])
    set_interp(nt, "LINEAR")
    geo = n.new("ShaderNodeNewGeometry")
    sep = n.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])
    mul = n.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    L.new(sep.outputs[axis], mul.inputs[0])
    mul.inputs[1].default_value = freq
    add = n.new("ShaderNodeMath")
    add.operation = "ADD"
    L.new(mul.outputs[0], add.inputs[0])
    L.new(t.outputs[0], add.inputs[1])
    sn = n.new("ShaderNodeMath")
    sn.operation = "SINE"
    L.new(add.outputs[0], sn.inputs[0])
    gt = n.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    L.new(sn.outputs[0], gt.inputs[0])
    gt.inputs[1].default_value = 0.2
    mix = n.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    L.new(gt.outputs[0], mix.inputs["Factor"])
    mix.inputs[6].default_value = lin(c2)
    mix.inputs[7].default_value = lin(c1)
    sc = n.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    L.new(mix.outputs[2], sc.inputs[0])
    L.new(_power(nt), sc.inputs["Scale"])
    saved = ctx.FOG["dist"]
    ctx.FOG["dist"] = saved * 2.5
    sock = _fog(nt, sc.outputs[0])
    ctx.FOG["dist"] = saved
    _emit_out(nt, sock)
    return mat


def mat_flat(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    rgb = nt.nodes.new("ShaderNodeRGB")
    rgb.outputs[0].default_value = lin(color)
    _emit_out(nt, _fog(nt, rgb.outputs[0]))
    return mat


def mat_wet_ground(name, color, puddles):
    """Asfalto toon con charcos: donde hay charco el piso es transparente y se
    ve el mundo espejado de abajo, entintado."""
    mat = mat_toon(name, color)
    nt = mat.node_tree
    n = nt.nodes
    out = next(x for x in n if x.type == "OUTPUT_MATERIAL")
    em = next(x for x in n if x.type == "EMISSION")
    tex = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, puddles.get("stretch", 0.35), 1.0)
    nt.links.new(tex.outputs["Object"], mp.inputs["Vector"])
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = puddles["scale"]
    noise.inputs["Detail"].default_value = 2.0
    nt.links.new(mp.outputs[0], noise.inputs["Vector"])
    gt = n.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    nt.links.new(noise.outputs["Fac"], gt.inputs[0])
    gt.inputs[1].default_value = puddles["threshold"]
    mask = gt.outputs[0]
    # charcos puestos a mano, en coordenadas de mundo: [x, y, rx, ry]. Para el
    # charco donde termina un plano y empieza el siguiente, el azar no sirve.
    geo = n.new("ShaderNodeNewGeometry")
    sep = n.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    for (px, py, rx, ry) in puddles.get("spots", []):
        acc = None
        for comp, c0, r in ((0, px, rx), (1, py, ry)):
            d = n.new("ShaderNodeMath")
            d.operation = "SUBTRACT"
            nt.links.new(sep.outputs[comp], d.inputs[0])
            d.inputs[1].default_value = c0
            q = n.new("ShaderNodeMath")
            q.operation = "DIVIDE"
            nt.links.new(d.outputs[0], q.inputs[0])
            q.inputs[1].default_value = r
            sq = n.new("ShaderNodeMath")
            sq.operation = "POWER"
            nt.links.new(q.outputs[0], sq.inputs[0])
            sq.inputs[1].default_value = 2.0
            if acc is None:
                acc = sq.outputs[0]
            else:
                ad = n.new("ShaderNodeMath")
                ad.operation = "ADD"
                nt.links.new(acc, ad.inputs[0])
                nt.links.new(sq.outputs[0], ad.inputs[1])
                acc = ad.outputs[0]
        inside = n.new("ShaderNodeMath")
        inside.operation = "LESS_THAN"
        nt.links.new(acc, inside.inputs[0])
        inside.inputs[1].default_value = 1.0
        mx = n.new("ShaderNodeMath")
        mx.operation = "MAXIMUM"
        nt.links.new(mask, mx.inputs[0])
        nt.links.new(inside.outputs[0], mx.inputs[1])
        mask = mx.outputs[0]
    tr = n.new("ShaderNodeBsdfTransparent")
    mix = n.new("ShaderNodeMixShader")
    nt.links.new(mask, mix.inputs[0])
    nt.links.new(em.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "DITHERED"
    return mat


def mat_tint(name, color, alpha, powered=False):
    """Velo semitransparente entre el piso y el reflejo: oscurece y entinta.
    powered: la opacidad sigue a la propiedad 'power' (conos de luz)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = lin(color)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = 1.0 - alpha
    if powered:
        a = nt.nodes.new("ShaderNodeMath")
        a.operation = "MULTIPLY"
        a.inputs[0].default_value = alpha
        nt.links.new(_power(nt), a.inputs[1])
        f = nt.nodes.new("ShaderNodeMath")
        f.operation = "SUBTRACT"
        f.inputs[0].default_value = 1.0
        nt.links.new(a.outputs[0], f.inputs[1])
        nt.links.new(f.outputs[0], mix.inputs[0])
    nt.links.new(em.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    return mat


def mat_beam(name, color, alpha):
    """Cono de luz plano y translucido, como se pinta en un fondo de anime."""
    mat = mat_tint(name, color, alpha, powered=True)
    em = next(x for x in mat.node_tree.nodes if x.type == "EMISSION")
    em.inputs["Strength"].default_value = 1.0
    # una sola cara: con las dos, el cono se ve el doble de denso
    mat.use_backface_culling = True
    return mat
