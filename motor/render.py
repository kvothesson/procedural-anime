"""
render.py - Un plano de punta a punta: Blender (escena) + post.

    python motor/render.py episodios/nodo_404 06_apagon               # plano completo
    python motor/render.py episodios/nodo_404 06_apagon --draft       # 540x960, 4 muestras -> _draft_<plano>
    python motor/render.py episodios/nodo_404 06_apagon --frames 1 40 66   # frames sueltos de prueba

Con --frames escribe los PNG en render/_prueba_<plano>/ (no pisa el render bueno)
y arma una lamina de contacto en out/_prueba_<plano>.png.
Con --draft escribe en render/_draft_<plano>/ y out/_draft_<plano>/: un borrador
nunca pisa el plano final (montaje.py solo lee out/<plano>/).

Blender devuelve exit 0 aunque el script tire una excepcion: se verifica que
haya frames y que no haya Traceback en la salida.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

MOTOR = Path(__file__).resolve().parent
sys.path.insert(0, str(MOTOR))
from plano import load_shot  # noqa: E402


def find_blender():
    if os.environ.get("BLENDER"):
        return os.environ["BLENDER"]
    if shutil.which("blender"):
        return "blender"
    found = sorted(Path("C:/Program Files/Blender Foundation").glob("*/blender.exe"))
    if found:
        return str(found[-1])
    sys.exit("No encuentro Blender. Instala Blender 5.2 y defini la variable de entorno "
             "BLENDER con la ruta al ejecutable (o agregalo al PATH).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode", type=Path)
    ap.add_argument("shot")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--frames", nargs="+", type=int, help="frames sueltos de prueba")
    ap.add_argument("--no-post", action="store_true")
    args = ap.parse_args()

    ep = args.episode.resolve()
    shot_json = ep / "shots" / f"{args.shot}.json"
    if not shot_json.exists():
        sys.exit(f"No existe {shot_json}")

    if args.frames:
        out_dir = ep / "render" / f"_prueba_{args.shot}"
        cfg = load_shot(shot_json)      # ya resuelto: el JSON temporal no hereda nada
        cfg["render_list"] = args.frames
        cfg.pop("render_frames", None)
        cfg.pop("still", None)
        tmp = ep / "render" / f"_prueba_{args.shot}.json"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        shot_arg = tmp
    else:
        out_dir = ep / "render" / (f"_draft_{args.shot}" if args.draft else args.shot)
        shot_arg = shot_json
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("f_*.png"):
        f.unlink()          # borrar archivos, no el directorio (Windows)

    cmd = [find_blender(), "-b", "-P", str(MOTOR / "escena.py"), "--", str(shot_arg), str(out_dir)]
    if args.draft:
        cmd.append("--draft")
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    log = ep / "render" / f"{out_dir.name}.log"
    log.write_text(proc.stdout + proc.stderr, encoding="utf-8")
    frames = sorted(out_dir.glob("f_*.png"))
    if proc.returncode != 0 or "Traceback" in proc.stdout + proc.stderr or not frames:
        tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-25:])
        sys.exit(f"FALLO el render de {args.shot} (exit {proc.returncode}, {len(frames)} frames)\n{tail}\nlog: {log}")
    print(f"{args.shot}: {len(frames)} frames en {time.time() - t0:.0f} s -> {out_dir}")

    if args.frames:
        # lamina de contacto sin post (el post de prueba se corre aparte si hace falta)
        from PIL import Image
        ims = [Image.open(f) for f in frames]
        w = 360
        h = int(ims[0].height * w / ims[0].width)
        sheet = Image.new("RGB", (w * len(ims), h))
        for k, im in enumerate(ims):
            sheet.paste(im.convert("RGB").resize((w, h)), (k * w, 0))
        dst = ep / "out" / f"_prueba_{args.shot}.png"
        dst.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(dst)
        print(f"lamina -> {dst}")
        return

    if not args.no_post:
        post = [sys.executable, str(MOTOR / "post.py"), str(ep), args.shot]
        if args.draft:
            post.append("--draft")
        subprocess.run(post, check=True)


if __name__ == "__main__":
    main()
