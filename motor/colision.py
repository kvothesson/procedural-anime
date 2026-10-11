"""
colision.py - Piezas que se atraviesan, frame por frame (con Blender, sin render).

    python motor/colision.py episodios/<ep> <plano> [--cada 1] [--solo objeto_a,objeto_b]

Arma la escena del plano y, en cada frame, cruza las mallas visibles de a pares
con un BVH en coordenadas de mundo. Los pares que ya se tocan en el frame 1
(articulaciones, piezas apoyadas) son la base y no se informan ("colision_base"
en el JSON agrega otros frames, p. ej. el robot ya armado de un despiece); todo choque
nuevo se informa con el rango de frames. Los contactos buscados (una pieza que
encaja en otra) se declaran en el JSON: "colision_ok": [["a", "b"], ...]. --solo: nombres (o prefijos) de los
objetos a cruzar contra todo lo demas.

Mirar frames no alcanza para ver traspasos: un brazo que atraviesa un
engranaje se ve tres frames y desaparece.
"""

import argparse
import subprocess
import sys
from pathlib import Path

MOTOR = Path(__file__).resolve().parent


def outside():
    sys.path.insert(0, str(MOTOR))
    from render import find_blender
    ap = argparse.ArgumentParser()
    ap.add_argument("episode", type=Path)
    ap.add_argument("shot")
    ap.add_argument("--cada", type=int, default=1)
    ap.add_argument("--solo", default="")
    ap.add_argument("--base", action="store_true", help="listar contactos del frame 1 entre piezas no vecinas")
    a = ap.parse_args()
    shot = (a.episode / "shots" / f"{a.shot}.json").resolve()
    cmd = [find_blender(), "-b", "-P", str(Path(__file__).resolve()), "--", str(shot), "_",
           "--sin-render", "--cada", str(a.cada), "--solo", a.solo] + (["--base"] if a.base else [])
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = p.stdout + p.stderr
    rep = [l[4:] for l in out.splitlines() if l.startswith("COL ")]
    if "Traceback" in out or not rep:
        print("\n".join(out.splitlines()[-30:]))
        sys.exit(1)
    print("\n".join(rep))


def inside():
    import runpy
    import bpy
    from mathutils.bvhtree import BVHTree

    argv = sys.argv[sys.argv.index("--") + 1:]
    cada = int(argv[argv.index("--cada") + 1])
    solo = [x for x in argv[argv.index("--solo") + 1].split(",") if x] if "--solo" in argv else []
    runpy.run_path(str(MOTOR / "escena.py"), run_name="__main__")
    scene = bpy.context.scene
    obs = [o for o in bpy.data.objects if o.type == "MESH" and not o.name.startswith(("piso", "pared"))]

    def tree(o):
        m = o.matrix_world
        verts = [m @ v.co for v in o.data.vertices]
        polys = [tuple(p.vertices) for p in o.data.polygons]
        return BVHTree.FromPolygons(verts, polys), verts

    def boxes_touch(va, vb):
        for i in range(3):
            if max(v[i] for v in va) < min(v[i] for v in vb) or max(v[i] for v in vb) < min(v[i] for v in va):
                return False
        return True

    def pick(o):
        return not solo or any(o.name.startswith(s) for s in solo)

    def hits():
        live = [o for o in obs if not o.hide_render]
        data = {o.name: tree(o) for o in live}
        out = set()
        for i, a in enumerate(live):
            for b in live[i + 1:]:
                if not (pick(a) or pick(b)):
                    continue
                (ta, va), (tb, vb) = data[a.name], data[b.name]
                if boxes_touch(va, vb) and ta.overlap(tb):
                    out.add((a.name, b.name))
        return out

    from plano import load_shot
    shot = load_shot(argv[0])
    ok = {tuple(sorted(x)) for x in shot.get("colision_ok", [])}
    # "colision_base": frames cuyos contactos son normales (por defecto el 1; en un
    # armado por despiece, tambien el frame con el robot completo)
    base = {(a, b) for a, b in ok} | {(b, a) for a, b in ok}
    for fb in shot.get("colision_base", [1]):
        scene.frame_set(fb)
        base |= hits()
    found = {}
    for f in range(1, scene.frame_end + 1, cada):
        scene.frame_set(f)
        for pair in hits() - base:
            found.setdefault(pair, []).append(f)
    print(f"COL base (se tocan en el frame 1, no se informan): {len(base)} pares", flush=True)
    if "--base" in argv:
        # los de la base que no son vecinos directos (mismo padre o padre/hijo)
        def near(a, b):
            A, B = bpy.data.objects[a], bpy.data.objects[b]
            pa, pb = A.parent, B.parent
            return pa == pb or pa == B or pb == A or (pa and pa.parent == pb) or (pb and pb.parent == pa)
        for a, b in sorted(base):
            if a in bpy.data.objects and b in bpy.data.objects and not near(a, b):
                print(f"COL   base lejana: {a} x {b}", flush=True)
    if not found:
        print("COL sin choques nuevos", flush=True)
    for (a, b), fs in sorted(found.items(), key=lambda x: x[1][0]):
        print(f"COL {a} x {b}: frames {fs[0]}-{fs[-1]} ({len(fs)})", flush=True)


if "bpy" in sys.modules or any("blender" in x.lower() for x in sys.argv[:1]):
    inside()
else:
    outside()
