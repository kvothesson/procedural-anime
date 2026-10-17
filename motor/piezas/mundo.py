"""Lo que todo plano tiene: cielo, luces, reflejo, linea de tinta, camara y
ajustes de render (con el perfil para una GPU de 2 GB)."""

import math

import bpy
from mathutils import Vector

from . import ctx
from .base import lin, link, linearize, set_interp
from .materiales import mat_flat


def build_world(sky):
    world = bpy.data.worlds.new("cielo")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    n = nt.nodes
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    ramp = n.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position = 0.0
    els[0].color = lin(sky["horizon"])
    els[1].position = sky.get("zenith_at", 0.5)
    els[1].color = lin(sky["top"])
    nt.links.new(sep.outputs[2], ramp.inputs["Fac"])
    world["ramp"] = ramp.name
    bg_cam = n.new("ShaderNodeBackground")
    nt.links.new(ramp.outputs["Color"], bg_cam.inputs["Color"])
    bg_amb = n.new("ShaderNodeBackground")
    bg_amb.inputs["Color"].default_value = lin(sky["ambient"])
    bg_amb.inputs["Strength"].default_value = sky.get("ambient_strength", 1.0)
    world["amb"] = bg_amb.name
    lp = n.new("ShaderNodeLightPath")
    mix = n.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(bg_amb.outputs[0], mix.inputs[1])
    nt.links.new(bg_cam.outputs[0], mix.inputs[2])
    out = n.new("ShaderNodeOutputWorld")
    nt.links.new(mix.outputs[0], out.inputs["Surface"])


def build_lights(items, colls):
    for i, l in enumerate(items):
        li = bpy.data.lights.new(f"luz{i}", l["kind"])
        li.color = lin(l["color"])[:3]
        li.energy = l["energy"]
        if l["kind"] == "SUN":
            li.angle = math.radians(l.get("angle", 1.0))
            # cada sol con sombra es un mapa mas en 2 GB de VRAM: solo el primero
            li.use_shadow = l.get("shadow", i == 0)
        else:
            li.shadow_soft_size = l.get("soft", 0.5)
        ob = bpy.data.objects.new(f"luz{i}", li)
        ob.location = l.get("at", (0, 0, 10))
        if "rot" in l:
            ob.rotation_euler = [math.radians(a) for a in l["rot"]]
        link(ob, colls["lights"])


def build_reflection(colls, tint):
    """Copia espejada (z -> -z) de todo lo que emite y del resto como silueta
    oscura. Va en su propia coleccion, excluida de Line Art."""
    dark = mat_flat("reflejo_oscuro", tint)
    mirror = bpy.data.objects.new("espejo", None)
    mirror.scale = (1, 1, -1)
    link(mirror, colls["refl"])
    for src_name in ("main", "neon"):
        for ob in list(colls[src_name].objects):
            # los hijos (arcos de los anillos) perderian a su padre al espejarse
            if ob.type not in ("MESH", "CURVE", "FONT") or ob.name.startswith("calle") or ob.parent:
                continue
            # lo que esta a ras del piso (pasto, camino, canteros) no tiene nada
            # que reflejar, y su copia queda justo bajo el charco tapandolo todo
            top = max((ob.matrix_world @ Vector(c)).z for c in ob.bound_box)
            if top < 0.5:
                continue
            cp = ob.copy()
            # Sin matrix_parent_inverse: la transformacion local de la copia es
            # la del original en el mundo, y el padre la espeja entera.
            cp.parent = mirror
            if src_name == "main":
                cp.data = ob.data.copy()
                cp.data.materials.clear()
                cp.data.materials.append(dark)
            link(cp, colls["refl"])


def build_lineart(e, colls):
    gp_data = bpy.data.grease_pencils.new("tinta") if hasattr(bpy.data, "grease_pencils") \
        else bpy.data.grease_pencils_v3.new("tinta")
    gp = bpy.data.objects.new("tinta", gp_data)
    link(gp)
    gp_data.layers.new("linea")
    m = bpy.data.materials.new("tinta_m")
    bpy.data.materials.create_gpencil_data(m)
    m.grease_pencil.color = lin(e["color"])
    # create_gpencil_data deja el trazo apagado en 5.x: sin esto Line Art
    # genera los trazos pero no se dibuja nada.
    m.grease_pencil.show_stroke = True
    m.grease_pencil.show_fill = False
    gp_data.materials.append(m)
    mod = gp.modifiers.new("lineart", "LINEART")
    mod.source_type = "COLLECTION"
    mod.source_collection = colls["main"]
    mod.target_layer = "linea"
    mod.target_material = m
    mod.radius = e.get("radius", 0.01)
    # el radio va en metros: un plano que viaja de lo general al detalle lo
    # baja en el camino ([[frame, radio], ...]) para que la tinta no engorde
    for f, r in e.get("radius_keys", []):
        mod.radius = r
        mod.keyframe_insert("radius", frame=f)
    mod.use_intersection = e.get("intersection", True)
    mod.use_crease = True
    mod.crease_threshold = math.radians(e.get("crease_deg", 140))
    mod.use_back_face_culling = False


def build_camera(c):
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = c["lens"]
    # "lens_keys": [[frame, mm], ...] cambia la lente en el plano (una hoja
    # de vistas con una camara distinta por frame, o un zoom)
    for f, mm in c.get("lens_keys", []):
        cam_data.lens = mm
        cam_data.keyframe_insert("lens", frame=f)
    cam_data.sensor_fit = "VERTICAL"
    cam_data.sensor_height = 36.0
    cam_data.clip_end = c.get("clip_end", 500)
    cam_data.clip_start = c.get("clip_start", 0.1)
    cam = bpy.data.objects.new("cam", cam_data)
    link(cam)
    target = bpy.data.objects.new("mira", None)
    link(target)
    tc = cam.constraints.new("TRACK_TO")
    tc.target = target
    tc.track_axis = "TRACK_NEGATIVE_Z"
    tc.up_axis = "UP_Y"
    frames = ctx.CFG["frames"]
    # "keys": [{"frame", "pos", "aim"}, ...] para movimientos con pausas.
    # Si no, from/to lineal de punta a punta.
    keys = c.get("keys") or [
        {"frame": 1, "pos": c["from"], "aim": c.get("from_aim")},
        {"frame": frames, "pos": c["to"], "aim": c.get("to_aim")},
    ]
    for k in keys:
        p = Vector(k["pos"])
        cam.location = p
        cam.keyframe_insert("location", frame=k["frame"])
        aim = Vector(k.get("aim") or (p.x, p.y + 20, p.z + c.get("rise", 4.0)))
        target.location = aim
        target.keyframe_insert("location", frame=k["frame"])
    if c.get("ease"):
        # sin grilla de pixeles que proteger: el easing le da peso a la camara
        for ob in (cam, target):
            set_interp(ob, "BEZIER")
    else:
        linearize(cam)
        linearize(target)
    bpy.context.scene.camera = cam


def setup_render(scene):
    r = scene.render
    r.engine = "BLENDER_EEVEE"
    r.resolution_x = ctx.CFG["width"]
    r.resolution_y = ctx.CFG["height"]
    r.resolution_percentage = ctx.CFG.get("scale_pct", 100)
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.film_transparent = False
    scene.eevee.taa_render_samples = ctx.CFG.get("samples", 16)
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.frame_start = 1
    scene.frame_end = ctx.CFG["frames"]
    if ctx.CFG.get("render_frames"):
        scene.frame_start, scene.frame_end = ctx.CFG["render_frames"]
    if hasattr(scene.eevee, "use_shadows"):
        scene.eevee.use_shadows = True
    tune_for_gpu(scene)


# Perfil para la maquina de referencia: GPU de 2 GB de VRAM, CPU de 4 nucleos.
# La VRAM es el cuello de botella: con el pool de sombras grande el frame
# tardaba minutos y Blender se caia sin traceback. El toon cuantiza la luz en
# 3 escalones, asi que sombras de baja resolucion y sin GI no se notan.
PERF = {
    "shadow_pool_size": "256",
    "shadow_resolution_scale": 0.5,
    "shadow_step_count": 2,
    "use_fast_gi": False,
    "use_raytracing": False,
    "gi_cubemap_resolution": "128",
    "gi_irradiance_pool_size": "16",
    # radio de influencia de cada luz: con 40 luces de vidriera y farol, un
    # umbral mas alto achica cuantos tiles toca cada una
    "light_threshold": 0.05,
}


def tune_for_gpu(scene):
    ee = scene.eevee
    for k, v in {**PERF, **ctx.CFG.get("perf", {})}.items():
        if hasattr(ee, k):
            setattr(ee, k, v)
    if ctx.DRAFT:
        scene.render.resolution_percentage = 50
        ee.taa_render_samples = 4
