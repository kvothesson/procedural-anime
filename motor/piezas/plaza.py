"""Plaza: ovalo de pasto con camino y canteros, arboles de anime, mastil con
bandera que ondea."""

import math
import random

import bpy
import bmesh

from .base import box_mesh, ellipse_ring, link
from .materiales import mat_toon, mat_wet_ground


def build_plaza(e, colls):
    """Plaza de la Republica: ovalo de pasto, camino de baldosa en el borde
    y un cantero de flores que la cruza. Va apenas sobre el asfalto."""
    cx, cy = e["center"]
    rx, ry = e["radii"]
    grass = ellipse_ring("pasto", cx, cy, rx, ry, 0, 0.93, 0.0, 0.08)
    grass.data.materials.append(mat_toon("pasto_m", e["grass"]))
    link(grass, colls["main"])
    path = ellipse_ring("camino", cx, cy, rx, ry, 0.93, 1.0, 0.0, 0.10)
    if e.get("wet_path"):
        # el charco atraviesa camino y asfalto: los dos llevan el mismo hueco
        path.data.materials.append(mat_wet_ground("camino_m", e["path"], e["wet_path"]))
    else:
        path.data.materials.append(mat_toon("camino_m", e["path"]))
    link(path, colls["main"])
    for k, (a, b) in enumerate(e["beds"]):
        bed = ellipse_ring(f"cantero{k}", cx, cy, rx, ry, a, b, 0.0, 0.35)
        bed.data.materials.append(mat_toon(f"cantero{k}_m", e["flowers"]))
        link(bed, colls["main"])
    # base del Obelisco: escalinata baja
    st = bpy.data.objects.new("escalon", box_mesh("escalon", e["plinth"], e["plinth"], 0.5))
    st.location = (cx, cy, 0)
    st.data.materials.append(mat_toon("escalon_m", e["path"]))
    link(st, colls["main"])


def build_trees(e, colls):
    """Arboles de anime: copa de 2-3 esferas suaves, tronco fino. Sin facetas
    (sombreado suave + subdiv 2) para que Line Art dibuje solo el contorno."""
    rnd = random.Random(e.get("seed", 13))
    leaves = [mat_toon(f"copa{i}", c) for i, c in enumerate(e["colors"])]
    trunk_m = mat_toon("tronco_m", e["trunk"])
    spots = []
    for row in e.get("rows", []):
        y = row["y"][0]
        while y < row["y"][1]:
            spots.append((row["x"] + rnd.uniform(-1, 1), y))
            y += row["spacing"] * rnd.uniform(0.8, 1.2)
    for ring in e.get("rings", []):
        cx, cy = ring["center"]
        for i in range(ring["count"]):
            a = 2 * math.pi * i / ring["count"] + rnd.uniform(-0.05, 0.05)
            if ring.get("skip_front") and math.sin(a) < -0.55:
                continue    # dejar libre la vista de camara al Obelisco
            spots.append((cx + ring["rx"] * math.cos(a), cy + ring["ry"] * math.sin(a)))
    for k, (x, y) in enumerate(spots):
        s = rnd.uniform(*e["scale"])
        tr = bpy.data.objects.new("tronco", box_mesh("tronco", 0.35 * s, 0.35 * s, 3.2 * s))
        tr.location = (x, y, 0)
        tr.data.materials.append(trunk_m)
        link(tr, colls["main"])
        mat = rnd.choice(leaves)
        for j in range(rnd.randint(2, 3)):
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=s * rnd.uniform(1.6, 2.3),
                                                  location=(x + rnd.uniform(-1, 1) * s,
                                                            y + rnd.uniform(-1, 1) * s,
                                                            s * rnd.uniform(3.8, 5.0)))
            cp = bpy.context.active_object
            for cc in list(cp.users_collection):
                cc.objects.unlink(cp)
            for poly in cp.data.polygons:
                poly.use_smooth = True
            cp.data.materials.append(mat)
            link(cp, colls["main"])


def build_flag(e, colls):
    """Mastil con la bandera argentina: celeste, blanco, celeste y el sol en
    la misma malla (asi ondea con ella). Ondea con un modificador Wave que
    avanza desde el mastil; un grupo de vertices la deja fija contra el palo
    y cada vez mas suelta hacia la punta. Es funcion del frame: determinista."""
    x, y = e["at"]
    H = e["height"]
    pole = bpy.data.objects.new("mastil", box_mesh("mastil", 0.22, 0.22, H))
    pole.location = (x, y, 0)
    pole.data.materials.append(mat_toon("mastil_m", e["pole"]))
    link(pole, colls["main"])
    W, Hf = e["size"]
    nx, nz = 48, 27
    z_top = H - 0.3
    sun_c = (W * 0.5, Hf * 0.5)
    sun_r = Hf * 0.13
    mesh = bpy.data.meshes.new("bandera")
    bm = bmesh.new()
    grid = [[bm.verts.new((W * i / nx, 0.0, -Hf * (1 - j / nz))) for j in range(nz + 1)]
            for i in range(nx + 1)]
    for i in range(nx):
        for j in range(nz):
            f = bm.faces.new([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]])
            band = j * 3 // nz            # 0 abajo, 1 medio, 2 arriba
            cx, cz = W * (i + 0.5) / nx, Hf * (j + 0.5) / nz
            if math.hypot(cx - sun_c[0], cz - sun_c[1]) < sun_r:
                f.material_index = 2
            else:
                f.material_index = 1 if band == 1 else 0
    bm.to_mesh(mesh)
    bm.free()
    fl = bpy.data.objects.new("bandera", mesh)
    fl.location = (x + 0.12, y, z_top)
    fl.data.materials.append(mat_toon("celeste", "#74acdf"))
    fl.data.materials.append(mat_toon("blanco", "#f2f2f2"))
    fl.data.materials.append(mat_toon("sol_m", "#f6b40e"))
    link(fl, colls["main"])
    # peso 0 en el mastil, 1 en la punta (curva suave): el palo no se mueve
    vg = fl.vertex_groups.new(name="suelta")
    for v in fl.data.vertices:
        vg.add([v.index], (v.co.x / W) ** 0.8, "REPLACE")
    wv = fl.modifiers.new("ondea", "WAVE")
    wv.use_x, wv.use_y = True, False
    wv.use_normal = True
    wv.start_position_x = -W * 0.5      # coordenadas locales: el frente de onda nace detras del palo
    wv.height = e.get("wave_height", 0.45)
    wv.width = e.get("wave_width", 2.2)
    wv.narrowness = e.get("wave_narrow", 1.2)
    wv.speed = e.get("wave_speed", 0.18)
    wv.time_offset = -200               # la onda ya viene corriendo en el frame 1
    wv.use_cyclic = True
    wv.vertex_group = "suelta"
    # flamea tambien en altura: segundo frente, mas chico, en diagonal
    wv2 = fl.modifiers.new("ondea2", "WAVE")
    wv2.use_x, wv2.use_y = True, True
    wv2.use_normal = True
    wv2.start_position_x, wv2.start_position_y = -W, Hf
    wv2.height = e.get("wave_height", 0.45) * 0.4
    wv2.width = e.get("wave_width", 2.2) * 0.6
    wv2.speed = e.get("wave_speed", 0.18) * 1.3
    wv2.time_offset = -200
    wv2.vertex_group = "suelta"
