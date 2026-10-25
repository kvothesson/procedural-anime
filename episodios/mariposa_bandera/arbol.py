"""
arbol.py - Ramas secas de la Reserva y donde cuelgan las crisalidas. Python puro
(sin bpy): lo usan piezas.py para armar el arbol y planos.py para apuntar las
camaras a las crisalidas.

    arbol({"base": [x, y, z], "alto": 1.2, "niveles": 4, "seed": 4,
           "crisalidas": 40, "largo": [0.018, 0.028]})
    -> {"ramas": [{"pts": [(x, y, z), ...], "radio": r, "nivel": n}],
        "colgadas": [{"at": (x, y, z), "largo": l, "rama": i}]}
"""

import math
import random


def _v(a, b, k=1.0):
    return tuple(x + y * k for x, y in zip(a, b))


def _norm(a):
    m = math.sqrt(sum(x * x for x in a)) or 1.0
    return tuple(x / m for x in a)


def _girar(d, ang, eje_az):
    """Inclina la direccion d un angulo ang (rad) hacia el azimut eje_az."""
    lado = (math.cos(eje_az), math.sin(eje_az), 0.0)
    nd = _norm(_v(tuple(x * math.cos(ang) for x in d), lado, math.sin(ang)))
    return nd


def arbol(T):
    rnd = random.Random(T.get("seed", 4))
    ramas = []

    def crecer(p0, d, largo, radio, nivel):
        n = 7
        pts = [p0]
        p = p0
        for i in range(n):
            # la rama se tuerce un poco y las finas se vencen hacia abajo
            d = _norm(_v(d, (rnd.gauss(0, 0.18), rnd.gauss(0, 0.18), -0.06 * nivel)))
            p = _v(p, d, largo / n)
            pts.append(p)
        ramas.append({"pts": pts, "radio": radio, "nivel": nivel})
        if nivel >= T.get("niveles", 4):
            return
        hijos = rnd.choice((2, 2, 3))
        for h in range(hijos):
            k = rnd.uniform(0.35, 0.95)
            i = min(n, max(1, int(k * n)))
            ang = math.radians(rnd.uniform(25, 55))
            az = rnd.uniform(0, 2 * math.pi)
            crecer(pts[i], _girar(d, ang, az), largo * rnd.uniform(0.55, 0.75), radio * 0.6, nivel + 1)

    crecer(tuple(T["base"]), (0.0, 0.0, 1.0), T.get("alto", 1.2) * 0.45, T.get("radio", 0.035), 0)
    # crisalidas: de las ramas finas, colgando debajo
    finas = [i for i, r in enumerate(ramas) if r["nivel"] >= 2]
    colgadas = []
    l0, l1 = T.get("largo", (0.018, 0.028))
    intentos = 0
    while len(colgadas) < T.get("crisalidas", 40) and intentos < 2000:
        intentos += 1
        i = rnd.choice(finas)
        pts = ramas[i]["pts"]
        j = rnd.randint(1, len(pts) - 2)
        s = rnd.random()
        p = tuple(a + (b - a) * s for a, b in zip(pts[j], pts[j + 1]))
        p = (p[0], p[1], p[2] - ramas[i]["radio"])
        lg = rnd.uniform(l0, l1)
        if any(math.dist(p, c["at"]) < T.get("separacion", 0.07) for c in colgadas):
            continue
        colgadas.append({"at": p, "largo": lg, "rama": i})
    return {"ramas": ramas, "colgadas": colgadas}


def _dist_seg(p, a, b):
    ab = [y - x for x, y in zip(a, b)]
    ap = [y - x for x, y in zip(a, p)]
    t = max(0.0, min(1.0, sum(x * y for x, y in zip(ap, ab)) / (sum(x * x for x in ab) or 1e-9)))
    return math.dist(p, [x + y * t for x, y in zip(a, ab)])


def libre(A, p, sin=()):
    """Distancia de un punto a la superficie de la rama mas cercana (las ramas
    de "sin" no cuentan)."""
    d = 9.0
    for k, r in enumerate(A["ramas"]):
        if k in sin:
            continue
        for a, b in zip(r["pts"], r["pts"][1:]):
            d = min(d, _dist_seg(p, a, b) - r["radio"])
    return d


def camino_libre(A, a, b, margen=0.065, sin=()):
    n = max(2, int(math.dist(a, b) / 0.01))
    return all(libre(A, [x + (y - x) * i / n for x, y in zip(a, b)], sin) > margen for i in range(n + 1))
