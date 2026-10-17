"""
osm.py - El entorno real de un lugar desde OpenStreetMap, en metros y en el
marco de la escena. Python puro (sin bpy): lo lee piezas/entorno.py.

    python motor/osm.py episodios/catedral            # baja OSM (si no esta) y convierte
    python motor/osm.py episodios/catedral --bajar    # vuelve a bajar los datos

Lee <ep>/data/osm.json (que bajar y como ubicarlo) y escribe:
  <ep>/data/osm_raw.json   la respuesta de Overpass, tal cual (cache)
  <ep>/data/entorno.json   edificios, calles, areas, vias y arboles en metros

El marco: "origen" [lat, lon] cae en "origen_local" [x, y] de la escena y el
eje +y de la escena apunta a "rumbo_deg" (grados desde el este, antihorario).
x queda a la derecha de y. Asi el entorno calza con una pieza modelada a mano
(la catedral) que ya tiene sus ejes.

OSM casi nunca trae la altura y en barrios bajos faltan casas. Lo que falta se
completa y queda marcado ("src": "relleno"): alturas por tipo de edificio,
casas sobre la linea municipal de las manzanas vacias y arboles de vereda.
Con "relleno": false solo queda lo que trae OSM.

Terreno: con "terreno" en osm.json se baja la elevacion (tiles terrarium de
Mapzen/AWS: SRTM de 30 m en Argentina, el mismo dato que el MDE nacional) y
se guarda una grilla en metros de escena: z = elevacion - "ref_m" (la cota
del piso de la pieza modelada). "plataformas" aplana donde la pieza manda.

Datos (c) colaboradores de OpenStreetMap, licencia ODbL. Elevacion: Mapzen
Terrain Tiles (SRTM, NASA/USGS; dominio publico).
"""

import argparse
import json
import math
import random
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

SERVERS = ["https://overpass-api.de/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter",
           "https://overpass.private.coffee/api/interpreter"]

# ancho de calzada por tipo (m) cuando OSM no trae width ni lanes
ANCHO = {"motorway": 20, "trunk": 18, "primary": 15, "secondary": 13, "tertiary": 11,
         "residential": 9, "living_street": 7, "unclassified": 8, "service": 5, "pedestrian": 6,
         "footway": 2.5, "cycleway": 2.0, "path": 2.0, "steps": 2.5, "track": 3.0}
AUTOS = {"motorway", "trunk", "primary", "secondary", "tertiary", "residential", "living_street",
         "unclassified"}
# altura por tipo (m) cuando OSM no trae height ni building:levels
ALTO = {"commercial": 7.5, "retail": 5.0, "yes": 6.5, "apartments": 18.0, "residential": 9.0,
        "house": 6.5, "detached": 6.5, "school": 9.0, "college": 10.0, "university": 12.0,
        "hospital": 12.0, "office": 12.0, "church": 12.0, "garage": 3.0, "roof": 4.0,
        "industrial": 8.0, "train_station": 7.0}
VERDE = {"park", "garden", "recreation_ground", "pitch", "common", "grass", "village_green",
         "playground", "meadow", "wood", "scrub"}


# ------------------------------------------------------------------ bajar
def bajar(spec, dst):
    lat, lon = spec["centro"]
    R = spec.get("radio", 450)
    q = f"""[out:json][timeout:120];
(
 way["building"](around:{R},{lat},{lon});
 relation["building"](around:{R},{lat},{lon});
 way["highway"](around:{R},{lat},{lon});
 way["railway"](around:{R},{lat},{lon});
 way["leisure"](around:{R},{lat},{lon});
 way["landuse"](around:{R},{lat},{lon});
 way["natural"](around:{R},{lat},{lon});
 way["amenity"](around:{R},{lat},{lon});
 node["natural"="tree"](around:{R},{lat},{lon});
);
out geom tags;"""
    body = urllib.parse.urlencode({"data": q}).encode()
    for intento in range(3):
        for url in SERVERS:
            try:
                req = urllib.request.Request(url, data=body, headers={"User-Agent": "procedural-anime/1"})
                raw = urllib.request.urlopen(req, timeout=180).read()
                json.loads(raw)
                dst.write_bytes(raw)
                print(f"OSM -> {dst} ({len(raw) // 1024} KB, {url})")
                return
            except Exception as ex:      # los espejos de Overpass fallan seguido
                print(f"  {url}: {ex}")
        time.sleep(5 * (intento + 1))
    raise SystemExit("Overpass no respondio")


# ------------------------------------------------------------------ marco
class Marco:
    def __init__(self, spec):
        self.la0, self.lo0 = spec["origen"]
        self.x0, self.y0 = spec.get("origen_local", [0.0, 0.0])
        a = math.radians(spec.get("rumbo_deg", 90.0))
        self.Y = (math.cos(a), math.sin(a))          # +y de la escena en (este, norte)
        self.X = (math.sin(a), -math.cos(a))         # +x: a la derecha de +y
        self.kx = 111320 * math.cos(math.radians(self.la0))
        self.ky = 110574

    def inverse(self, x, y):
        dx, dy = x - self.x0, y - self.y0
        E = dx * self.X[0] + dy * self.Y[0]
        N = dx * self.X[1] + dy * self.Y[1]
        return self.la0 + N / self.ky, self.lo0 + E / self.kx

    def __call__(self, p):
        E = (p["lon"] - self.lo0) * self.kx
        N = (p["lat"] - self.la0) * self.ky
        return (round(self.x0 + E * self.X[0] + N * self.X[1], 2),
                round(self.y0 + E * self.Y[0] + N * self.Y[1], 2))


def _num(v):
    try:
        return float(str(v).split()[0].replace(",", "."))
    except (ValueError, IndexError):
        return None


def alto(t, rnd):
    h = _num(t.get("height"))
    if h:
        return h, "osm"
    lv = _num(t.get("building:levels"))
    if lv:
        return lv * 3.2 + 1.0, "osm"
    return ALTO.get(t.get("building", "yes"), 6.5) * rnd.uniform(0.85, 1.15), "tipo"


def ancho(t):
    w = _num(t.get("width"))
    if w:
        return w
    lanes = _num(t.get("lanes"))
    if lanes and t.get("highway") in AUTOS:
        return lanes * 3.3 + 1.5
    return ANCHO.get(t.get("highway"), 3.0)


# ------------------------------------------------------------------ geometria
def _dentro(poly, x, y):
    ins = False
    j = len(poly) - 1
    for i in range(len(poly)):
        (xi, yi), (xj, yj) = poly[i], poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            ins = not ins
        j = i
    return ins


class Ocupado:
    """Mascara de 1 m de lo que ya hay (edificios, calles con vereda, plazas,
    zonas libres): el relleno solo va donde esta vacio."""

    def __init__(self, R, res=1.0):
        self.R, self.res = R, res
        n = int(2 * R / res)
        self.img = Image.new("1", (n, n), 0)
        self.dr = ImageDraw.Draw(self.img)
        self.arr = None

    def px(self, x, y):
        return ((x + self.R) / self.res, (self.R - y) / self.res)

    def poly(self, pts, grow=0):
        if len(pts) >= 3:
            self.dr.polygon([self.px(*p) for p in pts], fill=1, outline=1)
            if grow:
                self.dr.line([self.px(*p) for p in pts + pts[:1]], fill=1, width=int(2 * grow / self.res))
        self.arr = None

    def line(self, pts, w):
        self.dr.line([self.px(*p) for p in pts], fill=1, width=max(1, int(round(w / self.res))), joint="curve")
        for p in pts:
            x, y = self.px(*p)
            r = w / 2 / self.res
            self.dr.ellipse([x - r, y - r, x + r, y + r], fill=1)
        self.arr = None

    def libre(self, pts):
        if self.arr is None:
            self.arr = np.array(self.img, dtype=bool)
        tmp = Image.new("1", self.img.size, 0)
        ImageDraw.Draw(tmp).polygon([self.px(*p) for p in pts], fill=1, outline=1)
        m = np.array(tmp, dtype=bool)
        if not m.any():
            return False
        return not (m & self.arr).any()


def _rect(c, u, w, d):
    """Rectangulo centrado en c, ancho w a lo largo de u, fondo d."""
    n = (-u[1], u[0])
    return [(c[0] + sx * u[0] * w / 2 + sy * n[0] * d / 2, c[1] + sx * u[1] * w / 2 + sy * n[1] * d / 2)
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


# ------------------------------------------------------------------ convertir
def convertir(spec, raw):
    M = Marco(spec)
    rnd = random.Random(spec.get("seed", 11))
    R = spec.get("radio", 450)
    excl = set(spec.get("excluir", []))
    out = {"_fuente": "(c) colaboradores de OpenStreetMap, ODbL. " + spec.get("_lugar", ""),
           "_fecha_osm": raw.get("osm3s", {}).get("timestamp_osm_base"),
           "edificios": [], "calles": [], "areas": [], "vias": [], "andenes": [], "arboles": []}
    occ = Ocupado(R)
    for z in spec.get("zonas_libres", []):
        occ.poly([tuple(p) for p in z])
    for e in raw["elements"]:
        if e["id"] in excl:
            continue
        t = e.get("tags", {})
        g = e.get("geometry")
        if e["type"] == "node":
            if t.get("natural") == "tree":
                x, y = M({"lat": e["lat"], "lon": e["lon"]})
                out["arboles"].append([x, y, 1.0, "osm"])
            continue
        if not g:
            continue          # relaciones: sin geometria plana en esta salida
        pts = [M(p) for p in g]
        closed = len(pts) > 3 and pts[0] == pts[-1]
        if closed:
            pts = pts[:-1]
        if "building" in t and closed:
            if t.get("building") in ("cathedral",) or t.get("amenity") == "place_of_worship" and "Catedral" in t.get("name", ""):
                continue
            h, src = alto(t, rnd)
            out["edificios"].append({"p": pts, "h": round(h, 1), "k": t["building"], "src": src})
            occ.poly(pts, grow=1.0)
        elif "highway" in t and not closed:
            w = ancho(t)
            out["calles"].append({"p": pts, "w": round(w, 1), "k": t["highway"], "n": t.get("name", "")})
            occ.line(pts, w + (6.0 if t["highway"] in AUTOS else 1.0))
        elif t.get("railway") in ("rail", "light_rail", "subway", "tram") and not closed:
            out["vias"].append({"p": pts, "k": t["railway"]})
            occ.line(pts, 8.0)
        elif t.get("railway") == "platform":
            if closed:
                out["andenes"].append({"p": pts})
                occ.poly(pts)
            else:
                out["calles"].append({"p": pts, "w": 4.0, "k": "platform", "n": ""})
                occ.line(pts, 4.0)
        elif closed and (t.get("leisure") in VERDE or t.get("landuse") in VERDE or t.get("natural") in VERDE):
            out["areas"].append({"p": pts, "k": "verde"})
            occ.poly(pts)
        elif closed and t.get("amenity") == "parking":
            out["areas"].append({"p": pts, "k": "playa"})
            occ.poly(pts)
        elif closed and (t.get("landuse") in ("railway",) or t.get("amenity") in ("school", "college")):
            occ.poly(pts)        # sin casas inventadas adentro
    if spec.get("relleno", True):
        _relleno(out, occ, rnd, R)
    return out


def _relleno(out, occ, rnd, R):
    """Casas sobre la linea municipal de las calles con autos, donde no hay
    nada; arboles de vereda; arboles en las areas verdes."""
    casas = 0
    for c in out["calles"]:
        if c["k"] not in AUTOS:
            continue
        pts = c["p"]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            L = math.hypot(bx - ax, by - ay)
            if L < 6:
                continue
            u = ((bx - ax) / L, (by - ay) / L)
            n = (-u[1], u[0])
            for side in (-1, 1):
                s = rnd.uniform(0, 4)
                while s < L - 4:
                    lw = rnd.uniform(8.0, 12.0)
                    d = rnd.uniform(11.0, 18.0)
                    off = c["w"] / 2 + 3.0 + rnd.uniform(0.0, 1.5) + d / 2
                    cx = ax + u[0] * (s + lw / 2) + side * n[0] * off
                    cy = ay + u[1] * (s + lw / 2) + side * n[1] * off
                    if math.hypot(cx, cy) < R - 15:
                        q = _rect((cx, cy), u, lw * 0.97, d)
                        if occ.libre(q):
                            r = rnd.random()
                            h = 4.5 if r < 0.45 else 7.2 if r < 0.85 else rnd.uniform(9.5, 14.5)
                            out["edificios"].append({"p": [(round(x, 2), round(y, 2)) for x, y in q],
                                                     "h": round(h, 1), "k": "casa", "src": "relleno"})
                            occ.poly(q)
                            casas += 1
                    s += lw
            # arboles de vereda
            for side in (-1, 1):
                s = rnd.uniform(2, 8)
                while s < L:
                    if rnd.random() < 0.75:
                        off = c["w"] / 2 + 1.4
                        x = ax + u[0] * s + side * n[0] * off
                        y = ay + u[1] * s + side * n[1] * off
                        if math.hypot(x, y) < R - 5:
                            out["arboles"].append([round(x, 2), round(y, 2), round(rnd.uniform(0.8, 1.2), 2), "relleno"])
                    s += rnd.uniform(9, 14)
    for a in out["areas"]:
        if a["k"] != "verde":
            continue
        xs = [p[0] for p in a["p"]]
        ys = [p[1] for p in a["p"]]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        for _ in range(int(area / 230)):
            x, y = rnd.uniform(min(xs), max(xs)), rnd.uniform(min(ys), max(ys))
            if _dentro(a["p"], x, y) and not _cerca_de_camino(out["calles"], x, y):
                out["arboles"].append([round(x, 2), round(y, 2), round(rnd.uniform(0.9, 1.4), 2), "relleno"])
    print(f"relleno: {casas} casas, {len(out['arboles'])} arboles")


def _cerca_de_camino(calles, x, y):
    for c in calles:
        if c["k"] not in ("footway", "path", "pedestrian"):
            continue
        for (ax, ay), (bx, by) in zip(c["p"], c["p"][1:]):
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy or 1
            t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / L2))
            if math.hypot(ax + t * dx - x, ay + t * dy - y) < c["w"] / 2 + 1.5:
                return True
    return False


# ------------------------------------------------------------------ terreno
TILE = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"


def _tile_xy(lat, lon, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


class Dem:
    """Elevacion (m sobre el mar) en cualquier lat/lon, interpolada de los
    tiles terrarium (alto = R*256 + G + B/256 - 32768)."""

    def __init__(self, cache, z=15):
        self.cache, self.z, self.tiles = cache, z, {}
        cache.mkdir(parents=True, exist_ok=True)

    def _tile(self, tx, ty):
        k = (tx, ty)
        if k not in self.tiles:
            f = self.cache / f"{self.z}_{tx}_{ty}.png"
            if not f.exists():
                url = TILE.format(z=self.z, x=tx, y=ty)
                f.write_bytes(urllib.request.urlopen(urllib.request.Request(
                    url, headers={"User-Agent": "procedural-anime/1"}), timeout=60).read())
            a = np.asarray(Image.open(f).convert("RGB"), dtype=np.float64)
            self.tiles[k] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
        return self.tiles[k]

    def __call__(self, lat, lon):
        x, y = _tile_xy(lat, lon, self.z)
        px, py = (x % 1) * 256 - 0.5, (y % 1) * 256 - 0.5
        tx, ty = int(x), int(y)
        x0, y0 = math.floor(px), math.floor(py)
        fx, fy = px - x0, py - y0

        def at(i, j):
            ti, tj = tx, ty
            if i < 0:
                ti, i = ti - 1, i + 256
            elif i > 255:
                ti, i = ti + 1, i - 256
            if j < 0:
                tj, j = tj - 1, j + 256
            elif j > 255:
                tj, j = tj + 1, j - 256
            return self._tile(ti, tj)[j, i]
        return ((at(x0, y0) * (1 - fx) + at(x0 + 1, y0) * fx) * (1 - fy)
                + (at(x0, y0 + 1) * (1 - fx) + at(x0 + 1, y0 + 1) * fx) * fy)


def terreno(spec, M, cache):
    T = spec["terreno"]
    paso, lado = T.get("paso", 5.0), T.get("lado", 1400.0)
    n = int(lado / paso) + 1
    x0 = y0 = -lado / 2
    dem = Dem(cache)
    z = np.zeros((n, n))
    for j in range(n):
        for i in range(n):
            la, lo = M.inverse(x0 + i * paso, y0 + j * paso)
            z[j, i] = dem(la, lo)
    # suavizado: SRTM es de 30 m y mide techos y copas; el escalon de 1 m
    # entre celdas se veria como terrazas
    sig = T.get("suavizado_m", 10.0) / paso
    if sig > 0:
        from scipy.ndimage import gaussian_filter
        z = gaussian_filter(z, sig, mode="nearest")
    z -= T["ref_m"]
    # plataformas: la pieza modelada manda (la catedral sobre su zocalo)
    yy, xx = np.mgrid[0:n, 0:n] * paso + np.array([y0, x0])[:, None, None]
    for pl in T.get("plataformas", []):
        (ax, ay), (bx, by) = pl["min"], pl["max"]
        dx = np.maximum(np.maximum(ax - xx, xx - bx), 0)
        dy = np.maximum(np.maximum(ay - yy, yy - by), 0)
        d = np.hypot(dx, dy)
        w = np.clip(1 - d / pl.get("borde", 20.0), 0, 1)
        w = w * w * (3 - 2 * w)
        z = z * (1 - w) + pl["z"] * w
    print(f"terreno {n}x{n} cada {paso} m: z de {z.min():.1f} a {z.max():.1f} (escena)")
    return {"x0": x0, "y0": y0, "paso": paso, "n": n, "z": [round(float(v), 2) for v in z.ravel()]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode", type=Path)
    ap.add_argument("--bajar", action="store_true", help="vuelve a bajar los datos de Overpass")
    a = ap.parse_args()
    data = a.episode / "data"
    spec = json.loads((data / "osm.json").read_text(encoding="utf-8"))
    raw_p = data / "osm_raw.json"
    if a.bajar or not raw_p.exists():
        bajar(spec, raw_p)
    out = convertir(spec, json.loads(raw_p.read_text(encoding="utf-8")))
    if spec.get("terreno"):
        out["terreno"] = terreno(spec, Marco(spec), data / "dem")
    dst = data / "entorno.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    src = {}
    for b in out["edificios"]:
        src[b["src"]] = src.get(b["src"], 0) + 1
    print(f"{dst}: {len(out['edificios'])} edificios {src}, {len(out['calles'])} calles, "
          f"{len(out['areas'])} areas, {len(out['vias'])} vias, {len(out['arboles'])} arboles")


if __name__ == "__main__":
    main()
