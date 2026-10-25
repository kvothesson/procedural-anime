"""filete.py - El filete porteno en numeros, sin Blender: la chapa (paso y
profundidad de la canaleta), las capas y la paleta, y el motivo entero (hoja
de acanto, banda con voluta, firulete, rulo, bolitas, sombra) como una lista
de pinceladas con su horario, mas los viajes del pincel entre una y otra.

Lo usan piezas.py (dentro de Blender: geometria, pincel, contagio del color)
y banda.py (cada trazo suena cuando el pincel lo pinta).
"""

import json
import math
from functools import lru_cache

import numpy as np

PASO = 0.076      # paso de la chapa sinusoidal (76 mm)
AMP = 0.0085      # media profundidad de la canaleta

# capas de pintura: distancia a la chapa (m), de abajo hacia arriba
CAPA = {"sombra": 0.0012, "firulete": 0.0016, "fondo": 0.0020, "tono": 0.0026, "bolita": 0.0030,
        "linea": 0.0034, "brillo": 0.0040}

PALETA = {
    "linea": "#17110f", "verde": "#6aa23a", "verde_osc": "#2f6b2a", "brillo": "#eaf3a2",
    "rojo": "#d23a2a", "rojo_osc": "#7a1a14", "rojo_brillo": "#ffb27a",
    "firulete": "#fffaf0", "rulo": "#ffd23a", "sombra": "#24394a", "bolita": "#f4d24a",
}


# cuanto toman la luz toon las lineas finas (1 = como el resto)
LUZ = {"firulete": 0.35, "rulo": 0.35}


def surf(z):
    return -AMP * np.sin(2 * np.pi * np.asarray(z) / PASO)


# ------------------------------------------------------------------ 2D

def _resample(pts, step):
    pts = np.asarray(pts, float)
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    n = max(2, int(math.ceil(d[-1] / step)) + 1)
    s = np.linspace(0, d[-1], n)
    return np.c_[np.interp(s, d, pts[:, 0]), np.interp(s, d, pts[:, 1])], s


def _normales(pts):
    t = np.gradient(pts, axis=0)
    t /= np.linalg.norm(t, axis=1, keepdims=True) + 1e-12
    return t, np.c_[-t[:, 1], t[:, 0]]


def _bezier(p0, p1, p2, p3, n=80):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = (np.asarray(p, float) for p in (p0, p1, p2, p3))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def _espiral(c, r0, r1, vueltas, ang_fin, sentido=1, n=160):
    """Espiral logaritmica de r0 (adentro) a r1 (afuera); el punto exterior
    queda en el angulo ang_fin. sentido=1: antihorario hacia afuera."""
    th = np.linspace(0, vueltas * 2 * np.pi, n)
    b = math.log(r1 / r0) / th[-1]
    r = r0 * np.exp(b * th)
    phi = ang_fin - sentido * (th[-1] - th)
    return np.c_[c[0] + r * np.cos(phi), c[1] + r * np.sin(phi)]


# ------------------------------------------------------------------ el motivo

@lru_cache(maxsize=None)
def _motivo_cache(key):
    return _motivo(json.loads(key))


def motivo(e):
    return _motivo_cache(json.dumps(e, sort_keys=True))


def _acanto(eje, w_out, w_in, lobulos):
    """Hoja de acanto de filete: un solo follaje carnoso a lo largo de 'eje'
    (que termina enroscado), con el borde de afuera en lobulos que apuntan
    hacia la punta (sube suave, cae de golpe: la muesca). w_out/w_in: ancho
    [s, m] de cada lado; lobulos: [(s0, s1), ...] en fraccion del eje.
    Devuelve contorno, zona oscura, nervaduras y muescas."""
    p, s = _resample(eje, 0.002)
    k = s / s[-1]
    tg, nr = _normales(p)
    wo = np.interp(k, *zip(*w_out))
    wi = np.interp(k, *zip(*w_in))
    r = wo * 0.5
    adel = np.zeros_like(k)
    puntas, muescas = [], []
    for s0, s1 in lobulos:
        m = (k >= s0) & (k < s1)
        u = (k[m] - s0) / (s1 - s0)
        # lobulo redondo: sube en cuarto de seno y cae en cuarto de circulo
        g = np.where(u < 0.72, np.sin(np.pi / 2 * u / 0.72),
                     np.sqrt(np.clip(1 - ((u - 0.72) / 0.28) ** 2, 0, 1)))
        r[m] = wo[m] * (0.5 + 0.5 * g)
        adel[m] = wo[m] * 0.45 * g * 0.6
        i = np.flatnonzero(m)
        puntas.append(i[int(len(i) * 0.72)])
        muescas.append(i[-1])
    afuera = p + nr * r[:, None] + tg * adel[:, None]
    adentro = p - nr * wi[:, None]
    contorno = np.r_[afuera, adentro[-2:0:-1]]
    medio = p + nr * (0.30 * wo)[:, None]
    oscuro = np.r_[medio, adentro[-2:0:-1]]
    nerv = []
    for j, (s0, s1) in zip(puntas, lobulos):
        i0 = int(np.searchsorted(k, s0 + (s1 - s0) * 0.15))
        q0, q2 = p[i0], p[j] + (afuera[j] - p[j]) * 0.8
        q1 = (q0 + q2) / 2 + tg[i0] * 0.01
        nerv.append(_bezier(q0, q1, q1, q2, 20))
    cortes = [np.array([afuera[j], p[j] + nr[j] * wo[j] * 0.25]) for j in muescas[:-1]]
    return contorno, oscuro, nerv, cortes, p


def _motivo(e):
    """Hoja de acanto que nace de la voluta de la banda y se enrosca en su
    punta; la banda sale de la voluta hacia la derecha (peso a la izquierda,
    banda a la derecha, como pide el manual), firulete paralelo y bolitas.
    Devuelve la lista de piezas, cada una con su horario."""
    S = e.get("escala", 1.0)
    ox, oz = e.get("origen", (0.0, 0.0))
    f = e.get("inicio", 1)

    def W(pts):
        return np.asarray(pts) * S + np.array([ox, oz])

    C = np.array([-0.20, -0.08])
    yb = C[1] - 0.10
    # banda que termina en voluta: de adentro de la voluta hacia afuera, y
    # por abajo derecho hacia la derecha, con un rulo chico al final
    esp = _espiral(C, 0.012, 0.10, 2.3, -math.pi / 2)
    recta = np.c_[np.linspace(C[0] + 0.01, 0.36, 40), np.full(40, yb)]
    rulo = _espiral(np.array([0.36, yb + 0.030]), 0.006, 0.030, 0.85, -math.pi / 2, sentido=-1)[::-1]
    banda = np.r_[esp, recta[1:], rulo[1:]]
    BANDA = dict(w=0.034 * S, w_ini=0.008 * S)
    # la hoja: nace a la izquierda de la voluta, pasa por arriba y se
    # enrosca hacia adentro (en sentido horario) en su punta
    P0, P1, P2, P3 = C + (-0.115, -0.03), C + (-0.15, 0.18), C + (0.15, 0.27), C + (0.23, 0.11)
    d = (P3 - P2) / np.linalg.norm(P3 - P2)
    cen = P3 + 0.05 * np.array([d[1], -d[0]])
    a3 = math.atan2(*(P3 - cen)[::-1])
    rizo = _espiral(cen, 0.010, 0.05, 0.95, a3, sentido=1)[::-1]
    eje = np.r_[_bezier(P0, P1, P2, P3), rizo[1:]]
    cont, osc, nerv, cortes, ejer = _acanto(
        eje,
        w_out=[(0, 0.020), (0.12, 0.055), (0.35, 0.075), (0.55, 0.066), (0.72, 0.042), (0.86, 0.020), (1, 0.006)],
        w_in=[(0, 0.008), (0.12, 0.014), (0.35, 0.016), (0.55, 0.014), (0.72, 0.010), (0.86, 0.006), (1, 0.002)],
        lobulos=[(0.03, 0.16), (0.16, 0.30), (0.30, 0.44), (0.44, 0.57), (0.57, 0.69), (0.69, 0.80)])
    # firulete: acompana a la banda por fuera (en el talon, como permite el
    # manual), a algo mas de un ancho de banda: nace escondido bajo la hoja,
    # rodea la voluta por afuera y corre bajo la banda hasta antes del
    # remate, donde hace su propio rulo, como la banda
    br, sb = _resample(banda, 0.003)
    _, nb = _normales(br)
    s_esp = _resample(esp, 0.003)[1][-1]
    s_rec = s_esp + (recta[-1, 0] - recta[0, 0])
    tramo = (sb > s_esp - 0.165) & (sb < s_rec - 0.06)
    fir = br[tramo] - nb[tramo] * 0.040
    d = fir[-1] - fir[-2]
    d /= np.linalg.norm(d)
    cf = fir[-1] + 0.016 * np.array([d[1], -d[0]])
    rizo_f = _espiral(cf, 0.004, 0.016, 0.9, math.atan2(*(fir[-1] - cf)[::-1]), sentido=1)[::-1]
    firulete = np.r_[fir, rizo_f[1:]]
    # rulo fino que sale de abajo de la hoja y se enrosca en el hueco
    r0, r3 = np.array([0.015, -0.032]), np.array([0.16, -0.02])
    rulo_h = _bezier(r0, (0.07, -0.075), (0.13, -0.065), r3, 40)
    d = (r3 - rulo_h[-2]) / np.linalg.norm(r3 - rulo_h[-2])
    cr = r3 + 0.022 * np.array([-d[1], d[0]])
    rulo_h = np.r_[rulo_h, _espiral(cr, 0.005, 0.022, 1.0, math.atan2(*(r3 - cr)[::-1]), sentido=-1)[::-1][1:]]
    bolitas = [((0.200, 0.018), 0.011), ((0.214, 0.044), 0.008), ((0.220, 0.066), 0.006),
               ((0.445, -0.118), 0.012), ((0.468, -0.090), 0.008)]

    P = []

    def add(**k):
        P.append(k)

    # 1) el trazo: el contorno de la hoja con el pincel fino, y sus muescas
    t = f + 5
    add(kind="trazo", pts=W(np.r_[cont, cont[:1]]), w=0.0042 * S, capa="linea", col="linea",
        f=(t, t + 24)); t += 25
    for c in cortes:
        add(kind="trazo", pts=W(c), w=0.0034 * S, w_fin=0.001 * S, capa="linea", col="linea",
            f=(t, t + 0.5)); t += 0.5
    t = math.ceil(t)
    # 2) relleno de la hoja y su mitad oscura
    lado = (ejer[0], ejer[len(ejer) // 2])
    add(kind="relleno", poly=W(cont), capa="fondo", col="verde", f=(t, t + 4), eje=W(lado)); t += 4
    add(kind="relleno", poly=W(osc), capa="tono", col="verde_osc", f=(t, t + 4), eje=W(lado)); t += 4
    # 2b) brillos de la hoja antes de la banda: asi el brazo, que baja desde
    # la mano, pasa solo por encima de lo que todavia no se pinto
    for n in nerv:
        add(kind="trazo", pts=W(n), w=0.0045 * S, w_fin=0.0012 * S, capa="brillo", col="brillo",
            f=(t, t + 0.75)); t += 0.75
    t = math.ceil(t)
    add(kind="trazo", pts=W(ejer[:int(len(ejer) * 0.85)]), w=0.0040 * S, w_fin=0.001 * S, capa="brillo",
        col="brillo", f=(t, t + 2)); t += 2
    # 3) la banda: base roja, su sombra, sus bordes y el firulete
    add(kind="trazo", pts=W(banda), capa="fondo", col="rojo", f=(t, t + 6), **BANDA); t += 6
    add(kind="trazo", pts=W(banda), w=0.012 * S, w_ini=0.003 * S, capa="tono", col="rojo_osc",
        f=(t, t + 3), corrido=-0.010 * S); t += 3
    for lado_b in (1, -1):
        add(kind="trazo", pts=W(banda), w=0.0038 * S, capa="linea", col="linea", f=(t, t + 1.5),
            lado=lado_b, ref=BANDA); t += 1.5
    t = math.ceil(t) + 1
    add(kind="trazo", pts=W(firulete), w=0.0060 * S, capa="firulete", col="firulete", f=(t, t + 3)); t += 3
    add(kind="trazo", pts=W(rulo_h), w=0.0060 * S, w_fin=0.0030 * S, capa="firulete", col="rulo",
        f=(t, t + 1.5)); t += 1.5
    # 4) brillo de la banda
    add(kind="trazo", pts=W(banda), w=0.0045 * S, w_ini=0.001 * S, capa="brillo", col="rojo_brillo",
        f=(t, t + 2), corrido=0.009 * S); t += 3
    # 5) sombra proyectada: todo el motivo corrido abajo a la derecha
    som = np.array([0.009, -0.011])
    add(kind="relleno", poly=W(cont + som), capa="sombra", col="sombra", f=(t, t + 4), barrido=True)
    add(kind="trazo", pts=W(banda + som), capa="sombra", col="sombra", f=(t, t + 4), **BANDA)
    t += 5
    # 6) bolitas, de a una
    ang = np.linspace(0, 2 * np.pi, 24, endpoint=False)
    for (c, r) in bolitas:
        add(kind="relleno", poly=W(np.c_[c[0] + r * np.cos(ang), c[1] + r * np.sin(ang)]),
            capa="bolita", col="bolita", f=(t, t + 0.5), bolita=True)
        add(kind="relleno", poly=W(np.c_[c[0] - r * 0.35 + r * 0.3 * np.cos(ang),
                                         c[1] + r * 0.35 + r * 0.3 * np.sin(ang)]),
            capa="brillo", col="brillo", f=(t, t + 0.5), bolita=True)
        t += 1.2
    P = _viajes(P, f + 5, e.get("fin", 80))
    if e.get("terminado"):
        # el filete ya esta pintado (01 y 06): todo antes del primer cuadro
        for p in P:
            p["f"] = (-20.0, -19.0)
    if e.get("firma"):
        # la firma: repique, trazos cortos y paralelos de blanco bajo el remate
        # de la banda, de a uno
        g0, g1 = e["firma"]
        n = 5
        for k in range(n):
            x = 0.335 + k * 0.011
            a = W(np.array([[x, yb - 0.040], [x + 0.006, yb - 0.022]]))
            t0 = g0 + (g1 - g0) * k / n
            P.append(dict(kind="trazo", pts=a, w=0.0035 * S, w_fin=0.0015 * S, capa="brillo",
                          col="firulete", f=(t0, t0 + (g1 - g0) / n * 0.6)))
    return P


def _viajes(P, f_ini, f_fin, vel=0.09, max_h=2.5):
    """Tiempo para que el pincel viaje por el aire entre un trazo y el
    siguiente (1 cuadro cada 9 cm, entre 1 y 2,5), en vez de saltar de un
    punto a otro en un cuadro. Despues todo se reescala para terminar en f_fin."""
    import numpy as _np
    shift, prev_f1, prev_end = 0.0, None, None
    for p in P:
        f0, f1 = p["f"][0] + shift, p["f"][1] + shift
        if prev_f1 is not None and f0 >= prev_f1 - 1e-6:
            d = float(_np.linalg.norm(_cabeza(dict(p, f=(f0, f1)), f0) - prev_end))
            if d > 0.02:
                h = min(max_h, max(1.0, d / vel))
                shift += h
                f0, f1 = f0 + h, f1 + h
        p["f"] = (f0, f1)
        if prev_f1 is None or f1 >= prev_f1:
            prev_f1, prev_end = f1, _cabeza(p, f1)
    fin = max(p["f"][1] for p in P)
    if fin > f_fin:
        k = (f_fin - f_ini) / (fin - f_ini)
        for p in P:
            p["f"] = tuple(f_ini + (x - f_ini) * k for x in p["f"])
    return P



def _ancho(s, w, w_ini=None, w_fin=None):
    """Ancho de la pincelada a lo largo del trazo: de w_ini a w_fin, y finito
    en las dos puntas."""
    L = s[-1]
    ini = w if w_ini is None else w_ini
    fin = w if w_fin is None else w_fin
    ww = ini + (fin - ini) * s / max(L, 1e-9)
    return ww * np.clip(np.minimum(s, L - s) / 0.012 + 0.35, 0, 1)


def _cabeza(p, fr):
    """Donde esta la punta del pincel en el cuadro fr mientras pinta p."""
    f0, f1 = p["f"]
    k = float(np.clip((fr - f0) / max(f1 - f0, 1e-6), 0, 1))
    if p["kind"] == "trazo":
        q, s = _resample(p["pts"], 0.003)
        _, nr = _normales(q)
        off = p.get("corrido", 0.0)
        if p.get("ref"):
            off = off + p["lado"] * _ancho(s, **p["ref"]) / 2
        q = q + nr * np.asarray(off).reshape(-1, 1)
        i = int(round(k * (len(q) - 1)))
        return q[i]
    poly = np.asarray(p["poly"])
    if p.get("bolita"):
        return poly.mean(axis=0)
    if p.get("barrido"):
        # la sombra se pinta de izquierda a derecha: el pincel va por el
        # borde de abajo del frente
        x = poly[:, 0].min() + (poly[:, 0].max() - poly[:, 0].min()) * k
        cerca = poly[np.abs(poly[:, 0] - x) < 0.02]
        return cerca[cerca[:, 1].argmin()] if len(cerca) else poly.mean(axis=0)
    a, b = (np.asarray(p["eje"]) if p.get("eje") is not None else (poly[0], poly[len(poly) // 2]))
    # sobre el frente del relleno: el punto del contorno mas cercano a la
    # linea que avanza, del lado de afuera
    d = b - a
    front = np.abs((poly - a) @ d / (d @ d) - k)
    cerca = poly[front < 0.04]
    return cerca.mean(axis=0) if len(cerca) else a + d * k
