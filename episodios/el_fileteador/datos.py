"""datos.py - Entorno de La Boca sin los edificios de la franja de Caminito.

    python motor/osm.py episodios/el_fileteador      # data/entorno.json (OSM)
    python episodios/el_fileteador/datos.py           # data/entorno_caminito.json

Los conventillos de Caminito los arma piezas.py (caminito) sobre la calle
real; los edificios de OSM de esa franja (zonas_libres de osm.json) se sacan
para que no se pisen. osm.py solo usa zonas_libres para no inventar casas:
no saca lo que trae OSM. Tambien salen los arboles de la franja (la calle no
tiene).
"""

import json
from pathlib import Path

EP = Path(__file__).resolve().parent


def adentro(x, y, poly):
    c = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


def main():
    spec = json.loads((EP / "data" / "osm.json").read_text(encoding="utf-8"))
    d = json.loads((EP / "data" / "entorno.json").read_text(encoding="utf-8"))
    zonas = spec.get("zonas_libres", [])

    def libre(x, y):
        return any(adentro(x, y, z) for z in zonas)

    n0, a0 = len(d["edificios"]), len(d["arboles"])
    # sale todo edificio que toca la franja (con el centroide, los grandes que
    # dan a la calle se quedaban y se pisaban con los conventillos)
    d["edificios"] = [b for b in d["edificios"] if not any(libre(*p) for p in b["p"])]
    d["arboles"] = [t for t in d["arboles"] if not libre(t[0], t[1])]
    (EP / "data" / "entorno_caminito.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    print(f"edificios {n0} -> {len(d['edificios'])}, arboles {a0} -> {len(d['arboles'])}")


if __name__ == "__main__":
    main()
