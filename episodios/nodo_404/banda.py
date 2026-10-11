"""
banda.py - Banda de sonido de NODO 404. Sintesis pura: ni un sample.

    python episodios/nodo_404/banda.py   # -> episodios/nodo_404/out/nodo_404.wav (48 kHz, estereo)

Reutiliza las primitivas de motor/audio/dsp.py (aditiva con limite de
banda, campanas inarmonicas, reverb por convolucion).

Reglas (docs/PRODUCCION.md, seccion Sonido):
  - Cada evento se ancla a (plano, offset): si un plano cambia de duracion,
    todo se reacomoda solo. Las duraciones salen del 'frames' de cada JSON.
  - Semilla fija: dos renders de la misma partitura dan el mismo archivo.
  - Las ganancias son dramaturgia: la curva de volumen se mide al final.
  - Loop: se renderiza con cola y la cola se suma al principio. El acorde
    final se derrama sobre el charco del plano 1.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, sosfilt_zi

ROOT = Path(__file__).resolve().parent                     # carpeta del episodio
sys.path.insert(0, str(ROOT.parents[1] / "motor"))
sys.path.insert(0, str(ROOT.parents[1] / "motor" / "audio"))

import dsp  # noqa: E402
from plano import load_shot  # noqa: E402
from dsp import SR, n_samples, time_axis, note, place, stereo  # noqa: E402

np.random.seed(404)
TAIL = 6.0      # segundos de cola que se envuelven al principio


# ------------------------------------------------------------------ tiempos

def shot_frames(shot):
    """'frames' del JSON del plano, siguiendo la cadena de extends."""
    return load_shot(ROOT / "shots" / f"{shot}.json")["frames"]


def shot_starts():
    """Inicio (s) de cada plano segun el timeline y la duracion de cada JSON."""
    tl = json.loads((ROOT / "shots" / "timeline.json").read_text(encoding="utf-8"))
    starts, t = {}, 0.0
    for s in tl["shots"]:
        starts[s] = t
        t += shot_frames(s) / tl["fps_unique"]
    return starts, t


S, T = shot_starts()


def at(shot, offset_s=0.0, frame=None):
    """Tiempo absoluto de (plano, offset). frame: frame del plano (12 fps)."""
    if frame is not None:
        offset_s = (frame - 1) / 12.0
    return S[shot] + offset_s


# ------------------------------------------------------------------ instrumentos

def bell(freq, dur=6.0, bright=0.82):
    """Cristal: campana inarmonica + copia desafinada que bate (brillo vivo)."""
    a = dsp.struck(freq, dur, decay=3.8, bright=bright, inharmonicity=0.0021, partials=10)
    b = dsp.struck(freq * 1.0035, dur, decay=3.2, bright=bright * 0.9, inharmonicity=0.0021, partials=8)
    return 0.6 * a + 0.4 * b


def bandoneon(freq, dur, attack=0.25, release=1.2):
    """Lengüeta: dos sierras desafinadas + armonicos impares, formante cerca
    de 1.2 kHz y el fuelle como tremolo lento. Discreto: es color, no solista."""
    n = n_samples(dur)
    t = time_axis(n)
    tone = 0.5 * dsp.bl_saw(freq, n, 0.0018) + 0.5 * dsp.bl_saw(freq, n, -0.0018)
    odd = sum(np.sin(2 * np.pi * freq * k * t) / k for k in (1, 3, 5, 7, 9))
    x = 0.65 * tone + 0.35 * odd
    x = dsp.lowpass(x, 2600) + 0.5 * dsp.bandpass(x, 900, 1600)
    bellows = 1.0 + 0.07 * np.sin(2 * np.pi * 5.2 * t)
    return x * bellows * dsp.adsr(n, attack, 0.5, 0.85, release)


def chord_pad(notes, dur, attack=2.2, release=2.5, cutoff=1500, voices=5):
    out = sum(dsp.pad(note(nm), dur, voices=voices, cutoff=cutoff, attack=attack, release=release)
              for nm in notes)
    return out / len(notes)


def drop_plink():
    """Gota en el charco: senoide que cae de tono + salpicadura."""
    n = n_samples(0.35)
    t = time_axis(n)
    f = 600 + 900 * np.exp(-t / 0.012)
    ph = 2 * np.pi * np.cumsum(f) / SR
    tone = np.sin(ph) * np.exp(-t / 0.07)
    splash = dsp.bandpass(np.random.uniform(-1, 1, n), 2500, 9000) * np.exp(-t / 0.02)
    return 0.8 * tone + 0.35 * splash


def thump(f0=46.0, dur=1.4):
    """Latido grave: senoide con caida de tono + click de ataque."""
    n = n_samples(dur)
    t = time_axis(n)
    f = f0 + 30 * np.exp(-t / 0.05)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.35)
    click = dsp.lowpass(np.random.uniform(-1, 1, n), 1200) * np.exp(-t / 0.006)
    return dsp.soft_clip(1.2 * x + 0.2 * click, 1.4)


def boom(dur=4.0):
    n = n_samples(dur)
    t = time_axis(n)
    f = 34 + 40 * np.exp(-t / 0.12)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 1.1)
    rumble = dsp.lowpass(np.random.uniform(-1, 1, n), 220) * np.exp(-t / 0.8)
    return dsp.soft_clip(x + 0.6 * rumble / max(np.abs(rumble).max(), 1e-9), 1.8)


def relay(bright=1.0):
    """Corte de un tubo / rele: click metalico + golpecito grave."""
    n = n_samples(0.18)
    t = time_axis(n)
    click = dsp.highpass(np.random.uniform(-1, 1, n), 2500) * np.exp(-t / 0.004)
    body = np.sin(2 * np.pi * 95 * t) * np.exp(-t / 0.03)
    zap = np.sin(2 * np.pi * (1800 * bright) * t) * np.exp(-t / 0.015) * 0.25
    return 0.6 * click + 0.7 * body + zap


def glitch_burst(dur, seed=53):
    """Ruido digital: sample-and-hold, bitcrush y tonos cuadrados que saltan."""
    rnd = np.random.default_rng(seed)
    n = n_samples(dur)
    hold = rnd.integers(20, 400, 400)
    vals = rnd.uniform(-1, 1, 400)
    x = np.repeat(vals, hold)[:n]
    x = np.pad(x, (0, max(0, n - len(x))))
    t = time_axis(n)
    seg = (t * 28).astype(int)
    freqs = rnd.choice([220, 330, 440, 880, 1320, 2640], seg.max() + 1)
    sq = np.sign(np.sin(2 * np.pi * freqs[seg] * t))
    y = 0.55 * x + 0.35 * sq
    y = np.round(y * 6) / 6                      # bitcrush
    return y * dsp.adsr(n, 0.005, 0.05, 0.9, 0.04)


def whistle(dur=1.4):
    """La Luz Mala silba: senoide fina que baja, vibrato lento, muy lejos."""
    n = n_samples(dur)
    t = time_axis(n)
    f = 2350 - 420 * (t / dur) + 28 * np.sin(2 * np.pi * 5.5 * t)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.08 * np.sin(4 * np.pi * np.cumsum(f) / SR)
    return x * dsp.adsr(n, 0.12, 0.2, 0.8, 0.5)


def riser(dur):
    n = n_samples(dur)
    t = time_axis(n)
    u = t / dur
    f = 90 * (8.0 ** u)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.3 * np.sin(4 * np.pi * np.cumsum(f) / SR)
    air = sweep_band(np.random.uniform(-1, 1, n), lambda uu: 300 + 5000 * uu ** 2)
    return (0.5 * tone + 0.5 * air) * u ** 2.2


def sweep_band(x, fc_of_u, blocks=200, q=0.6):
    """Pasabanda que se mueve en el tiempo, por bloques y con estado continuo."""
    n = len(x)
    out = np.zeros(n)
    edges = np.linspace(0, n, blocks + 1).astype(int)
    zi = None
    for b in range(blocks):
        i, j = edges[b], edges[b + 1]
        fc = fc_of_u((i + j) / 2 / n)
        lo, hi = fc * (1 - q / 2), fc * (1 + q / 2)
        sos = butter(2, [max(lo, 20), min(hi, SR * 0.45)], "bandpass", fs=SR, output="sos")
        if zi is None:
            zi = sosfilt_zi(sos) * x[i]
        out[i:j], zi = sosfilt(sos, x[i:j], zi=zi)
    return out


def sweep_lowpass(x, fc_of_t, blocks=400):
    """Lowpass que se cierra en el tiempo (estereo), con estado continuo."""
    n = len(x)
    out = np.zeros_like(x)
    edges = np.linspace(0, n, blocks + 1).astype(int)
    zi = None
    for b in range(blocks):
        i, j = edges[b], edges[b + 1]
        fc = fc_of_t((i + j) / 2 / SR)
        sos = butter(2, min(fc, SR * 0.45), "lowpass", fs=SR, output="sos")
        if zi is None:
            zi = np.zeros((sos.shape[0], 2, 2))
        for c in range(2):
            out[i:j, c], zi[:, c, :] = sosfilt(sos, x[i:j, c], zi=zi[:, c, :])
    return out


def bus_pass(t_center, dur=4.0, v=12.0, d=10.6, f0=82.0):
    """El colectivo flotante: zumbido antigravedad con Doppler real
    (c = 343 m/s), volumen por distancia, paneo de izquierda a derecha y un
    soplido de aire que acompana. Devuelve estereo y su inicio."""
    n = n_samples(dur)
    t = time_axis(n) - dur / 2
    s = v * t                                   # posicion sobre la calle respecto de la camara
    r = np.sqrt(d * d + s * s)
    v_rad = v * s / r                           # + se aleja
    dop = 343.0 / (343.0 + v_rad)
    ph = 2 * np.pi * np.cumsum(f0 * dop) / SR
    hum = np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.25 * np.sin(3 * ph + 0.3) + 0.15 * np.sin(5 * ph)
    whine = 0.12 * np.sin(2 * np.pi * np.cumsum(1320 * dop) / SR)
    air = sweep_band(np.random.uniform(-1, 1, n), lambda u: 900 + 2600 * np.exp(-((u - 0.5) / 0.18) ** 2))
    gain = (d / r) ** 1.6
    mono = (0.6 * hum + whine + 0.9 * air) * gain
    pan = np.clip(s / 14.0, -1, 1)              # pantalla: entra por la izquierda
    ang = (pan + 1) * np.pi / 4
    st = np.stack([mono * np.cos(ang), mono * np.sin(ang)], axis=1)
    return st, t_center - dur / 2


# ------------------------------------------------------------------ ambiente

def rain_bed(T, seed=11):
    """Lluvia: dos ruidos decorrelacionados (cortina) + gotas sueltas en
    posiciones fijas. La densidad sigue la lluvia del video (rain_dim)."""
    rnd = np.random.default_rng(seed)
    n = n_samples(T)
    L = dsp.bandpass(rnd.uniform(-1, 1, n), 500, 7000)
    R = dsp.bandpass(rnd.uniform(-1, 1, n), 500, 7000)
    body = dsp.lowpass(rnd.uniform(-1, 1, n), 600) * 0.6
    curtain = np.stack([L + body, R + body], axis=1)
    curtain /= np.abs(curtain).max()
    drops = np.zeros((n, 2))
    k = n_samples(0.012)
    tk = time_axis(k)
    for _ in range(int(T * 55)):
        i = rnd.integers(0, n - k)
        f = rnd.uniform(1800, 5200)
        g = rnd.uniform(0.15, 1.0)
        dr = np.sin(2 * np.pi * f * tk) * np.exp(-tk / 0.0025) * g
        p = rnd.uniform(-1, 1)
        a = (p + 1) * np.pi / 4
        drops[i:i + k, 0] += dr * np.cos(a)
        drops[i:i + k, 1] += dr * np.sin(a)
    return 0.8 * curtain + 0.35 * drops


def city_hum(T, seed=5):
    """Rumor de ciudad: trafico lejano (ruido marron) + red electrica a 50 Hz."""
    rnd = np.random.default_rng(seed)
    n = n_samples(T)
    t = time_axis(n)
    brown = np.cumsum(rnd.uniform(-1, 1, n))
    brown = dsp.highpass(dsp.lowpass(brown, 260), 30)
    brown /= np.abs(brown).max()
    mains = 0.5 * np.sin(2 * np.pi * 50 * t) + 0.3 * np.sin(2 * np.pi * 100 * t) + \
        0.15 * np.sin(2 * np.pi * 150 * t)
    buzz = dsp.bandpass(np.sign(np.sin(2 * np.pi * 100 * t)), 200, 3000) * 0.08
    return stereo(0.7 * brown + 0.12 * mains + buzz)


def envelope(T, points):
    """Curva de ganancia por puntos [(t, g), ...], lineal entre puntos."""
    n = n_samples(T)
    ts, gs = zip(*points)
    return np.interp(time_axis(n), ts, gs)[:, None]


# ------------------------------------------------------------------ partitura

D_PENTA = ["D5", "F5", "G5", "A5", "C6", "D6", "F6", "A5"]


def music(Ttot):
    bus = np.zeros((n_samples(Ttot), 2))

    # 1 · charco: un bajo que aparece debajo de la lluvia
    place(bus, stereo(dsp.sub(note("D1"), 8.0, attack=3.0) * 0.5), at("01_charco", 1.6))

    # 2 · calle: Re menor 9, crece despacio
    place(bus, stereo(chord_pad(["D3", "A3", "E4", "F4", "C5"], 6.6, attack=2.6), -0.1), at("02_calle"))
    place(bus, stereo(dsp.sub(note("D2"), 6.6) * 0.45), at("02_calle"))
    for k, (nm, off) in enumerate((("A5", 2.2), ("E6", 3.6), ("D6", 5.0))):
        place(bus, stereo(bell(note(nm)) * 0.32, (-0.4, 0.35, 0.0)[k]), at("02_calle", off))

    # 3 · colectivo: Si bemol maj7(#11)
    place(bus, stereo(chord_pad(["Bb2", "F3", "A3", "D4", "E4"], 4.6, attack=1.2), 0.1), at("03_colectivo"))
    place(bus, stereo(dsp.sub(note("Bb1"), 4.6) * 0.45), at("03_colectivo"))

    # 4 · contrapicado: Fa/La -> Do sus2, arpegio de cristal que crece
    t4 = at("04_contrapicado")
    place(bus, stereo(chord_pad(["A2", "F3", "C4", "G4"], 3.4, attack=0.8)), t4)
    place(bus, stereo(chord_pad(["C3", "G3", "D4", "G4"], 3.4, attack=1.0)), t4 + 3.0)
    place(bus, stereo(dsp.sub(note("A1"), 3.2) * 0.5), t4)
    place(bus, stereo(dsp.sub(note("C2"), 3.4) * 0.5), t4 + 3.0)
    steps = 22
    for i in range(steps):
        nm = D_PENTA[(i * 3) % len(D_PENTA)]
        g = 0.12 + 0.3 * (i / steps) ** 1.5
        place(bus, stereo(bell(note(nm), 3.0) * g, np.sin(i * 1.3) * 0.7), t4 + 0.4 + i * 0.25)

    # 5+6 · apagon: Re menor 9 a pleno, que se cierra y se corta en seco
    t6 = at("06_apagon")
    full = chord_pad(["D3", "A3", "E4", "F4", "C5", "A4"], 6.0, attack=0.4, release=0.1, cutoff=2600)
    place(bus, stereo(full * 1.1), t6)
    place(bus, stereo(dsp.sub(note("D2"), 6.0, attack=0.1) * 0.6), t6)
    return bus


def music_after_cut(Ttot):
    """Lo que suena despues del corte del apagon: no pasa por el filtro."""
    bus = np.zeros((n_samples(Ttot), 2))
    t7 = at("07_reencendido")
    # reencendido: Re menor con bandoneon, y en la bajada resuelve a Re MAYOR
    t_on = at("07_reencendido", frame=30)
    for nm in ("D3", "A3", "F4"):
        place(bus, stereo(bandoneon(note(nm), 2.2, attack=0.15, release=0.8) * 0.22, -0.2), t_on)
    place(bus, stereo(chord_pad(["D3", "A3", "E4", "F4", "C5"], 2.0, attack=0.15, release=1.0) * 0.9), t_on)
    place(bus, stereo(chord_pad(["Bb2", "F3", "D4", "A4"], 1.6, attack=0.4, release=1.2) * 0.9), t_on + 1.5)
    t_maj = t_on + 2.7
    for nm in ("D3", "A3", "F#4", "A4"):
        place(bus, stereo(bandoneon(note(nm), 4.5, attack=0.5, release=3.0) * 0.2, 0.2), t_maj)
    place(bus, stereo(chord_pad(["D3", "A3", "E4", "F#4", "A4", "D5"], 7.0, attack=1.0, release=4.5) * 1.1),
          t_maj)
    place(bus, stereo(dsp.sub(note("D2"), 7.0, attack=0.6) * 0.6), t_maj)
    # el motivo del cristal, ahora en mayor, sube y queda flotando sobre el charco
    for k, nm in enumerate(("D5", "F#5", "A5", "E6", "D6")):
        place(bus, stereo(bell(note(nm), 6.0) * 0.36, (-0.5, -0.2, 0.15, 0.4, 0.0)[k]), t_maj + 0.3 + k * 0.42)
    return bus


def sfx(Ttot):
    bus = np.zeros((n_samples(Ttot), 2))
    # gota del plano 1 (frame 14 del post) + el cristal que responde
    t_drop = at("01_charco", frame=14)
    place(bus, stereo(drop_plink() * 0.7), t_drop)
    place(bus, stereo(bell(note("A5"), 6.0) * 0.45, -0.1), t_drop + 0.02)
    place(bus, stereo(bell(note("E6"), 6.0) * 0.25, 0.2), t_drop + 0.5)

    # colectivo: centro de la pasada ~ frame 26 del plano 3
    st, t0 = bus_pass(at("03_colectivo", frame=26), dur=4.2)
    place(bus, st * 0.9, t0)

    # apagon: reles que se acercan (lejos y suaves -> cerca y fuertes)
    rnd = np.random.default_rng(24)
    a0, a1 = at("06_apagon", frame=24), at("06_apagon", frame=53)
    for i in range(26):
        u = i / 25
        tt = a0 + (a1 - a0) * u ** 0.8 + rnd.uniform(-0.05, 0.05)
        g = 0.08 + 0.55 * u ** 1.6
        place(bus, stereo(relay(rnd.uniform(0.7, 1.3)) * g, rnd.uniform(-0.8, 0.8)), tt)
    place(bus, stereo(glitch_burst(0.55) * 0.5), at("06_apagon", frame=53))

    # en el negro: latido + campana con cada pulso del cristal (picos de power)
    for k, f in enumerate((65, 75, 85)):
        tb = at("06_apagon", frame=f)
        place(bus, stereo(thump() * 0.9), tb - 0.05)
        place(bus, stereo(bell(note(("A4", "F4", "D4")[k]), 5.0) * 0.4), tb)
    # la Luz Mala silba lejos, a la derecha (frames 77-80)
    place(bus, stereo(whistle(1.3) * 0.13, 0.65), at("06_apagon", frame=76))

    # reencendido: el latido sigue en el 7, reles del centro hacia afuera, subida y golpe
    for f in (1, 11, 21):
        place(bus, stereo(thump() * 0.7), at("07_reencendido", frame=f) - 0.05)
    rnd = np.random.default_rng(7)
    b0, b1 = at("07_reencendido", frame=6), at("07_reencendido", frame=30)
    for i in range(22):
        u = i / 21
        place(bus, stereo(relay(rnd.uniform(0.9, 1.5)) * (0.5 - 0.35 * u), rnd.uniform(-0.9, 0.9)),
              b0 + (b1 - b0) * u + rnd.uniform(-0.04, 0.04))
    place(bus, stereo(riser(b1 - b0 + 0.2) * 0.35), b0)
    place(bus, stereo(boom() * 0.95), at("07_reencendido", frame=30))
    return bus


# ------------------------------------------------------------------ mezcla

def main():
    Ttot = T + TAIL
    print(f"timeline {T:.2f} s: " + ", ".join(f"{k} @{v:.1f}" for k, v in S.items()))
    hall = dsp.make_ir(dur=5.0, decay=2.4, damping=5200, predelay=0.03)
    room = dsp.make_ir(dur=1.6, decay=0.6, damping=7000, predelay=0.01)

    # musica antes del corte: el apagon cierra el filtro y despues la corta en seco
    m = music(Ttot)
    c0, c1 = at("06_apagon", frame=24), at("06_apagon", frame=53)
    cut = at("06_apagon", frame=59)
    # dramaturgia: la musica entra contenida en la calle y crece hasta el
    # apagon, para que el corte pegue. Medido abajo, no supuesto.
    m *= envelope(Ttot, [
        (0, 1.0), (at("02_calle"), 0.5), (at("03_colectivo"), 0.62), (at("04_contrapicado"), 0.7),
        (at("06_apagon") - 0.3, 1.15), (at("06_apagon"), 1.45), (Ttot, 1.45)])
    m = sweep_lowpass(m, lambda t: 9000 if t < c0 else max(260.0, 9000 * (1 - (t - c0) / (c1 - c0)) ** 2 + 260)
                      if t < c1 else 260.0)
    m *= envelope(Ttot, [(0, 1), (cut - 0.01, 1), (cut, 0), (Ttot, 0)])
    m = dsp.reverb(m, hall, 0.38)
    # la reverb del corte tambien se corta: el silencio tiene que ser silencio
    m *= envelope(Ttot, [(0, 1), (cut + 0.02, 1), (cut + 0.08, 0), (Ttot, 0)])
    m2 = dsp.reverb(music_after_cut(Ttot), hall, 0.42)

    fx = dsp.reverb(sfx(Ttot), room, 0.22)

    # ambiente: la lluvia sigue al rain_dim del video; la ciudad se apaga con el apagon
    rain = rain_bed(Ttot)
    rain *= envelope(Ttot, [
        (0, 0.85), (at("06_apagon", frame=40), 0.85), (at("06_apagon", frame=60), 0.45),
        (at("07_reencendido", frame=10), 0.45), (at("07_reencendido", frame=36), 0.85), (Ttot, 0.85)])
    city = city_hum(Ttot)
    city *= envelope(Ttot, [
        (0, 0.0), (at("02_calle"), 0.0), (at("02_calle", 1.5), 0.35), (c0, 0.35), (cut, 0.0),
        (at("07_reencendido", frame=24), 0.0), (at("07_reencendido", frame=34), 0.3),
        (T - 1.0, 0.0), (Ttot, 0.0)])

    mix = 0.95 * m + 0.95 * m2 + 0.85 * fx + 0.32 * rain + 0.30 * city

    # loop: la cola despues de T se suma al principio (el acorde final cae
    # sobre el charco del plano 1). La lluvia ya es continua: se recorta.
    nT = n_samples(T)
    tail_music = (0.95 * m2 + 0.85 * fx)[nT:]
    out = mix[:nT].copy()
    out[:len(tail_music)] += tail_music
    out = dsp.soft_clip(out * 1.15, 1.25)
    out = dsp.normalize(out, -1.0)

    dst = ROOT / "out" / "nodo_404.wav"
    dst.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(dst, SR, (out * 32767).astype(np.int16))
    print(f"-> {dst}  ({len(out) / SR:.2f} s)")

    # verificacion de la intencion: curva de volumen por plano y en el negro
    rms = lambda a, b: 20 * np.log10(np.sqrt(np.mean(out[n_samples(a):n_samples(b)] ** 2)) + 1e-9)
    for s in S:
        print(f"  {s:18s} {rms(S[s], S[s] + 1.0):6.1f} dB (primer s)")
    print(f"  antes del corte    {rms(cut - 1.0, cut):6.1f} dB")
    print(f"  silencio (negro)   {rms(cut + 0.1, at('06_apagon', frame=64)):6.1f} dB")
    print(f"  golpe reencendido  {rms(at('07_reencendido', frame=30), at('07_reencendido', frame=30) + 1):6.1f} dB")
    print(f"  final del loop     {rms(T - 1.0, T):6.1f} dB   | arranque {rms(0, 1.0):6.1f} dB")


if __name__ == "__main__":
    main()
