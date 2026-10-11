"""
escena.py - Arma y renderiza un plano en Blender a partir de su JSON.

    python motor/render.py episodios/<ep> <plano>   (o: blender -b -P motor/escena.py -- <plano>.json <salida> [--draft])

Reglas de look (detalle en docs/PRODUCCION.md):
  - Cada material termina en Emission: el sombreado toon se calcula a mano
    (Shader to RGB -> rampa CONSTANTE sobre la luminancia, conservando el tono
    de la luz). Dos o tres tonos por superficie, borde de sombra duro.
  - Linea: Grease Pencil Line Art, color azul tinta, nunca negro puro.
  - Neon sin linea (el anime no contornea la luz).
  - Reflejos en el piso mojado = geometria espejada y sin luz (solo se refleja
    lo que emite), vista a traves de charcos recortados con alfa binario.
  - Niebla atmosferica por distancia dentro del shader: determinista.

Las piezas viven en motor/piezas/. Cada clave del JSON que arma algo esta en
PIEZAS, en el orden en que se construye (el orden importa: fija los nombres de
objetos y materiales, y con ellos el azar del apagon). Todas son opcionales.
Un episodio puede sumar las suyas en episodios/<ep>/piezas.py con una lista
PIEZAS = [("clave", build_fn), ...]; se arman despues de las del motor.
"""

import importlib.util
import shutil
import sys
from pathlib import Path

import bpy

MOTOR = Path(__file__).resolve().parent
sys.path.insert(0, str(MOTOR))

from plano import load_shot  # noqa: E402
from piezas import ctx  # noqa: E402
from piezas.base import collection  # noqa: E402
from piezas.ciudad import (build_blocks, build_cables, build_lamps, build_row_x,  # noqa: E402
                           build_skyline, build_street)
from piezas.colectivo import build_colectivo  # noqa: E402
from piezas.eventos import apply_blackout, build_luz_mala  # noqa: E402
from piezas.mundo import (build_camera, build_lights, build_lineart,  # noqa: E402
                          build_reflection, build_world, setup_render)
from piezas.espacio import build_estrellas, build_tierra  # noqa: E402
from piezas.mecanica import build_engranajes  # noqa: E402
from piezas.obelisco import build_obelisco  # noqa: E402
from piezas.plaza import build_flag, build_plaza, build_trees  # noqa: E402
from piezas.andes import (build_apacheta, build_camino, build_cordillera,  # noqa: E402
                          build_luna, build_puente, build_tambos, build_terreno)
from piezas.viaje import build_mensaje  # noqa: E402
from piezas.tokio import build_chochin, build_expendedoras, build_farol_hex, build_viaducto  # noqa: E402

SKY = {"horizon": "#2a1f4a", "top": "#070814", "ambient": "#1b2a4a"}
LINE = {"color": "#0d0b24"}


# Algunas piezas heredan ajustes de otras (la calle define el ancho de las
# hileras; las hileras, las ventanas del resto). Estas funciones los completan.

def _blocks(e, cfg):
    e = dict(e)
    st = cfg.get("street", {})
    e.setdefault("street_width", st.get("width", 20.0))
    e.setdefault("sidewalk", st.get("sidewalk", 4.0))
    return e


def _row_x(e, cfg):
    e = dict(e)
    bl = cfg.get("blocks", {})
    e.setdefault("windows", bl.get("windows"))
    for k in ("billboards", "billboard_colors", "balconies", "balcony_color", "shop_colors"):
        e.setdefault(k, bl.get(k))
    return e


def _skyline(e, cfg):
    e = dict(e)
    e.setdefault("windows", cfg.get("blocks", {}).get("windows"))
    return e


def _lamps(e, cfg):
    e = dict(e)
    e.setdefault("street_width", cfg.get("street", {}).get("width", 20.0))
    return e


# (clave del JSON, constructor, completar ajustes heredados o None)
PIEZAS = [
    ("street", build_street, None),
    ("blocks", build_blocks, _blocks),
    ("row_x", build_row_x, _row_x),
    ("plaza", build_plaza, None),
    ("trees", build_trees, None),
    ("flag", build_flag, None),
    ("skyline", build_skyline, _skyline),
    ("colectivo", build_colectivo, None),
    ("lamps", build_lamps, _lamps),
    ("cables", build_cables, None),
    ("estrellas", build_estrellas, None),
    ("tierra", build_tierra, None),
    ("engranajes", build_engranajes, None),
    # Andes (chasqui_relevo): todo se ubica sobre la ruta de "camino"
    ("terreno", build_terreno, None),
    ("cordillera", build_cordillera, None),
    ("camino", build_camino, None),
    ("puente", build_puente, None),
    ("tambos", build_tambos, None),
    ("apacheta", build_apacheta, None),
    # despues de todo lo que tiene relevo_s: el mensaje los enciende al pasar
    ("mensaje", build_mensaje, None),
    ("luna", build_luna, None),
    # Tokio (chasqui_relevo): callejon bajo las vias
    ("viaducto", build_viaducto, None),
    ("chochin", build_chochin, None),
    ("expendedoras", build_expendedoras, None),
    ("farol_hex", build_farol_hex, None),
]


def episode_pieces(shot_path):
    """PIEZAS de episodios/<ep>/piezas.py, si existe. El JSON vive en
    <ep>/shots/ (o en <ep>/render/ para las pruebas de render.py)."""
    src = Path(shot_path).resolve().parent.parent / "piezas.py"
    if not src.exists():
        return []
    spec = importlib.util.spec_from_file_location("piezas_episodio", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(getattr(mod, "PIEZAS", []))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cfg = load_shot(argv[0])
    out = Path(argv[1]) if len(argv) > 1 else Path("render/out")
    # --draft: mitad de resolucion y 4 muestras, para iterar. El post reescala.
    ctx.configurar(cfg, draft="--draft" in argv)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    setup_render(scene)
    build_world(cfg.get("sky", SKY))
    colls = {
        "main": collection("main"),
        "neon": collection("neon", "EXCLUDE"),
        "refl": collection("reflejo", "EXCLUDE"),
        "veil": collection("velo", "EXCLUDE"),
        "lights": collection("luces", "EXCLUDE"),
    }
    for key, build, prep in PIEZAS:
        if key in cfg:
            build(prep(cfg[key], cfg) if prep else cfg[key], colls)
    build_lights(cfg.get("lights", []), colls)
    crystal = build_obelisco(cfg["obelisco"], colls) if "obelisco" in cfg else None
    if "luz_mala" in cfg:
        build_luz_mala(cfg["luz_mala"], colls)
    for key, build in episode_pieces(argv[0]):
        if key in cfg:
            build(cfg[key], colls)
    # todo objeto necesita 'power': sin la propiedad, el atributo vale 0 y
    # cualquier emisivo sale apagado
    for ob in bpy.data.objects:
        if "power" not in ob:
            ob["power"] = 1.0
    if "blackout" in cfg:
        apply_blackout(cfg["blackout"], colls, crystal)
    # el reflejo solo tiene sentido sobre piso mojado: sin calle, sin espejo
    tint = cfg.get("reflection_tint", cfg.get("street", {}).get("reflection_tint"))
    if tint:
        build_reflection(colls, tint)
    build_lineart(cfg.get("line", LINE), colls)
    build_camera(cfg["camera"])
    print("escena armada", flush=True)
    if "--sin-render" in argv:
        return      # colision.py y otros chequeos: solo la escena

    out.mkdir(parents=True, exist_ok=True)
    if cfg.get("still"):
        # escena 3D quieta (todo el movimiento lo pone el post): un render y copias
        scene.frame_set(1)
        first = out.resolve() / "f_0001.png"
        scene.render.filepath = str(first)
        bpy.ops.render.render(write_still=True)
        for f in range(2, cfg["frames"] + 1):
            shutil.copyfile(first, out.resolve() / f"f_{f:04d}.png")
    elif cfg.get("render_list"):
        # pruebas: frames sueltos (antes / durante / despues de un evento)
        for f in cfg["render_list"]:
            scene.frame_set(f)
            scene.render.filepath = str(out.resolve()) + f"/f_{f:04d}.png"
            bpy.ops.render.render(write_still=True)
    else:
        scene.render.filepath = str(out.resolve()) + "/f_"
        bpy.ops.render.render(animation=True)
    print("render terminado", flush=True)


if __name__ == "__main__":
    main()
