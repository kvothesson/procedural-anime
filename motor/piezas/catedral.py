"""Catedral de San Isidro (Buenos Aires): la geometria base, a escala real.

Planta de OpenStreetMap (way 129970084 y sus partes) llevada al eje de la
nave; alturas del folleto de la parroquia (Oeyen: 60 m de largo, 18,5 de
ancho, 29 en el crucero, 19 m de altura interior, torre de 68,65 m) y de
fotos. Neogotica: cruz latina, tres naves, crucero, coro y abside de cinco
lados; columnas redondas con capitel, arcos apuntados, triforio, ventanales
altos, boveda de cruceria con nervios y espinazo; afuera arbotantes,
pinaculos, balaustradas y una sola torre con aguja al frente.

Ejes: x a lo ancho (0 = eje de la nave), y a lo largo (0 = cara interior del
frente; la torre queda en y < 0 y el abside hacia +y), z = piso interior.
Todo es recorrible: muros con espesor, vanos abiertos, bovedas con
espesor y techos solidos. "techo": false saca techos y bovedas (vista
cenital tipo maqueta).

Solo forma: un gris por familia (piedra, techo, suelo) para leer volumenes.
"""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from .base import lin, link, tint_light
from .materiales import _fog, mat_toon

# ---------------------------------------------------------------- medidas
BAY = 31.6 / 6          # tramo de la nave: 6 tramos hasta el crucero
NB = 6
XC = 4.7                # eje de las columnas (nave central de 9,4 m entre ejes)
XW = 9.35               # cara interior del muro de las naves laterales
TW = 0.8                # espesor de muros exteriores
TN = 0.6                # espesor de los muros de la nave alta
AI = XC - TN / 2        # media luz libre de la nave central (4,4)
Y_CR0, Y_CR1 = 31.6, 40.6           # crucero
XT = 14.6               # cara interior del testero del crucero
Y_AB = 46.6             # centro del abside (fin del coro recto)
Y_TO = -7.2             # frente de la torre

Z_CAP = 7.2             # arranque del capitel de las columnas
Z_ARC = 7.8             # arranque de los arcos formeros y de la boveda lateral
Z_ARC_TOP = 10.9        # clave de los arcos formeros
Z_TRI0, Z_TRI1 = 11.15, 13.0        # triforio
Z_V = 13.2              # arranque de la boveda alta
Z_CROWN = 19.0          # altura interior (folleto)
Z_AISLE_CROWN = 11.0
Z_WALL = 20.8           # coronamiento del muro alto
Z_RIDGE = 28.2          # cumbrera
Z_AISLE_WALL = 10.4     # coronamiento del muro lateral
Z_GROUND = -1.0         # vereda: el templo esta sobre un zocalo con escalinata
TOWER_TOP = 68.65


# ---------------------------------------------------------------- arcos
def arch(half, rise):
    """Perfil de un arco de media luz `half` y flecha `rise` (apuntado si
    rise >= half, rebajado si no). Devuelve (f, g): altura en funcion de la
    distancia al eje y su inversa."""
    if rise >= half - 1e-6:
        d = (rise * rise - half * half) / (2 * half)
        r = half + d

        def f(u):
            u = min(abs(u), half)
            return math.sqrt(max(r * r - (u + d) ** 2, 0.0))

        def g(z):
            z = min(max(z, 0.0), rise)
            return max(math.sqrt(max(r * r - z * z, 0.0)) - d, 0.0)
    else:
        c = (half * half - rise * rise) / (2 * rise)
        r = rise + c

        def f(u):
            u = min(abs(u), half)
            return math.sqrt(max(r * r - u * u, 0.0)) - c

        def g(z):
            z = min(max(z, 0.0), rise)
            return math.sqrt(max(r * r - (z + c) ** 2, 0.0))
    return f, g


def arch_chain(uc, half, v_spring, rise, sill=None, foot=None, n=12):
    """Mitad izquierda de un vano apuntado, de abajo hacia la clave. Con
    `sill` el vano es una ventana (cierra abajo en el eje); con `foot` es una
    puerta (las jambas bajan hasta foot, el borde del muro); sin ninguno es un
    arco abierto que nace en v_spring (el borde del muro)."""
    f, _ = arch(half, rise)
    pts = []
    if sill is not None:
        pts.append((uc, sill))
    if sill is not None or foot is not None:
        pts.append((uc - half, sill if sill is not None else foot))
    pts.append((uc - half, v_spring))
    for i in range(1, n + 1):
        u = -half + half * i / n
        pts.append((uc + u, v_spring + f(u)))
    return pts


def circle_chain(uc, vc, r, n=12):
    """Mitad izquierda de un circulo (rosetón, reloj), de abajo hacia arriba."""
    return [(uc - r * math.sin(math.pi * i / n), vc - r * math.cos(math.pi * i / n)) for i in range(n + 1)]


# ---------------------------------------------------------------- bmesh
class Pieza:
    """Un objeto de malla armado por partes."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.vidrios = []       # contornos 3D de las ventanas cerradas

    def prism(self, poly2, O, U, V, N, t, skip_axis=None):
        """Extruye el poligono 2D (u, v) -> O + U*u + V*v, con espesor t a lo
        largo de N (centrado). skip_axis=u: no hace caras laterales sobre ese
        eje (la costura entre dos mitades de un muro con vano)."""
        O, U, V, N = map(Vector, (O, U, V, N))
        front = [O + U * u + V * v + N * (t / 2) for u, v in poly2]
        back = [O + U * u + V * v - N * (t / 2) for u, v in poly2]
        fv = [self.bm.verts.new(p) for p in front]
        bv = [self.bm.verts.new(p) for p in back]
        for vs in (fv, list(reversed(bv))):
            try:
                self.bm.faces.new(vs)
            except ValueError:
                pass
        k = len(poly2)
        for i in range(k):
            j = (i + 1) % k
            (u0, v0), (u1, v1) = poly2[i], poly2[j]
            if skip_axis is not None and abs(u0 - skip_axis) < 1e-6 and abs(u1 - skip_axis) < 1e-6:
                continue
            if (u0, v0) == (u1, v1):
                continue
            try:
                self.bm.faces.new([fv[i], fv[j], bv[j], bv[i]])
            except ValueError:
                pass

    def wall(self, O, U, N, u0, u1, v0, v1, t, holes=(), vidrio=True):
        """Muro rectangular [u0,u1] x [v0,v1] con vanos sobre su eje central.
        holes: cadenas de arch_chain / circle_chain (mitad izquierda, abajo ->
        arriba), ordenadas de abajo hacia arriba. Se arma en dos mitades
        concavas, sin booleanas. Cada vano cerrado (ventana, roseton) deja
        su contorno en self.vidrios, salvo vidrio=False (campanario, galeria
        ciega)."""
        V = (0, 0, 1)
        if not holes:
            self.prism([(u0, v0), (u1, v0), (u1, v1), (u0, v1)], O, U, V, N, t)
            return
        uc = (u0 + u1) / 2
        left = [(uc, v1), (u0, v1), (u0, v0)]
        if abs(holes[0][0][1] - v0) > 1e-6 or abs(holes[0][0][0] - uc) < 1e-6:
            left.append((uc, v0))
        for h in holes:
            left += h
        right = [(2 * uc - u, v) for u, v in reversed(left)]
        if vidrio:
            Ov, Uv = Vector(O), Vector(U)
            for h in holes:
                if abs(h[0][0] - uc) < 1e-6:
                    full = h + [(2 * uc - u, v) for u, v in reversed(h[1:-1])]
                    self.vidrios.append([Ov + Uv * u + Vector((0, 0, v)) for u, v in full])
        self.prism(left, O, U, V, N, t, skip_axis=uc)
        self.prism(right, O, U, V, N, t, skip_axis=uc)

    def box(self, x0, x1, y0, y1, z0, z1):
        self.prism([(x0, z0), (x1, z0), (x1, z1), (x0, z1)], ((0, (y0 + y1) / 2, 0)),
                   (1, 0, 0), (0, 0, 1), (0, 1, 0), y1 - y0)

    def cyl(self, x, y, z0, z1, r0, r1=None, segs=16, rot=0.0):
        m = Matrix.Translation((x, y, (z0 + z1) / 2)) @ Matrix.Rotation(rot, 4, "Z")
        bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segs,
                              radius1=r0, radius2=r0 if r1 is None else r1,
                              depth=z1 - z0, matrix=m)

    def pinnacle(self, x, y, z0, w, h_shaft, h_spire):
        """Pinaculo: fuste cuadrado y agujita de cuatro caras."""
        self.box(x - w / 2, x + w / 2, y - w / 2, y + w / 2, z0, z0 + h_shaft)
        self.cyl(x, y, z0 + h_shaft, z0 + h_shaft + h_spire, w * 0.75, 0.0, segs=4, rot=math.pi / 4)

    def tube(self, pts, w, h):
        """Nervio: seccion rectangular w x h barrida por una polilinea 3D."""
        pts = [Vector(p) for p in pts]
        rings = []
        for i, p in enumerate(pts):
            a = pts[max(i - 1, 0)]
            b = pts[min(i + 1, len(pts) - 1)]
            T = (b - a).normalized()
            S = T.cross(Vector((0, 0, 1)))
            if S.length < 1e-4:
                S = T.cross(Vector((1, 0, 0)))
            S.normalize()
            Nn = S.cross(T).normalized()
            if Nn.z < 0:
                Nn = -Nn
            # el nervio cuelga de la superficie: casi todo queda por debajo
            c = p - Nn * (h * 0.35)
            rings.append([self.bm.verts.new(c + S * sx * w / 2 + Nn * sz * h / 2)
                          for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
        for r0, r1 in zip(rings, rings[1:]):
            for k in range(4):
                j = (k + 1) % 4
                self.bm.faces.new([r0[k], r0[j], r1[j], r1[k]])
        for r, flip in ((rings[0], True), (rings[-1], False)):
            self.bm.faces.new(list(reversed(r)) if flip else r)

    def done(self, mat, coll, weld=True, solidify=0.0):
        if weld:
            bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-4)
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        me = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(me)
        self.bm.free()
        ob = bpy.data.objects.new(self.name, me)
        ob.data.materials.append(mat)
        if solidify:
            m = ob.modifiers.new("espesor", "SOLIDIFY")
            m.thickness = solidify
            m.offset = 0.0
        link(ob, coll)
        return ob


# ---------------------------------------------------------------- bovedas
def vault_rect(vb, rb, cx, cy, a, b, zs, H, n=14, ribs=("diag", "ridge"), axis_long="y"):
    """Boveda de cruceria sobre el rectangulo cx±a, cy±b: el techo es el
    maximo de dos canones apuntados que llegan a la misma clave (aristas
    donde se cruzan, y ahi van los nervios diagonales). axis_long: el eje del
    canon principal (el espinazo corre por ahi)."""
    if axis_long == "x":
        # se arma en ejes locales y se gira: u a lo ancho, v a lo largo
        def P(u, v, z):
            return (cx + v, cy + u, z)
        a, b = b, a
    else:
        def P(u, v, z):
            return (cx + u, cy + v, z)
    fa, ga = arch(a, H)       # canon principal (corte transversal)
    fb, gb = arch(b, H)       # canon cruzado (corte longitudinal)
    # sector de muro (cerca de u = ±a): z = fb(v), u entre la arista y el muro
    for su in (-1, 1):
        rows = []
        for i in range(n + 1):
            v = -b + 2 * b * i / n
            z = fb(v)
            ug = ga(z)
            rows.append([P(su * (ug + (a - ug) * j / n), v, zs + z) for j in range(n + 1)])
        _grid(vb, rows)
    for sv in (-1, 1):
        rows = []
        for i in range(n + 1):
            u = -a + 2 * a * i / n
            z = fa(u)
            vg = gb(z)
            rows.append([P(u, sv * (vg + (b - vg) * j / n), zs + z) for j in range(n + 1)])
        _grid(vb, rows)
    if rb is None:
        return
    if "diag" in ribs:
        for su in (-1, 1):
            for sv in (-1, 1):
                pts = []
                for k in range(n + 1):
                    z = H * k / n
                    pts.append(P(su * ga(z), sv * gb(z), zs + z))
                rb.tube(pts, 0.22, 0.28)
    if "ridge" in ribs:
        rb.tube([P(0, -b, zs + H), P(0, b, zs + H)], 0.2, 0.22)
    if "wall" in ribs:
        for su in (-1, 1):
            rb.tube([P(su * a, -b + 2 * b * k / n, zs + fb(-b + 2 * b * k / n)) for k in range(n + 1)], 0.18, 0.2)


def transverse_rib(rb, cx, y, a, zs, H, n=16, along="x"):
    """Arco fajon: el arco que separa dos tramos, con el perfil del canon."""
    f, _ = arch(a, H)
    pts = []
    for k in range(n + 1):
        u = -a + 2 * a * k / n
        pts.append((cx + u, y, zs + f(u)) if along == "x" else (y, cx + u, zs + f(u)))
    rb.tube(pts, 0.32, 0.36)


def _grid(pc, rows):
    vs = [[pc.bm.verts.new(p) for p in row] for row in rows]
    for i in range(len(vs) - 1):
        for j in range(len(vs[i]) - 1):
            q = [vs[i][j], vs[i][j + 1], vs[i + 1][j + 1], vs[i + 1][j]]
            # los sectores son triangulos: el borde de la esquina degenera
            if (q[0].co - q[1].co).length < 1e-5 and (q[3].co - q[2].co).length < 1e-5:
                continue
            try:
                pc.bm.faces.new(q)
            except ValueError:
                pass


def apse_pts(r, n=5, cy=Y_AB):
    """Vertices del abside: medio decagono desde x = +r hasta x = -r."""
    return [(r * math.cos(math.pi * k / n), cy + r * math.sin(math.pi * k / n)) for k in range(n + 1)]


def vault_apse(vb, rb, r, zs, H, n=10):
    """Boveda del abside: un pano por lado que sube del arco del muro a la
    clave en el centro, con nervios radiales."""
    V = apse_pts(r)
    C = Vector((0, Y_AB))
    for i in range(len(V) - 1):
        A, B = Vector(V[i]), Vector(V[i + 1])
        half = (B - A).length / 2
        fw, _ = arch(half, H)
        rows = []
        for j in range(n + 1):
            t = j / n
            row = []
            for k in range(n + 1):
                w = k / n
                p = (A.lerp(B, w)).lerp(C, t)
                z = (1 - t) * fw((w - 0.5) * 2 * half) + H * math.sqrt(max(t * (2 - t), 0.0)) * t
                row.append((p.x, p.y, zs + z))
            rows.append(row)
        _grid(vb, rows)
    if rb is None:
        return
    for k in range(len(V)):
        A = Vector(V[k])
        pts = []
        for j in range(n + 1):
            t = j / n
            p = A.lerp(C, t)
            pts.append((p.x, p.y, zs + H * math.sqrt(max(t * (2 - t), 0.0)) * t))
        rb.tube(pts, 0.22, 0.28)


# ---------------------------------------------------------------- piezas
def _columns(pc):
    """Columnas de la nave: base ochavada, fuste redondo, capitel acampanado
    con abaco; del lado de la nave sube un baquetón hasta la boveda alta."""
    def column(x, y, ext=True):
        pc.cyl(x, y, 0.0, 0.25, 0.75, segs=8, rot=math.pi / 8)
        pc.cyl(x, y, 0.25, 0.75, 0.62, 0.5, segs=8, rot=math.pi / 8)
        pc.cyl(x, y, 0.75, Z_CAP, 0.45)
        pc.cyl(x, y, Z_CAP, Z_ARC - 0.18, 0.47, 0.72)
        pc.box(x - 0.68, x + 0.68, y - 0.68, y + 0.68, Z_ARC - 0.18, Z_ARC)
        if ext:
            sx = -1 if x > 0 else 1
            xs = x + sx * 0.45
            pc.cyl(xs, y, Z_ARC, Z_V - 0.35, 0.13, segs=8)
            pc.cyl(xs, y, Z_V - 0.35, Z_V, 0.14, 0.3, segs=8)

    for sx in (-1, 1):
        for k in range(1, NB):
            column(sx * XC, k * BAY)
        # pilares del crucero: mas gruesos, hasta la boveda alta
        for y in (Y_CR0, Y_CR1):
            x = sx * XC
            pc.cyl(x, y, 0.0, 0.3, 1.0, segs=8, rot=math.pi / 8)
            pc.cyl(x, y, 0.3, Z_V - 0.6, 0.72)
            pc.cyl(x, y, Z_V - 0.6, Z_V, 0.74, 0.95)
        # medias columnas adosadas al frente
        pc.cyl(sx * XC, 0.15, 0.75, Z_CAP, 0.45)
        pc.cyl(sx * XC, 0.15, Z_CAP, Z_ARC, 0.47, 0.72)
    # columnas del coro alto
    for sx in (-1, 1):
        pc.cyl(sx * 2.6, 2.2, 0.0, 6.0, 0.22, segs=12)


def _nave_walls(pc):
    """Muros de la nave alta, tramo por tramo: arco formero abierto abajo,
    ventanal arriba (las bovedas laterales y el triforio van aparte)."""
    for sx in (-1, 1):
        x = sx * XC
        N = (1, 0, 0)
        for k in range(NB):
            y0, y1 = k * BAY, (k + 1) * BAY
            ym = (y0 + y1) / 2
            hs = BAY / 2 - 0.45
            holes = [arch_chain(ym, hs, Z_ARC, Z_ARC_TOP - Z_ARC),
                     arch_chain(ym, 0.75, 16.2, 1.45, sill=13.9)]
            pc.wall((x, 0, 0), (0, 1, 0), N, y0, y1, Z_ARC, Z_WALL, TN, holes)
        # cornisa del triforio a lo largo, con su antepecho
        xin = x - sx * TN / 2
        x0, x1 = sorted((xin, xin - sx * 0.3))
        pc.box(x0, x1, 0.0, Y_CR0, Z_TRI0 - 0.25, Z_TRI0)
        # galeria ciega: arquitos sobre columnillas, delante del muro
        xs = x - sx * (TN / 2 + 0.12)
        for k in range(NB):
            y0 = k * BAY
            n = 4
            w = BAY / n
            for j in range(n):
                a = y0 + j * w
                pc.wall((xs, 0, 0), (0, 1, 0), N, a, a + w, Z_TRI0, Z_TRI1, 0.14,
                        [arch_chain(a + w / 2, w / 2 - 0.12, Z_TRI1 - 0.75, 0.55, sill=Z_TRI0 + 0.55)],
                        vidrio=False)


def _choir_walls(pc):
    """Coro recto (dos muros altos con ventana baja y ventanal) y abside."""
    for sx in (-1, 1):
        x = sx * XC
        holes = [arch_chain((Y_CR1 + Y_AB) / 2, 0.75, 6.0, 1.3, sill=2.4),
                 arch_chain((Y_CR1 + Y_AB) / 2, 0.75, 16.2, 1.45, sill=13.9)]
        pc.wall((x, 0, 0), (0, 1, 0), (1, 0, 0), Y_CR1, Y_AB, 0.0, Z_WALL, TN, holes)
    Vc = apse_pts(XC)
    for i in range(len(Vc) - 1):
        A, B = Vector(Vc[i] + (0,)), Vector(Vc[i + 1] + (0,))
        U = (B - A)
        L = U.length
        U.normalize()
        N = U.cross(Vector((0, 0, 1)))
        holes = [arch_chain(L / 2, 0.55, 6.2, 1.2, sill=2.2),
                 arch_chain(L / 2, 0.6, 16.0, 1.4, sill=13.6)]
        # se estira un poco para cerrar las juntas del poligono
        pc.wall(A - U * 0.25, U, N, 0.0, L + 0.5, 0.0, Z_WALL, TN,
                [[(u + 0.25, v) for u, v in h] for h in holes])


def _outer_walls(pc):
    """Muros perimetrales: naves laterales con ventanas, testeros del
    crucero con su ventanal y puerta, muros este y oeste de los brazos."""
    for sx in (-1, 1):
        x = sx * (XW + TW / 2)
        for k in range(NB):
            y0, y1 = k * BAY, (k + 1) * BAY
            ym = (y0 + y1) / 2
            pc.wall((x, 0, 0), (0, 1, 0), (1, 0, 0), y0, y1, 0.0, Z_AISLE_WALL, TW,
                    [arch_chain(ym, 0.7, 7.3, 1.25, sill=2.3)])
        # testero del crucero: puerta, ventanal grande y hastial
        xt = sx * (XT + TW / 2)
        holes = [arch_chain(36.1, 1.0, 3.3, 1.3, foot=0.0),
                 arch_chain(36.1, 2.1, 15.0, 3.4, sill=8.8)]
        pc.wall((xt, 0, 0), (0, 1, 0), (1, 0, 0), Y_CR0 - 0.3, Y_CR1 + 0.3, 0.0, Z_WALL, TW, holes)
        pc.prism([(Y_CR0 - 0.3, Z_WALL), (Y_CR1 + 0.3, Z_WALL), (36.1, Z_RIDGE + 0.6)],
                 (xt, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), TW)
        # brazos: muro oeste (sobre la nave lateral, y entero mas alla) y este
        xa0, xa1 = sx * (XW + TW), sx * (XT + TW)
        lo, hi = min(xa0, xa1), max(xa0, xa1)
        um = (lo + hi) / 2
        for y, holes in ((Y_CR0, [arch_chain(um, 0.85, 15.6, 1.6, sill=11.4)]),
                         (Y_CR1, [arch_chain(um, 1.0, 3.6, 1.2, foot=0.0),
                                  arch_chain(um, 0.85, 15.6, 1.6, sill=11.4)])):
            pc.wall((0, y, 0), (1, 0, 0), (0, 1, 0), lo, hi, 0.0, Z_WALL, TN, holes)
        # sobre la nave lateral, del lado del crucero: arco abierto y ventanal
        lo, hi = sorted((sx * (XC + TN / 2), sx * (XW + TW)))
        um = (lo + hi) / 2
        pc.wall((0, Y_CR0, 0), (1, 0, 0), (0, 1, 0), lo, hi, Z_ARC, Z_WALL, TN,
                [arch_chain(um, (hi - lo) / 2 - 0.3, Z_ARC, 2.4)])
        # del lado del coro el brazo cierra entero (detras estan los anexos)
        lo, hi = sorted((sx * (XC + TN / 2), sx * (XW + TW)))
        um = (lo + hi) / 2
        pc.wall((0, Y_CR1, 0), (1, 0, 0), (0, 1, 0), lo, hi, 0.0, Z_WALL, TN,
                [arch_chain(um, 0.9, 3.4, 1.2, foot=0.0)])
        # frente de las naves laterales: muro con ventana y remate inclinado
        lo, hi = sorted((sx * 5.0, sx * (XW + TW)))
        um = (lo + hi) / 2
        pc.wall((0, -TW / 2, 0), (1, 0, 0), (0, 1, 0), lo, hi, 0.0, Z_AISLE_WALL + 1.0, TW,
                [arch_chain(um, 0.65, 8.0, 1.2, sill=2.6)])
        top_out, top_in = Z_AISLE_WALL + 1.0, 13.8
        pts = [(sx * 5.0, Z_AISLE_WALL + 1.0), (sx * (XW + TW), Z_AISLE_WALL + 1.0),
               (sx * (XW + TW), top_out), (sx * 5.0, top_in)]
        if sx < 0:
            pts = list(reversed(pts))
        pc.prism([p for i, p in enumerate(pts) if i != 2], (0, -TW / 2, 0), (1, 0, 0), (0, 0, 1),
                 (0, 1, 0), TW)


def _tower(pc):
    """Torre-porch: cuerpo cuadrado con portada honda, gablete y rosetón;
    campanario con tres lancetas por cara; reloj; linterna ochavada y aguja.
    Contrafuertes escalonados en las esquinas, rematados en pinaculos."""
    W = 5.0                      # media ancho exterior
    T = 1.0
    yf, yb = Y_TO, 0.0
    ym = (yf + yb) / 2
    BODY = 28.0
    # frente: portada abierta y rosetón
    pc.wall((0, yf + 0.6, 0), (1, 0, 0), (0, 1, 0), -W, W, 0.0, BODY, 1.2,
            [arch_chain(0.0, 1.7, 7.0, 3.4, foot=0.0), circle_chain(0.0, 20.5, 2.6)])
    # derrame de la portada: dos arquivoltas que se abren hacia afuera
    for k, (half, rise, d) in enumerate(((2.25, 4.0, 0.45), (2.8, 4.6, 0.45))):
        pc.wall((0, yf - d * (k + 0.5), 0), (1, 0, 0), (0, 1, 0), -half - 0.55, half + 0.55, 0.0,
                7.0 + rise + 0.6, d, [arch_chain(0.0, half, 7.0, rise, foot=0.0)])
    # gablete sobre la portada
    pc.prism([(-3.9, 11.4), (3.9, 11.4), (0.0, 17.2)], (0, yf - 0.9, 0), (1, 0, 0), (0, 0, 1),
             (0, 1, 0), 0.5)
    # costados con ventanitas y muro de fondo abierto a la nave
    for sx in (-1, 1):
        pc.wall((sx * (W - T / 2), 0, 0), (0, 1, 0), (1, 0, 0), yf, yb, 0.0, BODY, T,
                [arch_chain(ym, 0.45, 3.6, 0.7, sill=1.6), arch_chain(ym, 0.55, 17.5, 0.9, sill=14.0)])
    pc.wall((0, -0.35, 0), (1, 0, 0), (0, 1, 0), -W + T, W - T, 0.0, BODY, 0.7,
            [arch_chain(0.0, 3.4, 8.6, 3.6, foot=0.0)])
    # coro alto (sobre el vestibulo, asoma a la nave) con antepecho
    pc.box(-AI, AI, yf + 1.2, 2.4, 5.8, 6.2)
    pc.box(-AI, AI, 2.25, 2.4, 6.2, 7.2)
    # entrepisos de la torre
    for z in (BODY - 0.4,):
        pc.box(-W, W, yf, yb, z, z + 0.4)
    # cornisa y balaustrada del cuerpo
    pc.box(-W - 0.3, W + 0.3, yf - 0.3, yb, BODY, BODY + 0.4)
    for sx in (-1, 1):
        pc.box(sx * (W + 0.3) - 0.15, sx * (W + 0.3) + 0.15, yf - 0.3, yb, BODY + 0.4, BODY + 1.3)
    pc.box(-W - 0.3, W + 0.3, yf - 0.3, yf - 0.0, BODY + 0.4, BODY + 1.3)
    # campanario: cuatro caras con tres lancetas
    Wb, z0, z1 = 4.2, BODY + 0.4, 41.0
    yc = ym
    for face in range(4):
        ang = math.pi / 2 * face
        U = Vector((math.cos(ang), math.sin(ang), 0))
        N = Vector((math.sin(ang), -math.cos(ang), 0))
        O = Vector((0, yc, 0)) + N * (Wb - 0.3)
        w = 2 * Wb / 3
        for j in range(3):
            a = -Wb + j * w
            pc.wall(O, U, N, a, a + w, z0, z1, 0.6, [arch_chain(a + w / 2, 0.5, 37.0, 1.4, sill=30.0)],
                    vidrio=False)
    # reloj
    pc.box(-3.7, 3.7, yc - 3.7, yc + 3.7, z1, 46.0)
    pc.box(-4.4, 4.4, yc - 4.4, yc + 4.4, z1, z1 + 0.5)
    for face in range(4):
        ang = math.pi / 2 * face
        d = Vector((math.sin(ang), -math.cos(ang), 0)) * 3.75
        m = Matrix.Translation((d.x, yc + d.y, 43.6)) @ Matrix.Rotation(ang, 4, "Z") \
            @ Matrix.Rotation(math.pi / 2, 4, "X")
        bmesh.ops.create_cone(pc.bm, cap_ends=True, segments=24, radius1=1.25, radius2=1.25,
                              depth=0.12, matrix=m)
    # linterna ochavada y aguja
    pc.cyl(0, yc, 46.0, 52.0, 3.1, 2.9, segs=8, rot=math.pi / 8)
    pc.cyl(0, yc, 52.0, 52.4, 3.4, 3.4, segs=8, rot=math.pi / 8)
    pc.cyl(0, yc, 52.4, TOWER_TOP - 1.4, 3.0, 0.15, segs=8, rot=math.pi / 8)
    # lucarnas al pie de la aguja
    for face in range(4):
        ang = math.pi / 2 * face
        U = Vector((math.cos(ang), math.sin(ang), 0))
        N = Vector((math.sin(ang), -math.cos(ang), 0))
        O = Vector((0, yc, 0)) + N * 2.6
        pc.prism([(-0.7, 52.4), (0.7, 52.4), (0.7, 54.2), (0.0, 55.6), (-0.7, 54.2)], O, U,
                 (0, 0, 1), N, 1.0)
    # cruz
    pc.box(-0.06, 0.06, yc - 0.06, yc + 0.06, TOWER_TOP - 1.4, TOWER_TOP)
    pc.box(-0.4, 0.4, yc - 0.06, yc + 0.06, TOWER_TOP - 0.75, TOWER_TOP - 0.6)
    # contrafuertes escalonados en las esquinas del frente y pinaculos
    for sx in (-1, 1):
        for front, (y0, y1) in ((True, (yf, yf + 1.4)), (False, (yb - 2.2, yb))):
            for (z0, z1, g) in ((Z_GROUND, 12, 1.3), (12, 24, 1.0), (24, BODY + 1.3, 0.7)):
                xa = sx * W
                pc.box(min(xa, xa + sx * g), max(xa, xa + sx * g), y0 - (g if front else 0), y1, z0, z1)
        for yy in (yf + 0.2, yb - 1.1):
            pc.pinnacle(sx * (W + 0.35), yy, BODY + 1.3, 0.75, 2.2, 3.0)
        for yy in (yc - 3.9, yc + 3.9):
            pc.pinnacle(sx * 3.9, yy, z1 + 0.5, 0.8, 4.2, 4.6)


def _buttresses(pc):
    """Contrafuertes de las naves laterales con pinaculo, arbotantes hasta
    el muro alto, pinaculitos sobre el muro alto y balaustradas."""
    xo = XW + TW
    for sx in (-1, 1):
        for k in range(NB + 1):
            y = k * BAY
            if k == NB:
                y -= 0.6
            x0, x1 = sorted((sx * xo, sx * (xo + 1.5)))
            pc.box(x0, x1, y - 0.5, y + 0.5, Z_GROUND, Z_AISLE_WALL + 0.6)
            pc.pinnacle(sx * (xo + 0.55), y, Z_AISLE_WALL + 0.6, 0.85, 2.6, 3.0)
            # arbotante: un arco rampante del contrafuerte al muro alto
            if 0 < k < NB:
                a = Vector((sx * (xo + 0.2), y, Z_AISLE_WALL + 2.4))
                b = Vector((sx * (XC + TN / 2), y, 17.2))
                pts = []
                for i in range(11):
                    t = i / 10
                    p = a.lerp(b, t)
                    p.z += math.sin(math.pi * t) * 0.9
                    pts.append(tuple(p))
                pc.tube(pts, 0.45, 0.7)
            # pinaculo sobre el muro alto
            if k < NB:
                pc.pinnacle(sx * (XC + 0.1), y, Z_WALL + 1.0, 0.6, 1.4, 2.0)
        # balaustrada de las naves laterales y del muro alto
        x0, x1 = sorted((sx * (xo - 0.15), sx * (xo - 0.45)))
        pc.box(x0, x1, -TW, Y_CR0 - 0.3, Z_AISLE_WALL, Z_AISLE_WALL + 1.0)
        x0, x1 = sorted((sx * (XC + TN / 2), sx * (XC + TN / 2 - 0.3)))
        pc.box(x0, x1, -0.6, Y_AB, Z_WALL, Z_WALL + 1.0)
        # torrecillas de las esquinas
        pc.cyl(sx * (xo + 0.1), -TW - 0.1, Z_GROUND, 13.0, 0.7, segs=8, rot=math.pi / 8)
        pc.cyl(sx * (xo + 0.1), -TW - 0.1, 13.0, 16.5, 0.7, 0.0, segs=8, rot=math.pi / 8)
        for y in (Y_CR0 - 0.3, Y_CR1 + 0.3):
            xx = sx * (XT + TW + 0.1)
            pc.cyl(xx, y, Z_GROUND, 23.5, 0.75, segs=8, rot=math.pi / 8)
            pc.cyl(xx, y, 23.5, 28.5, 0.75, 0.0, segs=8, rot=math.pi / 8)
    # contrafuertes del abside
    Vo = apse_pts(XC + TN / 2)
    for i in range(1, len(Vo) - 1):
        x, y = Vo[i]
        ang = math.atan2(y - Y_AB, x)
        m = Matrix.Translation((x + math.cos(ang) * 0.6, y + math.sin(ang) * 0.6, (Z_GROUND + 18.0) / 2)) \
            @ Matrix.Rotation(ang, 4, "Z")
        bmesh.ops.create_cube(pc.bm, size=1.0, matrix=m @ Matrix.Diagonal((1.4, 0.8, 18.0 - Z_GROUND, 1)))
        pc.pinnacle(x + math.cos(ang) * 0.6, y + math.sin(ang) * 0.6, 18.0, 0.7, 2.0, 3.0)


def _roofs(pc):
    """Techos: dos aguas sobre la nave y el crucero, medio cono ochavado
    sobre el abside, pendiente simple sobre las naves laterales."""
    hw = XC + TN / 2 + 0.2
    pc.prism([(-hw, Z_WALL), (hw, Z_WALL), (0.0, Z_RIDGE)], (0, (Y_AB - 0.6) / 2, 0), (1, 0, 0),
             (0, 0, 1), (0, 1, 0), Y_AB + 0.6)
    yc = (Y_CR0 + Y_CR1) / 2
    hy = (Y_CR1 - Y_CR0) / 2 + 0.5
    pc.prism([(yc - hy, Z_WALL), (yc + hy, Z_WALL), (yc, Z_RIDGE)], (0, 0, 0), (0, 1, 0),
             (0, 0, 1), (1, 0, 0), 2 * (XT + TW))
    # abside
    Vo = apse_pts(hw)
    apex = pc.bm.verts.new((0, Y_AB, Z_RIDGE))
    base = [pc.bm.verts.new((x, y, Z_WALL)) for x, y in Vo]
    for a, b in zip(base, base[1:]):
        pc.bm.faces.new([a, b, apex])
    pc.bm.faces.new(list(reversed(base)))
    pc.bm.faces.new([base[0], apex, base[-1]])
    # naves laterales
    for sx in (-1, 1):
        x_out, x_in = sx * (XW + TW), sx * (XC + TN / 2)
        # losa inclinada, no cuna: la boveda lateral sube por encima del
        # coronamiento del muro y una cuna llena la cortaba por dentro
        pts = [(x_out, Z_AISLE_WALL), (x_in, 13.0), (x_in, 13.35), (x_out, Z_AISLE_WALL + 0.35)]
        if sx < 0:
            pts.reverse()
        pc.prism(pts, (0, (Y_CR0 - TW) / 2, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), Y_CR0 + TW)


def _vaults(vb, rb):
    H = Z_CROWN - Z_V
    for k in range(NB):
        cy = (k + 0.5) * BAY
        vault_rect(vb, rb, 0.0, cy, AI, BAY / 2, Z_V, H, ribs=("diag", "ridge", "wall"))
        for sx in (-1, 1):
            a = (XW - (XC + TN / 2)) / 2
            vault_rect(vb, rb, sx * (XC + TN / 2 + a), cy, a, BAY / 2, Z_ARC, Z_AISLE_CROWN - Z_ARC,
                       ribs=("diag",))
    for k in range(NB + 1):
        transverse_rib(rb, 0.0, k * BAY, AI, Z_V, H)
        for sx in (-1, 1):
            a = (XW - (XC + TN / 2)) / 2
            transverse_rib(rb, sx * (XC + TN / 2 + a), k * BAY, a, Z_ARC, Z_AISLE_CROWN - Z_ARC)
    # crucero, brazos, coro
    yc = (Y_CR0 + Y_CR1) / 2
    hb = (Y_CR1 - Y_CR0) / 2
    vault_rect(vb, rb, 0.0, yc, AI, hb, Z_V, H, ribs=("diag", "ridge"))
    rb.tube([(-AI, yc, Z_CROWN), (AI, yc, Z_CROWN)], 0.2, 0.22)
    for sx in (-1, 1):
        a = (XT - AI) / 2
        vault_rect(vb, rb, sx * (AI + a), yc, a, hb - 0.3, Z_V, H, ribs=("diag", "ridge"), axis_long="x")
        transverse_rib(rb, yc, sx * AI, hb, Z_V, H, along="y")
    transverse_rib(rb, 0.0, Y_CR1, AI, Z_V, H)
    vault_rect(vb, rb, 0.0, (Y_CR1 + Y_AB) / 2, AI, (Y_AB - Y_CR1) / 2, Z_V, H,
               ribs=("diag", "ridge", "wall"))
    transverse_rib(rb, 0.0, Y_AB, AI, Z_V, H)
    vault_apse(vb, rb, AI, Z_V, H)


def _floor(pc, ground):
    """Zocalo y piso interior, escalinata al frente, presbiterio elevado."""
    zg = Z_GROUND
    pc.box(-(XW + TW), XW + TW, Y_TO, Y_CR0, zg, 0.0)
    pc.box(-(XT + TW), XT + TW, Y_CR0 - 0.3, Y_CR1 + 0.3, zg, 0.0)
    pc.box(-(XC + TN / 2), XC + TN / 2, Y_CR1, Y_AB, zg, 0.0)
    Vo = apse_pts(XC + TN / 2)
    pc.prism([(x, y) for x, y in Vo], (0, 0, (zg + 0.0) / 2), (1, 0, 0), (0, 1, 0), (0, 0, 1), -zg)
    # escalinata
    n = 5
    yp = Y_TO - 1.4
    pc.box(-6.5, 6.5, yp, Y_TO, zg, 0.0)
    for i in range(n):
        z1 = zg + (i + 1) * (-zg) / n
        pc.box(-6.5, 6.5, yp - (n - i) * 0.4, yp, zg, z1)
    # presbiterio: tarima de tres escalones y altar
    for i, (y0, z1) in enumerate(((37.4, 0.18), (37.8, 0.36), (38.2, 0.54))):
        pc.box(-AI, AI, y0, Y_AB, 0.0, z1)
    Vi = apse_pts(AI)
    pc.prism([(x, y) for x, y in Vi], (0, 0, 0.27), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.54)
    pc.box(-1.3, 1.3, 42.0, 43.2, 0.54, 1.5)
    if ground:
        g = ground / 2
        pc.box(-g, g, 20 - g, 20 + g, zg - 0.2, zg)


def _annexes(pc, roof):
    """Sacristia, capilla del Santisimo y casa parroquial, alrededor del
    abside (bloques simples a dos aguas, como en el plano de OSM)."""
    blocks = [(5.0, 11.6, 41.0, 52.2, 8.5), (-12.9, -5.0, 41.0, 52.2, 8.5),
              (-12.9, 11.6, 52.2, 56.7, 8.5), (-12.9, 11.6, 56.7, 64.3, 11.0)]
    for x0, x1, y0, y1, h in blocks:
        pc.box(x0, x1, y0, y1, Z_GROUND, h)
        # cumbrera a lo largo del lado mayor
        if (x1 - x0) > (y1 - y0):
            ymid, hy = (y0 + y1) / 2, (y1 - y0) / 2
            roof.prism([(ymid - hy, h), (ymid + hy, h), (ymid, h + hy * 0.9)], ((x0 + x1) / 2, 0, 0),
                       (0, 1, 0), (0, 0, 1), (1, 0, 0), x1 - x0)
        else:
            xm, hx = (x0 + x1) / 2, (x1 - x0) / 2
            roof.prism([(xm - hx, h), (xm + hx, h), (xm, h + hx * 0.9)], (0, (y0 + y1) / 2, 0),
                       (1, 0, 0), (0, 0, 1), (0, 1, 0), y1 - y0)


def mat_vitral(name, v):
    """Vitral: mosaico de celdas de color con plomo oscuro entre ellas, por
    coordenadas del mundo (sin UV): sirve igual en cualquier ventana. Emite
    con fuerza v["fuerza"]: de noche es la luz de afuera, de dia el sol."""
    colors = v.get("colores", ["#b9c3cc"])
    cw, ch = v.get("celda", [0.32, 0.45])
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

    geo = n.new("ShaderNodeNewGeometry")
    sep = n.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])
    a = m("DIVIDE", m("ADD", sep.outputs[0], sep.outputs[1]), cw)
    b = m("DIVIDE", sep.outputs[2], ch)
    cell = n.new("ShaderNodeCombineXYZ")
    L.new(m("FLOOR", a), cell.inputs[0])
    L.new(m("FLOOR", b), cell.inputs[1])
    noise = n.new("ShaderNodeTexWhiteNoise")
    noise.noise_dimensions = "3D"
    L.new(cell.outputs[0], noise.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    while len(els) < len(colors):
        els.new(0.5)
    for k, (el, c) in enumerate(zip(els, colors)):
        el.position = k / len(colors)
        el.color = lin(c)
    L.new(noise.outputs["Value"], ramp.inputs["Fac"])
    lead = v.get("plomo_ancho", 0.09)
    plomo = m("MAXIMUM", m("LESS_THAN", m("FRACT", a), lead), m("LESS_THAN", m("FRACT", b), lead))
    mix = n.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    L.new(plomo, mix.inputs["Factor"])
    L.new(ramp.outputs["Color"], mix.inputs[6])
    mix.inputs[7].default_value = lin(v.get("plomo", "#1a1a22"))
    em = n.new("ShaderNodeEmission")
    L.new(_fog(nt, mix.outputs[2]), em.inputs["Color"])
    em.inputs["Strength"].default_value = v.get("fuerza", 1.0)
    out = n.new("ShaderNodeOutputMaterial")
    L.new(em.outputs[0], out.inputs["Surface"])
    return mat


def _vidrios(piezas, mat, coll):
    pc = Pieza("catedral_vidrios")
    for src in piezas:
        for pts in src.vidrios:
            vs = [pc.bm.verts.new(p) for p in pts]
            try:
                pc.bm.faces.new(vs)
            except ValueError:
                pass
    ob = pc.done(mat, coll, weld=False)
    # el vidrio no lleva tinta propia: el borde del vano ya la tiene
    ob.lineart.usage = "EXCLUDE"
    return ob


def _luz_vitrales(vidrios, v, luz, colls):
    """La luz que entra por los ventanales altos: un punto sin sombra por
    ventana, un poco hacia adentro, con el color de su vitral. Tine las
    bovedas y el triforio (si no, de noche la arquitectura se pierde)."""
    colors = v.get("colores", ["#ffffff"])
    k = 0
    for pts in vidrios:
        c = sum(pts, Vector()) / len(pts)
        if c.z < luz.get("desde_z", 10.0) or c.y < -1.0:
            continue
        inward = Vector((-c.x, 0, 0)).normalized() if abs(c.x) > 0.5 else Vector((0, -1, 0))
        if abs(c.x) < 0.5 and c.y > Y_AB - 0.5:
            inward = Vector((0, -1, 0))
        tint_light(f"vitral_luz{k}", colors[k % len(colors)], luz.get("energia", 150),
                   tuple(c + inward * luz.get("adentro", 1.6) - Vector((0, 0, 0.5))), colls)
        k += 1


def _puertas(e, mat, coll):
    """Las dos hojas de la portada (vano de 3,4 m con arco apuntado), con la
    bisagra en cada jamba, cerca de la cara interior del muro. Se abren hacia
    adentro: e["abre"] = [[frame, grados], ...] (sin claves, cerradas)."""
    half, spring, rise = 1.68, 7.0, 3.4
    chain = arch_chain(0.0, half, spring, rise, foot=0.0)
    keys = e.get("abre", [[1, 0]])
    for sx, name in ((-1, "i"), (1, "d")):
        pc = Pieza(f"catedral_puerta_{name}")
        # en coordenadas de la hoja: x desde la bisagra hacia el centro del vano
        poly = [((u + half) * -sx, v) for u, v in chain] + [(half * -sx, 0.0)]
        if sx > 0:
            poly.reverse()
        pc.prism(poly, (0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), 0.12)
        ob = pc.done(mat, coll)
        ob.location = (sx * 1.7, Y_TO + 1.05, 0.0)
        for f, deg in keys:
            # la izquierda gira antihorario y la derecha horario: las dos hacia +y
            ob.rotation_euler = (0, 0, math.radians(-sx * deg))
            ob.keyframe_insert("rotation_euler", frame=f)


def build_catedral(e, colls):
    """e: {"techo": true, "anexos": true, "suelo": 240, "colores": {...},
    "vidrios": {...} (ver mat_vitral; false = vanos abiertos),
    "reflectores": [{"at": [x, y, z], "color": "#...", "energia": W,
    "apunta": [x, y, z] (cono; sin esto, luz puntual), "abre": grados}],
    "brillos": [{"kind": "point", "at": [x, y, z], "color", "strength", "falloff"}],
    "puertas": {"abre": [[frame, grados], ...]}}"""
    col = {"piedra": "#d8d4cb", "techo": "#8d949c", "suelo": "#7d8578", "puerta": "#6b5a4e",
           **e.get("colores", {})}
    # "brillos": resplandores suaves sumados sobre el cel (como el aerografo del
    # anime): la piedra se ve encendida por los reflectores. Siguen a la
    # propiedad "brillo" de cada objeto de la catedral (0..1, animable).
    brillos = [dict(g, prop="brillo") for g in e.get("brillos", [])]
    m_stone = mat_toon("catedral_piedra", col["piedra"], glows=brillos or None)
    m_roof = mat_toon("catedral_techo", col["techo"])
    m_ground = mat_toon("catedral_suelo", col["suelo"])
    main = colls["main"]
    techo = e.get("techo", True)

    pc = Pieza("catedral_columnas")
    _columns(pc)
    pc.done(m_stone, main)

    muros = Pieza("catedral_muros")
    _nave_walls(muros)
    _choir_walls(muros)
    _outer_walls(muros)
    vid = list(muros.vidrios)
    muros.done(m_stone, main)

    _puertas(e.get("puertas", {}), mat_toon("catedral_puerta", col["puerta"]), main)

    torre = Pieza("catedral_torre")
    _tower(torre)
    vid_t = list(torre.vidrios)
    torre.done(m_stone, main)
    if e.get("vidrios", True) is not False:
        holder = Pieza("_v")
        holder.vidrios = vid + vid_t
        holder.bm.free()
        _vidrios([holder], mat_vitral("catedral_vitral", e.get("vidrios") or {}), main)
        luz = (e.get("vidrios") or {}).get("luz")
        if luz:
            _luz_vitrales(holder.vidrios, e["vidrios"], luz, colls)

    pc = Pieza("catedral_contrafuertes")
    _buttresses(pc)
    pc.done(m_stone, main)

    pc = Pieza("catedral_piso")
    _floor(pc, 0)
    pc.done(m_stone, main)
    if e.get("suelo", 240):
        pc = Pieza("catedral_vereda")
        _floor_ground = e.get("suelo", 240) / 2
        pc.box(-_floor_ground, _floor_ground, 20 - _floor_ground, 20 + _floor_ground, Z_GROUND - 0.2, Z_GROUND)
        pc.done(m_ground, main)

    if e.get("anexos", True):
        pc = Pieza("catedral_anexos")
        rf = Pieza("catedral_anexos_techo")
        _annexes(pc, rf)
        pc.done(m_stone, main)
        if techo:
            rf.done(m_roof, main)
        else:
            rf.bm.free()

    # reflectores: luces sin sombra que lavan fachada y torre desde abajo
    # (de noche, desde lejos, la catedral se lee por su propia luz)
    # Con "apunta" es un cono (spot) hacia ese punto: un punto a ras del piso
    # pinta un charco duro en el suelo; el cono solo lava lo que mira.
    for i, r in enumerate(e.get("reflectores", [])):
        if "apunta" not in r:
            tint_light(f"catedral_reflector{i}", r["color"], r.get("energia", 3000), tuple(r["at"]), colls)
            continue
        li = bpy.data.lights.new(f"catedral_reflector{i}", "SPOT")
        li.color = lin(r["color"])[:3]
        li.energy = r.get("energia", 3000)
        li.spot_size = math.radians(r.get("abre", 30))
        li.spot_blend = 0.6
        li.shadow_soft_size = 0.3
        li.use_shadow = False
        ob = bpy.data.objects.new(li.name, li)
        ob.location = r["at"]
        d = Vector(r["apunta"]) - Vector(r["at"])
        ob.rotation_mode = "QUATERNION"
        ob.rotation_quaternion = Vector((0, 0, -1)).rotation_difference(d.normalized())
        link(ob, colls["lights"])

    if techo:
        vb = Pieza("catedral_bovedas")
        rb = Pieza("catedral_nervios")
        _vaults(vb, rb)
        vb.done(m_stone, main, weld=False, solidify=0.25)
        rb.done(m_stone, main, weld=False)
        pc = Pieza("catedral_techos")
        _roofs(pc)
        pc.done(m_roof, main)
    for ob in bpy.data.objects:
        if ob.name.startswith("catedral_"):
            ob["brillo"] = 1.0
