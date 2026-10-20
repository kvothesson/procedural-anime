"""
cielo.py - Hora del dia y clima de un plano. Python puro (lo usa plano.py).

    "hora": "18:45", "fecha": "2026-10-17", "clima": "lluvia"

La hora pone el sol donde esta de verdad ese dia en ese lugar (elevacion y
azimut astronomicos): las sombras caen hacia donde caerian. El lugar sale de
"lugar" {"lat", "lon", "rumbo_deg", "utc"} del plano o de la georreferencia
de los datos del entorno (motor/osm.py la escribe en entorno.json). De la
altura del sol salen el cielo, la luz, la niebla, cuantas ventanas estan
prendidas, si los reflectores de una fachada estan encendidos y cuanto
brillan los vitrales desde afuera. La paleta por defecto es "natural"; un
estilo puede traer la suya en "horas" (lista por elevacion del sol).

El clima ("despejado", "nublado", "lluvia", "niebla", "tormenta") se aplica
encima: fuerza y dureza del sol, cielo desaturado, niebla mas cerca, piso
mojado mas oscuro, la lluvia del post y, en tormenta, relampagos.

Prioridad: estilo < hora/clima < lo que el plano dice explicitamente. Un
plano con "interior": true (o un estilo de interior) no recibe lluvia ni
cambia de cielo: solo la luz que entra por los vitrales.
"""

import math
import random
from datetime import datetime, timedelta

# ------------------------------------------------------------------ sol


def sol(lat, lon, fecha, hora, utc=-3.0):
    """Elevacion y azimut (grados; azimut desde el norte, horario) del sol."""
    d = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M") - timedelta(hours=utc)
    jd = d.toordinal() + 1721424.5 + (d.hour + d.minute / 60) / 24
    n = jd - 2451545.0
    L = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439 - 0.0000004 * n)
    ra = math.degrees(math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam)))
    dec = math.asin(math.sin(eps) * math.sin(lam))
    gmst = (18.697374558 + 24.06570982441908 * n) % 24
    ha = math.radians(((gmst * 15 + lon - ra) + 540) % 360 - 180)
    la = math.radians(lat)
    elev = math.asin(math.sin(la) * math.sin(dec) + math.cos(la) * math.cos(dec) * math.cos(ha))
    az = math.atan2(-math.sin(ha), math.tan(dec) * math.cos(la) - math.sin(la) * math.cos(ha))
    return math.degrees(elev), math.degrees(az) % 360


def hacia(elev, az, rumbo_deg):
    """Vector (x, y, z) de la escena que apunta al sol. El eje +y de la
    escena esta a `rumbo_deg` del este (antihorario); +x a su derecha."""
    e, a, r = (math.radians(v) for v in (elev, az, rumbo_deg))
    E, N = math.sin(a) * math.cos(e), math.cos(a) * math.cos(e)
    x = E * math.sin(r) - N * math.cos(r)
    y = E * math.cos(r) + N * math.sin(r)
    return [round(x, 4), round(y, 4), round(math.sin(e), 4)]


# ------------------------------------------------------------------ paleta

# por elevacion del sol: cielo, ambiente, sol, ventanas encendidas (0..1) y
# "noche" (0..1: reflectores y vitrales desde afuera)
NATURAL = [
    {"elev": -18, "horizon": "#1b2246", "top": "#05070f", "ambient": "#1c2440", "amb": 0.55,
     "sol": "#8fa6ff", "energia": 0.25, "ventanas": 0.68, "noche": 1.0},
    {"elev": -8, "horizon": "#4d4f8e", "top": "#141a40", "ambient": "#363c6a", "amb": 0.75,
     "sol": "#9fb0ff", "energia": 0.3, "ventanas": 0.6, "noche": 1.0},
    {"elev": -2, "horizon": "#ff8a6a", "top": "#25306a", "ambient": "#6a5a86", "amb": 0.85,
     "sol": "#ff9070", "energia": 0.6, "ventanas": 0.45, "noche": 0.7},
    {"elev": 4, "horizon": "#ffb37a", "top": "#3d5a9e", "ambient": "#9a88a0", "amb": 0.95,
     "sol": "#ffa860", "energia": 2.0, "ventanas": 0.25, "noche": 0.2},
    {"elev": 12, "horizon": "#ffe2b8", "top": "#5d8fd6", "ambient": "#b9b6c4", "amb": 1.0,
     "sol": "#ffe0b0", "energia": 3.2, "ventanas": 0.08, "noche": 0.0},
    {"elev": 35, "horizon": "#d6eaff", "top": "#4a8ae0", "ambient": "#c8d6ea", "amb": 1.0,
     "sol": "#fff6e8", "energia": 4.0, "ventanas": 0.05, "noche": 0.0},
    {"elev": 90, "horizon": "#d6eaff", "top": "#3f80dc", "ambient": "#c8d6ea", "amb": 1.0,
     "sol": "#ffffff", "energia": 4.2, "ventanas": 0.05, "noche": 0.0},
]

CLIMAS = {
    #             sol x, ambiente x, desatura, niebla (m), lluvia, angulo del sol, piso x
    "despejado": dict(sol=1.0, amb=1.0, gris=0.0, niebla=None, lluvia=False, angulo=1.0, piso=1.0),
    "nublado": dict(sol=0.25, amb=1.3, gris=0.6, niebla=700, lluvia=False, angulo=15.0, piso=0.95),
    "lluvia": dict(sol=0.15, amb=1.15, gris=0.7, niebla=260, lluvia=True, angulo=20.0, piso=0.72),
    "niebla": dict(sol=0.3, amb=1.2, gris=0.5, niebla=70, lluvia=False, angulo=15.0, piso=0.9),
    "tormenta": dict(sol=0.08, amb=0.85, gris=0.8, niebla=200, lluvia=True, angulo=20.0, piso=0.65,
                     relampagos=True),
}


def _rgb(c):
    c = c.lstrip("#")
    return [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def _hex(v):
    return "#" + "".join(f"{max(0, min(255, round(x * 255))):02x}" for x in v)


def _mix(a, b, t):
    return _hex([x + (y - x) * t for x, y in zip(_rgb(a), _rgb(b))])


def _gris(c, t, oscurece=1.0):
    r = _rgb(c)
    lum = 0.3 * r[0] + 0.59 * r[1] + 0.11 * r[2]
    return _hex([(x + (lum - x) * t) * oscurece for x in r])


def paleta(elev, tabla=None):
    t = tabla or NATURAL
    if elev <= t[0]["elev"]:
        return dict(t[0])
    for a, b in zip(t, t[1:]):
        if a["elev"] <= elev <= b["elev"]:
            k = (elev - a["elev"]) / (b["elev"] - a["elev"])
            out = {}
            for key, va in a.items():
                vb = b[key]
                out[key] = _mix(va, vb, k) if isinstance(va, str) else va + (vb - va) * k
            return out
    return dict(t[-1])


# ------------------------------------------------------------------ aplicar


def aplicar(cfg, raw, lugar):
    """cfg: plano ya resuelto con su estilo. raw: lo que el plano dice
    explicitamente (eso no se toca). Devuelve cfg con hora y clima."""
    cfg = dict(cfg)
    clima = CLIMAS[raw.get("clima", cfg.get("clima", "despejado"))]
    interior = cfg.get("interior", False)
    hora = raw.get("hora", cfg.get("hora"))
    info = {}
    if hora and lugar:
        fecha = raw.get("fecha", cfg.get("fecha", "2026-10-17"))
        elev, az = sol(lugar["lat"], lugar["lon"], fecha, hora, lugar.get("utc", -3))
        p = paleta(elev, cfg.get("horas"))
        info = {"elevacion": round(elev, 1), "azimut": round(az, 1), "noche": round(p["noche"], 2)}
        if elev < -1:
            # de noche la luz con sombra es la luna: alta y del lado opuesto
            luz = hacia(40, (az + 180) % 360, lugar["rumbo_deg"])
        else:
            luz = hacia(max(elev, 1.5), az, lugar["rumbo_deg"])
        sky = {"horizon": p["horizon"], "top": p["top"], "ambient": p["ambient"], "ambient_strength": p["amb"]}
        lights = [{"kind": "SUN", "color": p["sol"], "energy": p["energia"], "hacia": luz, "shadow": True},
                  {"kind": "SUN", "color": p["ambient"], "energy": 0.35 * p["amb"],
                   "hacia": hacia(50, (az + 140) % 360, lugar["rumbo_deg"]), "shadow": False}]
        fog = {"color": _mix(p["horizon"], p["ambient"], 0.5), "dist": cfg.get("fog", {}).get("dist", 900)}
        noche, ventanas = p["noche"], p["ventanas"]
    else:
        sky = dict(cfg.get("sky", {}))
        lights = [dict(l) for l in cfg.get("lights", [])]
        fog = dict(cfg.get("fog", {}))
        noche, ventanas = None, None
    # clima encima
    if sky and not interior:
        for k in ("horizon", "top", "ambient"):
            if k in sky:
                sky[k] = _gris(sky[k], clima["gris"], 0.85 if clima["lluvia"] else 1.0)
        sky["ambient_strength"] = sky.get("ambient_strength", 1.0) * clima["amb"]
    if lights and not interior:
        lights[0]["energy"] = lights[0].get("energy", 1.0) * clima["sol"]
        lights[0]["angle"] = clima["angulo"]
    if clima["niebla"] and not interior:
        fog["dist"] = min(fog.get("dist", 900), clima["niebla"])
        if "color" in fog:
            fog["color"] = _gris(fog["color"], clima["gris"])
    if clima.get("relampagos") and not interior and lights:
        # "relampagos": [frames] en el plano los pone donde se pidan (en el
        # trueno de la musica); si no, al azar cada 30-70 cuadros
        pedidos = raw.get("relampagos")
        rnd = random.Random(cfg.get("frames", 72))
        if pedidos:
            fs = list(pedidos)
        else:
            fs, f = [], rnd.randint(8, 30)
            while f < cfg.get("frames", 72):
                fs.append(f)
                f += rnd.randint(30, 70)
        keys = []
        for f in fs:
            keys += [[f - 1, 0.0], [f, 9.0], [f + 1, 2.0], [f + 2, 7.0], [f + 4, 0.0]]
        lights.append({"kind": "SUN", "color": "#cfd8ff", "energy": 0.0, "energia_keys": keys,
                       "hacia": [0.2, -0.3, 0.93], "shadow": False})
    for k, v in (("sky", sky), ("lights", lights), ("fog", fog)):
        if v and k not in raw:
            cfg[k] = v
    if clima["lluvia"] and not interior and "rain" not in raw.get("post", {}):
        cfg["post"] = dict(cfg.get("post", {}), rain=_lluvia(clima))
    # piezas
    if "entorno" in cfg and "colores" not in raw.get("entorno", {}):
        ent = dict(cfg["entorno"])
        col = dict(ent.get("colores", {}))
        for k in ("piso", "vereda", "asfalto", "camino", "playa"):
            if k in col:
                col[k] = _gris(col[k], 0.15 * (1 - clima["piso"]), clima["piso"])
        ent["colores"] = col
        if ventanas is not None and "ventanas" in ent:
            ent["ventanas"] = dict(ent["ventanas"], lit=round(ventanas, 3))
        if noche is not None and "faroles" in ent:
            ent["faroles"] = dict(ent["faroles"], encendido=round(min(1.0, noche * 1.5), 3))
        cfg["entorno"] = ent
    if "catedral" in cfg and noche is not None:
        cat = dict(cfg["catedral"])
        if "reflectores" in cat:
            cat["reflectores"] = [dict(r, energia=round(r.get("energia", 3000) * noche)) for r in cat["reflectores"]]
        if "brillos" in cat:
            cat["brillos"] = [dict(g, strength=round(g["strength"] * noche, 3)) for g in cat["brillos"]]
        if isinstance(cat.get("vidrios"), dict) and not interior:
            cat["vidrios"] = dict(cat["vidrios"], fuerza=round(cat["vidrios"].get("fuerza", 1.0)
                                                              * (0.35 + 0.65 * noche), 3))
        cfg["catedral"] = cat
    cfg["_cielo"] = dict(info, clima=raw.get("clima", cfg.get("clima", "despejado")), interior=interior)
    return cfg


def _lluvia(clima):
    fuerte = clima.get("relampagos")
    k = 1.6 if fuerte else 1.0
    return {"angle_deg": 14 if fuerte else 8, "color": "#cfe0f0",
            "layers": [{"count": int(900 * k), "length": [18, 34], "width": 1, "speed": 2600, "alpha": 0.22},
                       {"count": int(260 * k), "length": [50, 90], "width": 2, "speed": 3800, "alpha": 0.3},
                       {"count": int(45 * k), "length": [160, 260], "width": 3, "speed": 5600, "alpha": 0.36}]}
