"""
render_todo.py - Todos los planos de un episodio, uno por vez, y el montaje.

    python motor/render_todo.py episodios/<ep>              # los que falten + montaje
    python motor/render_todo.py episodios/<ep> --sin-montaje
    python motor/render_todo.py episodios/<ep> --desde 14a_hora

Pensado para renders de horas, sin nadie mirando:
- Retoma: un plano con todos sus cuadros compuestos en out/<plano>/ se salta.
  Si se corta (luz, reinicio), se vuelve a lanzar y sigue por el que falta.
- Espera a que no haya otro Blender corriendo antes de cada plano (con 2 GB de
  VRAM, dos a la vez se cuelgan).
- Le pide a Windows que no se suspenda mientras corre (SetThreadExecutionState:
  es un pedido del proceso, no cambia la configuracion; se suelta al terminar).
- Escribe el avance en out/_render_todo.log (plano, cuadros, minutos, estimado).

Para que sobreviva a cerrar la terminal, lanzarlo desacoplado, por ejemplo en
Windows: Start-Process python -ArgumentList 'motor/render_todo.py','episodios/<ep>' -WindowStyle Hidden
"""

import json
import subprocess
import sys
import time
from pathlib import Path

MOTOR = Path(__file__).resolve().parent
sys.path.insert(0, str(MOTOR))
from plano import load_shot  # noqa: E402


def despierto(si):
    """Que Windows no entre en suspension por inactividad mientras corre."""
    if sys.platform != "win32":
        return
    import ctypes
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if si else 0))


def blender_corriendo():
    if sys.platform != "win32":
        r = subprocess.run(["pgrep", "-x", "blender"], capture_output=True)
        return r.returncode == 0
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq blender.exe"], capture_output=True, text=True)
    return "blender.exe" in r.stdout.lower()


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    ep = Path(sys.argv[1]).resolve()
    tl = json.loads((ep / "shots" / "timeline.json").read_text(encoding="utf-8"))
    shots = tl["shots"]
    if "--desde" in sys.argv:
        shots = shots[shots.index(sys.argv[sys.argv.index("--desde") + 1]):]
    log = ep / "out" / "_render_todo.log"
    log.parent.mkdir(parents=True, exist_ok=True)

    def anotar(msg):
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        print(line, flush=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    pend = []
    for s in shots:
        n = load_shot(ep / "shots" / f"{s}.json")["frames"]
        hechos = len(list((ep / "out" / s).glob("p_*.png")))
        if hechos < n:
            pend.append((s, n))
    total = sum(n for _, n in pend)
    anotar(f"empieza: {len(pend)} planos pendientes, {total} cuadros")
    despierto(True)
    try:
        hecho, t_ini = 0, time.time()
        for i, (s, n) in enumerate(pend):
            while blender_corriendo():
                time.sleep(20)
            t0 = time.time()
            r = subprocess.run([sys.executable, str(MOTOR / "render.py"), str(ep), s],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode != 0:
                anotar(f"FALLO {s}: {(r.stdout + r.stderr).strip().splitlines()[-1:]}")
                continue
            hecho += n
            ritmo = (time.time() - t_ini) / max(1, hecho)
            falta = (total - hecho) * ritmo / 3600
            anotar(f"{s}: {n} cuadros en {(time.time() - t0) / 60:.1f} min ({i + 1}/{len(pend)}); "
                   f"faltan ~{falta:.1f} h")
        if "--sin-montaje" not in sys.argv:
            r = subprocess.run([sys.executable, str(MOTOR / "montaje.py"), str(ep)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            anotar("montaje: " + " | ".join((r.stdout + r.stderr).strip().splitlines()[-3:]))
        anotar("terminado")
    finally:
        despierto(False)


if __name__ == "__main__":
    main()
