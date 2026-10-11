"""
engrane.py - Verifica que dos engranajes que engranan no se atraviesen (sin Blender).

    python motor/engrane.py episodios/<ep> <plano> pinon_roto:rueda_escape rueda_escape_pinon:rueda_grande

colision.py no sirve para esto: dos ruedas engranadas ya se tocan en el frame 1
(van a la base) y no distingue tocar de atravesar. Aca se arma el contorno de
dientes de cada una (mismo PERFIL que gear_mesh), girado con gear_angle (lo
mismo que renderiza la escena) y llevado al plano comun; frame por frame se
mide cuanto entra un contorno en el otro. Los dos engranajes tienen que tener
la misma orientacion ("rot" o "axis").
"""

import argparse
import math
import sys
from pathlib import Path
from unittest import mock

MOTOR = Path(__file__).resolve().parent
sys.path.insert(0, str(MOTOR))
for name in ("bpy", "bmesh", "mathutils"):
    sys.modules[name] = mock.MagicMock()
from plano import load_shot  # noqa: E402
from piezas import ctx  # noqa: E402
from piezas.mecanica import AXES, PERFIL, gear_angle  # noqa: E402


def euler_xyz(rx, ry, rz):
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    # R = Rz @ Ry @ Rx (orden XYZ de Blender)
    return [[cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx],
            [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx],
            [-sy, cy * sx, cy * cx]]


def basis(g):
    rot = [math.radians(a) for a in g["rot"]] if "rot" in g else list(AXES[g.get("axis", "y")])
    R = euler_xyz(*rot)
    col = lambda i: [R[0][i], R[1][i], R[2][i]]  # noqa: E731
    return col(0), col(1)


def contour(g, ang_deg, center_uv, sub=4):
    n, r = g.get("teeth", 24), g["r"]
    depth = g.get("depth", r * 0.08)
    pts = []
    for k in range(n):
        for ph, tip in PERFIL:
            a = 2 * math.pi * (k + ph) / n
            pts.append((a, r - depth + depth * tip))
    out = []
    a0 = math.radians(ang_deg)
    for i in range(len(pts)):
        (aa, ra), (ab, rb) = pts[i], pts[(i + 1) % len(pts)]
        if ab < aa:
            ab += 2 * math.pi
        for s in range(sub):
            t = s / sub
            a, rr = aa + (ab - aa) * t, ra + (rb - ra) * t
            out.append((center_uv[0] + rr * math.cos(a + a0), center_uv[1] + rr * math.sin(a + a0)))
    return out


def inside(p, poly):
    x, y = p
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def dist_edge(p, poly):
    best = 1e9
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        dx, dy = x2 - x1, y2 - y1
        t = max(0.0, min(1.0, ((p[0] - x1) * dx + (p[1] - y1) * dy) / (dx * dx + dy * dy or 1)))
        best = min(best, math.hypot(p[0] - x1 - t * dx, p[1] - y1 - t * dy))
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode", type=Path)
    ap.add_argument("shot")
    ap.add_argument("pares", nargs="+", help="a:b")
    ap.add_argument("--tol", type=float, default=0.0015, help="metros de contacto tolerados")
    a = ap.parse_args()
    cfg = load_shot(a.episode / "shots" / f"{a.shot}.json")
    ctx.CFG = cfg
    E = cfg["engranajes"]
    tick, stop = E.get("tick", {"bps": 1.0, "jump": 0.18}), E.get("stop")
    G = {g["name"]: g for g in E["list"]}
    bad = False
    for par in a.pares:
        na, nb = par.split(":")
        ga, gb = G[na], G[nb]
        X, Y = basis(ga)
        uv = lambda g: (sum(g["at"][i] * X[i] for i in range(3)), sum(g["at"][i] * Y[i] for i in range(3)))  # noqa
        ca, cb = uv(ga), uv(gb)
        worst, frames = 0.0, []
        for f in range(1, cfg["frames"] + 1):
            pa = contour(ga, gear_angle(ga, f, tick, stop), ca)
            pb = contour(gb, gear_angle(gb, f, tick, stop), cb)
            pen = max([dist_edge(p, pb) for p in pa if inside(p, pb)] +
                      [dist_edge(p, pa) for p in pb if inside(p, pa)] + [0.0])
            if pen > a.tol:
                frames.append(f)
            worst = max(worst, pen)
        gap = math.hypot(ca[0] - cb[0], ca[1] - cb[1])
        msg = f"{na} x {nb}: centros a {gap:.4f} m, maxima penetracion {worst * 1000:.1f} mm"
        if frames:
            bad = True
            msg += f" en {len(frames)} frames ({frames[0]}-{frames[-1]})"
        print(msg)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
