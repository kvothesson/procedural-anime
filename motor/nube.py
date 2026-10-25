"""
nube.py - Render de un plano repartido en varias GPUs de Modal (pago por segundo).

    modal run motor/nube.py --ep episodios/nodo_404 --shot 02_calle               # 6 GPUs
    modal run motor/nube.py --ep episodios/nodo_404 --shot 02_calle --gpus 12
    modal run motor/nube.py --ep episodios/nodo_404 --shot 02_calle --frames 1,36,72   # prueba
    modal run motor/nube.py ... --tope 0.3     # corta todo si el gasto estimado pasa 0,3 USD (def. 0,5)
    NUBE_GPU=none modal run motor/nube.py ...  # solo CPU (no pide tarjeta); T4 / L4 / A10 con tarjeta

Solo la escena de Blender (lo caro). Los frames bajan a render/_nube_<plano>/ con el
mismo formato que render.py (f_, m_, c_ y anclas.json unificado); el post se corre en
la PC. Cada contenedor arma la escena entera y renderiza su tramo de frames, asi que
el armado (escena + compilar shaders, ~35 s) se paga una vez por GPU.
"""

import json
import os
import sys
import time
from pathlib import Path

import modal

MOTOR = Path(__file__).resolve().parent
BLENDER_URL = "https://download.blender.org/release/Blender5.2/blender-5.2.1-linux-x64.tar.xz"
GPU = os.environ.get("NUBE_GPU", "L4")     # L4 pide tarjeta cargada en Modal; T4 es la mas barata
PRECIO_GPU = {"T4": 0.000164, "L4": 0.000222, "A10": 0.000306, "none": 0.0}[GPU]

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("curl", "xz-utils", "libx11-6", "libxi6", "libxxf86vm1", "libxfixes3",
                 "libxrender1", "libxkbcommon0", "libsm6", "libice6", "libxext6", "libgl1",
                 "libegl1", "libglu1-mesa", "libvulkan1", "libwayland-client0")
    .run_commands(f"curl -sL {BLENDER_URL} | tar -xJ -C /opt && mv /opt/blender-* /opt/blender")
    # sin esto el contenedor solo trae CUDA: EEVEE necesita las librerias graficas del driver
    .env({"NVIDIA_DRIVER_CAPABILITIES": "all"})
    .add_local_dir(MOTOR, "/work/motor", ignore=["__pycache__", "*.pyc"])
)
app = modal.App("procedural-anime-render", image=image)


@app.function(gpu=None if GPU == "none" else GPU, cpu=4, memory=8192, timeout=3600)
def render_tramo(ep_name: str, ep_files: dict, cfg: dict, frames: list) -> dict:
    import subprocess
    t0 = time.time()
    ep = Path("/work/episodios") / ep_name
    for rel, data in ep_files.items():
        p = ep / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    cfg = dict(cfg, render_list=frames)
    cfg.pop("render_frames", None)
    cfg.pop("still", None)
    tmp = ep / "render" / "_tramo.json"      # escena.py toma el episodio de ../.. del JSON
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    out = ep / "render" / "_tramo"
    proc = subprocess.run(["/opt/blender/blender", "-b", "-P", "/work/motor/escena.py",
                           "--", str(tmp), str(out)], capture_output=True, text=True)
    log = proc.stdout + proc.stderr
    files = {f.name: f.read_bytes() for f in out.glob("*")} if out.exists() else {}
    gpu_line = next((l for l in log.splitlines() if "GPU" in l or "Vulkan" in l or "OpenGL" in l), "")
    return {"files": files, "segundos": time.time() - t0, "log_tail": "\n".join(log.splitlines()[-25:]),
            "error": proc.returncode != 0 or "Traceback" in log or not any(n.startswith("f_") for n in files),
            "gpu": gpu_line}


@app.local_entrypoint()
def main(ep: str, shot: str, gpus: int = 6, frames: str = "", tope: float = 0.5):
    sys.path.insert(0, str(MOTOR))
    from plano import load_shot
    ep_dir = Path(ep).resolve()
    cfg = load_shot(ep_dir / "shots" / f"{shot}.json")
    lista = [int(f) for f in frames.split(",")] if frames else list(range(1, cfg["frames"] + 1))
    # el episodio sin renders ni videos (piezas.py, shots, data)
    ep_files = {str(p.relative_to(ep_dir)).replace("\\", "/"): p.read_bytes()
                for p in ep_dir.rglob("*") if p.is_file()
                and p.relative_to(ep_dir).parts[0] not in ("render", "out", "voz", "capturas", "ref")}
    n = min(gpus, len(lista))
    # tramos intercalados (1,7,13...) para que todos tengan el mismo trabajo
    tramos = [lista[k::n] for k in range(n)]
    out = ep_dir / "render" / f"_nube_{shot}"
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*"):
        f.unlink()
    # GPU + 4 nucleos y 8 GB (~0,00007 USD/s); ver modal.com/pricing
    usd_s = PRECIO_GPU + 0.00007
    t0 = time.time()
    args = [(ep_dir.name, ep_files, cfg, t) for t in tramos]
    # llamadas en curso por tramo: [(FunctionCall, inicio)]. Un tramo lento (un contenedor
    # en una maquina mala tardo 751 s contra 125 s del resto) se relanza en paralelo y
    # gana el primero que termina; el otro se cancela.
    vivas = {k: [(render_tramo.spawn(*a), time.time())] for k, a in enumerate(args)}
    anclas, seg_cont, fallas, duraciones, relanzados = {}, 0.0, 0, [], 0
    while vivas:
        time.sleep(2)
        for k in list(vivas):
            for call, inicio in vivas[k]:
                try:
                    res = call.get(timeout=0)
                except (TimeoutError, modal.exception.TimeoutError):
                    continue
                for otra, ini in vivas.pop(k):
                    if otra is not call:
                        otra.cancel()
                        seg_cont += time.time() - ini
                seg_cont += res["segundos"]
                if res["error"]:
                    fallas += 1
                    print(f"tramo {k} FALLO:\n{res['log_tail']}")
                    break
                duraciones.append(time.time() - inicio)
                for name, data in res["files"].items():
                    if name == "anclas.json":
                        anclas.update(json.loads(data))
                    else:
                        (out / name).write_bytes(data)
                print(f"tramo {k}: {len(tramos[k])} frames en {res['segundos']:.0f} s  {res['gpu']}")
                break
        # limite: el doble de la mediana, cuando ya termino la mitad
        if len(duraciones) >= len(tramos) // 2:
            limite = max(60.0, 2 * sorted(duraciones)[len(duraciones) // 2])
            for k, calls in vivas.items():
                if len(calls) < 3 and time.time() - calls[-1][1] > limite:
                    calls.append((render_tramo.spawn(*args[k]), time.time()))
                    relanzados += 1
                    print(f"tramo {k}: lleva mas de {limite:.0f} s, relanzado")
        # tope de gasto: lo ya cobrado + lo que corre ahora
        gasto = (seg_cont + sum(time.time() - ini for cs in vivas.values() for _, ini in cs)) * usd_s
        if gasto > tope:
            for cs in vivas.values():
                for call, _ in cs:
                    call.cancel()
            sys.exit(f"CORTADO: el gasto estimado (~{gasto:.3f} USD) paso el tope de {tope} USD")
    if anclas:
        (out / "anclas.json").write_text(json.dumps(anclas), encoding="utf-8")
    pared = time.time() - t0
    hechos = len(list(out.glob("f_*.png")))
    print(f"\n{shot}: {hechos}/{len(lista)} frames en {pared:.0f} s de reloj, {n} contenedores ({GPU}), "
          f"{relanzados} relanzados, {seg_cont:.0f} s de contenedor, ~{seg_cont * usd_s:.3f} USD, "
          f"{fallas} tramos fallidos -> {out}")
