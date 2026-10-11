"""
montaje.py - Pega los planos ya compuestos en un solo video.

    python motor/montaje.py episodios/nodo_404            # usa <episodio>/shots/timeline.json
    python motor/montaje.py episodios/nodo_404 --draft    # con los borradores (out/_draft_<plano>)

Copia los frames de out/<plano>/p_*.png a una sola secuencia numerada y
encodea una vez: el demuxer concat trabaja sobre archivos de media y
re-encodear por plano agrega una generacion de perdida por corte.

Antes de pegar verifica el loop: ultimo frame crudo del ultimo plano contra el
primero del primer plano (render/, sin post: lluvia y grano cambian por frame).
Si la diferencia media pasa LOOP_TOL avisa, pero no corta el montaje.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

LOOP_TOL = 0.5      # diferencia media aceptable (0..255) en el empalme del loop


def check_loop(root, shots):
    """Diferencia media entre el ultimo frame crudo y el primero, o None si faltan."""
    import cv2
    import numpy as np
    first = sorted((root / "render" / shots[0]).glob("f_*.png"))
    last = sorted((root / "render" / shots[-1]).glob("f_*.png"))
    if not first or not last:
        return None
    a = cv2.imread(str(last[-1])).astype(np.float32)
    b = cv2.imread(str(first[0])).astype(np.float32)
    if a.shape != b.shape:
        return float("inf")
    return float(np.abs(a - b).mean())


def main():
    if len(sys.argv) < 2:
        raise SystemExit("uso: python motor/montaje.py episodios/<nombre> [--draft]")
    ROOT = Path(sys.argv[1]).resolve()
    draft = "--draft" in sys.argv
    pre = "_draft_" if draft else ""
    tl = json.loads((ROOT / "shots" / "timeline.json").read_text(encoding="utf-8"))
    seq = ROOT / "out" / "_montaje"
    seq.mkdir(parents=True, exist_ok=True)
    for f in seq.glob("m_*.png"):
        f.unlink()          # borrar archivos, no el directorio (Windows)
    n = 0
    report = []
    for shot in tl["shots"]:
        frames = sorted((ROOT / "out" / f"{pre}{shot}").glob("p_*.png"))
        if not frames:
            if draft:
                hint = f"python motor/render.py {sys.argv[1]} {shot} --draft"
            else:
                hint = f"python motor/post.py {sys.argv[1]} {shot}"
            raise SystemExit(f"Falta componer {shot}: {hint}")
        for fr in frames:
            n += 1
            shutil.copyfile(fr, seq / f"m_{n:05d}.png")
        report.append(f"{shot}: {len(frames)} frames ({len(frames) / tl['fps_unique']:.1f} s)")
    out = ROOT / "out" / f"{tl['name']}{'_draft' if draft else ''}.mp4"
    video = ROOT / "out" / f"{tl['name']}{'_draft' if draft else ''}_video.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(tl["fps_unique"]),
           "-i", str(seq / "m_%05d.png"), "-r", str(tl["fps_out"]),
           "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", str(video)]
    subprocess.run(cmd, check=True)
    wav = ROOT / "out" / f"{tl['name']}.wav"
    if wav.exists():
        # banda de audio/banda.py: AAC 320 kbps a 48 kHz (44.1 mete artefactos de resampleo)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(wav),
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
                        "-shortest", "-movflags", "+faststart", str(out)], check=True)
    else:
        video.replace(out)
    print("\n".join(report))
    d = check_loop(ROOT, tl["shots"])
    if d is None:
        print("loop: sin frames crudos en render/ para medir el empalme")
    elif d > LOOP_TOL:
        print(f"AVISO loop: el empalme {tl['shots'][-1]} -> {tl['shots'][0]} difiere {d:.2f}/255 (tolerancia {LOOP_TOL})")
    else:
        print(f"loop: empalme {tl['shots'][-1]} -> {tl['shots'][0]} ok ({d:.2f}/255)")
    print(f"{n} frames, {n / tl['fps_unique']:.1f} s -> {out}")


if __name__ == "__main__":
    main()
