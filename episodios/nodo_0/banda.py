"""
banda.py - Banda de sonido de NODO 0 (La marea de cobre). Sintesis pura: ni un sample.

    python episodios/nodo_0/banda.py   # -> episodios/nodo_0/out/nodo_0.wav (48 kHz, estereo)

Sin voces. La musica lleva la emocion:
  - Milonga de bandoneon granular a 60 BPM (el pulso del nodo: el mismo latido
    ambar que se ve), 2/4 con acentos 3-3-2. Re menor; resuelve a Re mayor
    cuando el nodo se estabiliza (09).
  - La radio suena en AM: portadora, estatica, silbido de heterodino que deriva,
    un locutor de formantes que no dice palabras y una frase de bandoneon por el
    ancho de banda de AM. Entra cuando Nyx enchufa el cable (05) y es el
    "sueno" del 06-07.
  - 08: el tiempo se detiene. Corte a silencio absoluto (con colas de reverb y
    todo); en el mundo congelado solo suena Nyx: alas, cable, pulsos y la
    descarga a tierra. El mundo vuelve con el color.
  - Cada evento se ancla a (plano, frame) y sale de los JSON: los latidos del
    resplandor y de la radio, el telar hilo por hilo, las letras del HUD, la
    cuenta 3-2-1, los pulsos y la descarga.
  - Loop: se renderiza con cola y la cola se suma al principio.

Instrumentos compartidos con NODO 404 (campana, bandoneon, glitch, silbido de la
luz mala, filtros): se importan de su banda sin tocarla.
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

import dsp  # noqa: E402
from plano import load_shot  # noqa: E402
from dsp import SR, n_samples, time_axis, note, place, stereo  # noqa: E402

_spec = importlib.util.spec_from_file_location("banda_nodo", ROOT.parent / "nodo_404" / "banda.py")
nodo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nodo)

np.random.seed(404)
TAIL = 5.0
FPS = 12
BPM = 60
BEAT = 60.0 / BPM

# ------------------------------------------------------------------ tiempos

TL = json.loads((ROOT / "shots" / "timeline.json").read_text(encoding="utf-8"))
C = {s: load_shot(ROOT / "shots" / f"{s}.json") for s in TL["shots"]}
S = {}
_t = 0.0
for _s in TL["shots"]:
    S[_s] = _t
    _t += C[_s]["frames"] / FPS
T = _t
INTERIOR = ["03_galpon", "04_mapa", "05_conexion", "06_sombra", "07_orden", "08_medio_segundo", "09_luz_mala"]


def at(shot, frame):
    """Tiempo absoluto de un frame (1 = primer cuadro) de un plano."""
    return S[shot] + (frame - 1) / FPS


def fin(shot):
    return S[shot] + C[shot]["frames"] / FPS


def latidos(shot, clave):
    """Frames de golpe de un latido ("resplandor" o "radio") en un plano."""
    e = C[shot].get(clave, {})
    L = e.get("latido")
    if not L:
        return []
    paso = round(FPS * 60 / L.get("bpm", 60))
    return list(range(L["desde"], C[shot]["frames"] + 1, paso))


# ------------------------------------------------------------------ instrumentos

def bandoneon_granular(freqs, dur, grain=0.09, density=55, jitter=0.012, seed=1):
    """El fuelle desarmado en granos: un acorde de bandoneon cortado en granos
    con ventana de Hann, desparramados en el tiempo y con un poco de afinacion
    corrida. Suena a bandoneon que respira desde lejos."""
    rnd = np.random.default_rng(seed)
    src_dur = 2.5
    src = sum(nodo.bandoneon(f, src_dur, attack=0.05, release=0.3) for f in freqs) / len(freqs)
    n = n_samples(dur)
    out = np.zeros(n)
    g = n_samples(grain)
    win = np.hanning(g)
    for _ in range(int(density * dur)):
        s0 = rnd.integers(n_samples(0.3), len(src) - g * 2)
        rate = 1.0 + rnd.normal(0, jitter)
        idx = s0 + np.arange(g) * rate
        piece = np.interp(idx, np.arange(len(src)), src) * win
        t0 = rnd.integers(0, max(1, n - g))
        out[t0:t0 + g] += piece * rnd.uniform(0.4, 1.0)
    return dsp.lowpass(out, 3200) / max(1.0, density * grain * 0.5)


def bajo_milonga(freq, dur):
    """Bajo de milonga: pulsado corto, con cuerpo."""
    n = n_samples(dur)
    t = time_axis(n)
    x = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(4 * np.pi * freq * t) + 0.1 * np.sin(6 * np.pi * freq * t)
    return dsp.soft_clip(x * 0.9, 1.4) * np.exp(-t / 0.35) * np.minimum(1, t / 0.006)


def punteo(freq, dur=1.6):
    """Hilo del telar: cuerda punteada brillante (como un charango)."""
    a = dsp.struck(freq, dur, decay=0.7, bright=0.9, inharmonicity=0.0008, partials=10)
    return a


def latido(f0=52.0):
    """El nodo late: golpe grave y tibio, con un armonico de cobre."""
    n = n_samples(0.9)
    t = time_axis(n)
    f = f0 * (1 + 0.6 * np.exp(-t / 0.03))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.22)
    cobre = dsp.struck(f0 * 8.1, 0.9, decay=0.25, bright=0.7, inharmonicity=0.004, partials=6)
    return dsp.soft_clip(x * 1.2, 1.3) + 0.12 * cobre


def viento(dur, seed=3, brillo=900):
    rnd = np.random.default_rng(seed)
    n = n_samples(dur)
    t = time_axis(n)
    x = rnd.uniform(-1, 1, n)
    x = dsp.lowpass(x, brillo)
    mod = 0.55 + 0.3 * np.sin(2 * np.pi * 0.11 * t + 1.0) + 0.15 * np.sin(2 * np.pi * 0.37 * t)
    return x * mod


def hilos_cantan(dur):
    """Los cables del telegrafo con viento: un silbido eolico que va y viene."""
    n = n_samples(dur)
    t = time_axis(n)
    f = 760 + 40 * np.sin(2 * np.pi * 0.21 * t) + 15 * np.sin(2 * np.pi * 1.3 * t)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.3 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR)
    return x * (0.5 + 0.5 * np.sin(2 * np.pi * 0.09 * t) ** 2)


def chapa(seed=0):
    """La chapa se dilata con el calor: un tac metalico con cola que se dobla."""
    rnd = np.random.default_rng(seed)
    n = n_samples(1.2)
    t = time_axis(n)
    f0 = rnd.uniform(380, 620)
    f = f0 * (1 - 0.05 * t)
    ping = (np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.6 * np.sin(2 * np.pi * np.cumsum(f * 2.37) / SR)) \
        * np.exp(-t / 0.25)
    tac = dsp.bandpass(rnd.uniform(-1, 1, n), 1500, 5000) * np.exp(-t / 0.008)
    return 0.5 * ping + 0.6 * tac


def zumbido_dron(dur, f=118, seed=0):
    """Un dron que flota: zumbido de tobera, sin helices."""
    rnd = np.random.default_rng(seed)
    n = n_samples(dur)
    t = time_axis(n)
    x = sum(np.sin(2 * np.pi * f * k * t + rnd.uniform(0, 6)) / k for k in (1, 2, 3, 5))
    air = dsp.bandpass(rnd.uniform(-1, 1, n), f * 6, f * 14) * 0.4
    return (0.5 * x + air) * dsp.adsr(n, 0.3, 0.2, 0.9, 0.4)


def pasada(dur=1.3, f_from=2400, f_to=500, seed=0):
    """Un dron que pasa: rafaga de aire con el centro que baja (Doppler)."""
    rnd = np.random.default_rng(seed)
    n = n_samples(dur)
    x = nodo.sweep_band(rnd.uniform(-1, 1, n), lambda u: f_from + (f_to - f_from) * u, q=0.5)
    t = time_axis(n)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.5
    return x * env


def servo(dur=0.35, f0=600, f1=900, seed=0):
    """Motorcito: tono de engranaje que cambia de altura, con raspado."""
    rnd = np.random.default_rng(seed)
    n = n_samples(dur)
    t = time_axis(n)
    f = f0 + (f1 - f0) * t / dur
    x = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.3 + dsp.bandpass(rnd.uniform(-1, 1, n), 2000, 6000) * 0.4
    x = dsp.lowpass(x, 5000)
    return x * dsp.adsr(n, 0.01, 0.05, 0.8, 0.05)


def click(f=2400, dur=0.06):
    n = n_samples(dur)
    t = time_axis(n)
    return (np.sin(2 * np.pi * f * t) * np.exp(-t / 0.008) +
            0.5 * np.random.uniform(-1, 1, n) * np.exp(-t / 0.002))


def tecla(f=1800):
    """Una letra del HUD que aparece: tic de teletipo."""
    return click(f, 0.05) * 0.7


def bip(f, dur=0.22):
    n = n_samples(dur)
    t = time_axis(n)
    x = np.sin(2 * np.pi * f * t) + 0.3 * np.sign(np.sin(2 * np.pi * f * t))
    return x * dsp.adsr(n, 0.004, 0.03, 0.8, 0.06)


def chillido_lechuza():
    """La lechuza vizcachera: dos notas cortas que suben (un chirrido, no un ulular)."""
    out = []
    for f0, f1, d in ((1500, 2100, 0.12), (1700, 2600, 0.16)):
        n = n_samples(d)
        t = time_axis(n)
        f = f0 + (f1 - f0) * t / d
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.25 * dsp.bandpass(np.random.uniform(-1, 1, n), 2000, 5000)
        out.append(x * np.sin(np.pi * t / d))
        out.append(np.zeros(n_samples(0.05)))
    return np.concatenate(out)


def pulso_energia(f0, f1, dur=0.18):
    """Un pulso que corre por el cable: zap brillante que sube."""
    n = n_samples(dur)
    t = time_axis(n)
    f = f0 * (f1 / f0) ** (t / dur)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.4 * np.sin(2 * np.pi * np.cumsum(f * 2) / SR)
    return x * np.exp(-t / (dur * 0.5)) * np.minimum(1, t / 0.003)


def descarga(dur=2.6):
    """Arco a tierra: chasquido electrico, trueno corto y la tierra que tiembla."""
    n = n_samples(dur)
    t = time_axis(n)
    crack = dsp.highpass(np.random.uniform(-1, 1, n), 1500) * np.exp(-t / 0.05)
    chis = dsp.bandpass(np.random.uniform(-1, 1, n), 3000, 9000) * np.exp(-t / 0.4) * \
        (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 37 * t)))
    rumble = dsp.lowpass(np.random.uniform(-1, 1, n), 120) * np.exp(-t / 0.9) * 4
    thump = np.sin(2 * np.pi * (38 + 30 * np.exp(-t / 0.05)) * t) * np.exp(-t / 0.6)
    return dsp.soft_clip(0.8 * crack + 0.35 * chis + 0.5 * rumble + 0.9 * thump, 1.2)


# ------------------------------------------------------------------ la radio AM

def locutor(dur, seed=7):
    """Un locutor de radio vieja sin palabras: pulso glotal con entonacion,
    filtrado por formantes de vocales que cambian por silaba, con pausas."""
    rnd = np.random.default_rng(seed)
    n = n_samples(dur)
    t = time_axis(n)
    f0 = 118 + 14 * np.sin(2 * np.pi * 0.6 * t) + 8 * np.sin(2 * np.pi * 2.1 * t)
    src = np.zeros(n)
    phase = np.cumsum(f0) / SR
    src = (phase % 1.0) - 0.5                         # sierra: la voz
    src += 0.08 * rnd.uniform(-1, 1, n)
    vocales = [(730, 1090), (530, 1840), (270, 2290), (570, 840), (300, 870)]
    out = np.zeros(n)
    i = 0
    while i < n:
        d = n_samples(rnd.uniform(0.09, 0.2))
        j = min(n, i + d)
        if rnd.random() < 0.14:                       # pausa entre palabras
            i = j + n_samples(rnd.uniform(0.05, 0.2))
            continue
        f1, f2 = vocales[rnd.integers(len(vocales))]
        seg = src[i:j]
        y = dsp.bandpass(seg, f1 * 0.8, f1 * 1.25) + 0.6 * dsp.bandpass(seg, f2 * 0.85, f2 * 1.15)
        out[i:j] += y * np.hanning(j - i)
        i = j
    return out / max(np.abs(out).max(), 1e-9)


def frase_tango(dur, seed=2):
    """La frase de bandoneon que la radio repite: Re menor, cadencia de tango."""
    mel = [("A4", 0.5), ("F4", 0.25), ("E4", 0.25), ("D4", 0.75), ("A4", 0.25),
           ("A#4", 0.5), ("A4", 0.25), ("G4", 0.25), ("F4", 0.5), ("E4", 0.5)]
    n = n_samples(dur)
    out = np.zeros(n)
    t0 = 0.0
    while t0 < dur:
        for nm, d in mel:
            if t0 >= dur:
                break
            place(out, nodo.bandoneon(note(nm), d * 1.4, attack=0.06, release=0.25), t0)
            t0 += d
        t0 += 0.6
    return out


def am(x, seed=11, qsb=0.18):
    """Pasar una senal por una radio AM vieja: banda angosta, saturacion,
    desvanecimiento lento (QSB), estatica en chasquidos, soplido y un silbido
    de heterodino que deriva."""
    rnd = np.random.default_rng(seed)
    n = len(x)
    t = time_axis(n)
    y = dsp.bandpass(x, 320, 2800)
    y = dsp.soft_clip(y * 1.6, 1.5)
    y *= 0.75 + 0.25 * np.sin(2 * np.pi * qsb * t + 0.7)
    hiss = dsp.bandpass(rnd.uniform(-1, 1, n), 1500, 6000) * 0.07
    crackle = np.zeros(n)
    for _ in range(int(n / SR * 9)):
        i = rnd.integers(0, n - 200)
        crackle[i:i + 200] += rnd.uniform(-1, 1, 200) * np.exp(-np.arange(200) / 30) * rnd.uniform(0.2, 1)
    het_f = 1750 + 600 * np.sin(2 * np.pi * 0.05 * t + 2) + 60 * np.sin(2 * np.pi * 0.8 * t)
    het = np.sin(2 * np.pi * np.cumsum(het_f) / SR) * 0.035
    return y + hiss + 0.35 * crackle + het


# ------------------------------------------------------------------ partitura

D_MENOR = [note("D3"), note("F3"), note("A3")]
D_MAYOR = [note("D3"), note("F#3"), note("A3")]
BAJO = {"D": note("D2"), "A": note("A1"), "G": note("G1"), "F": note("F1")}


def musica(Ttot):
    """Milonga: colchon granular + bajo 3-3-2 (a 60 BPM, compas de 2/4 = 2 s).
    Entra el bajo con la llegada (02), se adelgaza en el sueno AM (05-07), calla
    en el 08 y vuelve en el 09 resolviendo a Re mayor."""
    bus = np.zeros((n_samples(Ttot), 2))
    resuelve = at("09_luz_mala", 22)                  # primer latido estable
    # colchon granular por tramos de 4 s, con el acorde que toca
    t = 0.0
    k = 0
    while t < Ttot:
        acorde = D_MAYOR if t >= resuelve - 0.5 else D_MENOR
        g = bandoneon_granular([f * 2 for f in acorde], 4.6, seed=k)
        g *= dsp.adsr(len(g), 0.8, 0.5, 0.9, 1.0)
        place(bus, stereo(g * 0.55, -0.25 if k % 2 else 0.25), t)
        t += 4.0
        k += 1
    # bajo de milonga: 3-3-2 en semicorcheas sobre cada compas de 2 s
    prog = ["D", "D", "A", "D", "G", "A", "D", "D"]
    b = 0
    tb = S["02_llegada"]
    while tb < Ttot:
        raiz = prog[b % len(prog)]
        for off, acc in ((0.0, 1.0), (0.75, 0.75), (1.5, 0.85)):
            f = BAJO[raiz]
            if raiz == "D" and tb + off >= resuelve and acc < 0.8:
                f = note("F#2")                         # la tercera mayor asoma en el bajo
            place(bus, stereo(bajo_milonga(f, 0.6) * 0.42 * acc), tb + off)
        tb += 2 * BEAT
        b += 1
    # melodia del 09-10: la frase del tango, ahora en mayor, a cielo abierto
    mel = [("A4", 1.0), ("F#4", 0.5), ("E4", 0.5), ("D4", 1.5), ("A4", 0.5), ("B4", 1.0),
           ("A4", 0.5), ("F#4", 0.5), ("E4", 1.0), ("D4", 2.0)]
    tm = resuelve + 1.0
    for nm, d in mel:
        place(bus, stereo(nodo.bandoneon(note(nm), d * 1.3, attack=0.12, release=0.6) * 0.32, 0.15), tm)
        tm += d
    return bus


def sonido_mundo(Ttot):
    """Ambiente y efectos del mundo (se congelan en el 08)."""
    bus = np.zeros((n_samples(Ttot), 2))
    n = n_samples(Ttot)
    # viento: afuera fuerte, adentro apagado
    v = viento(Ttot)
    afuera = nodo.envelope(Ttot, [(0, 0.7), (S["03_galpon"] - 0.2, 0.7), (S["03_galpon"] + 0.3, 0.18),
                                  (S["10_salida"] - 0.2, 0.18), (S["10_salida"] + 0.6, 0.7), (Ttot, 0.7)])[:, 0]
    bus += stereo(v * afuera * 0.5)
    hil = hilos_cantan(Ttot) * nodo.envelope(Ttot, [(0, 0.0), (S["02_llegada"], 0.12), (S["03_galpon"], 0.0),
                                                    (S["10_salida"] + 1.0, 0.0), (Ttot, 0.06)])[:, 0]
    bus += stereo(hil * 0.6, -0.4)

    # el nodo late (resplandor del exterior y radio estabilizada)
    for shot, clave in (("01_horizonte", "resplandor"), ("10_salida", "resplandor"), ("09_luz_mala", "radio")):
        for f in latidos(shot, clave):
            place(bus, stereo(latido() * (0.55 if clave == "radio" else 0.35)), at(shot, f))

    # 02: llegan los drones (pasan cerca de camara), la chapa cruje al sol
    for i, (lag, pan) in enumerate(((0, -0.3), (2, -0.6), (6, 0.4))):
        place(bus, stereo(pasada(1.8, 2600, 420, seed=i) * 0.32, pan), at("02_llegada", 4 + lag))
    for i, f in enumerate((22, 47)):
        place(bus, stereo(chapa(i) * 0.25, 0.3 if i else -0.2), at("02_llegada", f))

    # 03: adentro. Zumbidos de los drones que bajan, la radio crepita, el telar
    for i, (f0, f1, fr) in enumerate(((1, 22, 118), (1, 26, 147), (7, 28, 96))):
        z = zumbido_dron(at("03_galpon", f1) - at("03_galpon", f0) + 1.0, fr, seed=i)
        place(bus, stereo(z * 0.12, (-0.4, 0.4, 0.0)[i]), at("03_galpon", f0))
    for i, f in enumerate((5, 40)):
        place(bus, stereo(chapa(10 + i) * 0.18, 0.5), at("03_galpon", f))
    esc = C["03_galpon"]["aegis"]["escudo"]
    f0, dt, nh = esc["desde"], esc.get("hilo", 1), esc.get("hilos", 9)
    place(bus, stereo(click(700, 0.12) * 0.4), at("03_galpon", f0))                     # el marco se abre
    place(bus, stereo(servo(0.3, 300, 500) * 0.15), at("03_galpon", f0))
    escala = ["D5", "F5", "G5", "A5", "C6", "D6", "F6", "G6", "A6"]
    f = f0 + 4
    for i in range(nh):                                                                 # urdimbre: sube
        place(bus, stereo(punteo(note(escala[i % 9])) * 0.16, -0.5 + i / nh), at("03_galpon", f))
        f += dt
    for j in range(nh):                                                                 # trama: baja
        place(bus, stereo(punteo(note(escala[(nh - 1 - j) % 9]) * 2) * 0.1, 0.5 - j / nh), at("03_galpon", f))
        f += dt

    # 04: el mapa se abre; el medidor sube y queda pitando en rojo
    place(bus, stereo(nodo.riser(0.7) * 0.25), at("04_mapa", 9) - 0.35)
    place(bus, stereo(nodo.bell(note("A5"), 3.0) * 0.12, 0.3), at("04_mapa", 16))
    m0 = C["04_mapa"]["mapa"]["medidor"]["desde"]
    place(bus, stereo(servo(0.65, 200, 1400, seed=4) * 0.18), at("04_mapa", m0))
    t = at("04_mapa", m0 + 8)
    while t < fin("04_mapa"):
        place(bus, stereo(bip(1320, 0.12) * 0.12, 0.3), t)
        t += 0.5

    # 05: Nyx gira la cabeza (chillido de lechuza), planea, el cable avanza y enchufa
    place(bus, stereo(servo(0.18, 900, 1500, seed=5) * 0.2), at("05_conexion", 14))
    place(bus, stereo(chillido_lechuza() * 0.18, 0.1), at("05_conexion", 17))
    place(bus, stereo(pasada(1.4, 900, 600, seed=7) * 0.12), at("05_conexion", 21))
    c0, c1 = C["05_conexion"]["nyx"]["crece"]
    for f in range(c0, c1, 2):
        place(bus, stereo(click(3200, 0.03) * 0.12), at("05_conexion", f))           # trinquete
    place(bus, stereo(click(900, 0.15) * 0.6), at("05_conexion", c1))                  # clac: enchufado

    # 06: el datamosh cruje; la torre que no existe hace temblar la chapa
    for g0, g1, amt in C["06_sombra"]["post"].get("datamosh", []):
        place(bus, stereo(nodo.glitch_burst(0.18, seed=g0) * 0.25 * amt), at("06_sombra", g0))
        place(bus, stereo(nodo.glitch_burst(0.1, seed=g1) * 0.18 * amt), at("06_sombra", (g0 + g1) // 2))
    tz = at("06_sombra", 36)
    n6 = n_samples(fin("06_sombra") - tz + 1.0)
    tt = time_axis(n6)
    torre = (np.sin(2 * np.pi * 41 * tt) + 0.4 * np.sin(2 * np.pi * 82.5 * tt)) * np.clip(tt / 1.5, 0, 1)
    torre *= np.clip((tt[-1] - tt) / 0.8, 0, 1)
    place(bus, stereo(torre * 0.3), tz)
    place(bus, stereo(chapa(20) * 0.3, -0.4), at("06_sombra", 40))

    # 07: Aegis prende el visor, el HUD se escribe, la cuenta 3-2-1
    place(bus, stereo(servo(0.4, 180, 320, seed=8) * 0.2), at("07_orden", 7))
    h = C["07_orden"]["hud"]
    piezas = 1 + h.get("bloques", 5) + len(h.get("resto", " /NODO_00"))
    for i in range(piezas):
        place(bus, stereo(tecla(1600 + 120 * (i % 3)) * 0.22), at("07_orden", h["desde"] + 3 + i))
    for j, (fc, _d) in enumerate(h.get("cuenta", [])):
        place(bus, stereo(bip((880, 740, 587)[j % 3], 0.3) * 0.3), at("07_orden", fc))

    # 09: la luz mala se enciende en el mapa
    fm = C["09_luz_mala"]["mapa"]["luz_mala"]
    place(bus, stereo(nodo.bell(note("D6"), 5.0) * 0.22, 0.2), at("09_luz_mala", fm))
    place(bus, stereo(nodo.whistle(1.8) * 0.1, 0.3), at("09_luz_mala", fm) + 0.3)

    # 10: los drones salen por la brecha y se van
    for i, (lag, pan) in enumerate(((0, 0.2), (2, -0.3), (6, 0.5))):
        place(bus, stereo(pasada(2.2, 700, 2600, seed=20 + i) * 0.25, pan), at("10_salida", 10 + lag))
    return bus


def radio_am(Ttot):
    """La radio suena en AM desde que Nyx enchufa (05) hasta el corte del 08;
    se estabiliza (09) en un murmullo limpio y bajo que acompana el latido."""
    a = at("05_conexion", C["05_conexion"]["nyx"]["crece"][1])
    b = fin("09_luz_mala") + 1.0
    dur = b - a
    voz = locutor(dur)
    tango = frase_tango(dur)
    sig = am(0.7 * voz + 0.6 * tango)
    bus = np.zeros((n_samples(Ttot), 2))
    place(bus, stereo(sig * 0.5, 0.2), a)
    # antes de enchufar: la radio crepita bajita, sola, en el galpon
    pre0, pre1 = S["03_galpon"], a
    est = am(np.zeros(n_samples(pre1 - pre0)), seed=3, qsb=0.3) * 0.25
    place(bus, stereo(est, 0.3), pre0)
    return bus


# ------------------------------------------------------------------ silencio del 08

def congelar_mascara(Ttot):
    """1 = suena el mundo; 0 = el tiempo detenido. Corte seco al empezar el 08
    (con colas de reverb y todo) y vuelta con el color."""
    # la imagen se desatura en dos cuadros; el sonido se corta en seco al
    # empezar el plano. Vuelve con la rampa del color.
    k = C["08_medio_segundo"]["post"]["congelar"]["keys"]
    t0 = S["08_medio_segundo"]
    pts = [(0, 1.0), (t0 - 0.002, 1.0), (t0, 0.0)]
    for f, v in k:
        if at("08_medio_segundo", f) > t0 + 0.2 and v < 1.0:
            pts.append((at("08_medio_segundo", f), 1.0 - v))
        elif at("08_medio_segundo", f) > t0 + 0.2:
            pts.append((at("08_medio_segundo", f), 0.0))
    pts.append((Ttot, 1.0))
    pts.sort()
    return nodo.envelope(Ttot, pts)


def nyx_en_el_08(Ttot):
    """Lo unico que suena con el tiempo detenido."""
    bus = np.zeros((n_samples(Ttot), 2))
    e = C["08_medio_segundo"]
    # el medio segundo es silencio absoluto: lo primero que suena es Nyx
    # abriendo las alas, despues
    place(bus, stereo(servo(0.4, 500, 800, seed=30) * 0.22), at("08_medio_segundo", 7))       # alas
    c0, c1 = e["nyx"]["cable2"]["crece"]
    for f in range(c0, c1, 2):
        place(bus, stereo(click(2800, 0.03) * 0.14, 0.3), at("08_medio_segundo", f))
    place(bus, stereo(click(700, 0.15) * 0.5, 0.4), at("08_medio_segundo", c1))               # muerde la abrazadera
    for i, p in enumerate(e["pulsos"]):
        n = p.get("n", 3)
        lag = p.get("separacion", 2)
        base = (300, 600, 1200)[i % 3]
        for k in range(n):
            place(bus, stereo(pulso_energia(base, base * 2.2) * 0.2, -0.3 + 0.3 * i),
                  at("08_medio_segundo", p["de"] + k * lag))
    place(bus, stereo(descarga() * 0.75, 0.35), at("08_medio_segundo", e["descarga"]["frame"]))
    return bus


# ------------------------------------------------------------------ mezcla

def main():
    Ttot = T + TAIL
    print(f"timeline {T:.2f} s: " + ", ".join(f"{k} @{v:.1f}" for k, v in S.items()))
    hall = dsp.make_ir(dur=4.0, decay=1.9, damping=5200, predelay=0.03)
    galpon = dsp.make_ir(dur=2.2, decay=0.9, damping=4500, predelay=0.015)     # chapa: rebota
    chico = dsp.make_ir(dur=0.8, decay=0.25, damping=7000, predelay=0.005)

    m = musica(Ttot)
    # dramaturgia: suave al abrir, crece con la llegada, se adelgaza en el sueno AM,
    # vuelve plena cuando el nodo se estabiliza, y baja a la noche del loop
    m *= nodo.envelope(Ttot, [(0, 0.55), (S["02_llegada"], 0.8), (S["05_conexion"], 0.8),
                              (at("05_conexion", 54), 0.35), (S["08_medio_segundo"], 0.35),
                              (at("09_luz_mala", 20), 0.5), (at("09_luz_mala", 24), 1.0),
                              (S["10_salida"] + 4, 1.0), (T, 0.55), (Ttot, 0.55)])
    m = dsp.reverb(m, hall, 0.35)
    w = sonido_mundo(Ttot)
    r = radio_am(Ttot)
    adentro = nodo.envelope(Ttot, [(0, 0.0), (S["03_galpon"] - 0.01, 0.0), (S["03_galpon"], 1.0),
                                   (S["10_salida"] - 0.01, 1.0), (S["10_salida"], 0.0), (Ttot, 0.0)])
    w = dsp.reverb(w, galpon, 0.28) * adentro + dsp.reverb(w, hall, 0.15) * (1 - adentro)
    r = dsp.reverb(r, galpon, 0.25)

    mundo = 0.85 * m + 1.0 * w + 0.9 * r
    mundo *= congelar_mascara(Ttot)                  # silencio = silencio: tambien las colas
    nyx = dsp.reverb(nyx_en_el_08(Ttot), chico, 0.15)
    mix = mundo + nyx

    # loop: la cola despues de T se suma al principio
    nT = n_samples(T)
    out = mix[:nT].copy()
    tail = mix[nT:]
    out[:len(tail)] += tail
    out = dsp.soft_clip(out * 1.1, 1.2)
    out = dsp.normalize(out, -1.0)

    dst = ROOT / "out" / f"{TL['name']}.wav"
    dst.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(dst, SR, (out * 32767).astype(np.int16))
    print(f"-> {dst}  ({len(out) / SR:.2f} s)")

    rms = lambda a, b: 20 * np.log10(np.sqrt(np.mean(out[n_samples(a):n_samples(b)] ** 2)) + 1e-9)  # noqa: E731
    for s in S:
        print(f"  {s:18s} {rms(S[s], fin(s)):6.1f} dB")
    f8 = S["08_medio_segundo"]
    sil = out[n_samples(f8 + 0.01):n_samples(f8 + 0.5)]
    print(f"  antes del 08       {rms(f8 - 1.0, f8):6.1f} dB | silencio (08, 0.5 s) "
          f"{rms(f8 + 0.01, f8 + 0.5):6.1f} dB (pico {np.abs(sil).max():.5f})")
    d = at("08_medio_segundo", C["08_medio_segundo"]["descarga"]["frame"])
    print(f"  descarga           {rms(d, d + 0.6):6.1f} dB")
    print(f"  final del loop     {rms(T - 1.0, T):6.1f} dB | arranque {rms(0, 1.0):6.1f} dB")


if __name__ == "__main__":
    main()
