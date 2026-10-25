"""Caminito: conventillos de chapa a los dos lados de la calle real (la
polilinea de OSM), el gris que la recorre y el barrido cian que lo trae.

Todo se ubica por s: metros sobre la calle desde la esquina de Garibaldi y
Lamadrid (s = 0) hasta Magallanes (s ~ 140). Las fachadas quedan a "ancho"/2
del eje, cada lote es un frente recto (la cuerda de la curva), con su color
por piso, ventanas con postigos, balcones con baranda de hierro y, en
algunos, la escalera de hierro por fuera que sube al balcon.

El gris: cada material compara s del punto con la propiedad "frente" de su
objeto (animable): lo que queda del lado de s < frente sale gris. El borde va
en bloques (compresion). Con "frente" = -1e4 no hay gris.
"""

import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from piezas import ctx
from piezas.base import lin, link
from piezas.materiales import _emit_out, _fog, _toon_light, mat_tint


from calle import PALETA, PISO, cargar, lotes  # noqa: E402

_CALLE = None


def calle():
    global _CALLE
    if _CALLE is None:
        _CALLE = cargar(ctx.EPISODIO, ctx.CFG.get("caminito", {}).get("datos", "data/entorno.json"))
    return _CALLE


def punto(s, lado=0.0, z=0.0):
    return Vector(calle().punto(s, lado, z))


# ------------------------------------------------------------------ material

def _attr(nt, name, kind):
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_type = kind
    at.attribute_name = name
    return at.outputs["Fac"]


def mat_conventillo(name, color, chapa=True, gris=None):
    """Toon con canaletas de chapa por shader (bump de un seno en z, que se
    apaga con la distancia para no hacer moire) y el gris por "frente": la
    s del punto es su proyeccion sobre la cuerda de la calle."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    n = nt.nodes
    light = _toon_light(nt)
    geo = n.new("ShaderNodeNewGeometry")
    if chapa:
        dif = [x for x in n if x.type == "BSDF_DIFFUSE"][0]
        sep = n.new("ShaderNodeSeparateXYZ")
        nt.links.new(geo.outputs["Position"], sep.inputs[0])
        k = n.new("ShaderNodeMath")
        k.operation = "MULTIPLY"
        k.inputs[1].default_value = 2 * math.pi / 0.076
        nt.links.new(sep.outputs["Z"], k.inputs[0])
        si = n.new("ShaderNodeMath")
        si.operation = "SINE"
        nt.links.new(k.outputs[0], si.inputs[0])
        cam = n.new("ShaderNodeCameraData")
        fade = n.new("ShaderNodeMapRange")
        fade.inputs["From Min"].default_value = 6.0
        fade.inputs["From Max"].default_value = 22.0
        fade.inputs["To Min"].default_value = 1.0
        fade.inputs["To Max"].default_value = 0.0
        nt.links.new(cam.outputs["View Distance"], fade.inputs["Value"])
        bump = n.new("ShaderNodeBump")
        bump.inputs["Distance"].default_value = 0.004
        nt.links.new(si.outputs[0], bump.inputs["Height"])
        nt.links.new(fade.outputs["Result"], bump.inputs["Strength"])
        nt.links.new(bump.outputs["Normal"], dif.inputs["Normal"])
    # s del punto: la de la calle mas cercana, guardada por vertice ("s"). La
    # proyeccion sobre la cuerda se corria varios metros en la curva y el
    # color no volvia detras de la banda
    s_at = _attr(nt, "s", "GEOMETRY")
    # borde en bloques de 0,7 m (compresion): ruido sobre la posicion redondeada
    snap = n.new("ShaderNodeVectorMath")
    snap.operation = "SNAP"
    snap.inputs[1].default_value = (0.7, 0.7, 0.7)
    nt.links.new(geo.outputs["Position"], snap.inputs[0])
    nz = n.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.35
    nt.links.new(snap.outputs[0], nz.inputs["Vector"])
    mr = n.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.3
    mr.inputs["From Max"].default_value = 0.7
    mr.inputs["To Min"].default_value = -2.5
    mr.inputs["To Max"].default_value = 2.5
    nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
    add = n.new("ShaderNodeMath")
    add.operation = "ADD"
    nt.links.new(s_at, add.inputs[0])
    nt.links.new(mr.outputs["Result"], add.inputs[1])
    lt = n.new("ShaderNodeMath")
    lt.operation = "LESS_THAN"
    nt.links.new(add.outputs[0], lt.inputs[0])
    nt.links.new(_attr(nt, "frente", "OBJECT"), lt.inputs[1])
    mix = n.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(lt.outputs[0], mix.inputs["Factor"])
    mix.inputs[6].default_value = lin(color)
    mix.inputs[7].default_value = lin(gris or _gris(color))
    mul = n.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(mix.outputs[2], mul.inputs[6])
    nt.links.new(light, mul.inputs[7])
    _emit_out(nt, _fog(nt, mul.outputs[2]))
    return mat


def _gris(c):
    """El gris comprimido de un color: su luminancia, apenas azulada y sin
    contraste (los claros bajan, los oscuros suben)."""
    c = c.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    y = 0.299 * r + 0.587 * g + 0.114 * b
    y = 120 + (y - 120) * 0.45
    return "#%02x%02x%02x" % (int(y * 0.96), int(y * 0.99), int(min(255, y * 1.05)))


def _s_por_vertice(me):
    """Atributo "s" de cada vertice: la s del punto mas cercano de la calle."""
    C = calle()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    xy = co.reshape(-1, 3)[:, :2]
    out = np.empty(len(xy))
    for a in range(0, len(xy), 2000):
        d = np.linalg.norm(xy[a:a + 2000, None, :] - C.p[None, :, :], axis=2)
        out[a:a + 2000] = C.s[d.argmin(axis=1)]
    at = me.attributes.new("s", "FLOAT", "POINT")
    at.data.foreach_set("value", out.astype(np.float32))


def frente_keys(ob, e):
    """Propiedad "frente" del objeto, cuadro por cuadro desde "barrido"."""
    keys = e.get("barrido", {}).get("keys")
    if not keys:
        ob["frente"] = -1e4
        return
    for f, s in keys:
        ob["frente"] = float(s)
        ob.keyframe_insert('["frente"]', frame=f)
    if ob.animation_data and ob.animation_data.action:
        from piezas.base import set_interp
        set_interp(ob, e.get("barrido", {}).get("interp", "LINEAR"))


# ------------------------------------------------------------------ geometria

class Casa:
    """Una malla en el marco de un frente: u a lo largo de la fachada, v hacia
    adentro del lote (v < 0: hacia la calle), z arriba."""

    def __init__(self, o, U, N):
        self.o, self.U, self.N = Vector(o), Vector(U), Vector(N)
        self.bm = bmesh.new()

    def w(self, u, v, z):
        return self.o + self.U * u + self.N * v + Vector((0, 0, z))

    def caja(self, u0, u1, v0, v1, z0, z1, mi):
        c = [self.w(u, v, z) for z in (z0, z1) for v in (v0, v1) for u in (u0, u1)]
        vs = [self.bm.verts.new(p) for p in c]
        for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            fc = self.bm.faces.new([vs[i] for i in f])
            fc.material_index = mi

    def barra(self, p0, p1, r, mi):
        """Barra de seccion cuadrada entre dos puntos (u, v, z) del marco."""
        a, b = self.w(*p0), self.w(*p1)
        d = (b - a).normalized()
        x = d.cross(Vector((0, 0, 1)))
        if x.length < 1e-3:
            x = self.U.copy()
        x = x.normalized() * r
        y = d.cross(x).normalized() * r
        c = [q + sx * x + sy * y for q in (a, b) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        vs = [self.bm.verts.new(p) for p in c]
        for f in ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
            fc = self.bm.faces.new([vs[i] for i in f])
            fc.material_index = mi


def build_caminito(e, colls):
    """Conventillos a los dos lados, segun el plan de calle.lotes. e:
    {"ancho": 8.0 (entre fachadas), "seed", "desde", "hasta" (s),
    "barrido": {"keys": [[frame, s], ...]}}"""
    C = calle()
    mats, idx = [], {}

    def M(color, chapa=True):
        k = (color, chapa)
        if k not in idx:
            idx[k] = len(mats)
            mats.append(mat_conventillo(f"conv_{color[1:]}_{'c' if chapa else 'm'}", color, chapa))
        return idx[k]

    hierro = M("#2a2733", False)
    vidrio = M("#1d2230", False)
    puerta = M("#5a3a2a", False)
    techo = M("#8a6f62", True)
    obs = []
    plan = lotes(C, e)
    for n_lote, lo in enumerate(plan):
        o = Vector((*lo["o"], 0))
        U = Vector((*lo["U"], 0))
        N = Vector((*lo["N"], 0))
        L = lo["L"]
        casa = Casa(o, U, N)
        if lo["pisos"] == 0:
            # tapial con un mural de un color
            casa.caja(0, L, 0, 0.3, 0, lo["h"], M(lo["mural"], False))
        else:
            pisos, cols, trim, post = lo["pisos"], lo["colores"], lo["trim"], lo["postigos"]
            H = lo["h"]
            for k in range(pisos):
                casa.caja(0, L, 0, 9.0, k * PISO, (k + 1) * PISO, M(cols[k]))
                # cornisa de cada piso
                casa.caja(-0.05, L + 0.05, -0.10, 0.0, (k + 1) * PISO - 0.08, (k + 1) * PISO + 0.06,
                          M(trim, False))
                nv = max(1, int(L / 2.6))
                for j in range(nv):
                    uc = L * (j + 0.5) / nv
                    if k == 0 and j == nv // 2:
                        casa.caja(uc - 0.55, uc + 0.55, -0.04, 0.0, 0.0, 2.3, puerta)
                        casa.caja(uc - 0.65, uc + 0.65, -0.07, 0.0, 2.3, 2.42, M(trim, False))
                        continue
                    z0 = k * PISO + 0.95
                    casa.caja(uc - 0.5, uc + 0.5, -0.03, 0.0, z0, z0 + 1.45, vidrio)
                    for a0, a1 in ((uc - 0.58, uc - 0.5), (uc + 0.5, uc + 0.58)):
                        casa.caja(a0, a1, -0.07, 0.0, z0 - 0.08, z0 + 1.53, M(trim, False))
                    casa.caja(uc - 0.58, uc + 0.58, -0.07, 0.0, z0 + 1.45, z0 + 1.53, M(trim, False))
                    casa.caja(uc - 0.62, uc + 0.62, -0.12, 0.0, z0 - 0.1, z0, M(trim, False))
                    # postigos abiertos contra la chapa
                    for a0 in (uc - 1.1, uc + 0.6):
                        casa.caja(a0, a0 + 0.5, -0.06, -0.02, z0, z0 + 1.45, M(post, False))
            # pretil y techo de chapa
            casa.caja(-0.05, L + 0.05, -0.12, 9.0, H, H + 0.55, M(cols[-1]))
            casa.caja(-0.3, L + 0.3, -0.5, 9.2, H + 0.55, H + 0.65, techo)
            if lo["balcon"]:
                b0, b1 = lo["balcon"]
                zb = PISO
                casa.caja(b0, b1, -1.05, 0.0, zb - 0.12, zb, hierro)
                for u in np.arange(b0, b1 + 1e-6, 0.14):
                    casa.barra((u, -1.02, zb), (u, -1.02, zb + 0.95), 0.012, hierro)
                casa.barra((b0, -1.02, zb + 0.97), (b1, -1.02, zb + 0.97), 0.025, hierro)
                for u in (b0, b1):
                    casa.barra((u, -1.02, zb + 0.97), (u, 0.0, zb + 0.97), 0.025, hierro)
                if lo["escalera"]:
                    # escalera de hierro por fuera: sube por la fachada hasta el balcon
                    ua, ub = (b0 - 2.6, b0) if lo["escalera"] == "izq" else (b1 + 2.6, b1)
                    n = 14
                    for i in range(n):
                        u = ua + (ub - ua) * (i + 0.5) / n
                        z = zb * (i + 1) / n
                        casa.caja(u - 0.11, u + 0.11, -1.0, -0.1, z - 0.04, z, hierro)
                    for v in (-1.0, -0.1):
                        casa.barra((ua, v, 0.0), (ub, v, zb), 0.03, hierro)
                    casa.barra((ua, -1.0, 0.95), (ub, -1.0, zb + 0.95), 0.02, hierro)
                    for i in range(0, n + 1, 3):
                        u = ua + (ub - ua) * i / n
                        z = zb * i / n
                        casa.barra((u, -1.0, z), (u, -1.0, z + 0.95), 0.012, hierro)
        me = bpy.data.meshes.new(f"conventillo_{n_lote:02d}")
        casa.bm.to_mesh(me)
        casa.bm.free()
        _s_por_vertice(me)
        ob = bpy.data.objects.new(me.name, me)
        link(ob, colls["main"])
        frente_keys(ob, e)
        obs.append(ob)
    for ob in obs:
        for m in mats:
            ob.data.materials.append(m)
    global FRENTES
    FRENTES = [dict(lo, o=Vector((*lo["o"], 0)), U=Vector((*lo["U"], 0)), N=Vector((*lo["N"], 0)),
                    b=lo.get("balcon")) for lo in plan]
    if e.get("barrido", {}).get("plano", True) and e.get("barrido", {}).get("keys"):
        _plano_barrido(e, colls)


FRENTES = []


def _plano_barrido(e, colls):
    """La linea del barrido: una cortina cian finita que cruza la calle en
    s = frente, de fachada a fachada, con scanlines."""
    ancho = e.get("ancho", 8.0)
    B = e["barrido"]
    bpy.ops.mesh.primitive_plane_add(size=1.0)
    pl = bpy.context.active_object
    pl.name = "barrido_cian"
    for cl in list(pl.users_collection):
        cl.objects.unlink(pl)
    link(pl, colls["neon"])
    pl.scale = (ancho + 0.4, B.get("alto", 14.0), 1)
    pl.data.materials.append(mat_tint("barrido_m", B.get("color", "#7ff6ff"), B.get("alfa", 0.35)))
    pl.rotation_mode = "XYZ"
    for f, s in B["keys"]:
        p, t, n = calle().at(s)
        pl.location = (p[0], p[1], B.get("alto", 14.0) / 2)
        ang = math.atan2(t[1], t[0])
        pl.rotation_euler = (math.pi / 2, 0, ang + math.pi / 2)
        pl.keyframe_insert("location", frame=f)
        pl.keyframe_insert("rotation_euler", frame=f)
    # "hasta": [f0, f1]: la cortina se apaga (se achata) cuando la alcanzan
    if B.get("hasta"):
        f0, f1 = B["hasta"]
        for f, k in ((f0, 1.0), (f1, 0.0)):
            pl.scale = ((ancho + 0.4) * max(k, 1e-3), B.get("alto", 14.0) * max(k, 1e-3), 1)
            pl.keyframe_insert("scale", frame=f)
