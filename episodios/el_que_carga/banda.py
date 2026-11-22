"""banda.py - Banda de sonido de EL QUE CARGA. Sintesis pura: ni un sample.

    python episodios/el_que_carga/banda.py   # -> out/el_que_carga.wav (48 kHz, estereo)

Re menor, lenta. Lo que manda la imagen:
  - Cada pisada del Hombre-Tanque es un golpe grave de maquina: los cuadros
    salen del mismo ciclo que mueve las piernas (piezas.CICLO via planos.py),
    no de una lista a mano. Pie izquierdo y derecho en paneo opuesto.
  - Cada gota de aceite que toca el piso es un plink (solo se oye cerca: 03,
    y bajito en el 08).
  - El bandoneon (de nodo_404/banda.py) es su voz: una frase por bioma, de
    a una nota por pisada, que baja. Arriba (02) no hay bandoneon: campanas
    claras, otra vida.
  - 05 viento con nieve, 06 silbido fino de la sal, 07 el cartel: acorde
    entero de milonga. 08 glitch donde se rompe el visor y la musica se ahoga.
  - 09: los pasos se alejan y el zoom a la roca se llena de un grave que es
    el mismo dron con que arranca el 01 (loop).
Semilla fija.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / "motor"))
sys.path.insert(0, str(ROOT.parents[1] / "motor" / "audio"))
sys.path.insert(0, str(ROOT))

import dsp  # noqa: E402
from dsp import SR, n_samples, note, place, stereo, time_axis  # noqa: E402
from plano import load_shot  # noqa: E402

np.random.seed(1404)
TAIL = 6.0


def _nodo404():
    spec = importlib.util.spec_from_file_location("banda_nodo404", ROOT.parent / "nodo_404" / "banda.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


N4 = _nodo404()
TL = json.loads((ROOT / "shots" / "timeline.json").read_text(encoding="utf-8"))
CFG = {s: load_shot(ROOT / "shots" / f"{s}.json") for s in TL["shots"]}
S, t = {}, 0.0
for s in TL["shots"]:
    S[s] = t
    t += CFG[s]["frames"] / TL["fps_unique"]
T = t


def at(shot, frame=1):
    return S[shot] + (frame - 1) / 12.0


def pisadas(shot):
    """[(cuadro, lado)] en que cada pie toca el piso: el pie baja cuando el
    coseno de su fase cruza a negativo (ver piezas.pose)."""
    tq = CFG[shot].get("tanque", {})
    c = tq.get("ciclo")
    if not c:
        return []
    N = c.get("frames", 18)
    out = []
    for f in range(1, CFG[shot]["frames"] + 1):
        for lado, off in (("i", 0.0), ("d", np.pi)):
            a = np.cos(2 * np.pi * (f - 2 + c.get("fase", 0)) / N + off)
            b = np.cos(2 * np.pi * (f - 1 + c.get("fase", 0)) / N + off)
            if a > 0 >= b:
                out.append((f, lado))
    return out


def gotas(shot, per=7):
    """Cuadros en que una gota llega al piso (piezas.build_tanque: cae ~5 cuadros)."""
    out = []
    for f in range(1, CFG[shot]["frames"] + 1):
        for off in (0, 3):
            if (f + off) % per == 5:
                out.append(f)
    return out


# ------------------------------------------------------------------ instrumentos

def pisada(peso=1.0):
    """Pie de maquina: golpe grave + chapa que vibra + crujido de tierra."""
    n = n_samples(1.2)
    tt = time_axis(n)
    golpe = N4.thump(f0=38.0, dur=1.2)[:n]
    chapa = sum(np.sin(2 * np.pi * f * tt) * np.exp(-tt / d) for f, d in ((143, 0.18), (311, 0.09), (587, 0.05)))
    tierra = dsp.lowpass(np.random.uniform(-1, 1, n), 900) * np.exp(-tt / 0.06)
    return peso * (0.9 * golpe + 0.18 * chapa + 0.25 * tierra)


def chirrido(dur=0.5):
    """Articulacion seca: friccion con tono que sube un poco."""
    n = n_samples(dur)
    tt = time_axis(n)
    f = 420 + 160 * tt / dur
    x = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * (0.5 + 0.5 * np.random.uniform(0, 1, n))
    return dsp.bandpass(x, 600, 3200) * dsp.adsr(n, 0.05, 0.1, 0.6, 0.2) * 0.25


def viento(dur, lo, hi, seed):
    rnd = np.random.default_rng(seed)
    n = n_samples(dur)
    tt = time_axis(n)
    x = dsp.bandpass(rnd.uniform(-1, 1, n), lo, hi)
    x /= np.abs(x).max() + 1e-9
    return x * (0.6 + 0.4 * np.sin(2 * np.pi * 0.23 * tt + rnd.uniform(0, 6))) * dsp.adsr(n, 0.6, 0.2, 1.0, 0.6)


def dron(dur, attack=1.5, release=2.0):
    return N4.chord_pad(["D2", "A2", "D3"], dur, attack=attack, release=release, cutoff=700)


# ------------------------------------------------------------------ partitura

FRASES = {          # una nota por pisada, de a una frase por bioma: baja, como el
    "04_puna": ["A4", "G4", "F4", "E4", "D4"],
    "05_nieve": ["F4", "E4", "D4", "C4", "A3"],
    "06_salinas": ["D4", "E4", "F4", "E4"],
    "08_visor": ["A3", "D4"],
}


def musica(Ttot):
    bus = np.zeros((n_samples(Ttot), 2))
    # dron: arranca a pleno en el 01 y vuelve a crecer en el zoom del 09 (empalme del loop)
    place(bus, stereo(0.55 * dron(at("03_pie", 1) + 1.0, attack=0.02)), 0.0)
    place(bus, stereo(0.35 * dron(at("07_leyenda") - at("03_pie") + 1.5)), at("03_pie"))
    place(bus, stereo(0.30 * dron(at("09_lejos") - at("07_leyenda") + 1.0)), at("07_leyenda"))
    place(bus, stereo(0.72 * dron(T - at("09_lejos", 30) + TAIL, attack=2.4)), at("09_lejos", 30))
    # 02 cima: campanas claras en La mayor, otra vida
    for k, nm in enumerate(["A5", "C#6", "E6", "A6", "E6", "C#6"]):
        place(bus, stereo(0.16 * N4.bell(note(nm), 3.0), 0.5 - 0.2 * k), at("02_cima", 1 + 6 * k))
    # bandoneon: una nota por pisada
    for shot, notas in FRASES.items():
        ps = pisadas(shot)
        for (f, lado), nm in zip(ps, notas):
            place(bus, stereo(0.2 * N4.bandoneon(note(nm), 1.1, attack=0.08, release=0.6), -0.15), at(shot, f))
    # 07 el cartel: milonga, Re menor - La7 - Re menor, con el bandoneon entero
    for k, acorde in enumerate((["D3", "F3", "A3", "D4"], ["C#3", "E3", "G3", "A3"], ["D3", "F3", "A3", "D4"])):
        for nm in acorde:
            place(bus, stereo(0.09 * N4.bandoneon(note(nm), 1.8, attack=0.12, release=0.9)), at("07_leyenda", 1 + 20 * k))
    place(bus, stereo(0.18 * N4.bell(note("D6"), 4.0)), at("07_leyenda", 50))
    return bus


def efectos(Ttot):
    bus = np.zeros((n_samples(Ttot), 2))
    cerca = {"03_pie": 1.0, "04_puna": 0.55, "05_nieve": 0.5, "06_salinas": 0.55, "08_visor": 0.7, "09_lejos": 0.12}
    for shot, g in cerca.items():
        for f, lado in pisadas(shot):
            place(bus, stereo(g * pisada(), -0.25 if lado == "i" else 0.25), at(shot, f))
            if shot in ("03_pie", "08_visor"):
                place(bus, stereo(g * chirrido()), at(shot, f) - 0.25)
    for shot, g in (("03_pie", 0.5), ("08_visor", 0.12), ("01_revelacion", 0.08)):
        for f in gotas(shot):
            place(bus, stereo(g * N4.drop_plink(), np.random.uniform(-0.3, 0.3)), at(shot, f))
    # 01: la roca cruje cuando aparece el; 09: rumor del zoom
    place(bus, stereo(0.3 * N4.boom(4.0)), at("01_revelacion", 30))
    # biomas
    place(bus, stereo(0.18 * viento(at("06_salinas") - at("05_nieve") + 0.4, 300, 2200, 3)), at("05_nieve") - 0.2)
    place(bus, stereo(0.08 * N4.whistle(at("07_leyenda") - at("06_salinas"))), at("06_salinas"))
    place(bus, stereo(0.07 * viento(at("05_nieve") - at("04_puna") + 0.4, 150, 900, 8)), at("04_puna") - 0.2)
    # 08 el visor se rompe
    g0, g1 = CFG["08_visor"]["post"]["glitch"][0][:2]
    place(bus, stereo(0.35 * N4.glitch_burst((g1 - g0 + 1) / 12.0)), at("08_visor", g0))
    return bus


def main():
    Ttot = T + TAIL
    print(f"timeline {T:.2f} s: " + ", ".join(f"{k} @{v:.2f}" for k, v in S.items()))
    hall = dsp.make_ir(dur=3.4, decay=1.8, damping=4200, predelay=0.03)
    m = dsp.reverb(musica(Ttot), hall, 0.35)
    fx = dsp.reverb(efectos(Ttot), dsp.make_ir(dur=1.0, decay=0.4, damping=6000, predelay=0.01), 0.15)
    nT = n_samples(T)

    def envolver(x):            # la cola cae sobre el principio: loop sin costura
        y = x[:nT].copy()
        y[:len(x) - nT] += x[nT:]
        return y
    mus, fxx = envolver(m), envolver(fx)
    # la musica se ahoga mientras el visor se rompe
    g0, g1 = CFG["08_visor"]["post"]["glitch"][0][:2]
    a, b = at("08_visor", g0), at("08_visor", g1 + 1)
    mus *= N4.envelope(T, [(0, 1), (a - 0.05, 1), (a, 0.15), (b, 0.15), (b + 0.6, 1), (T, 1)])
    out = 0.9 * mus + 0.9 * fxx
    out = dsp.soft_clip(out * 1.1, 1.2)
    out = dsp.normalize(out, -1.0)
    dst = ROOT / "out" / f"{TL['name']}.wav"
    dst.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(dst, SR, (out * 32767).astype(np.int16))
    print(f"-> {dst}  ({len(out) / SR:.2f} s)")
    rms = lambda a, b: 20 * np.log10(np.sqrt(np.mean(out[n_samples(a):n_samples(b)] ** 2)) + 1e-9)
    for s in S:
        print(f"  {s:14s} {rms(S[s], S[s] + 1.0):6.1f} dB (primer s)  pisadas {len(pisadas(s))}")
    print(f"  glitch 08        {rms(a, b):6.1f} dB")
    print(f"  final del loop   {rms(T - 1.0, T):6.1f} dB   | arranque {rms(0, 1.0):6.1f} dB")


if __name__ == "__main__":
    main()
