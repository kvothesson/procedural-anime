"""
banda.py - Banda de sonido de NUNCA SE APAGAN. Sintesis pura: ni un sample.

    python episodios/nunca_se_apagan/banda.py   # -> out/nunca_se_apagan.wav (48 kHz, estereo)

El gradiente de la imagen tambien suena (el calor recuerda, el frio computa):
  - Afuera: atardecer de barrio (viento, grillos, rumor), el Tren de la Costa
    lejos abajo de la barranca, los pasos de los dos y un pad calido mayor
    con un arpegio pulsado.
  - La puerta cruje mientras se abre (plano 3).
  - Adentro (corte al plano 4): se corta la calle. Zumbido de los racks
    (50 Hz y armonicos, ventiladores), pasos con la reverb larga de la nave,
    pad frio suspendido y campanitas de vidrio sueltas.
  - Cada linea de texto lleva un blip: agudo ella (el visor), grave el.
  - El latido (plano 8): una sola vocal de coro imposible, todos juntos.

Eventos anclados a (plano, frame) del timeline: si un plano cambia de
duracion, todo se reacomoda. Los pasos salen de las claves reales de la nena.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / "motor"))
sys.path.insert(0, str(ROOT.parents[1] / "motor" / "audio"))

import dsp  # noqa: E402
from dsp import SR, n_samples, note, place, stereo, time_axis  # noqa: E402
from plano import load_shot  # noqa: E402

np.random.seed(2087)
FPS = 12
TL = json.loads((ROOT / "shots" / "timeline.json").read_text(encoding="utf-8"))
SHOTS = {s: load_shot(ROOT / "shots" / f"{s}.json") for s in TL["shots"]}
S, T = {}, 0.0
for s in TL["shots"]:
    S[s] = T
    T += SHOTS[s]["frames"] / FPS
ADENTRO = S["04_umbral"]


def at(shot, frame=1):
    return S[shot] + (frame - 1) / FPS


def envelope(Ttot, points):
    t = np.arange(n_samples(Ttot)) / SR
    xs, ys = zip(*points)
    return np.interp(t, xs, ys)


# ------------------------------------------------------------------ afuera
def viento(dur, seed=3):
    rng = np.random.default_rng(seed)
    x = dsp.bandpass(rng.standard_normal(n_samples(dur)), 180, 900)
    t = time_axis(len(x))
    return x * (0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * t + 1.3)) * 0.12


def grillos(dur, seed=7):
    """Grillos: trinos de 4.4 kHz en rafagas, dos o tres bichos."""
    rng = np.random.default_rng(seed)
    out = np.zeros(n_samples(dur))
    for k in range(3):
        f = 4300 + 250 * k
        t = 0.3 * k
        while t < dur:
            n = n_samples(0.12)
            tt = time_axis(n)
            chirp = np.sin(2 * np.pi * f * tt) * (np.sin(2 * np.pi * 38 * tt) > 0) * np.hanning(n)
            place(out, chirp * 0.05 * rng.uniform(0.5, 1.0), t)
            t += rng.uniform(0.35, 0.9)
    return out


def tren_lejos(dur, t0):
    """Tren de la Costa abajo de la barranca: rumor grave que crece y pasa,
    traqueteo de ruedas, todo filtrado por la distancia."""
    n = n_samples(dur)
    t = time_axis(n)
    rng = np.random.default_rng(11)
    rumor = dsp.lowpass(rng.standard_normal(n), 220) * 1.6
    clac = np.zeros(n)
    k = 0.0
    while k < dur:
        place(clac, dsp.bandpass(rng.standard_normal(n_samples(0.05)), 300, 1200) * np.hanning(n_samples(0.05)), k)
        k += 0.42 if int(k / 0.42) % 2 == 0 else 0.18
    env = np.exp(-((t - dur / 2) / (dur / 4)) ** 2)
    out = np.zeros(n_samples(T + 1))
    place(out, (rumor + 0.5 * clac) * env * 0.25, t0)
    return out


def paso(pesado):
    """Paso: golpe de ruido filtrado; el del papa mas grave y largo."""
    dur = 0.16 if pesado else 0.09
    n = n_samples(dur)
    x = np.random.standard_normal(n)
    x = dsp.lowpass(x, 700 if pesado else 1500) * dsp.exp_decay(n, 0.035 if pesado else 0.018)
    return x * (0.5 if pesado else 0.3)


def pasos():
    """Pasos de los dos, desde las claves reales de la nena (paso != 0 es
    un pie que apoya); el papa con un desfase y mas lento."""
    out = np.zeros(n_samples(T + 2))
    for shot, cfg in SHOTS.items():
        for k in cfg["nena"]["keys"]:
            if k.get("paso"):
                t = at(shot, k["frame"])
                place(out, paso(False), t)
                if k["paso"] > 0:
                    place(out, paso(True), t + 0.21)
    return out


def calido(dur):
    """Pad mayor calido (Re add9) con un arpegio pulsado lento: la memoria."""
    acorde = ["D3", "A3", "E4", "F#4"]
    pad = sum(dsp.pad(note(nm), dur, voices=5, cutoff=1400, attack=1.5, release=2.0) for nm in acorde)
    out = pad * 0.16
    arp = ["D4", "F#4", "A4", "E5", "A4", "F#4"]
    t, i = 0.4, 0
    while t < dur - 1:
        place(out, dsp.struck(note(arp[i % len(arp)]), 2.5, decay=2.2, bright=0.55) * 0.09, t)
        t += 0.75
        i += 1
    return out


def crujido(dur):
    """La puerta: una resonancia grave que se arrastra (bisagra) sobre un
    rozamiento de madera."""
    n = n_samples(dur)
    t = time_axis(n)
    f = 70 + 25 * np.sin(2 * np.pi * 0.9 * t) + 12 * np.random.default_rng(5).standard_normal(n).cumsum() / np.sqrt(n)
    ph = 2 * np.pi * np.cumsum(f) / SR
    tono = np.sign(np.sin(ph)) * 0.4 + np.sin(ph * 2.01) * 0.3
    roce = dsp.bandpass(np.random.standard_normal(n), 400, 2200) * 0.25
    return dsp.bandpass(tono, 60, 1600) * 0.35 * np.hanning(n) + roce * np.hanning(n)


# ------------------------------------------------------------------ adentro
def zumbido(dur, seed=13):
    """Los racks: 50 Hz con armonicos (la red) y ventiladores (ruido de banda
    ancha con un tono de aspas), con un latido lento de carga."""
    n = n_samples(dur)
    t = time_axis(n)
    red = sum(np.sin(2 * np.pi * 50 * k * t) / k ** 1.3 for k in (1, 2, 3, 5, 7)) * 0.10
    rng = np.random.default_rng(seed)
    vent = dsp.bandpass(rng.standard_normal(n), 250, 5000) * 0.07
    aspas = np.sin(2 * np.pi * 186 * t) * 0.012 + np.sin(2 * np.pi * 241 * t) * 0.008
    carga = 1.0 + 0.08 * np.sin(2 * np.pi * 0.23 * t)
    return (red + vent + aspas) * carga


def frio(dur):
    """Pad frio suspendido (Si sus2 con la novena arriba): el computo."""
    acorde = ["B2", "F#3", "C#4", "F#4", "C#5"]
    return sum(dsp.pad(note(nm), dur, voices=6, spread=0.004, cutoff=2200, attack=2.5, release=3.0)
               for nm in acorde) * 0.13


def campanitas(dur, t0):
    rng = np.random.default_rng(17)
    out = np.zeros(n_samples(T + 6))
    notas = ["F#5", "C#6", "B5", "G#5", "E6"]
    t = t0 + 1.0
    while t < t0 + dur:
        f = note(rng.choice(notas))
        place(out, dsp.struck(f, 3.0, decay=1.6, bright=0.9, inharmonicity=0.004, partials=8) * 0.035, t)
        t += rng.uniform(1.4, 3.2)
    return out


def blip(agudo):
    n = n_samples(0.11)
    t = time_axis(n)
    f = 1650 if agudo else 520
    return np.sin(2 * np.pi * f * t) * dsp.exp_decay(n, 0.03) * (0.06 if agudo else 0.07)


def coro(dur):
    """El latido: una vocal sostenida ("a") de muchas voces que no respiran,
    por sintesis de formantes sobre un acorde, todas juntas una vez."""
    n = n_samples(dur)
    out = np.zeros(n)
    for nm in ("B3", "F#4", "B4", "D#5", "F#5"):
        f = note(nm)
        src = dsp.bl_saw(f, n, 0.002) + dsp.bl_saw(f, n, -0.002)
        voz = sum(dsp.bandpass(src, fc * 0.92, fc * 1.08) * g for fc, g in ((730, 1.0), (1090, 0.5), (2440, 0.25)))
        out += voz
    return out * dsp.adsr(n, 0.08, 0.3, 0.7, 0.6) * 0.5


# ------------------------------------------------------------------ mezcla
def main():
    Ttot = T + 4.0
    N = n_samples(Ttot)
    hall = dsp.make_ir(dur=6.0, decay=3.2, damping=4200, predelay=0.04)   # la nave
    calle = dsp.make_ir(dur=1.2, decay=0.4, damping=8000, predelay=0.005)

    def pad_to(x):
        y = np.zeros(N)
        y[:min(len(x), N)] = x[:N]
        return y

    # afuera: ambiente y musica calida, se cortan en seco al entrar
    # el tren va a la izquierda: la barranca y el rio quedan a la izquierda de la caminata
    fuera = (stereo(pad_to(viento(ADENTRO + 1)), 0.0) + stereo(pad_to(grillos(ADENTRO + 1)), 0.35)
             + stereo(pad_to(tren_lejos(9.0, 2.5)), -0.65))
    fuera += 0.9 * stereo(pad_to(calido(ADENTRO + 3)), 0.0)
    fuera += 0.8 * stereo(pad_to(np.concatenate([np.zeros(n_samples(at("03_atrio", 44))),
                                                 crujido((74 - 44) / FPS)])), 0.0)
    fuera = dsp.reverb(fuera, calle, 0.18)
    fuera *= envelope(Ttot, [(0, 0), (0.6, 1), (ADENTRO - 0.02, 1), (ADENTRO, 0), (Ttot, 0)])[:, None]

    # adentro: zumbido, pad frio, campanitas; todo en la nave
    dentro = pad_to(np.concatenate([np.zeros(n_samples(ADENTRO)), zumbido(Ttot - ADENTRO)]))
    # (mono hasta la reverb: la nave lo abre)
    dentro += pad_to(np.concatenate([np.zeros(n_samples(ADENTRO)), frio(Ttot - ADENTRO)]))
    dentro += pad_to(campanitas(T - ADENTRO - 3, ADENTRO))
    # el latido: el coro entra con los leds y el zumbido se hunde un instante
    t_lat = at("08_boveda", 86)
    dentro += 1.1 * pad_to(np.concatenate([np.zeros(n_samples(t_lat)), coro(2.6)]))
    dentro *= envelope(Ttot, [(0, 0), (ADENTRO, 0), (ADENTRO + 0.05, 1), (t_lat - 0.1, 1), (t_lat + 0.2, 0.55),
                              (t_lat + 1.4, 0.55), (T, 1), (Ttot, 0.0)])
    dentro = dsp.reverb(stereo(dentro, 0.0), hall, 0.42)

    # pasos: afuera secos, adentro con la nave
    p = stereo(pad_to(pasos()), 0.15)
    pf = p * envelope(Ttot, [(0, 1), (ADENTRO - 0.01, 1), (ADENTRO, 0), (Ttot, 0)])[:, None]
    pd = dsp.reverb(p * envelope(Ttot, [(0, 0), (ADENTRO, 0), (ADENTRO + 0.01, 1), (Ttot, 1)])[:, None], hall, 0.5)

    # blips de cada linea
    bl = np.zeros(N)
    for shot, cfg in SHOTS.items():
        for ln in cfg.get("dialogo", []):
            place(bl, blip(ln["quien"] == "ella"), at(shot, ln["f0"]))

    mix = 0.9 * fuera + 0.85 * dentro + 0.8 * pf + 0.7 * pd + stereo(bl, 0.0)
    mix = mix[:n_samples(T)]
    st = dsp.normalize(dsp.soft_clip(mix * 1.1, 1.2), -1.0)
    out = st.mean(axis=1)
    dst = ROOT / "out" / "nunca_se_apagan.wav"
    dst.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(dst, SR, (st * 32767).astype(np.int16))
    print(f"-> {dst}  ({len(out) / SR:.2f} s, timeline {T:.2f} s)")

    rms = lambda a, b: 20 * np.log10(np.sqrt(np.mean(out[n_samples(a):n_samples(b)] ** 2)) + 1e-9)
    for s in S:
        print(f"  {s:16s} {rms(S[s] + 0.2, S[s] + 1.2):6.1f} dB (primer s)")
    print(f"  antes de entrar  {rms(ADENTRO - 1.0, ADENTRO):6.1f} dB | al entrar {rms(ADENTRO, ADENTRO + 1.0):6.1f} dB")
    print(f"  latido           {rms(t_lat, t_lat + 1.0):6.1f} dB | final {rms(T - 1.0, T):6.1f} dB")


if __name__ == "__main__":
    main()
