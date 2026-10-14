"""
piezas.py - DUENDE ROJO: el Uritorco visto desde Capilla del Monte y el duende
rojo (red sprite) que asoma sobre el cerro.

Ejes: el observador (la calle techada) esta en el origen; x = este, y = norte,
z arriba, en metros. Todo se ubica por azimut y distancia desde ahi, con las
medidas reales: el Uritorco a 5,7 km y azimut 61 grados; el duende sobre una
tormenta a 150-300 km, con la base a ~13 grados de elevacion y la cima a ~23.

El duende se construye a una distancia menor que la real (no hace falta
geometria a 200 km), pero con los mismos angulos: se ve igual.

    "uritorco": {"az": 61, "dist": 5700, "alto": 1000},
    "duende": {"az": 61, "dist": 30000, "elev": [13, 23.5], "ancho_deg": 14,
               "seed": 3, "fase": [[1, 0.0], [60, 1.0]], "brillo": [[1, 1.0]]}

"fase" (0..1) es el avance de la descarga: 0 = nada, ~0.1 el halo, 0.2-0.6 las
cabezas que bajan, 1 = los tentaculos abiertos. Se anima con claves.
"""

import importlib.util
import math
import random
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

from piezas import ctx
from piezas.base import action_fcurves, link, set_interp

# utilitarios del episodio NODO 0 (mallas, tubos, nodos de shader)
_spec = importlib.util.spec_from_file_location(
    "piezas_nodo0", Path(__file__).resolve().parent.parent / "nodo_0" / "piezas.py")
N0 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(N0)
_m, _mix, _noise, _mesh_obj = N0._m, N0._mix, N0._noise, N0._mesh_obj


def _dir(az):
    a = math.radians(az)
    return Vector((math.sin(a), math.cos(a), 0.0))


def _prop_keys(ob, name, keys, default=1.0, interp="LINEAR"):
    ob[name] = default
    for f, v in keys or []:
        ob[name] = v
        ob.keyframe_insert(f'["{name}"]', frame=f)
    if keys:
        for fc in action_fcurves(ob.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = interp


# --- el cerro -------------------------------------------------------------------

def build_uritorco(e, colls):
    """El Uritorco y las sierras que lo acompanan, como relieve: una cumbre
    principal en la direccion y distancia reales, hombros a los costados y
    lomas mas bajas cerca del pueblo. De noche es silueta con un poco de forma."""
    from mathutils import noise
    az, dist, alto = e.get("az", 61), e.get("dist", 5700), e.get("alto", 1000)
    c = _dir(az) * dist
    lado = Vector((c.y, -c.x, 0)).normalized()
    lomas = [(c, alto, 1700, 1300),
             (c + lado * 2600 - _dir(az) * 500, alto * 0.72, 1500, 1200),
             (c - lado * 3200 + _dir(az) * 800, alto * 0.62, 2000, 1500),
             (c - lado * 6500 + _dir(az) * 2500, alto * 0.55, 2600, 1800),
             (c + lado * 6000 + _dir(az) * 1500, alto * 0.5, 2500, 1700),
             (_dir(az + 25) * 2200, 160, 900, 700)]

    def h(x, y):
        z = 0.0
        for p, hh, rx, ry in lomas:
            z += hh * math.exp(-(((x - p.x) / rx) ** 2 + ((y - p.y) / ry) ** 2))
        rid = 1 - abs(noise.noise(Vector((x / 900, y / 900, 2.3))))
        return z * (0.82 + 0.3 * rid) + 12 * noise.noise(Vector((x / 300, y / 300, 0.7)))

    S, n = e.get("tam", 26000), e.get("res", 160)
    bm = bmesh.new()
    rows = []
    for j in range(n + 1):
        row = []
        for i in range(n + 1):
            x, y = -S * 0.25 + S * i / n, -S * 0.25 + S * j / n
            row.append(bm.verts.new((x, y, h(x, y))))
        rows.append(row)
    for j in range(n):
        for i in range(n):
            bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))

    def albedo(nt):
        f = _m(nt, "GREATER_THAN", _noise(nt, 0.0012, (1, 1, 1), 3.0), 0.55)
        return _mix(nt, f, e.get("color", "#2c2a3a"), e.get("mancha", "#23202e"))
    _mesh_obj("uritorco", bm, [N0.mat_toon_albedo("uritorco", albedo)], colls["main"], smooth=True)


# --- el duende ------------------------------------------------------------------

def mat_duende(name, strength, cabeza=2.6, sosten=0.4, vida=0.55):
    """Luz aditiva (Transparent + Emission): se suma al cielo, no lo tapa.
    Por punto: "nace" (fase en la que la cabeza de la descarga pasa por ahi) y
    "alt" (0 abajo, 1 arriba, para el color). La propiedad "fase" del objeto
    avanza; cada punto se enciende cuando fase >= nace, con un pico en la
    cabeza (exp) y despues un brillo sostenido que se apaga de a poco."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    def attr(nm, kind="GEOMETRY"):
        a = nt.nodes.new("ShaderNodeAttribute")
        a.attribute_type = kind
        a.attribute_name = nm
        return a.outputs["Fac"]

    fase, nace, alt, brillo = attr("fase", "OBJECT"), attr("nace"), attr("alt"), attr("brillo", "OBJECT")
    dt = _m(nt, "SUBTRACT", fase, nace)
    vis = _m(nt, "GREATER_THAN", dt, 0.0)
    head = _m(nt, "EXPONENT", _m(nt, "DIVIDE", _m(nt, "MAXIMUM", dt, 0.0), -0.025))
    resto = _m(nt, "EXPONENT", _m(nt, "DIVIDE", _m(nt, "MAXIMUM", _m(nt, "SUBTRACT", dt, 0.05), 0.0), -vida))
    inten = _m(nt, "MULTIPLY", vis, _m(nt, "ADD", _m(nt, "MULTIPLY", head, cabeza),
                                       _m(nt, "MULTIPLY", resto, sosten)))
    # titileo: cada trazo late a su ritmo ("chispa" = su azar) mientras vive
    chispa = attr("chispa")
    late = _m(nt, "ADD", 0.78, _m(nt, "MULTIPLY", 0.22, _m(nt, "SINE", _m(nt, "ADD", _m(nt, "MULTIPLY", fase, 90.0),
                                                                           _m(nt, "MULTIPLY", chispa, 40.0)))))
    inten = _m(nt, "MULTIPLY", inten, late)
    inten = _m(nt, "MULTIPLY", _m(nt, "MULTIPLY", inten, brillo), strength)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, N0.lin("#4a3cff")       # puntas: azul violaceo
    els[1].position, els[1].color = 0.3, N0.lin("#a8123a")
    for pos, col in ((0.55, "#e0101e"), (0.9, "#ff3a2a")):       # cuerpo rojo profundo, arriba anaranjado
        el = els.new(pos)
        el.color = N0.lin(col)
    nt.links.new(alt, ramp.inputs["Fac"])
    sc = nt.nodes.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    nt.links.new(ramp.outputs["Color"], sc.inputs[0])
    nt.links.new(inten, sc.inputs["Scale"])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(sc.outputs[0], em.inputs["Color"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = False
    return mat


def mat_resplandor(name, color, strength, anillo=None, disco=False, cae_abajo=0.0, ruido=0.0):
    """Brillo difuso aditivo en degrade (nunca en capas): cae con la distancia
    al centro del objeto (coordenadas de objeto, -1..1). anillo=r: el maximo
    esta en un anillo de radio r (el halo del duende suele ser una rosquilla)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    # en la superficie de una esfera la distancia al centro vale siempre 1:
    # el degrade sale de cuanto mira la cara a la camara (centro brillante,
    # borde que se desvanece)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    if disco:
        # disco chato visto casi de canto: la cara de abajo es plana y brilla
        # pareja; el degrade va por el radio en el plano del disco
        d = _m(nt, "SQRT", _m(nt, "ADD", _m(nt, "MULTIPLY", sep.outputs[0], sep.outputs[0]),
                              _m(nt, "MULTIPLY", sep.outputs[1], sep.outputs[1])))
    else:
        lw = nt.nodes.new("ShaderNodeLayerWeight")
        lw.inputs["Blend"].default_value = 0.5
        d = lw.outputs["Facing"]
    if anillo:
        d = _m(nt, "MULTIPLY", _m(nt, "ABSOLUTE", _m(nt, "SUBTRACT", d, anillo)), 1 / max(1e-3, 1 - anillo))
    k = _m(nt, "POWER", _m(nt, "MAXIMUM", _m(nt, "SUBTRACT", 1.0, d), 0.0), 2.4 if disco else 3.0)
    if cae_abajo:
        # se apaga hacia abajo (z del objeto de 1 a -1)
        k = _m(nt, "MULTIPLY", k, _m(nt, "POWER", _m(nt, "MAXIMUM", _m(nt, "MULTIPLY",
                                                    _m(nt, "ADD", sep.outputs[2], 1.0), 0.5), 0.0), cae_abajo))
    if ruido:
        # un velo natural no es un anillo perfecto: el ruido lo rompe en jirones
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 2.6
        nz.inputs["Detail"].default_value = 4.0
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        k = _m(nt, "MULTIPLY", k, _m(nt, "POWER", _m(nt, "MAXIMUM", _m(nt, "SUBTRACT", nz.outputs["Fac"], 0.3), 0.0),
                                     ruido))
        k = _m(nt, "MULTIPLY", k, 4.0)
    br = nt.nodes.new("ShaderNodeAttribute")
    br.attribute_type = "OBJECT"
    br.attribute_name = "brillo"
    k = _m(nt, "MULTIPLY", _m(nt, "MULTIPLY", k, br.outputs["Fac"]), strength)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = N0.lin(color)
    nt.links.new(k, em.inputs["Strength"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = True
    return mat


def _ramas(rng, W, H, n_col):
    """Descargas: columnas que nacen arriba y bajan con un paseo al azar,
    abriendose en ramas que se afinan hasta un hilo, mas una capa de
    filamentos finisimos que cuelgan del cuerpo de abajo (el "flequillo" de
    las fotos). Cada trazo es (puntos, chispa): puntos = [(posicion, radio,
    nace)], chispa = azar del trazo para su titileo. Devuelve trazos y cuentas
    (puntos brillantes en los nudos)."""
    trazos, cuentas = [], []
    seg = H / 70.0
    vel = 0.55 / H                                 # fase por metro: cruza todo en ~0.55
    rmin = W * 0.00045                             # ~medio pixel a 1080 de ancho: un hilo

    def afinar(r0, u):
        return max(rmin, r0 * max(0.0, 1 - u) ** 1.35)

    def bajar(p, d, r, t0, largo, nivel, fil=False):
        pts = [(p.copy(), r, t0)]
        t = t0
        recorrido = 0.0
        while recorrido < largo and p.z > H * 0.02:
            d = (d + Vector((rng.gauss(0, 0.2 if fil else 0.16), rng.gauss(0, 0.08), rng.gauss(0, 0.05)))).normalized()
            if d.z > -0.6:                         # siempre baja
                d.z = -0.6
                d.normalize()
            p = p + d * seg * (0.6 if fil else 1.0)
            recorrido += seg * (0.6 if fil else 1.0)
            t += seg * vel * rng.uniform(0.85, 1.2)
            rr = afinar(r, recorrido / largo)
            pts.append((p.copy(), rr, t))
            if fil:
                continue
            if nivel < 4 and rng.random() < (0.17 if nivel == 0 else 0.11):
                lat = Vector((rng.choice((-1, 1)) * rng.uniform(0.35, 0.8), rng.gauss(0, 0.2), 0))
                dd = (d + lat).normalized()
                if nivel == 0 and rng.random() < 0.4:
                    cuentas.append((p.copy(), r * 1.2, t))
                bajar(p.copy(), dd, rr * 0.62, t, (largo - recorrido) * rng.uniform(0.35, 0.8), nivel + 1)
            # filamentos: hilos que se desprenden de la mitad de abajo del trazo
            if p.z < H * 0.6 and rng.random() < 0.22:
                bajar(p.copy(), (d + Vector((rng.gauss(0, 0.5), 0, 0))).normalized(), rmin * rng.uniform(1.4, 2.4),
                      t, H * rng.uniform(0.04, 0.16), nivel + 1, fil=True)
        trazos.append((pts, rng.random()))

    for i in range(n_col):
        central = i == 0                           # la columna del medio: la mas brillante
        x = 0.0 if central else rng.gauss(0, W * 0.2)
        top = H * (0.9 if central else rng.uniform(0.74, 0.86))
        p = Vector((x, rng.uniform(-W * 0.05, W * 0.05), top))
        t0 = 0.1 if central else rng.uniform(0.12, 0.3)
        largo = top - H * (0.03 if central else rng.uniform(0.02, 0.3))
        r = W * (0.0065 if central else rng.uniform(0.002, 0.0034))
        bajar(p, Vector((rng.gauss(0, 0.12), 0, -1)).normalized(), r, t0, largo, 0)
        # cabellera: trazos finos que suben desde el nacimiento y se abren
        for _ in range(rng.randint(3, 6)):
            q = p.copy()
            pts = [(q.copy(), r * 0.45, t0 + 0.02)]
            dd = Vector((rng.gauss(0, 0.35), 0, 1)).normalized()
            n = rng.randint(6, 14)
            for k in range(n):
                q = q + dd * seg * 0.8
                dd = (dd + Vector((rng.gauss(0, 0.22), 0, 0))).normalized()
                pts.append((q.copy(), afinar(r * 0.45, (k + 1) / n), t0 + 0.02 + k * seg * vel * 0.8))
            trazos.append((pts, rng.random()))
    return trazos, cuentas


def _tubos(name, trazos, H, k_radio, mat, coll, segs=6):
    bm = bmesh.new()
    lay_n = bm.verts.layers.float.new("nace")
    lay_a = bm.verts.layers.float.new("alt")
    lay_c = bm.verts.layers.float.new("chispa")
    for pts, chispa in trazos:
        if len(pts) < 2:
            continue
        rings = []
        for i, (p, r, t) in enumerate(pts):
            a = pts[max(0, i - 1)][0]
            b = pts[min(len(pts) - 1, i + 1)][0]
            tg = (b - a).normalized()
            ref = Vector((0, 1, 0)) if abs(tg.y) < 0.9 else Vector((1, 0, 0))
            u = tg.cross(ref).normalized()
            w = tg.cross(u).normalized()
            ring = []
            for s in range(segs):
                ang = 2 * math.pi * s / segs
                v = bm.verts.new(p + (u * math.cos(ang) + w * math.sin(ang)) * r * k_radio)
                v[lay_n] = t
                v[lay_a] = max(0.0, min(1.0, p.z / H))
                v[lay_c] = chispa
                ring.append(v)
            rings.append(ring)
        for ra, rb in zip(rings, rings[1:]):
            for s in range(segs):
                bm.faces.new((ra[s], ra[(s + 1) % segs], rb[(s + 1) % segs], rb[s]))
    ob = _mesh_obj(name, bm, [mat], coll)
    ob.visible_shadow = False
    return ob


def _un_duende(e, colls, nombre="duende", retardo=0.0, con_luz=True):
    """El duende rojo: halo en rosquilla que nace primero, campana difusa,
    columnas que bajan y se abren en tentaculos (rojo arriba, azul en las
    puntas), cuentas brillantes en los nudos. Todo luz aditiva, sin tinta."""
    az, dist = e.get("az", 61), e.get("dist", 30000)
    e0, e1 = e.get("elev", [13, 23.5])
    z0 = dist * math.tan(math.radians(e0))
    z1 = dist * math.tan(math.radians(e1))
    H = z1 - z0
    W = 2 * dist * math.tan(math.radians(e.get("ancho_deg", 14) / 2))
    rng = random.Random(e.get("seed", 3))

    root = bpy.data.objects.new(nombre, None)
    root.location = _dir(az) * dist + Vector((0, 0, z0))
    root.rotation_euler = (0, 0, -math.radians(az))      # x local: de costado a la vista
    link(root, colls["neon"])

    trazos, cuentas = _ramas(rng, W, H, e.get("columnas", 24))
    nucleo = _tubos(f"{nombre}_nucleo", trazos, H, 1.0, mat_duende(f"{nombre}_nucleo", e.get("fuerza", 3.2), cabeza=1.6),
                    colls["neon"])
    aura = _tubos(f"{nombre}_aura", trazos, H, 4.5, mat_duende(f"{nombre}_aura", e.get("fuerza_aura", 0.7),
                                                             cabeza=1.0, sosten=0.55), colls["neon"])
    bm = bmesh.new()
    lay_n = bm.verts.layers.float.new("nace")
    lay_a = bm.verts.layers.float.new("alt")
    for p, r, t in cuentas:
        out = bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=r * 1.1)
        for v in out["verts"]:
            v.co += p
            v[lay_n] = t
            v[lay_a] = max(0.0, min(1.0, p.z / H))
    perlas = _mesh_obj(f"{nombre}_cuentas", bm, [mat_duende(f"{nombre}_cuentas", e.get("fuerza", 3.2) * 1.6,
                                                          cabeza=3.0, sosten=0.7, vida=0.9)], colls["neon"])
    perlas.visible_shadow = False
    for ob in (nucleo, aura, perlas):
        ob.parent = root

    # halo: rosquilla chata arriba de todo; nace primero y se va enseguida
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0)
    halo = _mesh_obj(f"{nombre}_halo", bm, [mat_resplandor(f"{nombre}_halo", "#ff4a5e", e.get("fuerza_halo", 0.0),
                                                        anillo=0.45, disco=True, ruido=1.6)], colls["neon"])
    for p in halo.data.polygons:
        p.use_smooth = True
    halo.parent = root
    halo.location = (0, 0, H * 1.02)
    halo.scale = (W * 0.55, W * 0.55, H * 0.04)
    # campana: brillo rojo difuso donde nacen las columnas (la "medusa")
    # la campana como forma propia se leia pegada al cielo (contorno limpio,
    # color parejo): el resplandor alrededor lo hace el post a partir de la
    # forma real de los tentaculos (post.resplandor). Queda solo si se pide.
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0)
    campana = _mesh_obj(f"{nombre}_campana", bm, [mat_resplandor(f"{nombre}_campana", "#ff2238",
                                                              e.get("fuerza_campana", 0.0), cae_abajo=1.5)], colls["neon"])
    for p in campana.data.polygons:
        p.use_smooth = True
    campana.parent = root
    campana.location = (0, 0, H * 0.8)
    campana.scale = (W * 0.42, W * 0.25, H * 0.24)

    fase0 = e.get("fase", [[1, 1.0]])
    if retardo:
        # el miembro del grupo se enciende "retardo" de fase despues; mientras
        # el original esta en hit-stop (fase 0) o en el golpe (fase 1) lo sigue
        def _f0(f):
            ks = sorted(fase0)
            if f <= ks[0][0]:
                return ks[0][1]
            for (fa, va), (fb, vb) in zip(ks, ks[1:]):
                if fa <= f <= fb:
                    return va + (vb - va) * (f - fa) / max(1, fb - fa)
            return ks[-1][1]
        fase = [[f, (_f0(f) if _f0(f) >= 0.999 else max(0.0, _f0(f) - retardo))]
                for f in range(1, ctx.CFG["frames"] + 1)]
    else:
        fase = fase0
    for ob in (nucleo, aura, perlas):
        _prop_keys(ob, "fase", fase, interp=e.get("interp", "LINEAR"))
        _prop_keys(ob, "brillo", e.get("brillo"), interp="LINEAR")

    # el halo y la campana siguen a la fase: se evalua la curva de fase en
    # cada frame y se escribe su brillo
    def fase_en(f):
        ks = sorted(fase)
        if f <= ks[0][0]:
            return ks[0][1]
        for (fa, va), (fb, vb) in zip(ks, ks[1:]):
            if fa <= f <= fb:
                return va + (vb - va) * (f - fa) / max(1, fb - fa)
        return ks[-1][1]

    # el brillo se interpola entre sus claves (con el diccionario de claves,
    # un "brillo 0" en el cuadro 1 dejaba la luz roja prendida el resto del plano)
    brk = sorted(e.get("brillo") or [])

    def brillo_en(f):
        if not brk:
            return 1.0
        if f <= brk[0][0]:
            return brk[0][1]
        for (fa, va), (fb, vb) in zip(brk, brk[1:]):
            if fa <= f <= fb:
                return va + (vb - va) * (f - fa) / max(1, fb - fa)
        return brk[-1][1]

    frames = ctx.CFG["frames"]
    hk, ck = [], []
    for f in range(1, frames + 1):
        x = fase_en(f)
        g = brillo_en(f)
        hk.append((f, g * max(0.0, min(1.0, x / 0.04)) * math.exp(-max(0.0, x - 0.05) / 0.06)))
        ck.append((f, g * max(0.0, min(1.0, (x - 0.12) / 0.25)) * (0.7 + 0.3 * math.exp(-max(0, x - 0.5) / 0.4))))
    _prop_keys(halo, "brillo", hk)
    _prop_keys(campana, "brillo", ck)

    # la luz del duende: un sol rojo que viene de donde esta (de atras del
    # cerro, un poco de arriba). Sin sombra: pinta la cresta y los bordes de lo
    # que mira hacia el duende. Sigue el brillo de la campana.
    L = e.get("luz", {})
    if con_luz and L.get("energia", 0) > 0:
        el = math.radians((e0 + e1) / 2)
        llega = -(_dir(az) * math.cos(el) + Vector((0, 0, math.sin(el))))
        li = bpy.data.lights.new(f"luz_{nombre}", "SUN")
        li.color = N0.lin(L.get("color", "#ff2a3a"))[:3]
        li.use_shadow = False
        li.angle = math.radians(8)
        lo = bpy.data.objects.new(f"luz_{nombre}", li)
        lo.rotation_euler = llega.to_track_quat("-Z", "Y").to_euler()
        link(lo, colls["lights"])
        for f, v in ck:
            li.energy = L["energia"] * v
            li.keyframe_insert("energy", frame=f)
    return root


def build_duende(e, colls):
    """Un duende o un grupo ("grupo": [{"daz": desvio de azimut, "ancho_deg",
    "elev", "seed", "retardo", "fuerza"...}]). Sobre una tormenta grande los
    duendes casi nunca salen solos: se encienden en cadena, uno al lado del
    otro, en milisegundos. El primero del grupo es el central y lleva la luz."""
    grupo = e.get("grupo")
    if not grupo:
        return _un_duende(e, colls)
    raices = []
    for i, m in enumerate(grupo):
        p = {**e, **m}
        p["az"] = e.get("az", 61) + m.get("daz", 0.0)
        p.pop("grupo", None)
        raices.append(_un_duende(p, colls, nombre="duende" if i == 0 else f"duende{i}",
                                 retardo=m.get("retardo", 0.0), con_luz=(i == 0)))
    return raices[0]


def build_tormenta(e, colls):
    """La tormenta lejana, abajo del horizonte detras del cerro: un resplandor
    chato (disco aditivo) que se enciende con cada rayo. Un rayo = un golpe de
    1 cuadro y una cola de 2-3; algunos dobles. "rayos": frames; "dispara":
    el rayo que dispara al duende (el mas fuerte)."""
    az, dist = e.get("az", 61), e.get("dist", 30000)
    el = math.radians(e.get("elev", 6.5))
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=12, radius=1.0)
    ob = _mesh_obj("tormenta", bm, [mat_resplandor("tormenta", e.get("color", "#c9b8ff"),
                                                   e.get("fuerza", 1.6), disco=True)], colls["neon"])
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.visible_shadow = False
    ob.location = _dir(az) * dist + Vector((0, 0, dist * math.tan(el)))
    ob.rotation_euler = (math.radians(90), 0, -math.radians(az))   # disco de frente a la vista
    W = 2 * dist * math.tan(math.radians(e.get("ancho_deg", 30) / 2))
    ob.scale = (W / 2, dist * math.tan(math.radians(e.get("alto_deg", 7))) / 2, 1)
    frames = ctx.CFG["frames"]
    val = [0.0] * (frames + 1)
    rng = random.Random(e.get("seed", 5))
    golpes = [(f, rng.uniform(0.35, 0.7)) for f in e.get("rayos", [])]
    if e.get("dispara"):
        golpes.append((e["dispara"], 1.0))
    for f0, a in golpes:
        for k, g in enumerate((1.0, 0.45, 0.2, 0.08)):
            if f0 + k <= frames:
                val[f0 + k] = max(val[f0 + k], a * g)
        if rng.random() < 0.35 and f0 + 3 <= frames:      # rayo doble
            val[f0 + 3] = max(val[f0 + 3], a * 0.6)
    _prop_keys(ob, "brillo", [(f, val[f]) for f in range(1, frames + 1)], interp="CONSTANT")
    return ob


# --- la calle techada ---------------------------------------------------------
# Marco local de la calle: +y = hacia el Uritorco (azimut az), +x = a la derecha.
# El observador (origen) esta en la calle; el arco a "arco" metros.

def _local(az):
    a = math.radians(az)
    ex = Vector((math.cos(a), -math.sin(a), 0))
    ey = Vector((math.sin(a), math.cos(a), 0))
    return ex, ey


def a_mundo(az, x, y, z):
    ex, ey = _local(az)
    return ex * x + ey * y + Vector((0, 0, z))


def _texto3d(name, body, size, mat, coll, parent, loc, font=None):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    f = font or ctx.FONT
    if f:
        try:
            cu.font = bpy.data.fonts.load(f, check_existing=True)
        except RuntimeError:
            pass
    cu.size = size
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = 0.0                 # plano y de una cara: desde atras del arco no se lee al reves
    ob = bpy.data.objects.new(name, cu)
    ob.data.materials.append(mat)
    mat.use_backface_culling = True
    ob.parent = parent
    ob.location = loc
    ob.rotation_euler = (math.radians(90), 0, 0)      # el texto mira a -y local
    link(ob, coll)
    return ob


def build_calle(e, colls):
    """La calle techada de Capilla del Monte (foto de referencia): fachadas
    blancas y crema de uno y dos pisos con balcones, toldos y vidrieras, una
    naranja; el arco de madera con borde fileteado y el cartel; la calle
    techada detras con sus luces; cables cruzando, faroles y la copa de un
    arbol en primer plano."""
    az = e.get("az", 61)
    A = e.get("arco", 40.0)
    rng = random.Random(e.get("seed", 12))
    root = bpy.data.objects.new("calle", None)
    root.rotation_euler = (0, 0, -math.radians(az))
    link(root, colls["main"])
    T = N0.mat_toon
    asfalto = T("asfalto", e.get("asfalto", "#2a2830"))
    vereda = T("vereda", "#4a4650")
    blancos = [T(f"fachada_{i}", c) for i, c in enumerate(e.get("fachadas", ["#e8e2d6", "#d9d1c3", "#cfc4b2", "#e4dccb", "#d98a4e"]))]
    vano = T("vano_oscuro", "#1a1720")
    baranda = T("baranda", "#2a2630")
    toldos = [T(f"toldo_{i}", c) for i, c in enumerate(("#b8432e", "#2f6f6a", "#c9a35a", "#4a5a8a"))]
    vidriera = N0.mat_neon("vidriera", e.get("vidriera", "#ffcf8a"), 0.9)
    vidriera_fria = N0.mat_neon("vidriera_fria", "#bfe0ff", 0.6)

    bm = bmesh.new()
    N0._bm_box(bm, (0, 50, -0.05), (8, 160, 0.1), 0)
    for sx in (-1, 1):
        N0._bm_box(bm, (sx * 5, 50, 0.07), (2, 160, 0.14), 1)
    _mesh_obj("calle_piso", bm, [asfalto, vereda], colls["main"]).parent = root

    # fachadas, de los dos lados
    bm = bmesh.new()
    bm_luz = bmesh.new()
    bm_fria = bmesh.new()
    nb = len(blancos)
    for sx in (-1, 1):
        y = -12.0
        while y < 120:
            w = rng.uniform(6, 12)
            pisos = rng.choice((1, 2, 2, 2))
            h = 3.6 * pisos + rng.uniform(0.2, 1.0)
            mi = rng.randrange(nb - 1) if rng.random() > 0.12 else nb - 1      # alguna naranja
            x0 = sx * 6.0
            N0._bm_box(bm, (x0 + sx * 4, y + w / 2, h / 2), (8, w - 0.15, h), mi)
            N0._bm_box(bm, (x0 + sx * 0.15, y + w / 2, h + 0.15), (0.5, w, 0.3), mi)          # cornisa
            # planta baja: vidriera (calida) o puerta
            for k in range(max(1, int(w // 4))):
                yy = y + 1.2 + k * 4 + rng.uniform(0, 0.6)
                if yy + 2.6 > y + w:
                    break
                target = bm_luz if rng.random() < 0.7 else bm_fria
                N0._bm_box(target, (x0 - sx * 0.02, yy + 1.3, 1.55), (0.05, 2.4, 2.1))
                N0._bm_box(bm, (x0 - sx * 0.05, yy + 1.3, 2.75), (0.12, 2.6, 0.18), nb + 1)
                if rng.random() < 0.6:                                               # toldo
                    q = [(x0, yy, 3.0), (x0, yy + 2.6, 3.0), (x0 - sx * 1.3, yy + 2.6, 2.55), (x0 - sx * 1.3, yy, 2.55)]
                    N0._bm_quad_slab(bm, q if sx > 0 else q[::-1], 0.04, nb + 2 + rng.randrange(4))
            if pisos == 2:
                for k in range(max(1, int(w // 3.2))):
                    yy = y + 1.0 + k * 3.2
                    if yy + 1.6 > y + w:
                        break
                    lit = rng.random() < 0.35
                    N0._bm_box(bm_luz if lit else bm, (x0 - sx * 0.02, yy + 0.8, 5.4), (0.05, 1.2, 1.6), nb)
                    if rng.random() < 0.5:                                           # balcon
                        N0._bm_box(bm, (x0 - sx * 0.55, yy + 0.8, 4.35), (1.1, 1.8, 0.12), mi)
                        N0._bm_box(bm, (x0 - sx * 1.07, yy + 0.8, 4.85), (0.05, 1.8, 0.9), nb + 1)
            y += w
    mats = blancos + [vano, baranda] + toldos
    _mesh_obj("fachadas", bm, mats, colls["main"]).parent = root
    _mesh_obj("vidrieras", bm_luz, [vidriera], colls["neon"]).parent = root
    _mesh_obj("vidrieras_frias", bm_fria, [vidriera_fria], colls["neon"]).parent = root

    # la calle techada: techo sobre la calle detras del arco, con luces colgando
    bm = bmesh.new()
    N0._bm_box(bm, (0, A + 40, 4.45), (12, 80, 0.15), 0)
    for k in range(9):
        N0._bm_box(bm, (0, A + 3 + k * 9, 4.2), (12, 0.25, 0.35), 0)
    _mesh_obj("techado", bm, [T("techado", "#3a3640")], colls["main"]).parent = root
    bm = bmesh.new()
    for k in range(16):
        for xx in (-2.2, 2.2):
            N0._bm_cyl(bm, (xx, A + 4 + k * 4.8, 4.05), 0.35, 0.12, segs=12)
    _mesh_obj("techado_luces", bm, [N0.mat_neon("techado_luz", "#ffd9a0", 1.6)], colls["neon"]).parent = root
    for k in range(4):
        li = bpy.data.lights.new(f"techado_luz{k}", "POINT")
        li.color = N0.lin("#ffc98a")[:3]
        li.energy = e.get("luz_techado", 900)
        li.use_shadow = False
        li.shadow_soft_size = 3
        lo = bpy.data.objects.new(f"techado_luz{k}", li)
        lo.location = a_mundo(az, 0, A + 6 + k * 14, 3.6)
        link(lo, colls["lights"])

    # el arco: dos pilares y el panel de madera con la parte de arriba curva
    madera = T("arco_madera", e.get("madera", "#7a4f30"))
    oro = N0.mat_neon("arco_filete", "#e2b867", 0.55)
    bm = bmesh.new()
    for sx in (-1, 1):
        N0._bm_box(bm, (sx * 5.0, A, 2.3), (0.45, 0.45, 4.6), 0)
    n = 24
    Wp, z0, zs, zc = 10.6, 4.4, 6.1, 7.0
    front, back = [], []
    for i in range(n + 1):
        u = i / n
        x = -Wp / 2 + Wp * u
        ztop = zs + (zc - zs) * math.sin(math.pi * u)
        for yy, lst in ((A - 0.2, front), (A + 0.2, back)):
            lst.append((bm.verts.new((x, yy, z0)), bm.verts.new((x, yy, ztop))))
    for lst, flip in ((front, False), (back, True)):
        for i in range(n):
            f = [lst[i][0], lst[i + 1][0], lst[i + 1][1], lst[i][1]]
            bm.faces.new(f[::-1] if flip else f)
    for i in range(n):
        bm.faces.new([front[i][1], front[i + 1][1], back[i + 1][1], back[i][1]])
        bm.faces.new([front[i][0], back[i][0], back[i + 1][0], front[i + 1][0]])
    for lst_i in (0, n):
        bm.faces.new([front[lst_i][0], front[lst_i][1], back[lst_i][1], back[lst_i][0]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    arco = _mesh_obj("arco", bm, [madera], colls["main"])
    arco.parent = root
    # filete: borde dorado siguiendo la curva y volutas a los costados
    bm = bmesh.new()
    borde = [Vector((-Wp / 2 + Wp * i / n + 0, A - 0.24, zs + (zc - zs) * math.sin(math.pi * i / n) - 0.18))
             for i in range(n + 1)]
    N0._bm_tube(bm, borde, 0.05, 6)
    N0._bm_tube(bm, [Vector((-Wp / 2 + 0.2, A - 0.24, z0 + 0.18)), Vector((Wp / 2 - 0.2, A - 0.24, z0 + 0.18))], 0.05, 6)
    for sx in (-1, 1):
        for cz, r0 in ((5.4, 0.5), (5.05, 0.3)):
            c = Vector((sx * (Wp / 2 - 1.1), A - 0.24, cz))
            N0._bm_tube(bm, N0._espiral(c, (-sx, 0, 0), (0, 0, 1), r0, turns=1.6), 0.04, 6)
    _mesh_obj("arco_filete", bm, [oro], colls["neon"]).parent = root
    letras = N0.mat_neon("cartel_letras", "#fff6ea", 1.6)
    _texto3d("cartel_1", e.get("cartel", "Capilla del Monte"), 0.95, letras, colls["neon"], root, (0, A - 0.25, 5.85))
    _texto3d("cartel_2", e.get("cartel2", "PUEBLO URITORCO"), 0.36, letras, colls["neon"], root, (0, A - 0.25, 5.05))

    # cables que cruzan la calle (silueta contra el cielo, sin tinta)
    bm = bmesh.new()
    for yy, za, zb in ((6, 7.5, 6.8), (14, 8.2, 7.9), (22, 7.0, 7.6), (31, 6.4, 6.9), (52, 7.8, 8.3), (8, 6.2, 9.0)):
        pa, pb = Vector((-6.5, yy, za)), Vector((6.5, yy + rng.uniform(-3, 3), zb))
        N0._bm_tube(bm, N0._cable(pa, pb, 0.6, 10), 0.035, 5)
    for xx in (-5.8, 5.8):
        N0._bm_tube(bm, N0._cable(Vector((xx, -12, 7.6)), Vector((xx, 60, 7.9)), 0.9, 24), 0.03, 5)
    hil = _mesh_obj("cables", bm, [N0.mat_flat("cables", "#0e0c14")], colls["veil"])
    hil.parent = root
    hil.visible_shadow = False

    # faroles en las veredas
    bm = bmesh.new()
    bm_l = bmesh.new()
    for k, yy in enumerate((10, 26, 62)):
        sx = -1 if k % 2 else 1
        N0._bm_box(bm, (sx * 5.6, yy, 2.4), (0.12, 0.12, 4.8), 0)
        N0._bm_box(bm, (sx * 5.0, yy, 4.75), (1.2, 0.1, 0.1), 0)
        N0._bm_box(bm_l, (sx * 4.5, yy, 4.6), (0.45, 0.3, 0.2))
        li = bpy.data.lights.new(f"farol{k}", "POINT")
        li.color = N0.lin("#ffd29a")[:3]
        li.energy = e.get("luz_farol", 600)
        li.use_shadow = False
        lo = bpy.data.objects.new(f"farol{k}", li)
        lo.location = a_mundo(az, sx * 4.5, yy, 4.3)
        link(lo, colls["lights"])
    _mesh_obj("faroles", bm, [baranda], colls["main"]).parent = root
    _mesh_obj("faroles_luz", bm_l, [N0.mat_neon("farol_luz", "#ffe2b0", 1.8)], colls["neon"]).parent = root

    # la copa de un arbol en primer plano (arriba a la derecha, como en la foto)
    if e.get("arbol", True):
        bm = bmesh.new()
        for _ in range(26):
            c = Vector((rng.uniform(3.5, 7.5), rng.uniform(5, 9), rng.uniform(6.2, 8.6)))
            out = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=rng.uniform(0.6, 1.2))
            for v in out["verts"]:
                v.co += c
        N0._bm_box(bm, (6.5, 7, 3.2), (0.35, 0.35, 6.4))
        _mesh_obj("arbol", bm, [T("arbol", "#1d2a22")], colls["main"]).parent = root
    return root


def mat_dron_noche(name, color, luz=1.0):
    """Los drones de noche: casi silueta (tono oscuro azulado), con un filo de
    luz roja del lado del duende y un tono medio tenue de los faroles."""
    D = ctx.CFG.get("duende", {})
    az = D.get("az", 61)
    rim = ctx.CFG.get("rim_drones", 1.0)
    rim_color = ctx.CFG.get("rim_color", "#ff3a40")
    if ctx.CFG.get("rim_desde") == "pueblo":
        # sin duende, la luz que hay es la de los faroles: del lado del pueblo y de abajo
        hacia = -_dir(az) * math.cos(math.radians(25)) - Vector((0, 0, math.sin(math.radians(25))))
    else:
        el = math.radians(sum(D.get("elev", [12, 24])) / 2)
        hacia = _dir(az) * math.cos(el) + Vector((0, 0, math.sin(el)))
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    lum = N0._dot(nt, geo.outputs["Normal"], hacia)
    arriba = N0._dot(nt, geo.outputs["Normal"], (0, 0, 1))
    base = _mix(nt, 1.0, color, ctx.CFG.get("drones_sombra", "#56527a"), "MULTIPLY")
    base = _mix(nt, _m(nt, "MULTIPLY", _m(nt, "GREATER_THAN", arriba, 0.6), 0.35), base,
                _mix(nt, 1.0, color, "#8a7aa0", "MULTIPLY"))
    # los drones son cajas: no hay curvatura donde aparezca un filo. Se
    # encienden las caras que miran hacia el duende (la tapa, los cantos de las
    # alas), que de espaldas a camara dibujan el contorno en rojo
    # tres tonos: sombra azulada, rojo medio que conserva el color de cada
    # pieza, y brillo en lo que mira de lleno al duende
    medio = _mix(nt, 1.0, rim_color, _mix(nt, 0.3, color, "#ffffff"), "MULTIPLY")
    medio = _mix(nt, 0.45, base, medio)
    # el filo se anima por objeto (propiedad "rim" de cada pieza del dron): se
    # apaga en el mismo cuadro que el duende
    ra = nt.nodes.new("ShaderNodeAttribute")
    ra.attribute_type = "OBJECT"
    ra.attribute_name = "rim"
    rim_k = _m(nt, "MULTIPLY", ra.outputs["Fac"], rim)
    k1 = _m(nt, "MULTIPLY", _m(nt, "GREATER_THAN", lum, 0.12), rim_k)
    k2 = _m(nt, "MULTIPLY", _m(nt, "GREATER_THAN", lum, 0.7), _m(nt, "MULTIPLY", rim_k, 0.35))
    col = _mix(nt, k1, base, medio)
    col = _mix(nt, k2, col, rim_color, "ADD")
    N0._emit_out(nt, N0._fog(nt, col))
    return mat


def _rim_keys(root, e):
    """"rim": [[frame, 0..1]] sobre todas las piezas del dron (si no, 1)."""
    for ob in [root] + list(root.children_recursive):
        _prop_keys(ob, "rim", e.get("rim"), default=1.0, interp="LINEAR")


def build_nyx(e, colls):
    """Nyx de NODO 0 con el material de noche."""
    N0.mat_dron = mat_dron_noche
    root = N0.build_nyx(e, colls)
    _rim_keys(root, e)
    return root


def build_vesper(e, colls):
    N0.mat_dron = mat_dron_noche
    root = N0.build_vesper(e, colls)
    _rim_keys(root, e)
    return root


def build_reflejo(e, colls):
    """El duende reflejado en las lentes de Nyx: hilos rojos que cuelgan dentro
    de cada lente (espejados: lo de arriba queda arriba) y un disco rojo tenue;
    siguen el brillo del duende. Ademas, las pupilas se dilatan ("pupila")."""
    root = bpy.data.objects.get("nyx")
    if root is None:
        return None
    rng = random.Random(e.get("seed", 21))
    bm = bmesh.new()
    for sx in (-1, 1):
        c = Vector((sx * 0.075, -0.2165, 0.025))
        for k in range(e.get("hilos", 9)):
            x0 = rng.uniform(-0.03, 0.03)
            p = c + Vector((x0, 0, 0.026 - abs(x0) * 0.3))
            pts = [p.copy()]
            for _ in range(7):
                p = p + Vector((rng.gauss(0, 0.003), 0, -rng.uniform(0.005, 0.009)))
                if (p - c).length > 0.042:
                    break
                pts.append(p.copy())
            if len(pts) > 1:
                N0._bm_tube(bm, pts, 0.0011, 4)
    hilos = _mesh_obj("nyx_reflejo", bm, [N0.mat_neon("nyx_reflejo", "#ff2a3a", 2.2, fog=False)], colls["neon"],
                      parent=root)
    bm = bmesh.new()
    for sx in (-1, 1):
        N0._bm_cyl(bm, (sx * 0.075, -0.2128, 0.025), 0.044, 0.002, axis="y", segs=24)
    disco = _mesh_obj("nyx_reflejo_disco", bm, [N0.mat_neon("nyx_reflejo_disco", "#7a0a1a", 1.0, fog=False)],
                      colls["neon"], parent=root)
    for ob in (hilos, disco):
        for f, v in e.get("brillo", [[1, 1.0]]):
            N0.key_power(ob, f, v)
    # las pupilas de NODO 0 son un solo objeto con el origen en el centro del
    # dron: escalarlo las correria. Se rehacen, una por lente, con el origen en
    # su centro, y se dilatan en el lugar
    if e.get("pupila"):
        viejo = bpy.data.objects.get("nyx_pupilas")
        mat = viejo.data.materials[0] if viejo else N0.mat_flat("nyx_pupila", N0.TINTA)
        if viejo:
            bpy.data.objects.remove(viejo, do_unlink=True)
        for sx in (-1, 1):
            bm = bmesh.new()
            N0._bm_box(bm, (0, 0, 0), (0.026, 0.006, 0.026))
            p = _mesh_obj(f"nyx_pupila_{sx}", bm, [mat], colls["neon"], parent=root)
            p.location = (sx * 0.075, -0.2115, 0.025)
            for f, v in e["pupila"]:
                p.scale = (v, 1, v)
                p.keyframe_insert("scale", frame=f)
            set_interp(p, "BEZIER")
    return hilos


def build_registro(e, colls):
    """El registro que proyecta Vesper: placa fileteada con la linea de tiempo
    de los chasquidos (barras herrumbre) y, medio segundo despues de algunos,
    la marca roja de un duende. Se ve el ritmo y se ve la regla: el duende
    viene siempre detras del chasquido. Mira a camara ("mira").

        "registro": {"at": [x, y, z], "mira": [x, y, z], "desde": 20,
                     "golpes": [0, 1, 2, 3.5, 4.5, 5.5, 7], "duendes": [1, 3.5, 5.5]}
    """
    W, Hh = e.get("ancho", 1.1), e.get("alto", 0.55)
    piv = bpy.data.objects.new("registro", None)
    link(piv, colls["neon"])
    N0._orientar(piv, e["at"], e["mira"])
    f0 = e.get("desde", 20)
    bm = bmesh.new()
    N0._bm_box(bm, (0, 0, -0.004), (W, Hh, 0.004))
    placa = _mesh_obj("registro_placa", bm, [N0.mat_tint("registro_placa", "#100a12", 0.72)], N0._oclusion(colls), parent=piv)
    placa.visible_shadow = False
    bm = bmesh.new()
    N0._marco_filete(bm, W, Hh, filacteria=False)
    filete = _mesh_obj("registro_filete", bm, [N0.mat_neon("registro_filete", "#ffb000", 1.1, fog=False)], colls["neon"], parent=piv)
    golpes = e.get("golpes", [0, 1, 2, 3.5, 4.5, 5.5, 7])
    span = max(golpes) + 1.0
    x0, x1 = -W / 2 + 0.1, W / 2 - 0.1
    X = lambda t: x0 + (x1 - x0) * t / span
    bm = bmesh.new()
    N0._bm_tube(bm, [Vector((x0, -0.08, 0.006)), Vector((x1, -0.08, 0.006))], 0.004, 4)
    eje = _mesh_obj("registro_eje", bm, [N0.mat_neon("registro_eje", "#ffb000", 0.8, fog=False)], colls["neon"], parent=piv)
    herr = N0.mat_neon("registro_golpe", "#ff5a1c", 1.8, fog=False)
    rojo = N0.mat_neon("registro_duende", "#ff2a3a", 2.4, fog=False)
    objs = [placa, filete, eje]
    for ob in objs:
        _sc(ob, [(1, 0.001), (f0, 0.001), (f0 + 2, 1.0)])
    f = f0 + 3
    for k, t in enumerate(golpes):
        bm = bmesh.new()
        N0._bm_box(bm, (X(t), -0.08 + 0.07, 0.006), (0.012, 0.14, 0.004))
        ob = _mesh_obj(f"registro_g{k}", bm, [herr], colls["neon"], parent=piv)
        _sc(ob, [(1, 0.001), (f, 0.001), (f + 1, 1.0)])
        if t in e.get("duendes", []):
            bm = bmesh.new()
            N0._bm_box(bm, (X(t + 0.5), 0.12, 0.006), (0.03, 0.03, 0.004))
            N0._bm_tube(bm, [Vector((X(t), 0.0, 0.006)), Vector((X(t + 0.5), 0.1, 0.006))], 0.003, 4)
            d = _mesh_obj(f"registro_d{k}", bm, [rojo], colls["neon"], parent=piv)
            _sc(d, [(1, 0.001), (f + 2, 0.001), (f + 3, 1.0)])
        f += 2
    return piv


def _sc(ob, keys):
    for f, v in keys:
        ob.scale = (v, v, v)
        ob.keyframe_insert("scale", frame=f)
    set_interp(ob, "CONSTANT")


def build_mapa(e, colls):
    """El mapa de Vesper de NODO 0, con los puntos de este episodio."""
    N0.RUTAS.clear()
    return N0.build_mapa(e, colls)


PIEZAS = [
    ("uritorco", build_uritorco),
    ("tormenta", build_tormenta),
    ("duende", build_duende),
    ("calle", build_calle),
    ("nyx", build_nyx),
    ("vesper", build_vesper),
    ("reflejo", build_reflejo),
    ("registro", build_registro),
    ("mapa", build_mapa),
]
