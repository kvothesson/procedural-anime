"""Piezas de EL FILETEADOR: chapa acanalada de conventillo que recupera el
color, filete porteno que se pinta trazo por trazo y el pincel de filetear
(el motivo y sus horarios, sin Blender, en filete.py).

Todo el filete sale de un solo motivo (motivo()): una lista de piezas de
pintura, cada una con su forma 2D sobre la pared, su capa y su horario
[f0, f1]. De ahi salen la geometria, el avance del pincel y los cuadros en
que cada punto de la chapa recupera el color.

Pared: plano XZ (X a la derecha, Z arriba), la camara mira hacia +Y. La chapa
tiene canaletas horizontales: y = surf(z). La pintura copia esa forma, unos
milimetros por delante, asi el sol marca las canaletas tambien sobre el filete.
"""

import importlib.util
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from piezas import ctx
from piezas.base import lin, link, linearize
from piezas.materiales import _emit_out, _fog, _toon_light

sys.path.insert(0, str(Path(__file__).resolve().parent))
import caminito  # noqa: E402  (conventillos, gris y barrido de la calle)
from filete import (AMP, CAPA, LUZ, PALETA, PASO, _ancho, _cabeza, _normales,  # noqa: E402
                    _resample, motivo, surf)


# ------------------------------------------------------------------ mallas

def _malla(name, verts, faces, attrs, coll):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    for k, vals in attrs.items():
        at = me.attributes.new(k, "FLOAT", "POINT")
        at.data.foreach_set("value", np.asarray(vals, np.float32))
    me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    link(ob, coll)
    return ob


def _cinta(name, pts, w, w_ini, w_fin, eps, corrido, coll, cols=3, lado=0, ref=None):
    """Cinta de pintura sobre la chapa. 'rev' = fraccion del recorrido (0 en
    el arranque del trazo): el shader la muestra hasta donde va el pincel."""
    p, s = _resample(pts, 0.003)
    _, nr = _normales(p)
    # lado/ref: el borde de otra pincelada (contorno de la banda o del tallo)
    off = corrido + (lado * _ancho(s, **ref) / 2 if ref else 0.0)
    p = p + nr * np.asarray(off).reshape(-1, 1)
    k = s / max(s[-1], 1e-9)
    ww = _ancho(s, w, w_ini, w_fin)
    verts, rev = [], []
    for i in range(len(p)):
        for c in range(cols + 1):
            q = p[i] + nr[i] * (c / cols - 0.5) * ww[i]
            verts.append((q[0], float(surf(q[1])) - eps, q[1]))
            rev.append(k[i])
    faces = []
    for i in range(len(p) - 1):
        for c in range(cols):
            a = i * (cols + 1) + c
            b = a + cols + 1
            faces.append((a, a + 1, b + 1, b))
    return _malla(name, verts, faces, {"rev": rev}, coll), p, k


def _relleno(name, poly, eps, coll, eje=None):
    """Poligono relleno, cortado cada 8 mm en Z para que siga las canaletas.
    'rev' = avance a lo largo de 'eje' (base -> punta)."""
    poly = np.asarray(poly, float)
    bm = bmesh.new()
    vs = [bm.verts.new((x, 0.0, z)) for x, z in poly]
    bm.faces.new(vs)
    z0, z1 = poly[:, 1].min(), poly[:, 1].max()
    for z in np.arange(z0 + 0.004, z1, 0.008):
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, z), plane_no=(0, 0, 1))
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    if eje is None:
        eje = (poly[0], poly[len(poly) // 2])
    a, b = np.asarray(eje[0]), np.asarray(eje[1])
    d = b - a
    Ld = float(np.dot(d, d)) or 1.0
    bm.verts.index_update()
    verts, rev = [], []
    for v in bm.verts:
        x, z = v.co.x, v.co.z
        verts.append((x, float(surf(z)) - eps, z))
        rev.append(float(np.clip(np.dot((x, z) - a, d) / Ld, 0, 1)))
    bm.verts.index_update()
    faces = [[v.index for v in fc.verts] for fc in bm.faces]
    bm.free()
    return _malla(name, verts, faces, {"rev": rev}, coll)


# ------------------------------------------------------------------ materiales

def _attr(nt, name, kind):
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_type = kind
    at.attribute_name = name
    return at.outputs["Fac"]


def _corte(nt):
    """1 donde el barrido todavia no paso: x del mundo < "corte" del objeto,
    con el borde en bloques de 4 cm (compresion). Sin "corte" (1e4), todo 1."""
    n = nt.nodes
    geo = n.new("ShaderNodeNewGeometry")
    snap = n.new("ShaderNodeVectorMath")
    snap.operation = "SNAP"
    snap.inputs[1].default_value = (0.04, 0.04, 0.04)
    nt.links.new(geo.outputs["Position"], snap.inputs[0])
    nz = n.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 9.0
    nt.links.new(snap.outputs[0], nz.inputs["Vector"])
    mr = n.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.3
    mr.inputs["From Max"].default_value = 0.7
    mr.inputs["To Min"].default_value = -0.08
    mr.inputs["To Max"].default_value = 0.08
    nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
    sep = n.new("ShaderNodeSeparateXYZ")
    nt.links.new(snap.outputs[0], sep.inputs[0])
    add = n.new("ShaderNodeMath")
    add.operation = "ADD"
    nt.links.new(sep.outputs["X"], add.inputs[0])
    nt.links.new(mr.outputs["Result"], add.inputs[1])
    lt = n.new("ShaderNodeMath")
    lt.operation = "LESS_THAN"
    nt.links.new(add.outputs[0], lt.inputs[0])
    nt.links.new(_attr(nt, "corte", "OBJECT"), lt.inputs[1])
    return lt.outputs[0]


def _corte_keys(ob):
    """"corte" del plano ([[frame, x], ...]): por donde va el barrido."""
    keys = ctx.CFG.get("corte")
    if not keys:
        ob["corte"] = 1e4
        return
    for f, x in keys:
        ob["corte"] = float(x)
        ob.keyframe_insert('["corte"]', frame=f)
    linearize(ob)


def mat_pintura(name, color, luz=1.0):
    """Esmalte: color plano con la luz toon (las canaletas se marcan) y solo
    hasta donde llego el pincel: rev <= prog del objeto. luz < 1: toma menos
    la sombra de la canaleta (lineas finas que si no se apagan)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    n = nt.nodes
    light = _toon_light(nt)
    mul = n.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = luz
    mul.inputs[6].default_value = lin(color)
    nt.links.new(light, mul.inputs[7])
    em = _emit_out(nt, _fog(nt, mul.outputs[2]))
    out = em.outputs[0].links[0].to_node
    lt = n.new("ShaderNodeMath")
    lt.operation = "LESS_THAN"
    nt.links.new(_attr(nt, "rev", "GEOMETRY"), lt.inputs[0])
    nt.links.new(_attr(nt, "prog", "OBJECT"), lt.inputs[1])
    # el barrido borra la pintura (bloques): visible = pintado y no cortado
    vis = n.new("ShaderNodeMath")
    vis.operation = "MULTIPLY"
    nt.links.new(lt.outputs[0], vis.inputs[0])
    nt.links.new(_corte(nt), vis.inputs[1])
    tr = n.new("ShaderNodeBsdfTransparent")
    mix = n.new("ShaderNodeMixShader")
    nt.links.new(vis.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def mat_chapa(name, gris, color, ruido):
    """Chapa: gris comprimido hasta su cuadro 'tc' (atributo por vertice) y
    despues su color. El borde se ensucia con ruido (en cuadros) para que no
    sea un circulo."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    n = nt.nodes
    geo = n.new("ShaderNodeNewGeometry")
    nz = n.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = ruido.get("escala", 7.0)
    nz.inputs["Detail"].default_value = 3.0
    nt.links.new(geo.outputs["Position"], nz.inputs["Vector"])
    k = n.new("ShaderNodeMapRange")
    k.inputs["From Min"].default_value = 0.3
    k.inputs["From Max"].default_value = 0.7
    # el ruido solo atrasa: el color nunca vuelve antes de que pase el pincel
    k.inputs["To Min"].default_value = 0.0
    k.inputs["To Max"].default_value = 2 * ruido.get("cuadros", 10.0)
    nt.links.new(nz.outputs["Fac"], k.inputs["Value"])
    add = n.new("ShaderNodeMath")
    add.operation = "ADD"
    nt.links.new(_attr(nt, "tc", "GEOMETRY"), add.inputs[0])
    nt.links.new(k.outputs["Result"], add.inputs[1])
    lt = n.new("ShaderNodeMath")
    lt.operation = "LESS_THAN"
    nt.links.new(add.outputs[0], lt.inputs[0])
    nt.links.new(_attr(nt, "reloj", "OBJECT"), lt.inputs[1])
    # color = ya llego el contagio y el barrido no paso
    ok = n.new("ShaderNodeMath")
    ok.operation = "MULTIPLY"
    nt.links.new(lt.outputs[0], ok.inputs[0])
    nt.links.new(_corte(nt), ok.inputs[1])
    col = n.new("ShaderNodeMix")
    col.data_type = "RGBA"
    nt.links.new(ok.outputs[0], col.inputs["Factor"])
    col.inputs[6].default_value = lin(gris)
    col.inputs[7].default_value = lin(color)
    light = _toon_light(nt)
    mul = n.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(col.outputs[2], mul.inputs[6])
    nt.links.new(light, mul.inputs[7])
    _emit_out(nt, _fog(nt, mul.outputs[2]))
    return mat


def _reloj(ob):
    for f in (1, ctx.CFG["frames"]):
        ob["reloj"] = float(f)
        ob.keyframe_insert('["reloj"]', frame=f)
    linearize(ob)


# ------------------------------------------------------------------ piezas

def _fuentes(e):
    """Puntos de los trazos con el cuadro en que el pincel pasa por ellos: de
    ahi se contagia el color a la chapa."""
    pts, fr = [], []
    for p in motivo(e):
        if p["kind"] != "trazo" or p["capa"] not in ("linea", "fondo"):
            continue
        q, s = _resample(p["pts"], 0.01)
        k = s / max(s[-1], 1e-9)
        pts.append(q)
        fr.append(p["f"][0] + k * (p["f"][1] - p["f"][0]))
    return np.concatenate(pts), np.concatenate(fr)


def _tc(verts_xz, e, vel, demora):
    src, fr = _fuentes(e)
    out = np.empty(len(verts_xz))
    for a in range(0, len(verts_xz), 4000):
        v = verts_xz[a:a + 4000]
        d = np.linalg.norm(v[:, None, :] - src[None, :, :], axis=2)
        out[a:a + 4000] = (fr[None, :] + demora + d / vel).min(axis=1)
    return out


def _grilla(name, x0, x1, z0, z1, dx, dz, yfun, e, vel, demora, mat, coll):
    xs = np.arange(x0, x1 + 1e-9, dx)
    zs = np.arange(z0, z1 + 1e-9, dz)
    X, Z = np.meshgrid(xs, zs)
    xz = np.c_[X.ravel(), Z.ravel()]
    verts = [(x, float(yfun(x, z)), z) for x, z in xz]
    nx = len(xs)
    faces = [(j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i)
             for j in range(len(zs) - 1) for i in range(nx - 1)]
    # "colorida": la chapa arranca con su color (el 01 y el 06)
    tc = np.full(len(xz), -1e3) if ctx.CFG.get("chapa", {}).get("colorida") else _tc(xz, e, vel, demora)
    ob = _malla(name, verts, faces, {"tc": tc}, coll)
    ob.data.materials.append(mat)
    _corte_keys(ob)
    # las canaletas se dibujan con su normal; su propia sombra, con el pool
    # chico de 2 GB, sale en escalones a lo largo de cada cresta
    ob.visible_shadow = False
    _reloj(ob)
    return ob


def build_chapa(e, colls):
    """Pared de conventillo: chapa acanalada abajo (dos hojas solapadas), un
    tablon de madera y otra chapa arriba, cada una de su color."""
    fil = ctx.CFG.get("filete", {})
    vel = e.get("velocidad", 0.006)       # m por cuadro que avanza el color
    dem = e.get("demora", 1.0)
    G = e.get("gris", "#8b9196")
    R = e.get("ruido", {"escala": 7.0, "cuadros": 10.0})
    C = e.get("colores", {})
    x0, x1 = e.get("x", (-0.8, 1.0))
    z0, zt, z1 = e.get("z", (-1.1, 0.40, 1.2))
    junta = e.get("junta", 0.53)
    mc = colls["main"]
    abajo = mat_chapa("chapa_abajo", G, C.get("abajo", "#6fb4d4"), R)
    _grilla("chapa_a", x0, junta + 0.02, z0, zt, 0.012, PASO / 10,
            lambda x, z: surf(z), fil, vel, dem, abajo, mc)
    _grilla("chapa_b", junta, x1, z0, zt, 0.012, PASO / 10,
            lambda x, z: surf(z) - 0.0035, fil, vel, dem, abajo, mc)
    arriba = mat_chapa("chapa_arriba", G, C.get("arriba", "#efc12f"), R)
    _grilla("chapa_c", x0, x1, zt + 0.08, z1, 0.012, PASO / 10,
            lambda x, z: surf(z), fil, vel, dem, arriba, mc)
    # tablon: frente (en grilla, para que el color le llegue igual) y canto de abajo
    tab = mat_chapa("tablon", "#77797c", C.get("tablon", "#4c8a3c"), R)
    _grilla("tablon_frente", x0, x1, zt, zt + 0.08, 0.012, 0.02,
            lambda x, z: -0.032, fil, vel, dem, tab, mc)
    me = bpy.data.meshes.new("tablon_canto")
    me.from_pydata([(x0, -0.032, zt), (x1, -0.032, zt), (x1, AMP, zt), (x0, AMP, zt),
                    (x0, -0.032, zt + 0.08), (x1, -0.032, zt + 0.08), (x1, AMP, zt + 0.08),
                    (x0, AMP, zt + 0.08)], [], [(0, 1, 2, 3), (4, 7, 6, 5)])
    ob = bpy.data.objects.new("tablon_canto", me)
    ob.data.materials.append(tab)
    me.attributes.new("tc", "FLOAT", "POINT").data.foreach_set("value", np.full(8, 1e4, np.float32))
    _reloj(ob)
    _corte_keys(ob)
    if ctx.CFG.get("corte"):
        _linea_corte(x0, x1, z0, z1, colls)
    link(ob, mc)
    # clavos: en la junta, sobre las crestas, y en el tablon
    clavo = mat_flat_toon("clavo", "#4a4d52")
    zs = [z for z in np.arange(z0, zt, PASO * 2) + PASO * 0.75]
    pos = [(junta + 0.012, float(surf(z)) - 0.0035, z) for z in zs]
    pos += [(x, -0.032, zt + 0.04) for x in np.arange(x0 + 0.1, x1, 0.32)]
    for i, p in enumerate(pos):
        bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.0045, depth=0.004,
                                            location=(p[0], p[1] - 0.002, p[2]),
                                            rotation=(math.pi / 2, 0, 0))
        c = bpy.context.active_object
        c.name = f"clavo{i}"
        c.data.materials.append(clavo)
        for cl in list(c.users_collection):
            cl.objects.unlink(c)
        link(c, mc)


def _linea_corte(x0, x1, z0, z1, colls):
    """La linea del barrido sobre la chapa: una franja cian que brilla, en x =
    corte, de arriba abajo."""
    from piezas.materiales import mat_neon
    bpy.ops.mesh.primitive_plane_add(size=1.0)
    o = bpy.context.active_object
    o.name = "linea_corte"
    for cl in list(o.users_collection):
        cl.objects.unlink(o)
    link(o, colls["neon"])
    o.rotation_euler = (math.pi / 2, 0, 0)
    o.scale = (0.012, z1 - z0, 1)
    o.data.materials.append(mat_neon("linea_corte_m", "#7ff6ff", 3.0, fog=False))
    for f, x in ctx.CFG["corte"]:
        o.location = (x, -0.04, (z0 + z1) / 2)
        o.keyframe_insert("location", frame=f)
    linearize(o)


def mat_flat_toon(name, color):
    from piezas.materiales import mat_toon
    return mat_toon(name, color)


def build_filete(e, colls):
    """Cada pieza del motivo es un objeto con su 'prog' (0 -> 1 entre f0 y f1).
    Va en la coleccion sin tinta: el Line Art no ve el shader, y dibujaria
    el contorno de lo que todavia no se pinto."""
    mats = {}
    coll = colls["neon"]
    for i, p in enumerate(motivo(e)):
        col = p["col"]
        if col not in mats:
            mats[col] = mat_pintura(f"pintura_{col}", e.get("colores", {}).get(col, PALETA[col]),
                                    LUZ.get(col, 1.0))
        eps = CAPA[p["capa"]]
        name = f"filete{i:03d}_{col}"
        if p["kind"] == "trazo":
            ob, _, _ = _cinta(name, p["pts"], p["w"], p.get("w_ini"), p.get("w_fin"), eps,
                              p.get("corrido", 0.0), coll, cols=4 if p["w"] > 0.01 else 2,
                              lado=p.get("lado", 0), ref=p.get("ref"))
        else:
            poly = np.asarray(p["poly"])
            if p.get("barrido"):
                eje = ((poly[:, 0].min(), 0), (poly[:, 0].max(), 0))
            elif p.get("bolita"):
                eje = (poly.mean(axis=0) + (0, 0.02), poly.mean(axis=0) - (0, 0.02))
            else:
                eje = p.get("eje")
            ob = _relleno(name, poly, eps, coll, eje)
        ob.data.materials.append(mats[col])
        ob.visible_shadow = False
        _corte_keys(ob)
        f0, f1 = p["f"]
        if f1 < 1:
            # ya pintado antes del plano ("terminado"): sin claves
            ob["prog"] = 1.0001
            continue
        for fr, v in ((1, -0.01), (math.floor(f0), -0.01 if f0 > math.floor(f0) else 0.0),
                      (f1, 1.0001)):
            ob["prog"] = v
            ob.keyframe_insert('["prog"]', frame=fr)
        linearize(ob)


def build_pincel(e, colls):
    """Pincel de filetear: pelo largo, virola y mango. La punta sigue al
    trazo que se esta pintando; entre trazos viaja por el aire."""
    fil = ctx.CFG.get("filete", {})
    P = motivo(fil)
    frames = ctx.CFG["frames"]
    eje = Vector(e.get("eje", (0.45, -0.62, 0.64))).normalized()
    root = bpy.data.objects.new("pincel", None)
    link(root, colls["main"])
    root.rotation_mode = "QUATERNION"
    root.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(eje)
    from piezas.materiales import mat_toon
    partes = (
        ("pelo", 0.0009, 0.0042, 0.0, 0.048, e.get("pelo", "#3b2a1f")),
        ("virola", 0.0050, 0.0050, 0.048, 0.072, "#b9bcc4"),
        ("mango", 0.0046, 0.0036, 0.072, 0.24, e.get("mango", "#8a5a32")),
        ("punta_mango", 0.0036, 0.0030, 0.24, 0.27, "#c4372c"),
    )
    for nm, r0, r1, z0, z1, col in partes:
        bpy.ops.mesh.primitive_cone_add(vertices=14, radius1=r0, radius2=r1, depth=z1 - z0,
                                        location=(0, 0, (z0 + z1) / 2))
        o = bpy.context.active_object
        o.name = f"pincel_{nm}"
        o.data.materials.append(mat_toon(f"pincel_{nm}_m", col))
        for cl in list(o.users_collection):
            cl.objects.unlink(o)
        link(o, colls["main"])
        o.parent = root
    # recorrido de la punta, cuadro por cuadro
    activos = [p for p in P]
    ini = np.array(activos[0]["pts"][0]) if activos[0]["kind"] == "trazo" else _cabeza(activos[0], 0)
    # entra y sale por abajo a la derecha, del lado del hombro
    fuera_ini = ini + np.array([0.30, -0.40])
    fuera_fin = None
    ultimo = None
    locs = []
    camino = e.get("camino")      # [[frame, x, z, separacion], ...]: recorrido a mano
    for fr in range(1, frames + 1):
        en = [p for p in activos if p["f"][0] <= fr <= p["f"][1] + 0.01]
        if camino:
            fs = [c[0] for c in camino]
            q = np.array([np.interp(fr, fs, [c[1] for c in camino]), np.interp(fr, fs, [c[2] for c in camino])])
            sep = float(np.interp(fr, fs, [c[3] for c in camino]))
        elif en:
            p = en[-1]
            q = _cabeza(p, fr)
            ultimo = q
            sep = 0.0
        else:
            prox = [p for p in activos if p["f"][0] > fr]
            if not ultimo is None and not prox:
                k = min(1.0, (fr - max(p["f"][1] for p in activos)) / 4)
                if fuera_fin is None:
                    fuera_fin = ultimo + np.array([0.32, -0.42])
                q = ultimo + (fuera_fin - ultimo) * k
                sep = 0.06 * k
            elif prox:
                q0 = _cabeza(prox[0], prox[0]["f"][0])
                if ultimo is None:
                    k = min(1.0, (fr - 1) / max(1, prox[0]["f"][0] - 1))
                    q = fuera_ini + (q0 - fuera_ini) * k
                    sep = 0.06 * (1 - k)
                else:
                    # viaje por el aire entre trazos: arco que se despega de la chapa
                    f_ant = max(p["f"][1] for p in activos if p["f"][1] < fr)
                    k = (fr - f_ant) / max(prox[0]["f"][0] - f_ant, 1e-6)
                    q = ultimo + (q0 - ultimo) * k
                    sep = 0.035 * math.sin(math.pi * k)
            else:
                q, sep = ultimo, 0.0
        y = float(surf(q[1])) - 0.0042
        root.location = Vector((q[0], y, q[1])) + eje * sep
        root.keyframe_insert("location", frame=fr)
        locs.append(tuple(root.location))
    linearize(root)
    if e.get("mano", True):
        em = e.get("mano") if isinstance(e.get("mano"), dict) else {}
        w, m = build_mano(root, eje, em, colls)
        build_brazo(root, locs, w, m, em.get("brazo", {}), colls)


# piel del fileteador: el robot del relojero (palma, dedos de bronce, bola de
# muneca, antebrazo) con otros colores y la manga del mameluco
COLORES_ROBOT = {"cuerpo": "#e2d5b6", "bronce": "#c4923a", "oscuro": "#2a2733",
                 "manga": "#35507e", "mancha": "#d23a2a"}


def _palo(name, p0, p1, r0, r1, mat, parent, coll, segs=12):
    """Cilindro de p0 a p1 (coordenadas locales del padre)."""
    p0, p1 = Vector(p0), Vector(p1)
    bpy.ops.mesh.primitive_cone_add(vertices=segs, radius1=r0, radius2=r1, depth=(p1 - p0).length,
                                    location=(0, 0, 0))
    o = bpy.context.active_object
    o.name = name
    for cl in list(o.users_collection):
        cl.objects.unlink(o)
    link(o, coll)
    o.data.materials.append(mat)
    o.parent = parent
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(p1 - p0)
    o.location = (p0 + p1) / 2
    return o


def _caja(name, c, ejes, medidas, mat, parent, coll):
    """Caja centrada en c, con sus ejes (a, b, c locales del padre) y medidas."""
    from mathutils import Matrix
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    o = bpy.context.active_object
    o.name = name
    for cl in list(o.users_collection):
        cl.objects.unlink(o)
    link(o, coll)
    o.data.materials.append(mat)
    o.parent = parent
    M = Matrix((ejes[0], ejes[1], ejes[2])).transposed()
    o.matrix_basis = Matrix.Translation(Vector(c)) @ M.to_4x4() @ Matrix.Diagonal((*medidas, 1.0))
    return o


def build_mano(root, eje, e, colls):
    """Mano del robot con agarre de fileteador (de lapiz, cerca de la virola,
    menique apoyado en la chapa) y el antebrazo que baja hacia la derecha.
    Va colgada del pincel: se mueve con el."""
    from piezas.materiales import mat_toon
    C = {**COLORES_ROBOT, **e.get("colores", {})}
    mc = colls["main"]
    m = {k: mat_toon(f"robot_{k}", v) for k, v in C.items()}
    q = root.rotation_quaternion.inverted()
    # ejes de la mano, locales del pincel: a = el mango (de la punta al cabo),
    # c = hacia la camara (lo que queda entre el mango y la camara se ve
    # agarrandolo), b = hacia el antebrazo; -c es el lado de la chapa
    a = Vector((0, 0, 1))
    cam = q @ Vector((0, -1, 0))
    c = (cam - a * cam.dot(a)).normalized()
    afuera = Vector(e.get("antebrazo", (0.25, -0.30, -0.92))).normalized()
    fa = q @ afuera
    b = a.cross(c)
    if b.dot(fa) < 0:
        b = -b
    g = a * e.get("agarre", 0.078)           # justo arriba de la virola
    R0, R1 = 0.0075, 0.006                   # dedos mas finos que en el puno

    def dedo(nombre, *puntos):
        for k, (p0, p1) in enumerate(zip(puntos, puntos[1:])):
            _palo(f"mano_{nombre}{k}", p0, p1, R0, R1, m["bronce"], root, mc)

    # agarre de lapiz, como pintan los fileteadores: pulgar e indice pinzan el
    # mango cerca de la virola, el mayor lo sostiene del lado de la chapa, el
    # anular recogido y el menique estirado apoyado en la chapa
    _caja("mano_palma", g + b * 0.048 + a * 0.012 - c * 0.006, (a, b, c), (0.062, 0.024, 0.052),
          m["oscuro"], root, mc)
    dedo("pulgar", g + b * 0.034 + c * 0.020 + a * 0.020, g + b * 0.016 + c * 0.016 + a * 0.008,
         g + c * 0.0085 + a * 0.002)
    dedo("indice", g + b * 0.034 + a * 0.040, g + b * 0.014 + a * 0.030 - c * 0.002,
         g + b * 0.0075 + a * 0.008, g + b * 0.006 - a * 0.002)
    dedo("mayor", g + b * 0.040 + a * 0.024 - c * 0.016, g + b * 0.018 + a * 0.004 - c * 0.020,
         g - c * 0.0085 - a * 0.004)
    dedo("anular", g + b * 0.044 + a * 0.010 - c * 0.022, g + b * 0.034 - a * 0.006 - c * 0.034,
         g + b * 0.040 - a * 0.010 - c * 0.024)
    # menique: baja de la palma a la chapa, justo debajo de ella (en el mundo),
    # unos mm adelante de las crestas para no meterse en la chapa
    nud = g + b * 0.046 - a * 0.004 - c * 0.014
    nw = root.rotation_quaternion @ nud
    dx, dz = e.get("apoyo", (-0.016, -0.036))
    apoyo = q @ Vector((nw.x + dx, -0.013, nw.z + dz))
    dedo("menique", nud, nud + (apoyo - nud) * 0.55 + c * 0.004, apoyo)
    # muneca, antebrazo y manga del mameluco (con una chorreadura de esmalte)
    w = g + b * 0.066 + a * 0.016 - c * 0.004
    # bola de muneca mas ancha que el antebrazo: tapa la union
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.042, location=w)
    o = bpy.context.active_object
    o.name = "mano_muneca"
    for cl in list(o.users_collection):
        cl.objects.unlink(o)
    link(o, mc)
    o.data.materials.append(m["oscuro"])
    o.parent = root
    return w, m


def _ik(S, W, L1, L2, polo):
    """Codo de un brazo de dos tramos (hombro S, muneca W), hacia el polo."""
    d = W - S
    n = d.length
    u = d / n
    n = min(n, L1 + L2 - 1e-4)
    a = (L1 * L1 - L2 * L2 + n * n) / (2 * n)
    h = math.sqrt(max(L1 * L1 - a * a, 0.0))
    v = (polo - u * polo.dot(u)).normalized()
    return S + u * a + v * h


def build_brazo(root, locs, w, m, e, colls):
    """Brazo de dos tramos, cuadro por cuadro: la muneca va con la mano; el
    hombro, fuera de cuadro abajo a la derecha, sigue a la mano con retraso
    (el cuerpo que se acomoda); el codo sale de IK hacia abajo. La manga
    sigue de largo mas alla del hombro: el brazo siempre sale del cuadro."""
    mc = colls["main"]
    R = root.rotation_quaternion
    L1, L2 = e.get("largos", (0.55, 0.48))
    polo = Vector(e.get("polo", (0.2, -0.35, -1.0))).normalized()
    hx, hy, hz = e.get("hombro", (0.45, -0.40, -0.35))
    Ws = [Vector(l) + R @ w for l in locs]
    n = len(Ws)
    vent = e.get("retraso", 6)

    def media(i):
        js = range(max(0, i - vent), min(n, i + vent + 1))
        return sum((Ws[j] for j in js), Vector()) / len(js)

    def cil(name, L, r0, r1, mat):
        bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=r0, radius2=r1, depth=L)
        o = bpy.context.active_object
        o.name = name
        for cl in list(o.users_collection):
            cl.objects.unlink(o)
        link(o, mc)
        o.data.materials.append(mat)
        o.rotation_mode = "QUATERNION"
        return o

    # radio1 en -Z (el extremo de abajo del cono) = el lado del codo
    # el antebrazo termina antes de la muneca: su tapa no asoma entre los dedos
    ante = cil("antebrazo", L2 - 0.035, 0.046, 0.036, m["cuerpo"])
    manga = cil("manga", L1, 0.072, 0.064, m["manga"])
    sigue = cil("manga_sigue", 0.6, 0.075, 0.072, m["manga"])
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.05)
    codo = bpy.context.active_object
    codo.name = "codo"
    for cl in list(codo.users_collection):
        cl.objects.unlink(codo)
    link(codo, mc)
    codo.data.materials.append(m["oscuro"])
    # gota de esmalte rojo en la manga, cerca del codo
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, radius=0.016,
                                         location=(0.0, -0.068, -L1 / 2 + 0.06))
    gota = bpy.context.active_object
    gota.name = "manga_mancha"
    gota.scale = (1.0, 0.45, 1.0)
    for cl in list(gota.users_collection):
        cl.objects.unlink(gota)
    link(gota, mc)
    gota.data.materials.append(m["mancha"])
    gota.parent = manga

    def poner(o, p0, p1, f):
        d = p1 - p0
        o.location = (p0 + p1) / 2
        o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d)
        o.keyframe_insert("location", frame=f)
        o.keyframe_insert("rotation_quaternion", frame=f)

    for i, W in enumerate(Ws):
        f = i + 1
        M = media(i)
        S = Vector((max(M.x + hx, 0.42), hy, min(M.z + hz, -0.60)))
        lim = 0.97 * (L1 + L2)
        if (S - W).length > lim:
            S = W + (S - W).normalized() * lim
        E = _ik(S, W, L1, L2, polo)
        poner(ante, E, E + (W - E).normalized() * (L2 - 0.035), f)
        poner(manga, E, E + (S - E).normalized() * L1, f)
        S2 = E + (S - E).normalized() * L1
        poner(sigue, S2, S2 + (S2 - E).normalized() * 0.6, f)
        codo.location = E
        codo.keyframe_insert("location", frame=f)
    for o in (ante, manga, sigue, codo):
        linearize(o)


# ------------------------------------------------------------------ robot entero

def _relojero():
    """El modulo de piezas de el_relojero (robot por pivotes, IK del brazo)."""
    src = Path(__file__).resolve().parent.parent / "el_relojero" / "piezas.py"
    spec = importlib.util.spec_from_file_location("piezas_relojero", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pincel_malla(root, coll, banda=False):
    """Pincel de filetear (mango largo) o "banda" (virola sin mango, pelo de
    mas de 5 cm), a lo largo de +Z de root, con la punta en el origen."""
    from piezas.materiales import mat_toon
    if banda:
        partes = (("pelo", 0.0012, 0.006, 0.0, 0.065, "#3b2a1f"),
                  ("virola", 0.007, 0.007, 0.065, 0.09, "#b9bcc4"))
    else:
        partes = (("pelo", 0.0009, 0.0042, 0.0, 0.048, "#3b2a1f"),
                  ("virola", 0.0050, 0.0050, 0.048, 0.072, "#b9bcc4"),
                  ("mango", 0.0046, 0.0036, 0.072, 0.24, "#8a5a32"),
                  ("punta_mango", 0.0036, 0.0030, 0.24, 0.27, "#c4372c"))
    for nm, r0, r1, z0, z1, col in partes:
        bpy.ops.mesh.primitive_cone_add(vertices=14, radius1=r0, radius2=r1, depth=z1 - z0,
                                        location=(0, 0, (z0 + z1) / 2))
        o = bpy.context.active_object
        o.name = f"{root.name}_{nm}"
        o.data.materials.append(mat_toon(f"{root.name}_{nm}_m", col))
        for cl in list(o.users_collection):
            cl.objects.unlink(o)
        link(o, coll)
        o.parent = root


def build_robot(e, colls):
    """El fileteador entero: el robot del relojero con la piel de 03 (crema,
    manga azul de mameluco, bronce), sin corazon encendido, con el pincel (o
    la banda) en la mano izquierda. e: lo de el_relojero ("at", "face",
    "pose", "ik_i") + "herramienta": [[frame, "pincel" | "banda" | null], ...]."""
    rel = _relojero()
    cfg = dict(e)
    cfg["colors"] = {"cuerpo": COLORES_ROBOT["cuerpo"], "bronce": COLORES_ROBOT["bronce"],
                     "oscuro": COLORES_ROBOT["manga"], "ojo": "#ffd27a", "corazon": "#ffd27a",
                     **e.get("colors", {})}
    pose = [dict(k) for k in e.get("pose", [{"frame": 1}])]
    pose[0].setdefault("corazon", 0.0)
    cfg["pose"] = pose
    # apoyado en lo que haya debajo (la calle peatonal de Caminito esta 14 cm
    # sobre el piso; un balcon, a 3,1 m): un rayo desde medio metro arriba
    if e.get("al_piso", True):
        bpy.context.view_layer.update()
        x, y, z = cfg.get("at", (0, 0, 0))
        dg = bpy.context.evaluated_depsgraph_get()
        ok, loc, *_ = bpy.context.scene.ray_cast(dg, Vector((x, y, z + 0.5)), Vector((0, 0, -1)))
        if ok:
            cfg["at"] = (x, y, loc.z)
    rel.build_relojero(cfg, colls)
    mano = rel.R("muneca_i")
    herr = e.get("herramienta", [[1, "pincel"]])
    for tipo in ("pincel", "banda"):
        if not any(t == tipo for _, t in herr):
            continue
        r = bpy.data.objects.new(f"robot_{tipo}", None)
        link(r, colls["main"])
        _pincel_malla(r, colls["main"], banda=(tipo == "banda"))
        r.parent = mano
        r.location = rel.GRIP
        # el mango cruza el puno (X local) y la punta sale hacia adelante y abajo
        r.rotation_euler = [math.radians(a) for a in e.get(f"{tipo}_rot", (0, -100, 0))]
        for f, t in herr:
            v = 1.0 if t == tipo else 0.0
            r.scale = (v, v, v)
            r.keyframe_insert("scale", frame=f)
        from piezas.base import set_interp
        set_interp(r, "CONSTANT")


# ------------------------------------------------------------------ la banda que corre

def build_banda_larga(e, colls):
    """Una sola linea larga (la banda roja con su firulete blanco) que sale del
    pincel y corre sola por las fachadas de un lado: por la chapa a la altura
    del primer piso, por las barandas de los balcones y baja en los tapiales.
    e: {"lado": 1, "desde": s0, "hasta": s1, "keys": [[frame, s], ...] (la
    punta)}. Las curvas crecen con bevel_factor_end (mapeo por largo)."""
    from piezas.materiales import mat_toon
    lado = e.get("lado", 1)
    s0, s1 = e["desde"], e["hasta"]
    F = [f for f in caminito.FRENTES if f["lado"] == lado]
    paso = 0.2 if s1 < s0 else -0.2
    pts, ss = [], []
    s = s0
    while (s - s1) * (s0 - s1) > 0:
        fr = next((f for f in F if f["s0"] <= s <= f["s1"]), None)
        if fr:
            u = (s - fr["s0"]) / (fr["s1"] - fr["s0"]) * fr["L"]
            if fr["pisos"] == 0:
                v, z = -0.08, fr["h"] - 0.35
            elif fr.get("balcon") and fr["b"][0] <= u <= fr["b"][1]:
                v, z = -1.08, 3.1 + 0.97
            else:
                v, z = -0.08, 3.55 + 0.25 * math.sin(s * 0.8)
            # arranca a la altura de la mano del robot y sube en 3 m
            k0 = abs(s - s0) / 3.0
            if "z_ini" in e and k0 < 1:
                z = e["z_ini"] + (z - e["z_ini"]) * k0
            q = fr["o"] + fr["U"] * u + fr["N"] * v + Vector((0, 0, z))
            pts.append(q)
            ss.append(s)
        s -= paso
    cu_pts = [tuple(p) for p in pts]
    mats = {"rojo": mat_toon("banda_larga_m", PALETA["rojo"]),
            "blanco": mat_toon("banda_larga_fir_m", PALETA["firulete"])}

    def curva(name, P, r, mat, dz):
        cu = bpy.data.curves.new(name, "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = r
        cu.bevel_resolution = 2
        cu.use_fill_caps = True
        cu.bevel_factor_mapping_start = "SPLINE"
        cu.bevel_factor_mapping_end = "SPLINE"
        sp = cu.splines.new("POLY")
        sp.points.add(len(P) - 1)
        for k, q in enumerate(P):
            sp.points[k].co = (q[0], q[1], q[2] + dz, 1)
        ob = bpy.data.objects.new(name, cu)
        ob.data.materials.append(mat)
        link(ob, colls["main"])
        return ob

    ob_b = curva("banda_larga", cu_pts, e.get("radio", 0.05), mats["rojo"], 0.0)
    ob_f = curva("banda_larga_firulete", cu_pts, 0.014, mats["blanco"], e.get("firulete_dz", 0.14))
    ss = np.asarray(ss)
    L = abs(ss[-1] - ss[0])
    for f, sh in e["keys"]:
        k = float(np.clip(abs(sh - ss[0]) / max(L, 1e-6), 0, 1))
        for ob, lag in ((ob_b, 0.0), (ob_f, 0.02)):
            ob.data.bevel_factor_end = max(0.0, k - lag)
            ob.data.keyframe_insert("bevel_factor_end", frame=f)
    for ob in (ob_b, ob_f):
        if ob.data.animation_data and ob.data.animation_data.action:
            from piezas.base import set_interp
            set_interp(ob.data, "LINEAR")


PIEZAS = [("chapa", build_chapa), ("filete", build_filete), ("pincel", build_pincel),
          ("caminito", caminito.build_caminito), ("robot", build_robot), ("banda_larga", build_banda_larga)]
