"""Despiece: piezas que llegan a su lugar (armar) o se van (desarmar).

Cada pieza tiene su transformacion de reposo (la que ya tiene el objeto al
armar la escena) y, en el JSON, de donde viene:

    "partes": {"cilindro": {"from": [0, 0, -6], "spin": [0, 0, 90], "span": [4, 14]}, ...}

from: desplazamiento desde el reposo, en el espacio del padre (metros).
spin: giro extra en grados al estar afuera. span: frames de viaje.
modo "armar": afuera hasta span[0], viaja, queda en reposo desde span[1].
modo "desarmar": al reves (reposo, viaja, afuera).
"ocultar": true -> la pieza no se ve mientras espera afuera (si no, todas las
piezas que todavia no llegaron quedan flotando en cuadro). Va en la raiz o por pieza.
"arc": metros que sube en el medio del viaje (trayectoria en arco); con "via",
solo en el primer tramo.
"clac": rebotito al encajar (metros hacia arriba, dos frames).

La pose es funcion pura del frame (una clave por frame), asi que la puede
recalcular cualquier chequeo de colisiones sin Blender (ver offset()).
"""

import math


def snap(t):
    """Viaja rapido y frena al encajar, sin pasarse (pasarse = atravesar)."""
    t = min(1.0, max(0.0, t))
    return 1.0 - (1.0 - t) ** 4


def launch(t):
    """Al desarmar: arranca lento (se suelta) y se va acelerando."""
    t = min(1.0, max(0.0, t))
    return t ** 3


def away(spec, f, modo="armar"):
    """Cuanto esta afuera la pieza en el frame f: 1 = explotada, 0 = en reposo."""
    a, b = spec["span"]
    t = (f - a) / max(1, b - a)
    return 1.0 - snap(t) if modo == "armar" else launch(t)


def _extra(spec, f, k, modo):
    """Arco (sube en el medio del viaje) y clac (rebotito al encajar), en z del padre."""
    z = spec.get("arc", 0.0) * 4 * k * (1 - k)
    c = spec.get("clac")
    if c and modo == "armar":
        d = f - spec["span"][1]
        z += {1: c, 2: c * 0.35}.get(d, 0.0)
    return z


def offset(spec, f, modo="armar"):
    """(desplazamiento xyz, giro xyz en radianes) de la pieza en el frame f.
    "via": punto de paso (mismo espacio que "from"): la primera mitad del viaje va
    de "from" a "via" y la segunda de "via" al reposo. Sirve para entrar derecho
    en un hueco (bajar hasta quedar enfrente y despues entrar en horizontal)."""
    k = away(spec, f, modo)
    if "via" in spec:
        fx, fy, fz = spec.get("from", (0, 0, 0))
        vx, vy, vz = spec["via"]
        if k > 0.5:
            # primer tramo (de "from" al punto de paso): con arco que sube rapido
            # al despegar (raiz del seno), asi pasa por encima de lo que hay al lado
            u = (k - 0.5) * 2
            arc = spec.get("arc", 0.0) * math.sqrt(max(0.0, math.sin(math.pi * u)))
            d = (vx + (fx - vx) * u, vy + (fy - vy) * u, vz + (fz - vz) * u + arc)
        else:
            # segundo tramo: derecho al reposo
            d = (vx * k * 2, vy * k * 2, vz * k * 2)
        sx, sy, sz = spec.get("spin", (0, 0, 0))
        d = (d[0], d[1], d[2] + _extra(dict(spec, arc=0.0), f, k, modo))
        return d, (math.radians(sx) * k, math.radians(sy) * k, math.radians(sz) * k)
    dx, dy, dz = spec.get("from", (0, 0, 0))
    dz_extra = _extra(spec, f, k, modo)
    sx, sy, sz = spec.get("spin", (0, 0, 0))
    return (dx * k, dy * k, dz * k + dz_extra), (math.radians(sx) * k, math.radians(sy) * k, math.radians(sz) * k)


def apply_despiece(objects, e, frames):
    """objects: nombre -> objeto de Blender. e: {"modo", "partes"}. Las piezas
    que no estan en "partes" no se tocan."""
    modo = e.get("modo", "armar")
    for name, spec in e.get("partes", {}).items():
        ob = objects[name]
        loc0 = tuple(ob.location)
        rot0 = tuple(ob.rotation_euler)
        for f in range(1, frames + 1):
            (dx, dy, dz), (rx, ry, rz) = offset(spec, f, modo)
            ob.location = (loc0[0] + dx, loc0[1] + dy, loc0[2] + dz)
            ob.rotation_euler = (rot0[0] + rx, rot0[1] + ry, rot0[2] + rz)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("rotation_euler", frame=f)
        if spec.get("ocultar", e.get("ocultar")):
            a, b = spec["span"]
            for f, hide in ((1, modo == "armar"), (a if modo == "armar" else b + 1, modo != "armar")):
                ob.hide_render = hide
                ob.keyframe_insert("hide_render", frame=max(1, f))
        if ob.animation_data and ob.animation_data.action:
            from .base import action_fcurves
            for fc in action_fcurves(ob.animation_data.action):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
