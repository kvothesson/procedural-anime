"""
banda.py - Banda de sonido de "El relevo" (chasqui). Musica sintetizada + las
voces REALES de chasqui (voz/<toma>/entrada.wav y salida.wav).

    python episodios/chasqui_relevo/banda.py   # -> out/chasqui_relevo.wav (48 kHz, estereo)

Reglas (docs/PRODUCCION.md, Sonido): eventos anclados a (plano, frame) y
calculados desde los JSON; semilla fija; la curva RMS se imprime y se lee.

  - Andes: quena y charango en re menor pentatonico. Tokio: el mismo motivo
    en un koto. Mismo mensaje, otro idioma.
  - Latido del cristal = golpe grave; cambio de color = campana; cada baliza
    que se enciende = una nota que sube (tiempos sacados de 03_camino.json).
  - Voces: donde las ubica voces.json (la misma fuente que los subtitulos).
    Original un poco a la izquierda, traduccion a la derecha; el original baja
    cuando entra la traduccion y la musica se corre debajo de las voces.
  - Loop: se renderiza con cola y la cola se suma al principio.
"""

from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / "motor"))
sys.path.insert(0, str(ROOT.parents[1] / "motor" / "audio"))

import dsp  # noqa: E402
from plano import load_shot  # noqa: E402
from dsp import SR, n_samples, time_axis, note, place, stereo  # noqa: E402

np.random.seed(7)
TAIL = 5.0
FPS = 12


# ------------------------------------------------------------------ tiempos

def shot_starts():
    tl = json.loads((ROOT / "shots" / "timeline.json").read_text(encoding="utf-8"))
    starts, t = {}, 0.0
    for s in tl["shots"]:
        starts[s] = t
        t += load_shot(ROOT / "shots" / f"{s}.json")["frames"] / tl["fps_unique"]
    return starts, t


S, T = shot_starts()


def at(shot, frame=1, offset=0.0):
    return S[shot] + (frame - 1) / FPS + offset


def cfg(shot):
    return load_shot(ROOT / "shots" / f"{shot}.json")


# ------------------------------------------------------------------ instrumentos

def quena(freq, dur, vib=5.2, depth=0.006, breath=0.10):
    """Cana soplada: fundamental fuerte, pocos armonicos, vibrato que llega
    tarde, soplo filtrado y una entrada que sube desde abajo."""
    n = n_samples(dur)
    t = time_axis(n)
    scoop = 1 - 0.02 * np.exp(-t / 0.05)
    vibr = 1 + depth * np.minimum(1, t / 0.45) * np.sin(2 * np.pi * vib * t)
    ph = 2 * np.pi * np.cumsum(freq * scoop * vibr) / SR
    tone = np.sin(ph) + 0.22 * np.sin(2 * ph) + 0.1 * np.sin(3 * ph) + 0.04 * np.sin(4 * ph)
    air = dsp.bandpass(np.random.uniform(-1, 1, n), freq * 1.5, min(freq * 5, 16000)) * breath
    env = dsp.adsr(n, 0.09, 0.2, 0.85, min(0.6, dur * 0.4))
    puff = 1 + 1.4 * np.exp(-t / 0.06)
    return (tone * 0.8 + air * puff) * env


def charango(freq, dur=1.6):
    """Cuerda doble metalica y brillante: dos cuerdas casi al unisono."""
    a = dsp.struck(freq, dur, decay=0.9, bright=0.86, inharmonicity=0.0007, partials=12)
    b = dsp.struck(freq * 1.004, dur, decay=0.8, bright=0.84, inharmonicity=0.0007, partials=12)
    return 0.55 * a + 0.45 * b


def strum(bus, chord, t0, pan=0.0, gain=0.25, gap=0.016, dur=1.6):
    for k, f in enumerate(chord):
        place(bus, stereo(charango(f, dur) * gain, pan + 0.1 * (k - len(chord) / 2) / len(chord)), t0 + k * gap)


def koto(freq, dur=2.6):
    """Cuerda de seda tensada: ataque seco, inarmonica, con un leve tiron de altura."""
    n = n_samples(dur)
    t = time_axis(n)
    out = np.zeros(n)
    for k in range(1, 10):
        fk = freq * k * np.sqrt(1 + 0.0012 * k * k)
        bend = 1 + 0.004 * np.exp(-t / 0.08)
        out += (0.8 ** (k - 1) / k) * np.sin(2 * np.pi * np.cumsum(fk * bend) / SR) * np.exp(-t / (2.0 / k ** 0.6))
    out *= np.minimum(1, t / 0.003)
    return out / np.abs(out).max()


def bell(freq, dur=4.0, bright=0.8):
    a = dsp.struck(freq, dur, decay=3.0, bright=bright, inharmonicity=0.0021, partials=10)
    b = dsp.struck(freq * 1.0035, dur, decay=2.6, bright=bright * 0.9, inharmonicity=0.0021, partials=8)
    return 0.6 * a + 0.4 * b


def thump(dur=0.7, f0=70, f1=42):
    """Bombo / latido: seno que cae de altura + un poco de parche."""
    n = n_samples(dur)
    t = time_axis(n)
    f = f1 + (f0 - f1) * np.exp(-t / 0.06)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.22)
    skin = dsp.lowpass(np.random.uniform(-1, 1, n), 900) * np.exp(-t / 0.02) * 0.4
    return body + skin


def swept(dur, f0, f1, q=1.6, seg=0.05):
    """Ruido por una banda que barre de f0 a f1 (soplido del mensaje)."""
    n = n_samples(dur)
    src = np.random.uniform(-1, 1, n + n_samples(seg))
    out = np.zeros(n)
    k = n_samples(seg)
    win = np.hanning(2 * k)
    for i in range(0, n, k):
        fc = f0 * (f1 / f0) ** (i / n)
        lo, hi = fc / q, min(fc * q, 20000)
        chunk = dsp.bandpass(src[i:i + 2 * k], lo, hi)
        j = min(n, i + 2 * k)
        out[i:j] += (chunk * win[:len(chunk)])[:j - i]
    return out / max(np.abs(out).max(), 1e-9)


def wind(dur):
    n = n_samples(dur)
    t = time_axis(n)
    w = dsp.lowpass(np.random.uniform(-1, 1, n), 700)
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.13 * t) * np.sin(2 * np.pi * 0.31 * t + 1)
    return w / np.abs(w).max() * lfo


def rain(dur):
    n = n_samples(dur)
    hiss = dsp.bandpass(np.random.uniform(-1, 1, n), 2500, 11000) * 0.5
    drops = np.zeros(n)
    for i in np.random.randint(0, n - 400, int(dur * 90)):
        drops[i:i + 400] += np.random.uniform(0.2, 1) * np.exp(-np.arange(400) / 60) * np.random.choice([-1, 1])
    drops = dsp.highpass(drops, 1800)
    return hiss + 0.5 * drops / max(np.abs(drops).max(), 1e-9)


def rumble(dur, fc=140):
    n = n_samples(dur)
    r = dsp.lowpass(np.random.uniform(-1, 1, n), fc)
    return r / np.abs(r).max()


def read_wav(path):
    """wav PCM16 -> float mono a 48 kHz."""
    with wave.open(str(path), "rb") as w:
        sr, ch = w.getframerate(), w.getnchannels()
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64) / 32768
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        a = resample_poly(a, SR, sr)
    return a


def active(x, thr=0.012, hold=0.25):
    """Envolvente 0/1 suavizada de donde hay voz (para el ducking)."""
    hop = n_samples(0.02)
    rms = np.array([np.sqrt(np.mean(x[i:i + hop] ** 2)) for i in range(0, len(x), hop)])
    on = (rms > thr).astype(float)
    k = int(hold / 0.02)
    on = np.convolve(on, np.ones(2 * k + 1), "same") > 0
    env = np.repeat(on.astype(float), hop)[:len(x)]
    sm = n_samples(0.12)
    return np.convolve(env, np.ones(sm) / sm, "same")


# ------------------------------------------------------------------ partitura

D = {k: note(k) for k in ("D3", "A3", "C4", "D4", "F4", "G4", "A4", "C5", "D5", "F5", "G5", "A5", "C6", "D6")}
MOTIF = [("A4", 0.0, 0.5), ("C5", 0.5, 0.5), ("D5", 1.0, 1.4)]        # el motivo del mensaje


def main():
    total = T + TAIL
    music = np.zeros((n_samples(total), 2))
    amb = np.zeros_like(music)
    ir = dsp.make_ir(3.6, 2.0, 5200)
    ir_city = dsp.make_ir(1.6, 0.8, 4000)

    # --- 1 apacheta: viento, latido del cristal, la quena entra; destello y salida
    place(amb, stereo(wind(T) * 0.10, 0.0), 0.0)
    a = cfg("01_apacheta")["apacheta"]["latido"]
    for k in range(4):
        f = 1 + a["beat_frames"] * (k + 0.5) - a.get("phase", 0)     # pico del sin^3
        if f <= 28:
            place(music, stereo(thump() * 0.30, 0.0), at("01_apacheta", f))
    place(music, stereo(quena(D["D5"], 2.6) * 0.16, -0.15), at("01_apacheta", 4))
    fl = cfg("01_apacheta")["mensaje"]["from_frame"]
    place(music, stereo(bell(D["A5"], 3.0) * 0.20, 0.1), at("01_apacheta", fl))
    place(amb, stereo(swept(1.6, 500, 4000) * 0.08, 0.3), at("01_apacheta", fl))

    # --- 2 puente: charango; la campana cae donde la luz cambia de color
    for k in range(8):
        t0 = at("02_puente", 1) + 0.5 * k
        ch = [D["D4"], D["A4"], D["D5"], D["F5"]] if k < 4 else [D["C4"], D["G4"], D["C5"], D["F5"]]
        strum(music, ch if k % 2 == 0 else ch[1:], t0, pan=-0.2, gain=0.10 if k % 2 else 0.14)
    sw = cfg("02_puente")["mensaje"]
    f_sw = next(f for f in range(1, sw.get("frames", 48) + 1)
                if np.interp(f, *zip(*sw["keys"])) >= sw["colors"][1][0])
    place(music, stereo(bell(D["D6"], 4.0) * 0.22, 0.25), at("02_puente", f_sw))
    place(music, stereo(bell(D["A5"], 4.0) * 0.12, -0.25), at("02_puente", f_sw, 0.04))
    place(amb, stereo(swept(4.0, 300, 900, 1.4) * 0.05, 0.0), at("02_puente", 1))

    # --- 3 camino: bombo de carrera; una nota por baliza encendida
    c3 = cfg("03_camino")
    keys, lead = c3["mensaje"]["keys"], c3.get("relevo", {}).get("lead", 0)
    scale = ["D5", "F5", "G5", "A5", "C6", "D6"]
    beacons = sorted(t["s"] + t.get("beacon_ahead", 2.0) for t in c3["tambos"]["list"])
    for i, sb in enumerate(beacons):
        fs = [f for f in range(1, c3["frames"] + 1) if np.interp(f, *zip(*keys)) + lead >= sb]
        if fs:
            tt = at("03_camino", fs[0] + c3.get("relevo", {}).get("delay", 0))
            place(music, stereo(charango(D[scale[i % len(scale)]], 1.8) * 0.20, -0.4 + 0.2 * i), tt)
            place(music, stereo(bell(D[scale[i % len(scale)]] * 2, 2.0) * 0.05, 0.3), tt)
    for k in range(16):
        place(music, stereo(thump(0.5, 80, 50) * (0.22 if k % 2 == 0 else 0.12), 0.0), at("03_camino", 1) + 0.25 * k)
    for k in range(4):
        strum(music, [D["D4"], D["A4"], D["D5"]], at("03_camino", 1) + 1.0 * k, pan=0.2, gain=0.09)

    # --- 4 orbita: el aire se abre; quintas largas y la quena arriba
    o0 = at("04_orbita", 1)
    for f, g in ((D["D3"], 0.10), (D["A3"], 0.08), (D["D4"], 0.06), (D["A4"], 0.04)):
        place(music, stereo(dsp.pad(f, 6.0, cutoff=1800, attack=1.0, release=2.0) * g, 0.0), o0 - 0.3)
    place(music, stereo(quena(D["A5"], 3.2, depth=0.008) * 0.10, -0.2), o0 + 0.8)
    place(music, stereo(quena(D["D6"], 1.6, depth=0.008) * 0.07, -0.2), o0 + 3.6)
    place(amb, stereo(swept(5.0, 2000, 400, 2.0) * 0.06, 0.0), o0)

    # --- 5 tokio: lluvia, ciudad, el tren; el motivo en koto
    t5 = at("05_tokio", 1)
    place(amb, stereo(rain(8.0) * 0.06, -0.3) + stereo(rain(8.0) * 0.06, 0.3), t5)
    place(amb, stereo(rumble(8.0, 90) * 0.06, 0.0), t5)
    v5 = cfg("05_tokio")["viaducto"]["tren"]
    tr0, tr1 = at("05_tokio", v5["frames"][0]), at("05_tokio", v5["frames"][1])
    n = n_samples(tr1 - tr0 + 1.0)
    tt = time_axis(n)
    pas = np.exp(-((tt - (tr1 - tr0) * 0.45) / ((tr1 - tr0) * 0.3)) ** 2)
    clack = np.zeros(n)
    for i in range(0, n - 2000, n_samples(0.36)):
        clack[i:i + 2000] += thump(2000 / SR, 140, 90)[:2000] * 0.5
    train = (rumble((n / SR), 220) + clack) * pas
    pan_t = np.linspace(-0.7, 0.7, n)
    place(amb, np.stack([train * np.cos((pan_t + 1) * np.pi / 4), train * np.sin((pan_t + 1) * np.pi / 4)], 1) * 0.10, tr0)
    land = cfg("05_tokio")["mensaje"][0]["keys"][-1][0]
    place(music, stereo(bell(D["A5"], 3.0) * 0.18, 0.0), at("05_tokio", land))
    for i, (nm, dt, du) in enumerate(MOTIF * 2):
        place(music, stereo(koto(D[nm] / (1 if i < 3 else 2), 2.6) * 0.16, 0.25), t5 + 0.4 + dt + (2.6 if i >= 3 else 0))
    sw5 = cfg("05_tokio")["farol_hex"]["colors"][1][0]
    place(music, stereo(bell(D["D6"], 4.0) * 0.20, 0.2), at("05_tokio", sw5))
    place(amb, stereo(swept(1.4, 600, 5000) * 0.07, 0.0), at("05_tokio", sw5))
    for k in range(3):
        place(music, stereo(koto(D[["D4", "A4", "C5"][k]], 2.6) * 0.10, -0.25), at("05_tokio", sw5) + 1.2 + 0.9 * k)

    # --- 6 cierre: la luz baja; destello; quena y charango resuelven; vuelve el viento
    t6 = at("06_cierre", 1)
    place(amb, stereo(wind(6.0) * 0.08, 0.0), t6)
    place(amb, stereo(swept(2.4, 4000, 500) * 0.07, 0.0), t6)
    fl6 = cfg("06_cierre")["apacheta"]["latido"]["flash"][1][0]
    tf = at("06_cierre", fl6)
    place(music, stereo(bell(D["D6"], 5.0) * 0.24, 0.0), tf)
    place(music, stereo(thump(0.9, 60, 38) * 0.35, 0.0), tf)
    for k, (nm, dt, du) in enumerate(MOTIF):
        place(music, stereo(quena(D[nm], du + 0.4) * 0.15, -0.15), tf + 0.6 + dt)
    strum(music, [D["D4"], D["A4"], D["D5"], D["F5"] * 2 ** (1 / 12)], tf + 2.1, pan=0.15, gain=0.13, dur=3.0)
    place(music, stereo(quena(D["D5"], 2.4) * 0.12, -0.15), tf + 2.6)

    music = dsp.reverb(music, ir, 0.32)
    amb_city = np.zeros_like(amb)
    i5, i6 = n_samples(S["05_tokio"]), n_samples(S["06_cierre"])
    amb_city[i5:i6] = amb[i5:i6]
    amb[i5:i6] = 0
    amb = amb + dsp.reverb(amb_city, ir_city, 0.25)

    # --- voces reales
    v = json.loads((ROOT / "voces.json").read_text(encoding="utf-8"))
    voices = np.zeros_like(music)
    duck = np.zeros(len(music))
    for key in ("ida", "vuelta"):
        tk = ROOT / "voz" / v[key]["take"]
        src, out = read_wav(tk / "entrada.wav"), read_wav(tk / "salida.wav")
        a_out = active(out)
        m = min(len(src), len(a_out))
        src = src[:m] * (1 - 0.6 * a_out[:m])               # el original baja cuando entra chasqui
        src = src / max(np.abs(src).max(), 1e-9) * 0.62
        out = out / max(np.abs(out).max(), 1e-9) * 0.78
        place(voices, stereo(src, -0.28), v[key]["at"])
        place(voices, stereo(out, 0.28), v[key]["at"])
        d = np.maximum(active(src * 4)[:len(src)], 0)
        i0 = n_samples(v[key]["at"])
        seg = np.maximum(active(read_wav(tk / "entrada.wav")), active(read_wav(tk / "salida.wav"))[:len(d)] if len(d) else 0)
        j = min(len(duck), i0 + len(seg))
        duck[i0:j] = np.maximum(duck[i0:j], seg[:j - i0])
    voices = dsp.reverb(voices, dsp.make_ir(0.6, 0.25, 6000), 0.08)
    g = 1 - 0.55 * duck
    mix = (music + amb) * g[:, None] + voices

    # loop: la cola vuelve al principio
    tail = mix[n_samples(T):]
    mix = mix[:n_samples(T)].copy()
    mix[:len(tail)] += tail
    mix = dsp.soft_clip(mix * 1.1, 1.2)
    mix = dsp.normalize(mix, -1.0)

    print("RMS por momento (dB):")
    for name, (t0, t1) in {"1 apacheta": (0, 3), "2 puente (voz es+ja)": (3, 7), "3 camino": (7, 11),
                           "4 orbita": (11, 16), "5 tokio (voz ja+es)": (16, 24), "6 cierre": (24, 30)}.items():
        seg = mix[n_samples(t0):n_samples(t1)]
        print(f"  {name:24s} {20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9):6.1f}")
    out = ROOT / "out" / "chasqui_relevo.wav"
    out.parent.mkdir(exist_ok=True)
    wavfile.write(out, SR, (mix * 32767).astype(np.int16))
    print(f"-> {out} ({len(mix) / SR:.1f} s)")


if __name__ == "__main__":
    main()
