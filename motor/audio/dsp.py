"""
dsp.py - Primitivas de sintesis.

Todo se genera por muestra, no hay un solo sample grabado.

Las tres cosas que separan "sintesis programada" de "senoide de juguete":

1. Sintesis aditiva con limite de banda. Una sierra hecha con np.mod aliasea
   y suena a chiptune barato. Sumando armonicos hasta Nyquist, no.
2. Envolventes por parcial. En un instrumento real los armonicos agudos se
   apagan antes que los graves. Un tono con una sola envolvente suena a organo.
3. Reverb por conviccion. Es lo que convierte un sintetizador en "musica en un
   lugar". Usamos conviccion FFT contra una respuesta al impulso generada.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, fftconvolve, sosfiltfilt

SR = 48000


# ---------------------------------------------------------------- utilidades

def n_samples(seconds: float) -> int:
    return int(round(seconds * SR))


def time_axis(n: int) -> np.ndarray:
    return np.arange(n) / SR


def note(name: str) -> float:
    """'A3' / 'C#4' / 'Bb2' -> frecuencia en Hz. A4 = 440."""
    steps = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    pitch = steps[name[0].upper()]
    i = 1
    while i < len(name) and name[i] in "#b":
        pitch += 1 if name[i] == "#" else -1
        i += 1
    octave = int(name[i:])
    return 440.0 * 2 ** ((pitch - 9) / 12.0 + (octave - 4))


def place(bus: np.ndarray, sig: np.ndarray, t_start: float) -> None:
    """Suma sig dentro de bus (estereo) arrancando en t_start segundos."""
    i = n_samples(t_start)
    if i >= len(bus):
        return
    j = min(len(bus), i + len(sig))
    bus[i:j] += sig[:j - i]


def stereo(mono: np.ndarray, pan: float = 0.0) -> np.ndarray:
    """pan -1 izquierda, +1 derecha. Ley de potencia constante."""
    angle = (pan + 1.0) * np.pi / 4.0
    return np.stack([mono * np.cos(angle), mono * np.sin(angle)], axis=1)


def soft_clip(x: np.ndarray, drive: float = 1.0) -> np.ndarray:
    return np.tanh(x * drive) / np.tanh(drive)


# ---------------------------------------------------------------- filtros

def lowpass(x: np.ndarray, fc: float, order: int = 4) -> np.ndarray:
    sos = butter(order, min(fc, SR * 0.49), "lowpass", fs=SR, output="sos")
    return sosfiltfilt(sos, x, axis=0)


def highpass(x: np.ndarray, fc: float, order: int = 4) -> np.ndarray:
    sos = butter(order, max(fc, 10.0), "highpass", fs=SR, output="sos")
    return sosfiltfilt(sos, x, axis=0)


def bandpass(x: np.ndarray, lo: float, hi: float, order: int = 2) -> np.ndarray:
    sos = butter(order, [max(lo, 10.0), min(hi, SR * 0.49)], "bandpass",
                 fs=SR, output="sos")
    return sosfiltfilt(sos, x, axis=0)


# ---------------------------------------------------------------- envolventes

def adsr(n: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    """Attack/decay/release en segundos, sustain en ganancia 0-1."""
    na, nd, nr = n_samples(a), n_samples(d), n_samples(r)
    ns = max(0, n - na - nd - nr)

    env = np.concatenate([
        np.linspace(0.0, 1.0, na, endpoint=False) if na else np.array([]),
        np.linspace(1.0, s, nd, endpoint=False) if nd else np.array([]),
        np.full(ns, s),
        np.linspace(s, 0.0, nr) if nr else np.array([]),
    ])
    return np.resize(env, n) if len(env) != n else env


def exp_decay(n: int, tau: float) -> np.ndarray:
    return np.exp(-time_axis(n) / max(tau, 1e-4))


# ---------------------------------------------------------------- osciladores

def bl_saw(freq: float, n: int, detune: float = 0.0,
           max_harmonics: int = 24) -> np.ndarray:
    """
    Sierra con limite de banda: aditiva, sin armonicos por encima de Nyquist.

    El tope de armonicos no es solo por velocidad. El pad se filtra despues a
    ~1.4 kHz, asi que generar 150 armonicos para tirar 130 a la basura es
    trabajo puro. 24 alcanzan y sobran.
    """
    f = freq * (1.0 + detune)
    t = time_axis(n)
    out = np.zeros(n)
    for k in range(1, max_harmonics + 1):
        if f * k >= SR * 0.45:
            break
        out += np.sin(2 * np.pi * f * k * t) / k
    return out * (2.0 / np.pi)


def struck(freq: float, dur: float, decay: float = 2.6, bright: float = 1.0,
           inharmonicity: float = 0.0004, partials: int = 14) -> np.ndarray:
    """
    Tono percutido tipo cuerda/campana.

    Cada parcial tiene su propia envolvente y los agudos se apagan mas rapido,
    que es lo que hace que suene golpeado y no soplado. La inarmonicidad
    minima es lo que diferencia una cuerda real de un organo.
    """
    n = n_samples(dur)
    t = time_axis(n)
    out = np.zeros(n)

    for k in range(1, partials + 1):
        fk = freq * k * np.sqrt(1.0 + inharmonicity * k * k)
        if fk >= SR * 0.45:
            break
        amp = bright ** (k - 1) / (k ** 1.35)
        tau = decay / (k ** 0.55)
        out += amp * np.sin(2 * np.pi * fk * t + np.random.uniform(0, 0.4)) * np.exp(-t / tau)

    attack = np.minimum(1.0, t / 0.004)   # 4 ms: percusivo pero sin click
    return out * attack / max(np.abs(out).max(), 1e-9)


def pad(freq: float, dur: float, voices: int = 5, spread: float = 0.006,
        cutoff: float = 1400.0, attack: float = 1.4, release: float = 2.2
        ) -> np.ndarray:
    """Colchon: varias sierras desafinadas entre si, filtradas y con ataque lento."""
    n = n_samples(dur)
    out = np.zeros(n)
    for v in range(voices):
        det = spread * (v - (voices - 1) / 2.0) / max(1, (voices - 1) / 2.0)
        out += bl_saw(freq, n, det)
    out /= voices

    out = lowpass(out, cutoff)
    return out * adsr(n, attack, 0.6, 0.72, release)


def sub(freq: float, dur: float, attack: float = 0.25) -> np.ndarray:
    """Bajo sinusoidal con un poco de saturacion para que exista en parlantes chicos."""
    n = n_samples(dur)
    t = time_axis(n)
    tone = np.sin(2 * np.pi * freq * t) + 0.22 * np.sin(2 * np.pi * freq * 2 * t)
    return soft_clip(tone * 0.8, 1.6) * adsr(n, attack, 0.4, 0.8, 1.0)


def noise(dur: float) -> np.ndarray:
    return np.random.uniform(-1.0, 1.0, n_samples(dur))


# ---------------------------------------------------------------- reverb

def make_ir(dur: float = 3.2, decay: float = 1.8, damping: float = 4200.0,
            predelay: float = 0.02) -> np.ndarray:
    """
    Respuesta al impulso sintetica: ruido con decaimiento exponencial y
    amortiguacion de agudos, que es como se comporta una sala real.
    Estereo decorrelacionado para que tenga ancho.
    """
    n = n_samples(dur)
    env = np.exp(-time_axis(n) / decay)

    ir = np.stack([
        lowpass(np.random.uniform(-1, 1, n) * env, damping),
        lowpass(np.random.uniform(-1, 1, n) * env, damping * 0.92),
    ], axis=1)

    pad_n = n_samples(predelay)
    ir = np.vstack([np.zeros((pad_n, 2)), ir])
    return ir / np.abs(ir).max()


def reverb(x: np.ndarray, ir: np.ndarray, mix: float = 0.3) -> np.ndarray:
    wet = np.stack([fftconvolve(x[:, c], ir[:, c])[:len(x)] for c in range(2)], axis=1)
    wet /= max(np.abs(wet).max(), 1e-9)
    return (1.0 - mix) * x + mix * wet


# ---------------------------------------------------------------- masterizado

def normalize(x: np.ndarray, peak_db: float = -1.0) -> np.ndarray:
    target = 10 ** (peak_db / 20.0)
    return x * (target / max(np.abs(x).max(), 1e-9))


def fade(x: np.ndarray, fade_in: float = 0.0, fade_out: float = 0.0) -> np.ndarray:
    out = x.copy()
    if fade_in:
        k = n_samples(fade_in)
        out[:k] *= np.linspace(0, 1, k)[:, None]
    if fade_out:
        k = n_samples(fade_out)
        out[-k:] *= np.linspace(1, 0, k)[:, None]
    return out
