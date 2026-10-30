"""
encuadre.py - Qué entra en cuadro, frame por frame y antes de renderizar (con Blender, sin render).

    python motor/encuadre.py episodios/<ep> <plano> [<plano> ...] [--cada 6] [--sujeto a,b] [--personaje mu_]
                             [--banda 0.21] [--franja 0.22,0.35] [--salida archivo.txt]

Proyecta las mallas con la cámara de cada frame y avisa lo que después cuesta un render entero:

  PERSONAJE_TAPA   el personaje ocupa demasiado cuadro (el sujeto queda chiquito)
  PERSONAJE_CORTADO se le sale la cabeza del cuadro
  PERSONAJE_ASOMA  apenas entra un pedazo por el borde (un casco suelto en una esquina)
  NO_SENALA        el personaje señala y el brazo no apunta al sujeto
  SUJETO_CHICO     el sujeto casi no se ve (menos del 2 % del cuadro)
  SUJETO_AFUERA    el sujeto queda cortado por los bordes
  SUJETO_BANDA     el sujeto queda debajo del texto de arriba (--banda, fracción del alto)
  SUJETO_TARJETA   el sujeto queda detrás de una franja de texto (--franja y0,y1)
  PEGADO_AL_LENTE  una pieza a menos de 4 cm del lente ocupa mucho cuadro: sale como mancha

--sujeto: prefijos de nombres de lo que hay que mostrar en esos planos, lo más justo posible (la
boya, no toda la mochila): la caja de una pieza grande no dice nada. --personaje: prefijo del personaje.
Mirar frames sueltos no alcanza: estos errores se repitieron en planos ya revisados a ojo.
Sale con código 1 si hay avisos. Los umbrales se calibraron con los 8 episodios de Cómo Anda.
"""

import argparse
import subprocess
import sys
from pathlib import Path

MOTOR = Path(__file__).resolve().parent
TAPA = 0.22            # fracción del cuadro para el personaje
ASOMA = 0.06
CHICO = 0.02
PEGADA = 0.15          # fracción del cuadro que no puede ocupar...
PEGADA_M = 0.04        # ...una pieza a menos de estos metros del lente
SENALA_DEDO = 0.5      # escala del dedo a partir de la cual el brazo está señalando
BRAZO = ("hombro", "manga", "brazo", "codo", "palma", "dedo", "pulgar")   # nombres de piezas del brazo


def outside():
    sys.path.insert(0, str(MOTOR))
    from render import find_blender
    ap = argparse.ArgumentParser()
    ap.add_argument("episode", type=Path)
    ap.add_argument("planos", nargs="+")
    ap.add_argument("--cada", type=int, default=6)
    ap.add_argument("--sujeto", default="")
    ap.add_argument("--personaje", default="mu_")
    ap.add_argument("--banda", type=float, default=0.21)
    ap.add_argument("--franja", default="")
    ap.add_argument("--salida", type=Path)
    a = ap.parse_args()
    lineas, avisos = [], 0
    for plano in a.planos:
        shot = (a.episode / "shots" / f"{plano}.json").resolve()
        cmd = [find_blender(), "-b", "-P", str(Path(__file__).resolve()), "--", str(shot), "_", "--sin-render",
               "--cada", str(a.cada), "--sujeto", a.sujeto, "--personaje", a.personaje,
               "--banda", str(a.banda), "--franja", a.franja]
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = p.stdout + p.stderr
        rep = [l[4:] for l in out.splitlines() if l.startswith("ENC ")]
        if "Traceback" in out or not rep:
            print("\n".join(out.splitlines()[-30:]))
            sys.exit(2)
        avisos += sum(1 for l in rep if l.startswith("AVISO"))
        lineas += [f"== {plano}"] + rep
    texto = "\n".join(lineas + [f"avisos: {avisos}"])
    print(texto)
    if a.salida:
        a.salida.parent.mkdir(parents=True, exist_ok=True)
        a.salida.write_text(texto + "\n", encoding="utf-8")
    sys.exit(1 if avisos else 0)


def inside():
    import runpy
    import bpy
    from bpy_extras.object_utils import world_to_camera_view

    argv = sys.argv[sys.argv.index("--") + 1:]

    def arg(nombre, defecto=""):
        return argv[argv.index(nombre) + 1] if nombre in argv else defecto

    cada = int(arg("--cada", "6"))
    sujeto = tuple(x for x in arg("--sujeto").split(",") if x)
    personaje = arg("--personaje", "mu_")
    banda = float(arg("--banda", "0.21"))
    franja = [float(x) for x in arg("--franja").split(",") if x]
    runpy.run_path(str(MOTOR / "escena.py"), run_name="__main__")
    scene = bpy.context.scene
    cam = scene.camera
    obs = [o for o in bpy.data.objects if o.type in ("MESH", "CURVE")]

    def puntos(o):
        """Vértices de la malla evaluada en coordenadas de mundo (cada tanto, para ir rápido)."""
        ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.to_mesh()
        m = ev.matrix_world
        vs = me.vertices
        paso = max(1, len(vs) // 200)
        out = [m @ vs[i].co for i in range(0, len(vs), paso)]
        ev.to_mesh_clear()
        return out

    def caja(pts):
        """Caja en pantalla (0..1, y hacia abajo): la que entra en cuadro y la completa, sin lo de atrás del lente."""
        pr = [world_to_camera_view(scene, cam, p) for p in pts]
        pr = [(p.x, 1 - p.y) for p in pr if p.z > 0]
        if not pr:
            return None
        x0, x1 = min(p[0] for p in pr), max(p[0] for p in pr)
        y0, y1 = min(p[1] for p in pr), max(p[1] for p in pr)
        vx0, vx1, vy0, vy1 = max(x0, 0), min(x1, 1), max(y0, 0), min(y1, 1)
        if vx1 <= vx0 or vy1 <= vy0:
            return None
        return {"todo": (x0, y0, x1, y1), "vis": (vx0, vy0, vx1, vy1), "area": (vx1 - vx0) * (vy1 - vy0)}

    def juntar(cajas):
        cajas = [c for c in cajas if c]
        if not cajas:
            return None
        t = [min(c["todo"][i] for c in cajas) if i < 2 else max(c["todo"][i] for c in cajas) for i in range(4)]
        v = [min(c["vis"][i] for c in cajas) if i < 2 else max(c["vis"][i] for c in cajas) for i in range(4)]
        return {"todo": t, "vis": v, "area": (v[2] - v[0]) * (v[3] - v[1])}

    def senala_mal(suj):
        """¿El brazo que señala apunta al sujeto? Rayo hombro → punta del dedo, en pantalla."""
        for lado in (1, -1):
            dedo = bpy.data.objects.get(f"{personaje}dedo_{lado}")
            hombro = bpy.data.objects.get(f"{personaje}hombro_{lado}")
            if not dedo or not hombro or dedo.hide_render or dedo.scale.z < SENALA_DEDO:
                continue
            a = world_to_camera_view(scene, cam, hombro.matrix_world.translation)
            pts = puntos(dedo)
            lejos = max(pts, key=lambda p: (p - hombro.matrix_world.translation).length)
            b = world_to_camera_view(scene, cam, lejos)
            ax, ay, bx, by = a.x, 1 - a.y, b.x, 1 - b.y
            dx, dy = bx - ax, by - ay
            n = (dx * dx + dy * dy) ** 0.5
            if n < 1e-4:
                continue
            x0, y0, x1, y1 = suj["vis"]
            # se recorre el rayo desde la punta del dedo: si toca la caja del sujeto, apunta
            for k in range(0, 200):
                px, py = bx + dx / n * k * 0.01, by + dy / n * k * 0.01
                if x0 <= px <= x1 and y0 <= py <= y1:
                    return False
            return True
        return False

    def elegir(o):
        return any(o.name.startswith(s) for s in sujeto)

    def se_ve(objetos):
        """¿Algún punto de estos objetos llega a la cámara sin que lo tape otra cosa?"""
        dg = bpy.context.evaluated_depsgraph_get()
        ojo = cam.matrix_world.translation
        nombres = {o.name for o in objetos}
        for o in objetos:
            pts = puntos(o)
            for p in pts[:: max(1, len(pts) // 6)]:
                v = world_to_camera_view(scene, cam, p)
                if v.z <= 0 or not (0 <= v.x <= 1 and 0 <= v.y <= 1):
                    continue
                d = p - ojo
                n = d.length
                hit, _, _, _, ob, _ = scene.ray_cast(dg, ojo, d.normalized(), distance=max(n - 0.005, 0.001))
                if not hit or ob.name in nombres:
                    return True
        return False

    avisos = {}

    def avisar(tipo, f, detalle=""):
        a = avisos.setdefault(tipo, {"frames": [], "detalle": detalle})
        a["frames"].append(f)
        if detalle:
            a["detalle"] = detalle

    resumen = []
    frames = sorted(set(range(1, scene.frame_end + 1, cada)) | {scene.frame_end})
    for f in frames:
        scene.frame_set(f)
        vivos = [o for o in obs if not o.hide_render]
        del_personaje = [o for o in vivos if personaje and o.name.startswith(personaje)]
        pers = juntar([caja(puntos(o)) for o in del_personaje])
        if pers and not se_ve(del_personaje):     # adentro de la máquina: está en cuadro, pero tapado
            pers = None
        # el brazo estirado agranda la caja sin tapar nada: lo que tapa es el cuerpo
        cuerpo = juntar([caja(puntos(o)) for o in del_personaje if not any(x in o.name for x in BRAZO)]) if pers else None
        suj = juntar([caja(puntos(o)) for o in vivos if elegir(o)]) if sujeto else None
        cabeza = bpy.data.objects.get(f"{personaje}casco")
        if pers:
            if cuerpo and cuerpo["area"] > TAPA:
                avisar("PERSONAJE_TAPA", f, f"{cuerpo['area'] * 100:.0f} % del cuadro (tope {TAPA * 100:.0f} %)")
            elif pers["area"] < ASOMA and (pers["todo"][0] < 0 or pers["todo"][1] < 0 or pers["todo"][2] > 1 or pers["todo"][3] > 1):
                avisar("PERSONAJE_ASOMA", f, f"{pers['area'] * 100:.1f} % del cuadro, cortado por el borde")
            if cabeza and not cabeza.hide_render:
                cc = caja(puntos(cabeza))
                if cc:
                    t = cc["todo"]
                    ancho, alto = max(t[2] - t[0], 1e-6), max(t[3] - t[1], 1e-6)
                    fuera = max(-t[0] / ancho, (t[2] - 1) / ancho, -t[1] / alto, (t[3] - 1) / alto)
                    if fuera > 0.1:
                        avisar("PERSONAJE_CORTADO", f, f"{fuera * 100:.0f} % del casco afuera")
        if suj:
            if suj["area"] < CHICO:
                avisar("SUJETO_CHICO", f, f"{suj['area'] * 100:.1f} % del cuadro")
            t = suj["todo"]
            ancho, alto = max(t[2] - t[0], 1e-6), max(t[3] - t[1], 1e-6)
            fuera = max(-t[0] / ancho, (t[2] - 1) / ancho, -t[1] / alto, (t[3] - 1) / alto)
            # un primer plano puede cortar al sujeto a propósito: solo si queda chico además de cortado
            if fuera > 0.25 and suj["area"] < 0.15:
                avisar("SUJETO_AFUERA", f, f"{fuera * 100:.0f} % afuera")
            v = suj["vis"]
            if v[1] < banda:
                tapado = (banda - v[1]) / max(v[3] - v[1], 1e-6)
                if tapado > 0.3:
                    avisar("SUJETO_BANDA", f, f"{tapado * 100:.0f} % del sujeto bajo el texto")
            if franja:
                tapado = max(0.0, min(v[3], franja[1]) - max(v[1], franja[0])) / max(v[3] - v[1], 1e-6)
                if tapado > 0.3:
                    avisar("SUJETO_TARJETA", f, f"{tapado * 100:.0f} % del sujeto detrás de la tarjeta")
            if pers and senala_mal(suj):
                avisar("NO_SENALA", f, "el rayo del brazo no toca al sujeto")
        for o in vivos:
            if personaje and o.name.startswith(personaje):
                continue
            pts = puntos(o)
            if pts and min((p - cam.matrix_world.translation).length for p in pts) < PEGADA_M:
                c = caja(pts)
                if c and c["area"] > PEGADA:
                    avisar("PEGADO_AL_LENTE", f, f"{o.name}: a menos de {PEGADA_M * 100:.0f} cm, {c['area'] * 100:.0f} % del cuadro")
        resumen.append((f, pers["area"] if pers else 0, suj["area"] if suj else 0))

    print("ENC cuadro: personaje / sujeto  " + "  ".join(
        f"{f}: {p * 100:.0f}/{s * 100:.0f}" for f, p, s in resumen[:: max(1, len(resumen) // 6)]), flush=True)
    for tipo, a in sorted(avisos.items()):
        fs = a["frames"]
        print(f"ENC AVISO {tipo}: cuadros {fs[0]}-{fs[-1]} ({len(fs)} de {len(frames)} mirados): {a['detalle']}", flush=True)
    if not avisos:
        print("ENC ok", flush=True)


if "bpy" in sys.modules or any("blender" in x.lower() for x in sys.argv[:1]):
    inside()
else:
    outside()
