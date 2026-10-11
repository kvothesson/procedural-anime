"""Espacio: estrellas en el cielo y la Tierra de noche vista desde orbita.

La Tierra no usa imagenes de afuera: la textura (continentes y luces de
ciudades) se genera con numpy a partir de poligonos lon/lat y una lista de
ciudades, directo a un bpy Image. Proyeccion equirectangular.
"""

import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

from .base import lin, link
from .materiales import _emit_out

# ------------------------------------------------------------------ estrellas


def build_estrellas(e, colls):
    """Suma estrellas al fondo que ve la camara (no iluminan nada). Voronoi
    sobre la direccion de vista: posicion fija en el cielo, tamano fijo."""
    world = bpy.context.scene.world
    nt = world.node_tree
    n, L = nt.nodes, nt.links
    bg = next(x for x in n if x.type == "BACKGROUND" and x.name != world["amb"])
    sky_link = next(l for l in nt.links if l.to_socket == bg.inputs["Color"])
    sky = sky_link.from_socket
    tc = n.new("ShaderNodeTexCoord")
    vor = n.new("ShaderNodeTexVoronoi")
    vor.voronoi_dimensions = "3D"
    vor.inputs["Scale"].default_value = e.get("scale", 55.0)
    L.new(tc.outputs["Generated"], vor.inputs["Vector"])
    sep = n.new("ShaderNodeSeparateColor")
    L.new(vor.outputs["Color"], sep.inputs[0])

    def m(op, a, b):
        node = n.new("ShaderNodeMath")
        node.operation = op
        for i, x in enumerate((a, b)):
            if isinstance(x, (int, float)):
                node.inputs[i].default_value = x
            else:
                L.new(x, node.inputs[i])
        return node.outputs[0]

    # radio por celda: unas pocas grandes, muchas chicas; y solo una fraccion de celdas tiene estrella
    radius = m("MULTIPLY", m("POWER", sep.outputs[0], 3.0), e.get("size", 0.06))
    star = m("LESS_THAN", vor.outputs["Distance"], radius)
    star = m("MULTIPLY", star, m("LESS_THAN", sep.outputs[1], e.get("density", 0.45)))
    star = m("MULTIPLY", star, m("ADD", 0.4, m("MULTIPLY", sep.outputs[2], 0.6)))
    tint = n.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    L.new(sep.outputs[2], tint.inputs["Factor"])
    tint.inputs[6].default_value = lin(e.get("cold", "#bcd4ff"))
    tint.inputs[7].default_value = lin(e.get("warm", "#fff1d6"))
    sc = n.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    L.new(tint.outputs[2], sc.inputs[0])
    L.new(m("MULTIPLY", star, e.get("strength", 1.0)), sc.inputs["Scale"])
    add = n.new("ShaderNodeVectorMath")
    add.operation = "ADD"
    L.new(sky, add.inputs[0])
    L.new(sc.outputs[0], add.inputs[1])
    L.new(add.outputs[0], bg.inputs["Color"])


# ------------------------------------------------------------------ tierra

# Costas simplificadas (lon, lat). Alcanza para que Sudamerica se reconozca
# desde orbita geoestacionaria a 72 W; el resto solo asoma en el borde.
SUDAMERICA = [
    (-77.3, 8.6), (-75.5, 10.5), (-72.0, 11.8), (-71.3, 12.4), (-68.0, 10.6), (-64.0, 10.6),
    (-61.8, 10.7), (-60.0, 8.5), (-57.0, 6.0), (-54.0, 5.7), (-51.5, 4.2), (-50.0, 1.8),
    (-49.0, -0.5), (-44.5, -2.5), (-41.0, -2.9), (-38.5, -3.7), (-35.2, -5.5), (-34.8, -7.5),
    (-35.5, -9.5), (-37.0, -11.0), (-38.9, -13.0), (-39.0, -17.5), (-40.0, -20.0), (-41.0, -22.0),
    (-43.0, -23.0), (-46.5, -24.0), (-48.5, -26.0), (-48.6, -28.5), (-50.5, -31.0), (-52.5, -33.5),
    (-53.5, -34.5), (-55.0, -34.9), (-56.3, -34.9), (-58.4, -34.5), (-57.3, -36.0), (-56.7, -36.5),
    (-57.5, -38.1), (-62.0, -39.0), (-62.3, -40.5), (-65.0, -41.0), (-64.0, -42.5), (-65.0, -45.0),
    (-67.5, -46.5), (-66.0, -48.0), (-68.5, -50.5), (-68.4, -52.3), (-65.5, -55.0), (-67.0, -55.9),
    (-70.0, -55.0), (-72.5, -53.0), (-74.5, -50.0), (-75.5, -46.5), (-74.0, -43.5), (-73.5, -40.0),
    (-73.5, -37.0), (-71.7, -33.0), (-71.5, -30.0), (-70.5, -27.0), (-70.2, -23.0), (-70.3, -18.3),
    (-72.0, -17.0), (-76.0, -14.0), (-78.0, -10.0), (-80.0, -7.0), (-81.2, -5.0), (-80.3, -3.4),
    (-80.0, -1.0), (-80.0, 1.0), (-78.8, 1.8), (-77.5, 4.0), (-77.4, 6.5),
]
CENTROAMERICA = [
    (-77.3, 8.6), (-79.5, 9.5), (-82.0, 9.0), (-83.5, 10.8), (-83.3, 15.0), (-87.5, 15.9),
    (-88.3, 18.5), (-87.0, 21.5), (-90.5, 21.0), (-91.5, 18.5), (-94.5, 18.2), (-97.3, 21.5),
    (-97.5, 25.9), (-97.0, 28.0), (-94.0, 29.5), (-89.5, 30.2), (-85.0, 29.8), (-82.8, 27.5),
    (-81.0, 25.2), (-80.0, 26.8), (-81.3, 30.5), (-79.0, 33.5), (-76.0, 35.5), (-76.0, 38.5),
    (-74.0, 40.5), (-70.0, 41.8), (-70.5, 43.5), (-66.0, 45.0), (-61.0, 45.5), (-60.0, 47.0),
    (-64.0, 49.0), (-56.0, 52.0), (-61.0, 56.0), (-65.0, 60.0), (-78.0, 62.0), (-95.0, 60.0),
    (-125.0, 60.0), (-125.0, 49.0), (-124.0, 42.0), (-120.5, 34.5), (-117.0, 32.5), (-114.5, 30.0),
    (-110.0, 24.0), (-109.5, 23.0), (-112.0, 29.0), (-114.8, 31.5), (-112.5, 29.0), (-110.5, 27.0),
    (-105.5, 22.5), (-105.0, 19.5), (-101.0, 17.5), (-96.5, 15.7), (-92.5, 14.5), (-91.0, 13.9),
    (-88.0, 13.2), (-86.0, 11.5), (-85.7, 10.5), (-84.5, 9.6), (-82.5, 8.2), (-80.0, 7.4),
    (-78.5, 8.2),
]
AFRICA = [
    (-17.0, 21.0), (-16.5, 14.5), (-17.5, 14.7), (-15.0, 11.0), (-13.0, 8.0), (-10.0, 6.0),
    (-7.5, 4.4), (-2.0, 4.8), (3.0, 6.3), (8.5, 4.5), (9.5, 2.0), (9.0, -1.0), (12.0, -6.0),
    (13.5, -12.0), (11.8, -17.0), (14.5, -22.5), (16.5, -28.6), (18.4, -34.0), (25.0, -34.0),
    (25.0, 30.0), (10.0, 37.0), (-6.0, 35.8), (-9.8, 31.5), (-13.0, 27.5),
]
CUBA = [(-85.0, 21.8), (-82.0, 23.1), (-77.5, 22.0), (-74.2, 20.2), (-77.5, 19.9), (-81.0, 21.6)]
LANDS = [SUDAMERICA, CENTROAMERICA, AFRICA, CUBA]

# (lon, lat, peso). La Argentina va con detalle: es el plano.
CITIES = [
    (-58.4, -34.6, 1.0), (-64.2, -31.4, 0.6), (-60.6, -32.9, 0.55), (-68.8, -32.9, 0.45),
    (-65.2, -26.8, 0.4), (-57.95, -34.9, 0.4), (-57.55, -38.0, 0.35), (-65.4, -24.8, 0.3),
    (-60.7, -31.6, 0.3), (-68.06, -38.95, 0.3), (-62.27, -38.7, 0.25), (-71.3, -41.13, 0.25),
    (-67.5, -45.86, 0.2), (-68.3, -54.8, 0.15), (-55.9, -27.4, 0.2), (-58.98, -27.45, 0.2),
    (-68.5, -31.5, 0.25), (-64.26, -27.8, 0.2), (-60.5, -31.7, 0.2), (-65.3, -43.3, 0.15),
    (-69.2, -51.6, 0.12), (-66.3, -33.3, 0.18), (-62.0, -38.0, 0.12), (-59.1, -37.3, 0.15),
    (-70.65, -33.45, 0.7), (-56.2, -34.9, 0.5), (-46.6, -23.5, 1.0), (-43.2, -22.9, 0.8),
    (-57.6, -25.3, 0.35), (-77.0, -12.0, 0.7), (-74.1, 4.7, 0.6), (-66.9, 10.5, 0.5),
    (-47.9, -15.8, 0.4), (-43.9, -19.9, 0.5), (-51.2, -30.0, 0.45), (-49.3, -25.4, 0.4),
    (-38.5, -13.0, 0.4), (-34.9, -8.0, 0.4), (-38.5, -3.7, 0.35), (-68.1, -16.5, 0.3),
    (-78.5, -0.2, 0.3), (-79.9, -2.2, 0.3), (-75.6, 6.2, 0.35), (-73.1, -36.8, 0.3),
    (-71.6, -33.0, 0.3), (-70.4, -23.6, 0.2), (-63.2, -17.8, 0.25), (-48.5, -1.4, 0.3),
    (-60.0, -3.1, 0.3), (-99.1, 19.4, 0.9), (-80.2, 25.8, 0.6), (-84.4, 33.7, 0.5),
    (-74.0, 40.7, 0.9), (-87.6, 41.9, 0.7), (-95.4, 29.8, 0.6), (-82.4, 23.1, 0.3),
]


def _land_mask(W, H):
    lon = (np.arange(W) + 0.5) / W * 360.0 - 180.0
    lat = 90.0 - (np.arange(H) + 0.5) / H * 180.0
    X, Y = np.meshgrid(lon, lat)
    mask = np.zeros((H, W), bool)
    for poly in LANDS:
        inside = np.zeros((H, W), bool)
        pts = poly + [poly[0]]
        for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
            if y0 == y1:
                continue
            cond = (Y >= min(y0, y1)) & (Y < max(y0, y1))
            xc = x0 + (Y - y0) * (x1 - x0) / (y1 - y0)
            inside ^= cond & (X < xc)
        mask |= inside
    mask |= Y < -68.0          # Antartida
    return mask, X, Y


def _splat(img, W, H, lon, lat, sigma_deg, amp):
    """Mancha gaussiana en grados de arco reales (corrige el estiramiento
    de la proyeccion lejos del ecuador)."""
    cx = (lon + 180.0) / 360.0 * W
    cy = (90.0 - lat) / 180.0 * H
    sx = sigma_deg / 360.0 * W / max(0.2, math.cos(math.radians(lat)))
    sy = sigma_deg / 180.0 * H
    x0, x1 = int(cx - 4 * sx), int(cx + 4 * sx) + 1
    y0, y1 = max(0, int(cy - 4 * sy)), min(H, int(cy + 4 * sy) + 1)
    xs = np.arange(x0, x1)
    ys = np.arange(y0, y1)
    gx = np.exp(-0.5 * ((xs + 0.5 - cx) / sx) ** 2)
    gy = np.exp(-0.5 * ((ys + 0.5 - cy) / sy) ** 2)
    img[y0:y1, xs % W] += amp * np.outer(gy, gx)


def earth_images(W=2048, H=1024, seed=72):
    """Devuelve (dia, noche) como arrays HxWx3 lineales."""
    land, X, Y = _land_mask(W, H)
    rng = np.random.default_rng(seed)
    day = np.zeros((H, W, 3), np.float32)
    day[:] = lin("#1b4a86")[:3]
    day[land] = lin("#4d7a3c")[:3]
    day[Y < -68.0] = lin("#e8eef5")[:3]
    # mar y tierra de noche: azules muy oscuros, la tierra apenas mas clara
    night = np.zeros((H, W, 3), np.float32)
    night[:] = lin("#050b1e")[:3]
    night[land] = lin("#0d1630")[:3]
    lights = np.zeros((H, W), np.float32)
    for lon, lat, w in CITIES:
        _splat(lights, W, H, lon, lat, 0.18 + 0.35 * w, 1.6 * w)
        _splat(lights, W, H, lon, lat, 0.05 + 0.08 * w, 2.5 * w)
    # pueblos: puntitos sobre tierra, mas densos cerca de las ciudades grandes
    ly, lx = np.nonzero(land & (Y > -56) & (Y < 50))
    pick = rng.choice(len(ly), 2600, replace=False)
    for k in pick:
        lon, lat = X[ly[k], lx[k]], Y[ly[k], lx[k]]
        near = sum(w / (1 + ((lon - c0) ** 2 + (lat - c1) ** 2) / 8) for c0, c1, w in CITIES)
        if rng.random() < 0.03 + 0.97 * min(1.0, near):
            _splat(lights, W, H, lon, lat, 0.06, rng.uniform(0.15, 0.5))
    warm = np.array(lin("#ffb35c")[:3], np.float32)
    night += lights[..., None] * warm
    return day, night


def _image(name, arr):
    H, W, _ = arr.shape
    img = bpy.data.images.new(name, W, H, alpha=False, float_buffer=True)
    rgba = np.ones((H, W, 4), np.float32)
    rgba[..., :3] = arr
    img.pixels.foreach_set(rgba[::-1].ravel())     # Blender guarda de abajo hacia arriba
    img.pack()
    img.colorspace_settings.name = "Non-Color"     # ya es lineal
    return img


def _equirect_uv(nt):
    """UV equirectangular desde las coordenadas del objeto: la longitud L cae
    en la direccion local (-cos L, -sin L, 0) y el norte en +Z (asi, vista de
    afuera con el norte arriba, el este queda a la derecha)."""
    n, L = nt.nodes, nt.links
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Object"], sep.inputs[0])

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

    x, y, z = sep.outputs[0], sep.outputs[1], sep.outputs[2]
    lon = m("ARCTAN2", m("MULTIPLY", y, -1.0), m("MULTIPLY", x, -1.0))
    lat = m("ARCTAN2", z, m("SQRT", m("ADD", m("MULTIPLY", x, x), m("MULTIPLY", y, y))))
    comb = n.new("ShaderNodeCombineXYZ")
    L.new(m("ADD", m("DIVIDE", lon, 2 * math.pi), 0.5), comb.inputs[0])
    L.new(m("ADD", m("DIVIDE", lat, math.pi), 0.5), comb.inputs[1])
    return comb.outputs[0]


def mat_tierra(name, day_img, night_img, e):
    """La Tierra tiene su propio sol (e["sun_dir"], de la Tierra hacia el Sol,
    en mundo): asi se la puede ver de noche aunque el satelite este iluminado
    de frente. Cel de dos tonos en el lado de dia, una franja de crepusculo y,
    del lado de noche, las luces de las ciudades."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    n, L = nt.nodes, nt.links
    uv = _equirect_uv(nt)
    texs = []
    for img in (day_img, night_img):
        t = n.new("ShaderNodeTexImage")
        t.image = img
        t.interpolation = "Cubic"
        t.extension = "EXTEND"
        L.new(uv, t.inputs["Vector"])
        texs.append(t)
    geo = n.new("ShaderNodeNewGeometry")
    dot = n.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    L.new(geo.outputs["Normal"], dot.inputs[0])
    dot.inputs[1].default_value = Vector(e.get("sun_dir", (1, 0, 0))).normalized()

    def step(edge):
        node = n.new("ShaderNodeMath")
        node.operation = "GREATER_THAN"
        L.new(dot.outputs["Value"], node.inputs[0])
        node.inputs[1].default_value = edge
        return node.outputs[0]

    def mix(fac, a, b):
        node = n.new("ShaderNodeMix")
        node.data_type = "RGBA"
        L.new(fac, node.inputs["Factor"])
        for sock, v in ((node.inputs[6], a), (node.inputs[7], b)):
            if isinstance(v, str):
                sock.default_value = lin(v)
            else:
                L.new(v, sock)
        return node.outputs[2]

    def scale(sock, k):
        node = n.new("ShaderNodeVectorMath")
        node.operation = "SCALE"
        L.new(sock, node.inputs[0])
        node.inputs["Scale"].default_value = k
        return node.outputs[0]

    day_dim = scale(texs[0].outputs["Color"], e.get("day_shade", 0.55))
    day = mix(step(e.get("day_full", 0.3)), day_dim, texs[0].outputs["Color"])
    dusk = mix(step(e.get("dusk", 0.07)), e.get("dusk_color", "#ff8a4a"), day)
    out = mix(step(0.0), texs[1].outputs["Color"], dusk)
    _emit_out(nt, out)
    return mat


def mat_atmosfera(name, color, strength):
    """Halo del borde: transparente de frente, color en el limbo."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    n, L = nt.nodes, nt.links
    lw = n.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    pw = n.new("ShaderNodeMath")
    pw.operation = "POWER"
    L.new(lw.outputs["Facing"], pw.inputs[0])
    pw.inputs[1].default_value = 3.0
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = lin(color)
    em.inputs["Strength"].default_value = strength
    tr = n.new("ShaderNodeBsdfTransparent")
    mix = n.new("ShaderNodeMixShader")
    L.new(pw.outputs[0], mix.inputs[0])
    L.new(tr.outputs[0], mix.inputs[1])
    L.new(em.outputs[0], mix.inputs[2])
    out = n.new("ShaderNodeOutputMaterial")
    L.new(mix.outputs[0], out.inputs["Surface"])
    mat.use_backface_culling = True
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    return mat


def earth_rotation(e):
    """Gira la Tierra para que el punto (sub_lon, sub_lat) mire a e["face_to"]
    (el satelite) con el norte lo mas cerca posible de +Z del mundo.
    Convencion de _equirect_uv: la longitud L cae en (-cos L, -sin L, 0) local,
    el norte en +Z local."""
    lon, lat = math.radians(e.get("sub_lon", 0.0)), math.radians(e.get("sub_lat", 0.0))
    d_loc = Vector((-math.cos(lon) * math.cos(lat), -math.sin(lon) * math.cos(lat), math.sin(lat)))
    n_loc = (Vector((0, 0, 1)) - d_loc * d_loc.z).normalized()
    s = (Vector(e.get("face_to", (0, 0, 0))) - Vector(e["center"])).normalized()
    up = Vector(e.get("north", (0, 0, 1)))
    n_w = (up - s * up.dot(s)).normalized()
    loc = Matrix((d_loc, n_loc, d_loc.cross(n_loc))).transposed()
    wld = Matrix((s, n_w, s.cross(n_w))).transposed()
    return (wld @ loc.transposed()).to_euler()


def build_tierra(e, colls):
    """Esfera con la Tierra. e: center, radius, sub_lon/sub_lat (punto que mira
    a face_to; p. ej. -72, 0), sun_dir (de la Tierra al Sol), atmosphere."""
    day, night = earth_images(e.get("tex_w", 2048), e.get("tex_w", 2048) // 2)
    mat = mat_tierra("tierra_m", _image("tierra_dia", day), _image("tierra_noche", night), e)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=e["radius"],
                                         location=e["center"])
    ob = bpy.context.active_object
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.name = "tierra"
    ob.data.materials.append(mat)
    ob.rotation_euler = earth_rotation(e)
    link(ob, colls["neon"])        # sin linea de tinta: es fondo
    if e.get("atmosphere"):
        a = e["atmosphere"]
        bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64,
                                             radius=e["radius"] * a.get("scale", 1.03),
                                             location=e["center"])
        at = bpy.context.active_object
        for c in list(at.users_collection):
            c.objects.unlink(at)
        for p in at.data.polygons:
            p.use_smooth = True
        at.name = "atmosfera"
        at.data.materials.append(mat_atmosfera("atmosfera_m", a.get("color", "#5fa8ff"),
                                               a.get("strength", 1.2)))
        link(at, colls["veil"])
    return ob
