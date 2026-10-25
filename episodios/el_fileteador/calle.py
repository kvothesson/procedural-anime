"""calle.py - Caminito en numeros, sin Blender: la polilinea de la calle medida
por s (metros desde la esquina de Garibaldi y Lamadrid) y el plan de los
lotes (que conventillo va donde, cuantos pisos, colores, balcon, escalera).

Lo usan caminito.py (dentro de Blender, para armar la geometria) y planos.py
(para ubicar camaras y al robot sobre balcones y escaleras reales del plan).
"""

import json
import random
from pathlib import Path

import numpy as np

PALETA = ["#6fb4d4", "#efc12f", "#c4372c", "#4c8a3c", "#dc7a2f", "#2e5ea6", "#5c9e86", "#e9dcc0"]
TRIM = ["#f0ebe0", "#c4372c", "#efc12f", "#2e5ea6", "#4c8a3c"]
PISO = 3.1


class Calle:
    """La polilinea de Caminito medida por longitud de arco."""

    def __init__(self, pts):
        p = np.asarray(pts, float)
        d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
        self.L = float(d[-1])
        n = int(self.L / 0.5) + 1
        s = np.linspace(0, self.L, n)
        self.s = s
        self.p = np.c_[np.interp(s, d, p[:, 0]), np.interp(s, d, p[:, 1])]
        t = np.gradient(self.p, axis=0)
        self.t = t / np.linalg.norm(t, axis=1, keepdims=True)
        self.n = np.c_[-self.t[:, 1], self.t[:, 0]]

    def at(self, s):
        s = float(np.clip(s, 0, self.L))
        i = int(round(s / self.L * (len(self.s) - 1)))
        return self.p[i], self.t[i], self.n[i]

    def punto(self, s, lado=0.0, z=0.0):
        """(x, y, z) a s metros de la esquina, 'lado' metros hacia +n."""
        p, t, n = self.at(s)
        q = p + n * lado
        return (float(q[0]), float(q[1]), float(z))


def cargar(ep, datos="data/entorno.json"):
    d = json.loads((Path(ep) / datos).read_text(encoding="utf-8"))
    return Calle([c for c in d["calles"] if c.get("n") == "Caminito"][0]["p"])


def lotes(C, e):
    """Plan de los conventillos de los dos lados: todo lo que sale del azar,
    en el orden fijo de la semilla. Cada lote: lado, s0, s1, o (esquina del
    frente sobre la fachada), U (a lo largo), N (hacia adentro del lote), L,
    pisos (0 = tapial), colores, trim, postigos, balcon (b0, b1 en u),
    escalera (None, "izq" o "der")."""
    rnd = random.Random(e.get("seed", 3))
    ancho = e.get("ancho", 8.0)
    out = []
    for lado in (1, -1):
        s = e.get("desde", 2.0)
        while s < e.get("hasta", C.L - 2.0):
            w = rnd.uniform(5.0, 8.5)
            if s + w > C.L - 1.0:
                break
            p0, _, _ = C.at(s)
            p1, _, _ = C.at(s + w)
            U = (p1 - p0) / np.linalg.norm(p1 - p0)
            N = np.array([-U[1], U[0]]) * lado
            o = p0 + N * (ancho / 2)
            L = float(np.linalg.norm(p1 - p0))
            lo = {"lado": lado, "s0": s, "s1": s + w, "o": o.tolist(), "U": U.tolist(), "N": N.tolist(),
                  "L": L}
            if rnd.random() < 0.12:
                lo.update(pisos=0, h=2.4, mural=rnd.choice(PALETA))
            else:
                pisos = rnd.choice((2, 2, 3))
                lo.update(pisos=pisos, h=pisos * PISO, colores=[rnd.choice(PALETA) for _ in range(pisos)],
                          trim=rnd.choice(TRIM), postigos=rnd.choice(PALETA))
                balcon = pisos >= 2 and rnd.random() < 0.65
                lo["balcon"] = (L * 0.12, L * 0.88) if balcon else None
                lo["escalera"] = None
                if balcon and rnd.random() < 0.5:
                    lo["escalera"] = "izq" if rnd.random() < 0.5 else "der"
            out.append(lo)
            s += w + rnd.uniform(0.0, 0.25)
    return out


def en_lote(lo, u, v, z):
    """Punto (x, y, z) del mundo en el marco del lote."""
    o, U, N = np.asarray(lo["o"]), np.asarray(lo["U"]), np.asarray(lo["N"])
    q = o + U * u + N * v
    return (float(q[0]), float(q[1]), float(z))
