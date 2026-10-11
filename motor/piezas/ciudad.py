"""Ciudad: calle mojada, hileras de edificios, megatorres, faroles y cables."""

import math
import random

import bpy
import bmesh

from .base import bm_box, box_mesh, CHAR_W, lin, link, text, tint_light
from .materiales import mat_beam, mat_flat, mat_neon, mat_screen, mat_tint, mat_toon, mat_wet_ground


def build_street(e, colls):
    L, W, S = e["length"], e["width"], e["sidewalk"]
    y0 = e.get("start", -20.0)
    ground = bpy.data.objects.new("calle", box_mesh("calle", W + 2 * S + 40, L, 0.02))
    ground.location = (0, y0 + L / 2, -0.02)
    ground.data.materials.append(mat_wet_ground("asfalto", e["asphalt"], e["puddles"]))
    link(ground, colls["main"])
    side_mat = mat_toon("vereda", e["sidewalk_color"])
    for sgn in (-1, 1):
        sw = bpy.data.objects.new("vereda", box_mesh("vereda", S, L, e.get("curb", 0.18)))
        sw.location = (sgn * (W / 2 + S / 2), y0 + L / 2, 0)
        sw.data.materials.append(side_mat)
        link(sw, colls["main"])
    # linea central a trazos, con trazos que faltan (pixeles muertos de la Ruta 404)
    rnd = random.Random(e.get("seed", 4))
    dash = mat_neon("trazo", e["line_color"], e.get("line_strength", 0.6))
    y = y0
    while y < y0 + L:
        if rnd.random() > e.get("missing", 0.25):
            d = bpy.data.objects.new("trazo", box_mesh("trazo", 0.18, 2.2, 0.01))
            d.location = (0, y, 0.0)
            d.data.materials.append(dash)
            link(d, colls["neon"])
        y += 4.5
    # velo del reflejo
    veil = bpy.data.objects.new("velo", box_mesh("velo", W + 2 * S + 40, L, 0.001))
    veil.location = (0, y0 + L / 2, -0.06)
    veil.data.materials.append(mat_tint("velo", e["reflection_tint"], e.get("reflection_dim", 0.45)))
    link(veil, colls["veil"])


def _bandera(name, text, color, size, at, facing, colls, rnd, frame_color):
    """Cartel horizontal que sale perpendicular de la fachada (tipo Corrientes):
    el que se lee de frente desde la calle. facing: +1 si sale hacia +x."""
    wdt = size * CHAR_W * len(text) + size * 0.9
    h = size * 1.7
    depth = 0.25
    x, y, z = at
    cx = x + facing * (wdt / 2 + 0.3)
    body = bpy.data.objects.new(name + "_caja", box_mesh(name, wdt, depth, h))
    body.location = (cx, y, z)
    body.data.materials.append(mat_toon(name + "_m", frame_color))
    link(body, colls["main"])
    # mensula que lo sostiene contra la pared
    arm = bpy.data.objects.new(name + "_brazo", box_mesh(name + "_b", 0.35, 0.12, 0.12))
    arm.location = (x + facing * 0.17, y, z + h + 0.1)
    arm.data.materials.append(mat_toon(name + "_bm", frame_color))
    link(arm, colls["main"])
    neon = mat_neon(name + "_n", color, 1.0)
    for dy in (-1, 1):
        for zz in (0.1, h - 0.15):
            bar = bpy.data.objects.new(name + "_marco", box_mesh(name + "_mf", wdt - 0.15, 0.05, 0.06))
            bar.location = (cx, y + dy * (depth / 2 + 0.02), z + zz)
            bar.data.materials.append(neon)
            link(bar, colls["neon"])
        text(name + "_txt", text, size, neon,
              (cx, y + dy * (depth / 2 + 0.03), z + h / 2),
              (math.pi / 2, 0, 0 if dy < 0 else math.pi), colls["neon"])
    tint_light(name + "_luz", color, rnd.uniform(0.8, 1.2) * size * 700,
                (x + facing * (wdt + 1.2), y, z + h / 2), colls)


def _frente(name, text, color, size, at, facing, length, colls, rnd, frame_color):
    """Marquesina pegada a la fachada, sobre la vidriera. Se ve en escorzo:
    da textura de calle comercial mas que lectura."""
    x, y, z = at
    size = min(size, length * 0.9 / (CHAR_W * len(text) + 0.6))
    h = size * 1.6
    body = bpy.data.objects.new(name + "_caja", box_mesh(name, 0.2, length, h))
    body.location = (x + facing * 0.1, y, z)
    body.data.materials.append(mat_toon(name + "_m", frame_color))
    link(body, colls["main"])
    neon = mat_neon(name + "_n", color, 1.0)
    # el texto mira a la calle: (90, 0, +-90) lo gira de -y a +-x
    text(name + "_txt", text, size, neon,
          (x + facing * 0.23, y, z + h / 2),
          (math.pi / 2, 0, math.pi / 2 * facing), colls["neon"])
    tint_light(name + "_luz", color, size * 500,
                (x + facing * 1.5, y, z + h / 2), colls)


def _building_mesh(e, rnd, sx, sy, sz, face):
    """Caja del edificio + balcones corridos en la fachada que mira a 'face'
    ((+-1, 0) o (0, +-1)). Los balcones usan el slot de material 1."""
    mesh = bpy.data.meshes.new("edif")
    bm = bmesh.new()
    bm_box(bm, 0, 0, 0, sx, sy, sz)
    if rnd.random() < e.get("balconies", 0.0):
        pz = e["windows"]["pitch_z"]
        z = e["windows"]["base"] + 0.05
        fx, fy = face
        while z < sz - 2.5:
            if fx:
                bm_box(bm, fx * (sx / 2 + 0.35), 0, z, 0.7, sy * 0.86, 0.16, 1)
            else:
                bm_box(bm, 0, fy * (sy / 2 + 0.35), z, sx * 0.86, 0.7, 0.16, 1)
            z += pz
        # cornisa: remate horizontal que en la foto marca cada edificio
        bm_box(bm, 0, 0, sz, sx + 0.6, sy + 0.6, 0.5, 1)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def _billboard(e, rnd, x, y, roof, colls):
    """Cartel de terraza mirando a la plaza (-y). Pantalla emisiva lisa con
    marco oscuro; se apaga con el resto."""
    if rnd.random() >= e.get("billboards", 0.0):
        return
    w, h = rnd.uniform(6, 11), rnd.uniform(3.5, 6)
    frame = bpy.data.objects.new("cartel_marco", box_mesh("cartel_marco", w + 0.6, 0.4, h + 0.6))
    frame.location = (x, y, roof + 1.5)
    frame.data.materials.append(mat_toon("cartel_marco_m", e.get("billboard_frame", "#1a1830")))
    link(frame, colls["main"])
    for leg in (-1, 1):
        lg = bpy.data.objects.new("cartel_pata", box_mesh("cartel_pata", 0.25, 0.25, 1.5))
        lg.location = (x + leg * w * 0.35, y, roof)
        lg.data.materials.append(mat_toon("cartel_pata_m", "#1a1830"))
        link(lg, colls["main"])
    scr = bpy.data.objects.new("pantalla", box_mesh("pantalla", w, 0.05, h))
    scr.location = (x, y - 0.24, roof + 1.8)
    c1 = rnd.choice(e["billboard_colors"])
    if e.get("screen_dark"):
        scr.data.materials.append(mat_screen("pantalla_m", c1, e["screen_dark"],
                                             freq=rnd.uniform(0.6, 1.6), speed=rnd.uniform(1.5, 4.0),
                                             axis=rnd.choice([0, 2])))
    else:
        scr.data.materials.append(mat_neon("pantalla_m", c1, 0.9))
    link(scr, colls["neon"])


def build_row_x(e, colls):
    """Hilera de edificios de frente a la camara (fachada a -y), cruzando el
    fondo: la otra vereda de la avenida, con el hueco de Corrientes."""
    rnd = random.Random(e.get("seed", 21))
    x = e["x"][0]
    while x < e["x"][1]:
        bw = rnd.uniform(*e["width"])
        if e["gap"][0] < x + bw / 2 < e["gap"][1]:
            x = e["gap"][1]
            continue
        bh = rnd.uniform(*e["height"])
        bd = rnd.uniform(*e["depth"])
        color = rnd.choice(e["colors"])
        yb = e["y"] + rnd.uniform(0, e.get("setback", 1.5))
        ob = bpy.data.objects.new("edif", _building_mesh(e, rnd, bw - 0.3, bd, bh, (0, -1)))
        ob.location = (x + bw / 2, yb + bd / 2, 0)
        ob.data.materials.append(mat_toon("edif_m", color, e["windows"]))
        ob.data.materials.append(mat_toon("balcon_m", e.get("balcony_color", color)))
        link(ob, colls["main"])
        _billboard(e, rnd, x + bw / 2, yb + 0.6, bh, colls)
        if rnd.random() < e.get("awning", 0.6):
            strip = bpy.data.objects.new("vidriera", box_mesh("vidriera", bw * 0.7, 0.05, 2.4))
            strip.location = (x + bw / 2, yb - 0.03, 0.4)
            c = rnd.choice(e["shop_colors"])
            strip.data.materials.append(mat_neon("vidriera_m", c, 0.55))
            link(strip, colls["neon"])
            tint_light(f"vidriera_luz_x{int(x)}", c, e.get("shop_light", 600),
                        (x + bw / 2, yb - 1.8, 1.4), colls)
        x += bw


def build_blocks(e, colls):
    rnd = random.Random(e.get("seed", 1))
    W = e["street_width"] / 2 + e["sidewalk"]
    for side in (-1, 1):
        signs = e["signs"][(0 if side < 0 else 1)::2]
        fronts = e.get("fronts", [])[(0 if side < 0 else 1)::2]
        sign_i = front_i = 0
        y = e.get("start", -15.0)
        while y < e["end"]:
            bw = rnd.uniform(*e["width"])
            bh = rnd.uniform(*e["height"])
            bd = rnd.uniform(*e["depth"])
            setback = rnd.uniform(0, e.get("setback", 1.0))
            color = rnd.choice(e["colors"])
            ob = bpy.data.objects.new("edif", _building_mesh(e, rnd, bd, bw - 0.3, bh, (-side, 0)))
            ob.location = (side * (W + setback + bd / 2), y + bw / 2, 0)
            ob.data.materials.append(mat_toon("edif_m", color, e["windows"]))
            ob.data.materials.append(mat_toon("balcon_m", e.get("balcony_color", color)))
            link(ob, colls["main"])
            _billboard(e, rnd, ob.location.x, ob.location.y - bw / 2 + 0.6, bh, colls)
            if rnd.random() < e.get("facade_screens", 0.0) and bh > 22:
                hs = rnd.uniform(8, min(16, bh - 12))
                ws = (bw - 0.3) * rnd.uniform(0.5, 0.8)
                z0 = rnd.uniform(8, bh - hs - 3)
                scr = bpy.data.objects.new("pantalla_fachada", box_mesh("pf", 0.12, ws, hs))
                # sobre la fachada que mira a la avenida, por delante de los balcones
                scr.location = (side * (W + setback) - side * 0.9, y + bw / 2, z0)
                scr.data.materials.append(mat_screen("pf_m", rnd.choice(e["billboard_colors"]),
                                                     e.get("screen_dark", "#1a1830"),
                                                     freq=rnd.uniform(0.5, 1.4), speed=rnd.uniform(1.5, 4.0),
                                                     axis=rnd.choice([1, 2])))
                link(scr, colls["neon"])
                tint_light(f"pf_luz{side}_{int(y)}", "#9fd8ff", 900,
                            (side * (W + setback) - side * 4, y + bw / 2, z0 + hs / 2), colls)
            # remate en la terraza: tanque / antena / caja, para romper la silueta
            if rnd.random() < 0.6:
                cs = rnd.uniform(1.5, 3.5)
                cap = bpy.data.objects.new("remate", box_mesh("remate", cs, cs, rnd.uniform(1.0, 3.0)))
                cap.location = (ob.location.x + rnd.uniform(-1, 1), ob.location.y + rnd.uniform(-1, 1), bh)
                cap.data.materials.append(mat_toon("remate_m", color))
                link(cap, colls["main"])
            if rnd.random() < 0.4:
                ant = bpy.data.objects.new("antena", box_mesh("antena", 0.12, 0.12, rnd.uniform(3, 7)))
                ant.location = (ob.location.x, ob.location.y, bh)
                ant.data.materials.append(mat_flat("antena_m", e["antenna_color"]))
                link(ant, colls["main"])
                blink = bpy.data.objects.new("baliza", box_mesh("baliza", 0.3, 0.3, 0.3))
                blink.location = (ob.location.x, ob.location.y, bh + ant.dimensions.z)
                blink.data.materials.append(mat_neon("baliza_m", "#ff3355", 1.5, fog=False))
                link(blink, colls["neon"])
            # marquesina de planta baja
            if rnd.random() < e.get("awning", 0.5):
                aw = bpy.data.objects.new("toldo", box_mesh("toldo", 1.4, bw * 0.8, 0.12))
                aw.location = (side * (W + setback - 0.7), y + bw / 2, 3.0)
                aw.data.materials.append(mat_toon("toldo_m", rnd.choice(e["colors"])))
                link(aw, colls["main"])
                strip = bpy.data.objects.new("vidriera", box_mesh("vidriera", 0.05, bw * 0.7, 2.2))
                strip.location = (side * (W + setback - 0.02), y + bw / 2, 0.4)
                shop_color = rnd.choice(e["shop_colors"])
                strip.data.materials.append(mat_neon("vidriera_m", shop_color, 0.55))
                link(strip, colls["neon"])
                # la vidriera derrama su color sobre la vereda y el pie del edificio
                tint_light(f"vidriera_luz{side}_{int(y)}", shop_color, e.get("shop_light", 450),
                            (side * (W + setback - 1.6), y + bw / 2, 1.4), colls)
                if front_i < len(fronts):
                    fr = fronts[front_i]
                    front_i += 1
                    _frente(f"frente{side}_{front_i}", fr["text"], fr["color"], fr.get("size", 0.7),
                            (side * (W + setback), y + bw / 2, 3.25), -side, bw * 0.8,
                            colls, rnd, e["sign_body"])
            # bandera perpendicular (se lee desde la calle)
            if sign_i < len(signs) and rnd.random() < e.get("sign_rate", 0.7):
                sg = signs[sign_i]
                sign_i += 1
                _bandera(f"bandera{side}_{sign_i}", sg["text"], sg["color"], sg.get("size", 0.8),
                         (side * (W + setback), y + bw / 2, sg.get("z", rnd.uniform(4.5, 8))),
                         -side, colls, rnd, e["sign_body"])
            y += bw


def build_skyline(e, colls):
    """Megatorres lejanas: llenan el punto de fuga. La niebla las vuelve
    siluetas, y solo las ventanas y las balizas las despegan del cielo."""
    rnd = random.Random(e.get("seed", 3))
    for i in range(e["count"]):
        w = rnd.uniform(*e["width"])
        h = rnd.uniform(*e["height"])
        x = rnd.uniform(-e["spread"], e["spread"])
        y = rnd.uniform(*e["y"])
        ob = bpy.data.objects.new("torre", box_mesh("torre", w, w * rnd.uniform(0.6, 1.2), h))
        ob.location = (x, y, 0)
        ob.data.materials.append(mat_toon("torre_m", rnd.choice(e["colors"]), e["windows"]))
        link(ob, colls["main"])
        if rnd.random() < 0.7:
            b = bpy.data.objects.new("baliza", box_mesh("baliza", 0.8, 0.8, 0.8))
            b.location = (x, y, h)
            b.data.materials.append(mat_neon("baliza_m", e["beacon"], 1.5, fog=False))
            link(b, colls["neon"])


def build_lamps(e, colls):
    """Faroles sobre el borde de la vereda, alternando lados. Cada uno: poste,
    brazo hacia la calle, cabeza emisiva, luz calida y un cono translucido."""
    half = e["street_width"] / 2
    pole_m = mat_toon("farol_m", e["pole_color"])
    head_m = mat_neon("farol_cabeza", e["color"], 1.4)
    beam_m = mat_beam("farol_cono", e["color"], e.get("beam_alpha", 0.10))
    y, side = e["start"], -1
    while y < e["end"]:
        x = side * (half + 0.4)
        pole = bpy.data.objects.new("poste", box_mesh("poste", 0.16, 0.16, e["height"]))
        pole.location = (x, y, 0)
        pole.data.materials.append(pole_m)
        link(pole, colls["main"])
        arm_len = e.get("arm", 1.8)
        hx = x - side * arm_len
        arm = bpy.data.objects.new("brazo", box_mesh("brazo", arm_len, 0.12, 0.12))
        arm.location = (x - side * arm_len / 2, y, e["height"] - 0.12)
        arm.data.materials.append(pole_m)
        link(arm, colls["main"])
        head = bpy.data.objects.new("cabeza", box_mesh("cabeza", 0.7, 0.35, 0.12))
        head.location = (hx, y, e["height"] - 0.3)
        head.data.materials.append(head_m)
        link(head, colls["neon"])
        # cono: de la cabeza al piso
        bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=e.get("beam_radius", 2.6), radius2=0.3,
                                        depth=e["height"] - 0.3, location=(hx, y, (e["height"] - 0.3) / 2))
        cone = bpy.context.active_object
        for c in cone.users_collection:
            c.objects.unlink(cone)
        cone.data.materials.append(beam_m)
        link(cone, colls["veil"])
        sp = bpy.data.lights.new("farol_luz", "SPOT")
        sp.color = lin(e["color"])[:3]
        sp.energy = e.get("energy", 900)
        sp.spot_size = math.radians(e.get("spot_deg", 75))
        sp.spot_blend = 0.15
        sp.use_shadow = False
        lo = bpy.data.objects.new("farol_luz", sp)
        lo.location = (hx, y, e["height"] - 0.45)
        link(lo, colls["lights"])
        y += e["spacing"]
        side = -side


def build_cables(e, colls):
    """Cables entre fachadas: curvas con bevel, catenaria aproximada."""
    rnd = random.Random(e.get("seed", 9))
    mat = mat_flat("cable_m", e["color"])
    for i in range(e["count"]):
        y = rnd.uniform(*e["y"])
        z = rnd.uniform(*e["z"])
        sag = rnd.uniform(0.6, 2.0)
        cu = bpy.data.curves.new("cable", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = e.get("thickness", 0.025)
        sp = cu.splines.new("POLY")
        pts = 16
        sp.points.add(pts - 1)
        x0, x1 = -e["span"] / 2, e["span"] / 2
        dy = rnd.uniform(-3, 3)
        for k in range(pts):
            t = k / (pts - 1)
            sp.points[k].co = (x0 + (x1 - x0) * t, y + dy * t, z - sag * 4 * t * (1 - t), 1)
        ob = bpy.data.objects.new("cable", cu)
        ob.data.materials.append(mat)
        link(ob, colls["main"])
