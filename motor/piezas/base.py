"""Utilidades de Blender sin estilo propio: color, colecciones, mallas,
keyframes, texto 3D y luces de tinte."""

import math

import bpy
import bmesh

from . import ctx


def lin(c):
    """'#rrggbb' sRGB -> tupla RGBA lineal. Blender espera color lineal."""
    c = c.lstrip("#")
    out = []
    for i in (0, 2, 4):
        v = int(c[i:i + 2], 16) / 255.0
        out.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


def action_fcurves(action):
    if hasattr(action, "fcurves"):
        return list(action.fcurves)
    curves = []
    for layer in action.layers:
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", []):
                curves.extend(bag.fcurves)
    return curves


def linearize(obj):
    if obj.animation_data and obj.animation_data.action:
        for fc in action_fcurves(obj.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


def link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


def collection(name, lineart="INCLUDE"):
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    coll.lineart_usage = lineart
    return coll


def box_mesh(name, sx, sy, sz):
    """Caja con el origen en la base: (0,0,0) es el centro del piso."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= sx
        v.co.y *= sy
        v.co.z = (v.co.z + 0.5) * sz
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def bm_box(bm, cx, cy, z0, sx, sy, sz, mat_index=0):
    """Agrega una caja (base en z0) a un bmesh existente."""
    out = bmesh.ops.create_cube(bm, size=1.0)
    for v in out["verts"]:
        v.co.x = v.co.x * sx + cx
        v.co.y = v.co.y * sy + cy
        v.co.z = (v.co.z + 0.5) * sz + z0
    for f in {f for v in out["verts"] for f in v.link_faces}:
        f.material_index = mat_index


def ellipse_ring(name, cx, cy, rx, ry, r_in, r_out, z, h, segs=128):
    """Anillo eliptico (r_in..r_out como fraccion de los radios) con altura h.
    r_in = 0 da un disco lleno."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    for f in ((r_in, z + h), (r_out, z + h)) if r_in > 0 else ((r_out, z + h),):
        k, zz = f
        rings.append([bm.verts.new((cx + rx * k * math.cos(2 * math.pi * i / segs),
                                    cy + ry * k * math.sin(2 * math.pi * i / segs), zz))
                      for i in range(segs)])
    if r_in > 0:
        a, b = rings
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new([a[i], a[j], b[j], b[i]])
    else:
        bm.faces.new(rings[0])
    bm.normal_update()
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    bm.to_mesh(mesh)
    bm.free()
    return bpy.data.objects.new(name, mesh)


def set_interp(idblock, interp):
    if idblock.animation_data and idblock.animation_data.action:
        for fc in action_fcurves(idblock.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = interp


def key_power(ob, frame, value):
    ob["power"] = value
    ob.keyframe_insert('["power"]', frame=frame)


CHAR_W = 0.62   # ancho medio de una mayuscula de Bahnschrift, en ems


def text(name, body, size, mat, loc, rot, coll):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    if ctx.FONT:
        cu.font = bpy.data.fonts.load(ctx.FONT, check_existing=True)
    cu.size = size
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = 0.02
    t = bpy.data.objects.new(name, cu)
    t.location = loc
    t.rotation_euler = rot
    t.data.materials.append(mat)
    link(t, coll)
    return t


def tint_light(name, color, energy, loc, colls):
    """La luz del cartel tine fachada y vereda. Sin sombra: con sombra, una
    docena de carteles llenan el pool de EEVEE, el frame tarda minutos y
    Blender se cae a veces sin traceback."""
    li = bpy.data.lights.new(name, "POINT")
    li.color = lin(color)[:3]
    li.energy = energy
    li.shadow_soft_size = 0.5
    li.use_shadow = False
    lo = bpy.data.objects.new(name, li)
    lo.location = loc
    link(lo, colls["lights"])
