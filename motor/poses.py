"""
poses.py - Poses clave como datos y el timing del sakuga, en Python puro (sin bpy).

La teoria viene de los editores de poses (Pivot, Stick Nodes, StykAnimate, las
herramientas de pose de Blender y Spine), sin su interfaz de mouse:

  - Una pose es una lista de articulaciones en el plano de perfil (x adelante,
    z arriba) con profundidad por articulacion. Los largos de hueso son fijos:
    la pose solo da direcciones (angulo absoluto de cada hueso, como en Pivot).
  - Se interpola el angulo de cada hueso, no la posicion: los miembros barren en
    arco y no se acortan.
  - Poses parciales: {"base": "guardia", ...} hereda otra y pisa lo que nombra.
  - Exposicion: la pose queda quieta hasta la clave siguiente. Entre las dos van
    pocos intermedios elegidos a mano ("ib"), no una curva.
  - Breakdown por rama: un intermedio no es el 50 % de todo el cuerpo. Con
    {"*": 0.7, "brazo_b": 0.3} el torso ya llego y el brazo todavia viene: overlap.
  - Push: exagerar cuanto se aparta una pose de otra. Despues de llegar, unos
    cuadros pasados ("pasa") y vuelve: overshoot. Antes de salir, lo mismo hacia
    atras: anticipacion.
  - Retraso por rama ("tarde"): la cabeza muestrea la linea dos cuadros antes que
    el cuerpo. Follow-through determinista, sin fisica.
  - Contactos ("contactos"): un pie clavado en el mundo durante un rango; la
    pierna se resuelve por IK de dos tramos y la rodilla dobla para el mismo lado.

Todo es funcion del frame: misma entrada, misma salida.

Un rig es un dict:
    {"huesos": [[hijo, padre], ...]   # en orden: el padre antes que el hijo
     "largo": {hijo: m}               # hueso con largo fijo (si no, offset libre)
     "prof": {art: m}                 # profundidad por defecto (y local)
     "ramas": {nombre: [art, ...]}    # grupos para breakdown y retraso
     "pies": [art, ...], "tobillo": m # suelo: el pie mas bajo a esa altura
     "poses": {nombre: {art: [x, z], "prof": {...}, "base": nombre}}}

Una linea de claves (la de un personaje):
    [[frame, pose, [x, y], yaw_grados, {opciones}], ...]
Opciones de una clave:
    "ib": 2 | [[cuadros, k], ...]  intermedios al llegar a esta clave (2 al 60 % por
                                   defecto; 0 = corte seco). k es un numero o un
                                   dict por rama ({"*": k, rama: k})
    "pasa": [cuadros, k]           llega pasado (push de k respecto de la anterior)
    "antes": [cuadros, k]          sale con anticipacion: los ultimos cuadros de
                                   esta clave empujan en contra de la siguiente
    "slide": [x, y]                la raiz viaja hasta ahi durante la clave (en doses)
    "suelo": false                 no apoyar los pies (en el aire)
"""

import math

# --- angulos y mezcla ----------------------------------------------------------------


def _ang(a, b):
    return math.atan2(b[1] - a[1], b[0] - a[0])


def _dang(a, b):
    """b - a por el arco corto."""
    return (b - a + math.pi) % (2 * math.pi) - math.pi


def _lerp_ang(a, b, k):
    return a + _dang(a, b) * k


def _lerp(a, b, k):
    return tuple(x + (y - x) * k for x, y in zip(a, b))


def padres(rig):
    return dict(rig["huesos"])


def rama_de(rig):
    """{articulacion: rama}. La raiz (hip) es la rama "raiz"."""
    out = {}
    for nombre, arts in rig.get("ramas", {}).items():
        for a in arts:
            out[a] = nombre
    return out


def _k_de(k, rama):
    """k numero o dict por rama: {"*": defecto, rama: k}."""
    if isinstance(k, dict):
        return k.get(rama, k.get("*", 0.5))
    return k


def _escalar(k, s):
    """k (numero o dict por rama) por s."""
    if isinstance(k, dict):
        return {r: v * s for r, v in k.items()}
    return k * s


def posiciones(rig, nombre):
    """Pose con herencia: {"base": otra} toma la otra y pisa lo que nombra."""
    P = rig["poses"][nombre]
    if "base" in P:
        out = posiciones(rig, P["base"])
        out = {**out, **{j: v for j, v in P.items() if j not in ("base", "prof")}}
        out["prof"] = {**out.get("prof", {}), **P.get("prof", {})}
        return out
    return {**P, "prof": dict(P.get("prof", {}))}


def parametros(rig, nombre):
    """Pose -> parametros interpolables: cadera, angulo de cada hueso con largo,
    desplazamiento de los que no lo tienen y profundidades."""
    P = posiciones(rig, nombre)
    prm = {"hip": tuple(P["hip"]), "ang": {}, "off": {},
           "prof": {**rig["prof"], **P["prof"]}}
    for hijo, padre in rig["huesos"]:
        if hijo in rig["largo"]:
            prm["ang"][hijo] = _ang(P[padre], P[hijo])
        else:
            prm["off"][hijo] = (P[hijo][0] - P[padre][0], P[hijo][1] - P[padre][1])
    return prm


def mezclar(rig, p, q, k):
    """De p a q. k numero o dict por rama (breakdown por miembro). k fuera de
    0..1 extrapola: k < 0 se aleja de q (anticipacion), k > 1 se pasa (overshoot)."""
    rama = rama_de(rig)
    kr = _k_de(k, "raiz")
    return {
        "hip": _lerp(p["hip"], q["hip"], kr),
        "ang": {j: _lerp_ang(p["ang"][j], q["ang"][j], _k_de(k, rama.get(j)))
                for j in p["ang"]},
        "off": {j: _lerp(p["off"][j], q["off"][j], _k_de(k, rama.get(j)))
                for j in p["off"]},
        "prof": {j: p["prof"][j] + (q["prof"][j] - p["prof"][j]) * _k_de(k, rama.get(j))
                 for j in p["prof"]},
    }


def empujar(rig, p, ref, k):
    """Push: p + (p - ref) * k. Exagera lo que p se aparta de ref."""
    return mezclar(rig, ref, p, 1.0 + k) if not isinstance(k, dict) else \
        mezclar(rig, ref, p, {r: 1.0 + v for r, v in k.items()})


def reemplazar(rig, prm, otro, ramas):
    """prm con las ramas nombradas tomadas de otro (para el retraso)."""
    rama = rama_de(rig)
    out = {"hip": prm["hip"], "ang": dict(prm["ang"]), "off": dict(prm["off"]),
           "prof": dict(prm["prof"])}
    for campo in ("ang", "off", "prof"):
        for j in out[campo]:
            if rama.get(j) in ramas:
                out[campo][j] = otro[campo][j]
    return out


# --- cinematica ------------------------------------------------------------------------


def fk(rig, prm, suelo=True):
    """Cinematica directa en el plano de perfil. Devuelve {articulacion: (x, y, z)}
    en coordenadas locales (x adelante, y = profundidad, z arriba)."""
    pos = {"hip": prm["hip"]}
    for hijo, padre in rig["huesos"]:
        px, pz = pos[padre]
        if hijo in rig["largo"]:
            a = prm["ang"][hijo]
            pos[hijo] = (px + rig["largo"][hijo] * math.cos(a),
                         pz + rig["largo"][hijo] * math.sin(a))
        else:
            dx, dz = prm["off"][hijo]
            pos[hijo] = (px + dx, pz + dz)
    dz = 0.0
    if suelo and rig.get("pies"):
        dz = rig.get("tobillo", 0.0) - min(pos[p][1] for p in rig["pies"])
    return {j: (x, prm["prof"].get(j, 0.0), z + dz) for j, (x, z) in pos.items()}


def ik2(a, b, c, objetivo, l1, l2):
    """IK analitica de dos tramos en el plano (x, z): cadera a, rodilla b, tobillo
    c. Devuelve la rodilla nueva y el tobillo (objetivo, o lo mas cerca que llega).
    La rodilla dobla para el mismo lado que en (a, b, c)."""
    ax, az = a
    tx, tz = objetivo
    d = math.hypot(tx - ax, tz - az)
    d = max(abs(l1 - l2) + 1e-6, min(d, l1 + l2 - 1e-6))
    base = math.atan2(tz - az, tx - ax)
    cos_a = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)
    alfa = math.acos(max(-1.0, min(1.0, cos_a)))
    # lado del doblez: signo del producto cruz (a->c) x (a->b) en la pose original
    lado = (c[0] - ax) * (b[1] - az) - (c[1] - az) * (b[0] - ax)
    s = 1.0 if lado >= 0 else -1.0
    ang = base + s * alfa
    rod = (ax + l1 * math.cos(ang), az + l1 * math.sin(ang))
    llega = (ax + d * math.cos(base), az + d * math.sin(base))
    return rod, llega


def al_mundo(local, root, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    return {j: (root[0] + x * c - y * s, root[1] + x * s + y * c, z)
            for j, (x, y, z) in local.items()}


def al_local(p, root, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    x, y = p[0] - root[0], p[1] - root[1]
    return (x * c + y * s, -x * s + y * c, p[2])


# --- la linea de claves ------------------------------------------------------------


def _ib(opt):
    """Intermedios de una clave: [[cuadros, k], ...]. Un entero n = n cuadros al 60 %."""
    ib = opt.get("ib", 2)
    if isinstance(ib, (int, float)):
        return [[int(ib), 0.6]] if ib else []
    return ib


def clave_en(keys, f):
    i = max((k for k in range(len(keys)) if keys[k][0] <= f), default=0) \
        if f >= keys[0][0] else 0
    return i


def pose_en(rig, keys, f):
    """Parametros de la pose en el frame f (sin raiz): exposicion, intermedios,
    overshoot y anticipacion."""
    i = clave_en(keys, f)
    k = keys[i]
    opt = k[4] if len(k) > 4 else {}
    prm = parametros(rig, k[1])
    t = f - k[0]
    prev = parametros(rig, keys[i - 1][1]) if i > 0 else None
    if prev is not None:
        # intermedios al llegar
        for n, kk in _ib(opt):
            if t < n:
                return mezclar(rig, prev, prm, kk)
            t -= n
        # llega pasado y vuelve
        if "pasa" in opt:
            n, kk = opt["pasa"]
            if t < n:
                return empujar(rig, prm, prev, _escalar(kk, 1 - t / n))
    # anticipacion: los ultimos cuadros de esta clave empujan en contra de la siguiente
    if "antes" in opt and i + 1 < len(keys):
        n, kk = opt["antes"]
        f1 = keys[i + 1][0]
        if f >= f1 - n:
            sig = parametros(rig, keys[i + 1][1])
            return empujar(rig, prm, sig, _escalar(kk, (f - (f1 - n) + 1) / n))
    return prm


def raiz_en(keys, f):
    """(x, y), yaw (radianes) y suelo en el frame f. "slide" viaja en doses."""
    i = clave_en(keys, f)
    k = keys[i]
    opt = k[4] if len(k) > 4 else {}
    x, y = k[2]
    if "slide" in opt and i + 1 < len(keys):
        f1 = keys[i + 1][0]
        fq = f - (f - k[0]) % 2
        u = min(1.0, (fq - k[0]) / max(1, f1 - k[0] - 1))
        x += (opt["slide"][0] - x) * u
        y += (opt["slide"][1] - y) * u
    return (x, y), math.radians(k[3]), opt.get("suelo", True)


def secuencia(rig, linea, frames):
    """[(frame, {articulacion: xyz en el mundo})] de un personaje.
    linea: {"keys": [...], "tarde": {rama: cuadros}, "contactos": [[art, f0, f1]]}."""
    keys = linea["keys"]
    tarde = linea.get("tarde", {})
    P = padres(rig)
    out = []
    for f in frames:
        prm = pose_en(rig, keys, f)
        for rama, n in tarde.items():
            prm = reemplazar(rig, prm, pose_en(rig, keys, max(keys[0][0], f - n)), {rama})
        root, yaw, suelo = raiz_en(keys, f)
        out.append((f, al_mundo(fk(rig, prm, suelo), root, yaw), root, yaw))
    for art, f0, f1 in linea.get("contactos", []):
        _clavar(rig, P, out, art, f0, f1)
    return [(f, pos) for f, pos, _, _ in out]


def _clavar(rig, P, out, art, f0, f1):
    """El tobillo art queda donde estaba en f0 hasta f1 (en el mundo). La pierna
    se resuelve por IK en el plano de perfil; lo que cuelga del tobillo (la punta
    del pie) viaja rigido con el."""
    rod = P[art]
    cad = P[rod]
    hijos = [h for h, p in rig["huesos"] if p == art]
    fijo = None
    for idx, (f, pos, root, yaw) in enumerate(out):
        if f == f0:
            fijo = {j: pos[j] for j in [art] + hijos}
        if fijo is None or not (f0 <= f <= f1):
            continue
        loc = {j: al_local(p, root, yaw) for j, p in pos.items()}
        obj = {j: al_local(p, root, yaw) for j, p in fijo.items()}
        a = (loc[cad][0], loc[cad][2])
        b = (loc[rod][0], loc[rod][2])
        c = (loc[art][0], loc[art][2])
        r, t = ik2(a, b, c, (obj[art][0], obj[art][2]), rig["largo"][rod], rig["largo"][art])
        loc[rod] = (r[0], loc[rod][1], r[1])
        dx, dz = t[0] - obj[art][0], t[1] - obj[art][2]
        loc[art] = (t[0], obj[art][1], t[1])
        for h in hijos:
            loc[h] = (obj[h][0] + dx, obj[h][1], obj[h][2] + dz)
        out[idx] = (f, al_mundo(loc, root, yaw), root, yaw)
