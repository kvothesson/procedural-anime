"""Entorno real desde OpenStreetMap: el terreno con su relieve, las calles con
sus veredas, las plazas, las vias del tren, los edificios extruidos y los
arboles.

Los datos ya vienen en metros y en el marco de la escena (motor/osm.py ->
<ep>/data/entorno.json), con la grilla de alturas en "terreno". Aca solo se
arma la geometria, todo apoyado en esa grilla; los colores los pone el estilo
del plano.

Todo lo que va a ras del piso queda fuera de la tinta (las cintas de calle se
pisan entre si y Line Art dibujaria cada borde): la tinta va en edificios y
arboles. Edificios y arboles van en pocas mallas grandes, no un objeto por
casa: son cientos.
"""

import json
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import ctx
from .base import collection, link
from .materiales import mat_beam, mat_neon, mat_tint, mat_toon

AUTOS = {"motorway", "trunk", "primary", "secondary", "tertiary", "residential", "living_street",
         "unclassified"}
_SUELO = None


def _suelo_coll():
    global _SUELO
    if _SUELO is None:
        _SUELO = collection("entorno_suelo", "EXCLUDE")
    return _SUELO


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


class Suelo:
    """Altura del terreno en metros de escena: la grilla de entorno.json
    ("terreno", de motor/osm.py), interpolada; sin grilla, un plano en z."""

    def __init__(self, T, z):
        self.T, self.z = T, z
        if T:
            self.n, self.paso, self.x0, self.y0 = T["n"], T["paso"], T["x0"], T["y0"]
            self.g = T["z"]

    def __call__(self, x, y):
        if not self.T:
            return self.z
        fx = min(max((x - self.x0) / self.paso, 0.0), self.n - 1.001)
        fy = min(max((y - self.y0) / self.paso, 0.0), self.n - 1.001)
        i, j = int(fx), int(fy)
        ax, ay = fx - i, fy - j
        g, n = self.g, self.n
        return ((g[j * n + i] * (1 - ax) + g[j * n + i + 1] * ax) * (1 - ay)
                + (g[(j + 1) * n + i] * (1 - ax) + g[(j + 1) * n + i + 1] * ax) * ay)


def _densify(pts, step=3.0):
    out = [pts[0]]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        k = max(1, int(math.hypot(bx - ax, by - ay) / step))
        out += [(ax + (bx - ax) * t / k, ay + (by - ay) * t / k) for t in range(1, k + 1)]
    return out


def _ribbon(bm, pts, w, H, off):
    """Cinta de ancho w por la polilinea, apoyada en el terreno H (+off), con
    un disco en cada quiebre para que esquinas y curvas queden cerradas."""
    corners = pts
    pts = _densify(pts)
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        if L < 0.01:
            continue
        sx, sy = -dy / L * w / 2, dx / L * w / 2
        za, zb = H(ax, ay) + off, H(bx, by) + off
        vs = [bm.verts.new((ax + sx, ay + sy, za)), bm.verts.new((bx + sx, by + sy, zb)),
              bm.verts.new((bx - sx, by - sy, zb)), bm.verts.new((ax - sx, ay - sy, za))]
        f = bm.faces.new(vs)
        if f.normal.z < 0:
            f.normal_flip()
    if w > 3:
        for x, y in corners:
            n = 10
            vs = [bm.verts.new((x + w / 2 * math.cos(2 * math.pi * k / n),
                                y + w / 2 * math.sin(2 * math.pi * k / n), H(x, y) + off)) for k in range(n)]
            bm.faces.new(vs)


def _dentro(poly, bb, x, y):
    if not (bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3]):
        return False
    ins = False
    j = len(poly) - 1
    for i in range(len(poly)):
        (xi, yi), (xj, yj) = poly[i], poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            ins = not ins
        j = i
    return ins


def _terreno(T, areas, mats, coll, lejos=3000.0):
    """Malla del terreno: la grilla, con cada cara pintada segun el area de
    OSM que la contiene (piso, pasto o playa de estacionamiento), y un anillo
    exterior hasta `lejos` que sigue la altura del borde."""
    n, paso, x0, y0, g = T["n"], T["paso"], T["x0"], T["y0"], T["z"]
    bm = bmesh.new()
    vs = [bm.verts.new((x0 + i * paso, y0 + j * paso, g[j * n + i])) for j in range(n) for i in range(n)]
    polys = []
    for a in areas:
        xs = [p[0] for p in a["p"]]
        ys = [p[1] for p in a["p"]]
        polys.append((a["p"], (min(xs), min(ys), max(xs), max(ys)), 1 if a["k"] == "verde" else 2))
    for j in range(n - 1):
        for i in range(n - 1):
            f = bm.faces.new([vs[j * n + i], vs[j * n + i + 1], vs[(j + 1) * n + i + 1], vs[(j + 1) * n + i]])
            cx, cy = x0 + (i + 0.5) * paso, y0 + (j + 0.5) * paso
            for poly, bb, k in polys:
                if _dentro(poly, bb, cx, cy):
                    f.material_index = k
                    break
    border = ([i for i in range(n)] + [j * n + n - 1 for j in range(1, n)]
              + [(n - 1) * n + i for i in range(n - 2, -1, -1)] + [j * n for j in range(n - 2, 0, -1)])
    cx, cy = x0 + (n - 1) * paso / 2, y0 + (n - 1) * paso / 2
    outer = []
    for b in border:
        v = vs[b].co
        k = lejos / max(math.hypot(v.x - cx, v.y - cy), 1.0)
        outer.append(bm.verts.new((cx + (v.x - cx) * k, cy + (v.y - cy) * k, v.z)))
    for a in range(len(border)):
        b = (a + 1) % len(border)
        bm.faces.new([vs[border[a]], vs[border[b]], outer[b], outer[a]])
    for f in bm.faces:
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
    me = bpy.data.meshes.new("entorno_terreno")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("entorno_terreno", me)
    for m in mats:
        ob.data.materials.append(m)
    link(ob, coll)
    return ob


def _flat(bm, pts, z):
    vs = [bm.verts.new((x, y, z)) for x, y in pts]
    try:
        f = bm.faces.new(vs)
        if f.normal.z < 0:
            f.normal_flip()
    except ValueError:
        pass


def _prism(bm, pts, z0, z1):
    lo = [bm.verts.new((x, y, z0)) for x, y in pts]
    hi = [bm.verts.new((x, y, z1)) for x, y in pts]
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([lo[i], lo[j], hi[j], hi[i]])
    for ring in (hi, list(reversed(lo))):
        try:
            bm.faces.new(ring)
        except ValueError:
            pass


def _gable(bm, pts, z, pitch):
    """Techo a dos aguas sobre un rectangulo (cumbrera por el lado largo)."""
    A, B, C, D = (Vector((p[0], p[1], z)) for p in pts)
    if (B - A).length < (D - A).length:
        A, B, C, D = B, C, D, A
    half = (D - A).length / 2
    up = Vector((0, 0, half * pitch))
    m0, m1 = (A + D) / 2 + up, (B + C) / 2 + up
    vs = [bm.verts.new(v) for v in (A, B, C, D, m0, m1)]
    A, B, C, D, M0, M1 = vs
    for f in ((A, B, M1, M0), (C, D, M0, M1), (A, M0, D), (B, C, M1), (A, D, C, B)):
        bm.faces.new(f)


def _tree(tronco, copa, x, y, z, s, rnd):
    """Arbol de anime: tronco fino y copa de dos esferas bajas en poligonos."""
    bmesh.ops.create_cone(tronco, cap_ends=True, segments=6, radius1=0.16 * s, radius2=0.12 * s,
                          depth=2.6 * s, matrix=Matrix.Translation((x, y, z + 1.3 * s)))
    for k in range(2):
        r = s * rnd.uniform(1.7, 2.4)
        bmesh.ops.create_icosphere(copa, subdivisions=1, radius=r, matrix=Matrix.Translation(
            (x + rnd.uniform(-0.8, 0.8) * s, y + rnd.uniform(-0.8, 0.8) * s, z + s * rnd.uniform(3.6, 4.6))))


def _faroles(calles, H, f, colls, R):
    """Faroles por las calles con autos, alternando veredas cada f["paso"] m:
    poste, brazo hacia la calle y cabeza encendida; la luz es pintada (un cono
    translucido y un charco calido en el piso), no una lampara real: con
    cientos de luces la placa de 2 GB no da. Cables colgando entre postes de
    la misma vereda."""
    alto, paso = f.get("alto", 5.5), f.get("paso", 30.0)
    enc = f.get("encendido", 1.0)
    postes, cabezas, conos, charcos, cables = (bmesh.new() for _ in range(5))
    cadenas = []
    for c in calles:
        if c["k"] not in AUTOS:
            continue
        pts = _densify(c["p"], 1.0)
        acum, prox, lado = 0.0, paso * 0.5, 1
        lados = {-1: [], 1: []}
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            d = math.hypot(bx - ax, by - ay)
            if d < 1e-6:
                continue
            while acum + d >= prox:
                t = (prox - acum) / d
                x, y = ax + (bx - ax) * t, ay + (by - ay) * t
                if math.hypot(x, y) < R:
                    nx, ny = -(by - ay) / d * lado, (bx - ax) / d * lado
                    px, py = x + nx * (c["w"] / 2 + 0.6), y + ny * (c["w"] / 2 + 0.6)
                    z = H(px, py)
                    bmesh.ops.create_cone(postes, cap_ends=True, segments=6, radius1=0.09, radius2=0.07,
                                          depth=alto, matrix=Matrix.Translation((px, py, z + alto / 2)))
                    hx, hy = px - nx * 1.4, py - ny * 1.4
                    brazo = [Vector((px, py, z + alto - 0.1)), Vector((hx, hy, z + alto - 0.25))]
                    _tubo(postes, brazo, 0.045)
                    bmesh.ops.create_cube(cabezas, size=1.0, matrix=Matrix.Translation((hx, hy, z + alto - 0.35))
                                          @ Matrix.Diagonal((0.5, 0.5, 0.12, 1)))
                    zc = z + alto - 0.42
                    bmesh.ops.create_cone(conos, cap_ends=False, segments=16, radius1=f.get("radio", 2.4),
                                          radius2=0.25, depth=zc - z,
                                          matrix=Matrix.Translation((hx, hy, z + (zc - z) / 2)))
                    bmesh.ops.create_circle(charcos, cap_ends=True, segments=20, radius=f.get("radio", 2.4) * 1.15,
                                            matrix=Matrix.Translation((hx, hy, H(hx, hy) + 0.2)))
                    lados[lado].append(Vector((px, py, z + alto - 0.05)))
                lado = -lado
                prox += paso
            acum += d
        cadenas += [v for v in lados.values() if len(v) > 1]
    if f.get("cables", True):
        for cad in cadenas:
            for a, b in zip(cad, cad[1:]):
                if (b - a).length > paso * 2.2:
                    continue
                pts = [a.lerp(b, k / 10) - Vector((0, 0, (b - a).length * 0.035 * 4 * (k / 10) * (1 - k / 10)))
                       for k in range(11)]
                _tubo(cables, pts, 0.012)
    col = f.get("color", "#ffb45c")
    _obj("entorno_postes", postes, mat_toon("entorno_poste_m", f.get("poste", "#2c2a38")), colls["main"])
    _obj("entorno_cables", cables, mat_toon("entorno_cable_m", f.get("cable", "#15131c")), colls["main"])
    cab = _obj("entorno_farol_cabezas", cabezas, mat_neon("entorno_farol_m", col, 1.6 * enc), colls["neon"])
    cab["power"] = enc
    if enc > 0.05:
        cn = _obj("entorno_farol_conos", conos, mat_beam("entorno_farol_cono", col, f.get("cono_alpha", 0.07) * enc),
                  colls["veil"])
        cn["power"] = 1.0
        ch = _obj("entorno_farol_charcos", charcos, mat_tint("entorno_farol_charco", col, f.get("charco_alpha", 0.18) * enc),
                  colls["veil"])
        ch["power"] = 1.0
    else:
        conos.free()
        charcos.free()


def _tubo(bm, pts, r):
    """Tubo de 5 lados por una polilinea (brazos de farol, cables)."""
    pts = [Vector(p) for p in pts]
    rings = []
    for i, p in enumerate(pts):
        T = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        S = T.cross(Vector((0, 0, 1)))
        if S.length < 1e-4:
            S = T.cross(Vector((1, 0, 0)))
        S.normalize()
        Nn = S.cross(T)
        rings.append([bm.verts.new(p + (S * math.cos(a) + Nn * math.sin(a)) * r)
                      for a in (2 * math.pi * k / 5 for k in range(5))])
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(5):
            j = (k + 1) % 5
            bm.faces.new([r0[k], r0[j], r1[j], r1[k]])


def build_entorno(e, colls):
    """e: {"datos": "data/entorno.json", "terreno": true, "z": -1.0 (sin
    terreno), "piso": 6000, "colores": {...}, "arboles": true, "relleno": true,
    "radio": 450, "ventanas": {...} (ver mat_toon), "quitar_arboles": [[x, y], ...]}"""
    data = json.loads((ctx.EPISODIO / e.get("datos", "data/entorno.json")).read_text(encoding="utf-8"))
    col = {"piso": "#b8b4aa", "vereda": "#cfcac0", "asfalto": "#77797e", "camino": "#c2b8a6",
           "pasto": "#9fb48f", "playa": "#8c8e92", "edificio": ["#d6d2ca", "#cbc6bd", "#dedad2"],
           "techo": "#a7a29a", "teja": "#a88f80", "via": "#8f8a82", "riel": "#55565c",
           "anden": "#c9c4ba", "copa": ["#8fa77f", "#9db58c"], "tronco": "#7a6a5c", **e.get("colores", {})}
    T = data.get("terreno") if e.get("terreno", True) else None
    H = Suelo(T, e.get("z", -1.0))
    R = e.get("radio", 1e9)
    relleno = e.get("relleno", True)
    rnd = random.Random(e.get("seed", 5))
    sc = _suelo_coll()
    main = colls["main"]

    def near(pts):
        return any(math.hypot(x, y) < R for x, y in pts)

    m_piso = mat_toon("entorno_piso_m", col["piso"])
    m_pasto = mat_toon("entorno_pasto_m", col["pasto"])
    m_asf = mat_toon("entorno_asfalto_m", col["asfalto"])
    m_playa = mat_toon("entorno_playa_m", col["playa"])
    if T:
        _terreno(T, [a for a in data["areas"] if near(a["p"])], [m_piso, m_pasto, m_playa], sc,
                 lejos=e.get("piso", 6000) / 2)
    else:
        bm = bmesh.new()
        s = e.get("piso", 6000) / 2
        _flat(bm, [(-s, -s), (s, -s), (s, s), (-s, s)], H.z - 0.01)
        _obj("entorno_piso", bm, m_piso, sc)
        for k, m in (("verde", m_pasto), ("playa", m_playa)):
            bm = bmesh.new()
            for a in data["areas"]:
                if a["k"] == k and near(a["p"]):
                    _flat(bm, a["p"], H.z + 0.03)
            _obj(f"entorno_{k}", bm, m, sc)

    # veredas, calzadas y caminos, apoyados en el terreno (alturas escalonadas)
    calles = [c for c in data["calles"] if near(c["p"])]
    bm = bmesh.new()
    for c in calles:
        if c["k"] in AUTOS:
            _ribbon(bm, c["p"], c["w"] + 6.0, H, 0.08)
    _obj("entorno_veredas", bm, mat_toon("entorno_vereda_m", col["vereda"]), sc)
    bm = bmesh.new()
    for c in calles:
        if c["k"] in AUTOS or c["k"] == "service":
            _ribbon(bm, c["p"], c["w"], H, 0.12)
    _obj("entorno_calzadas", bm, m_asf, sc)
    bm = bmesh.new()
    for c in calles:
        if c["k"] not in AUTOS and c["k"] != "service":
            _ribbon(bm, c["p"], c["w"], H, 0.14)
    _obj("entorno_caminos", bm, mat_toon("entorno_camino_m", col["camino"]), sc)

    # tren: balasto, rieles y andenes
    bm = bmesh.new()
    for v in data["vias"]:
        if near(v["p"]):
            _ribbon(bm, v["p"], 3.4, H, 0.16)
    _obj("entorno_balasto", bm, mat_toon("entorno_via_m", col["via"]), sc)
    bm = bmesh.new()
    for v in data["vias"]:
        if not near(v["p"]):
            continue
        for off in (-0.72, 0.72):
            for (ax, ay), (bx, by) in zip(v["p"], v["p"][1:]):
                L = math.hypot(bx - ax, by - ay) or 1
                ox, oy = -(by - ay) / L * off, (bx - ax) / L * off
                _ribbon(bm, [(ax + ox, ay + oy), (bx + ox, by + oy)], 0.12, H, 0.32)
    _obj("entorno_rieles", bm, mat_toon("entorno_riel_m", col["riel"]), sc)
    bm = bmesh.new()
    for a in data["andenes"]:
        if near(a["p"]):
            zs = [H(x, y) for x, y in a["p"]]
            _prism(bm, a["p"], min(zs) - 0.3, sum(zs) / len(zs) + 1.0)
    _obj("entorno_andenes", bm, mat_toon("entorno_anden_m", col["anden"]), main)

    # edificios: tres mallas por color, techos aparte. Cada uno nace del punto
    # mas bajo de su planta: en la barranca el zocalo queda a la vista
    eds = [b for b in data["edificios"] if near(b["p"]) and len(b["p"]) >= 3
           and (relleno or b["src"] != "relleno")]
    paredes = [bmesh.new() for _ in col["edificio"]]
    techos, tejas = bmesh.new(), bmesh.new()
    for b in eds:
        k = rnd.randrange(len(paredes))
        zs = [H(x, y) for x, y in b["p"]]
        z0, z1 = min(zs) - 0.3, max(zs) + b["h"]
        casa = b["k"] == "casa" and len(b["p"]) == 4 and b["h"] < 8
        _prism(paredes[k], b["p"], z0, z1)
        if casa and rnd.random() < 0.8:
            _gable(tejas, b["p"], z1, rnd.uniform(0.55, 0.8))
        else:
            # pretil: una franja mas alta en el borde del techo plano
            _prism(techos, b["p"], z1, z1 + 0.12)
    for i, bm in enumerate(paredes):
        _obj(f"entorno_edificios{i}", bm, mat_toon(f"entorno_edificio{i}_m", col["edificio"][i],
                                                    windows=e.get("ventanas")), main)
    _obj("entorno_techos", techos, mat_toon("entorno_techo_m", col["techo"]), main)
    _obj("entorno_tejas", tejas, mat_toon("entorno_teja_m", col["teja"]), main)

    if e.get("faroles"):
        _faroles(calles, H, e["faroles"], colls, R if R < 1e8 else 450)

    # arboles
    if e.get("arboles", True):
        copas = [bmesh.new() for _ in col["copa"]]
        tr = bmesh.new()
        # "quitar_arboles": puntos [x, y] de arboles que se sacan (de relleno que
        # tapan una vista que el plano necesita)
        quitar = {(round(q[0], 1), round(q[1], 1)) for q in e.get("quitar_arboles", [])}
        for x, y, s, src in data["arboles"]:
            if math.hypot(x, y) > R or (not relleno and src == "relleno") or (round(x, 1), round(y, 1)) in quitar:
                continue
            _tree(tr, copas[rnd.randrange(len(copas))], x, y, H(x, y) - 0.2,
                  s * e.get("escala_arboles", 1.3), rnd)
        _obj("entorno_troncos", tr, mat_toon("entorno_tronco_m", col["tronco"]), main)
        for i, bm in enumerate(copas):
            _obj(f"entorno_arboles{i}", bm, mat_toon(f"entorno_copa{i}_m", col["copa"][i]), main, smooth=True)
