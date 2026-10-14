"""
banda.py - Banda de sonido de DUENDE ROJO. Sintesis pura: ni un sample.

    python episodios/duende_rojo/banda.py   # -> episodios/duende_rojo/out/duende_rojo.wav (48 kHz, estereo)

A cientos de km la tormenta no se oye: se escucha en radio. La banda sale de
los sonidos reales de una tormenta en VLF, sintetizados:
  - sferic: el chasquido seco de cada rayo;
  - tweek: un silbido corto que baja y se clava cerca de 1,7 kHz (la guia de
    onda tierra-ionosfera corta abajo de esa frecuencia);
  - whistler: el silbido largo que baja durante segundos (la dispersion en la
    magnetosfera: el tiempo de llegada crece como 1/sqrt(f), o sea f ~ 1/t^2).
El 07 (el duende) es casi silencio: hit-stop mudo, golpe en los impact frames,
whistler en la camara lenta, silencio cuando se apaga.

Cada plano declara su cadencia ("fps" del JSON: 12 en doses, 24 el sakuga) y
cada evento se ancla a (plano, frame).
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

_spec = importlib.util.spec_from_file_location("banda_nodo0", ROOT.parent / "nodo_0" / "banda.py")
n0 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(n0)
nodo = n0.nodo

np.random.seed(2026)
TAIL = 4.0

# ------------------------------------------------------------------ tiempos

TL = json.loads((ROOT / "shots" / "timeline.json").read_text(encoding="utf-8"))
C = {s: load_shot(ROOT / "shots" / f"{s}.json") for s in TL["shots"]}
FPS = {s: C[s].get("fps", 12) for s in TL["shots"]}
S = {}
_t = 0.0
for _s in TL["shots"]:
    S[_s] = _t
    _t += C[_s]["frames"] / FPS[_s]
T = _t


def at(shot, frame):
    return S[shot] + (frame - 1) / FPS[shot]


def fin(shot):
    return S[shot] + C[shot]["frames"] / FPS[shot]


def tiene(shot):
    return shot in S


# ------------------------------------------------------------------ instrumentos VLF

def sferic(fuerza=1.0, seed=0):
    """El chasquido de un rayo en radio: impulso de banda ancha, muy corto, con
    un poco de cola grave."""
    rnd = np.random.default_rng(seed)
    n = n_samples(0.08)
    t = time_axis(n)
    imp = rnd.uniform(-1, 1, n) * np.exp(-t / 0.0025)
    cuerpo = np.sin(2 * np.pi * 900 * t) * np.exp(-t / 0.006)
    return (0.9 * dsp.highpass(imp, 400) + 0.4 * cuerpo) * fuerza


def tweek(dur=0.12, f_corte=1750, seed=0):
    """Silbido corto que baja y se clava en la frecuencia de corte de la guia
    de onda: f(t) = fc / sqrt(1 - (t0/(t+t0))^2), casi una campana metalica."""
    n = n_samples(dur)
    t = time_axis(n) + 0.004
    t0 = 0.004
    f = f_corte / np.sqrt(np.clip(1 - (t0 / t) ** 2, 1e-4, 1))
    f = np.minimum(f, 9000)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.35 * np.sin(2 * ph)
    return x * np.exp(-time_axis(n) / (dur * 0.45)) * np.minimum(1, time_axis(n) / 0.002)


def whistler(dur=3.2, f_alta=7500, f_baja=900, seed=0):
    """El silbido largo que baja: dispersion de la magnetosfera, el tiempo de
    llegada de cada frecuencia crece como 1/sqrt(f) => f(t) ~ 1/(t + t0)^2.
    Con un poco de ruido de banda angosta alrededor, como se oye en VLF."""
    rnd = np.random.default_rng(seed)
    n = n_samples(dur)
    t = time_axis(n)
    # f(t) = A / (t + t0)^2 con f(0) = f_alta y f(dur) = f_baja
    r = np.sqrt(f_alta / f_baja)
    t0 = dur / (r - 1)
    A = f_alta * t0 * t0
    f = A / (t + t0) ** 2
    ph = 2 * np.pi * np.cumsum(f) / SR
    tono = np.sin(ph) + 0.2 * np.sin(2 * ph + 0.5)
    aire = nodo.sweep_band(rnd.uniform(-1, 1, n), lambda u: float(A / (u * dur + t0) ** 2), q=0.12) * 0.6
    env = np.minimum(1, t / 0.25) * np.exp(-t / (dur * 0.7))
    return (0.8 * tono + aire) * env


def grillos(dur, seed=4):
    """Grillos de madrugada: trenes de pulsos agudos (4,6 kHz), dos o tres
    grillos con su propio ritmo, lejos."""
    rnd = np.random.default_rng(seed)
    n = n_samples(dur)
    out = np.zeros(n)
    t = time_axis(n)
    for g in range(3):
        f = rnd.uniform(4300, 4900)
        per = rnd.uniform(0.55, 0.9)
        fase = rnd.uniform(0, per)
        tono = np.sin(2 * np.pi * f * t)
        en_tren = ((t + fase) % per) < 0.18
        pulsos = (np.sin(2 * np.pi * 32 * t) > 0.2)
        out += tono * en_tren * pulsos * rnd.uniform(0.4, 1.0)
    return dsp.lowpass(out, 7000) * 0.5


def golpe_impacto():
    """Los impact frames: golpe grave con crepitar electrico."""
    n = n_samples(1.4)
    t = time_axis(n)
    sub = np.sin(2 * np.pi * (34 + 60 * np.exp(-t / 0.04)) * t) * np.exp(-t / 0.45)
    crep = dsp.bandpass(np.random.uniform(-1, 1, n), 2500, 9000) * np.exp(-t / 0.12) * \
        (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 47 * t)))
    return dsp.soft_clip(1.1 * sub + 0.45 * crep, 1.3)


# ------------------------------------------------------------------ mezcla

def main():
    Ttot = T + TAIL
    print(f"timeline {T:.2f} s: " + ", ".join(f"{k} @{v:.2f} ({FPS[k]} fps)" for k, v in S.items()))
    hall = dsp.make_ir(dur=4.5, decay=2.2, damping=4800, predelay=0.03)
    noche = np.zeros((n_samples(Ttot), 2))       # ambiente: se corta en el hit-stop
    radio = np.zeros((n_samples(Ttot), 2))       # VLF
    musica = np.zeros((n_samples(Ttot), 2))

    noche += stereo(grillos(Ttot) * 0.18, -0.3)
    noche += stereo(dsp.lowpass(np.random.uniform(-1, 1, n_samples(Ttot)), 300) * 0.05)
    fx = np.zeros((n_samples(Ttot), 2))         # lo que hacen los drones

    # --- la tormenta en la radio: un chasquido por cada relampago que se ve.
    # El volumen sigue la escucha de Nyx: dormido (01), antenas (02-04), lentes
    # apagadas escuchando (05-06)
    escucha = {"01_lente": 0.25, "02_antenas": 0.7, "03_tarde": 0.7, "04_registro": 0.7,
               "05_escucha": 1.0, "06_antes": 1.0, "08_pausa": 0.5, "09_mapa": 0.35}
    for shot, k in escucha.items():
        if not tiene(shot):
            continue
        tm = C[shot].get("tormenta", {})
        golpes = [(f, 0.75) for f in tm.get("rayos", [])]
        if tm.get("dispara"):
            golpes.append((tm["dispara"], 1.0))
        for f, a in golpes:
            if shot == "02_antenas" and f < 22:
                a *= 0.4                                    # antes de abrir las antenas
            t = at(shot, f)
            place(radio, stereo(sferic(a, seed=f) * 0.7 * k, -0.2), t)
            place(radio, stereo(tweek(0.12, f_corte=1700 + 60 * (f % 5), seed=f) * 0.3 * k, 0.15), t + 0.008)

    # --- el pulso de la noche: colchon de bandoneon granular, Re menor, muy bajo
    if tiene("02_antenas"):
        t0 = S["02_antenas"]
        t1 = S["07_duende"] if tiene("07_duende") else T
        g = n0.bandoneon_granular([note("D3"), note("F3"), note("A3")], t1 - t0 + 1.0, density=28, seed=3)
        g *= dsp.adsr(len(g), 2.5, 0.5, 0.8, 1.0)
        place(musica, stereo(g * 0.28), t0)

    # --- 05: el ritmo de la tormenta se vuelve musica: una nota por chasquido
    if tiene("05_escucha"):
        frase = ["A4", "D5", "F5", "E5", "D5", "A4", "D5"]
        for i, f in enumerate(C["05_escucha"]["tormenta"]["rayos"]):
            nm = frase[i % len(frase)]
            place(musica, stereo(nodo.bandoneon(note(nm), 0.9, attack=0.03, release=0.5) * 0.3, 0.1),
                  at("05_escucha", f) + 0.02)
        # las lentes se apagan
        place(fx, stereo(n0.servo(0.3, 1200, 500, seed=5) * 0.08), at("05_escucha", 10))

    # --- giros de Nyx y Vesper (servos), lentes, alas
    def giros(shot, quien, f_list, alto=900):
        for f in f_list:
            place(fx, stereo(n0.servo(0.22, alto, alto * 1.6, seed=f) * 0.12, -0.1 if quien == "nyx" else 0.3),
                  at(shot, f))
    if tiene("01_lente"):
        place(fx, stereo(nodo.bell(note("A6"), 1.6) * 0.05, 0.1), at("01_lente", 4))       # el destello
        place(fx, stereo(n0.servo(0.4, 600, 1400, seed=1) * 0.07), at("01_lente", 7))      # la lente se abre
    if tiene("02_antenas"):
        giros("02_antenas", "nyx", [10])
        place(fx, stereo(n0.servo(0.7, 300, 700, seed=2) * 0.1, -0.1), at("02_antenas", 14))
        for f in (8, 22, 35, 49):                                                          # la llama cuenta
            place(fx, stereo(n0.click(500, 0.08) * 0.05, 0.35), at("02_antenas", f))
    if tiene("03_tarde"):
        giros("03_tarde", "nyx", [36])
    if tiene("04_registro"):
        giros("04_registro", "nyx", [11])
        giros("04_registro", "vesper", [16], alto=600)
        r = C["04_registro"]["registro"]
        f0 = r.get("desde", 20)
        place(fx, stereo(nodo.bell(note("E6"), 1.4) * 0.07, 0.2), at("04_registro", f0))
        f = f0 + 3
        for g_ in r.get("golpes", []):
            place(fx, stereo(n0.tecla(1500) * 0.16, 0.1), at("04_registro", f))
            if g_ in r.get("duendes", []):
                place(fx, stereo(n0.bip(1760, 0.1) * 0.1, 0.2), at("04_registro", f + 3))
            f += 2
    if tiene("06_antes"):
        giros("06_antes", "nyx", [8], alto=1100)
        place(fx, stereo(n0.bip(990, 0.12) * 0.1), at("06_antes", 9))                      # lentes on
    if tiene("08_pausa"):
        # el 08 va a 24 fps (sigue la toma del 07): los cuadros son de 24
        place(fx, stereo(n0.servo(2.4, 500, 300, seed=8) * 0.06, -0.1), at("08_pausa", 24))   # baja las alas
        giros("08_pausa", "vesper", [56], alto=600)
        acorde = [note("D3"), note("F#3"), note("A3"), note("D4")]
        g = sum(nodo.bandoneon(fq, 6.5, attack=1.6, release=2.0) for fq in acorde) / 4
        place(musica, stereo(g * 0.3), at("08_pausa", 30))                                # resuelve a Re mayor
    if tiene("09_mapa"):
        m = C["09_mapa"]["mapa"]
        place(fx, stereo(nodo.riser(0.6) * 0.15, 0.2), at("09_mapa", m["aparece"][0]) - 0.3)
        for pe in m.get("puntos", []):
            place(fx, stereo(nodo.bell(note("D6"), 4.0) * 0.18, 0.15), at("09_mapa", pe.get("desde", 1)))
            place(fx, stereo(nodo.bell(note("A6"), 3.0) * 0.08, 0.25), at("09_mapa", pe.get("desde", 1)) + 0.35)
        place(fx, stereo(n0.pasada(1.8, 600, 2400, seed=9) * 0.2, 0.4), at("09_mapa", 56))     # Vesper sigue viaje
        giros("09_mapa", "nyx", [66])
        place(fx, stereo(n0.servo(0.35, 1400, 600, seed=10) * 0.07), at("09_mapa", 87))   # la lente se cierra
        mel = [("A4", 0.6), ("D5", 0.6), ("F#5", 0.9), ("E5", 0.6), ("D5", 1.6)]
        tm = at("09_mapa", 24)
        for nm, d in mel:
            place(musica, stereo(nodo.bandoneon(note(nm), d * 1.4, attack=0.08, release=0.5) * 0.28, 0.1), tm)
            tm += d

    if tiene("07_duende"):
        c = C["07_duende"]
        d = c["tormenta"].get("dispara", 1)
        place(radio, stereo(sferic(1.0) * 0.9), at("07_duende", d))
        place(radio, stereo(tweek(0.14) * 0.35, 0.2), at("07_duende", d) + 0.01)
        i0, i1 = c["post"]["impacto"]["frames"]
        place(radio, stereo(golpe_impacto() * 0.85), at("07_duende", i0))
        t_lento = at("07_duende", i1 + 1)
        place(radio, stereo(whistler(5.0, seed=1) * 0.3, -0.15), t_lento + 0.3)
        g = n0.bandoneon_granular([note("D3"), note("A3"), note("F4")], fin("07_hombro") - t_lento + 1.0
                                  if tiene("07_hombro") else 6.0, density=35, seed=7)
        g *= dsp.adsr(len(g), 2.0, 0.5, 0.85, 1.5)
        place(musica, stereo(g * 0.35), t_lento)
    if tiene("07_lentes"):
        place(radio, stereo(n0.servo(0.5, 1500, 2200, seed=3) * 0.05, 0.1), at("07_lentes", 1))
    if tiene("07_hombro"):
        place(radio, stereo(whistler(4.0, f_alta=6000, f_baja=1100, seed=2) * 0.22, 0.25), at("07_hombro", 10))
        for f in (40, 70):
            place(radio, stereo(tweek(0.1, seed=f) * 0.12, -0.3), at("07_hombro", f))
    radio = radio + fx

    # silencios: antes del 07 la tormenta toma aire (la radio y la musica bajan
    # en el final del 06); el hit-stop calla todo; el duende que se apaga corta
    # en seco y la noche vuelve de a poco
    pts = [(0, 1.0)]
    if tiene("06_antes"):
        pts += [(at("06_antes", 14), 1.0), (fin("06_antes") - 0.01, 0.35)]
    if tiene("07_duende"):
        a, b = at("07_duende", 2), at("07_duende", 4)
        pts += [(a - 0.002, 1.0), (a, 0.0), (b, 0.0), (b + 0.002, 0.25)]
    if tiene("07_hombro"):
        br = C["07_hombro"]["duende"].get("brillo", [])
        apaga = next((f for f, v in br if v == 0.0), None)
        if apaga:
            ta = at("07_hombro", apaga)
            pts += [(ta - 0.002, 0.25), (ta, 0.0), (ta + 0.9, 0.0), (ta + 3.5, 1.0)]
    pts.append((Ttot, 1.0))
    pts.sort()
    m_noche = nodo.envelope(Ttot, pts)
    corte = nodo.envelope(Ttot, [(p[0], 1.0 if p[1] > 0 else 0.0) for p in pts])

    # el final del 06: la tormenta toma aire antes del chasquido del 07
    duck = np.ones((n_samples(Ttot), 1))
    if tiene("06_antes"):
        duck = nodo.envelope(Ttot, [(0, 1.0), (at("06_antes", 14), 1.0), (fin("06_antes") - 0.01, 0.25),
                                    (fin("06_antes"), 1.0), (Ttot, 1.0)])
    mix = dsp.reverb(noche, hall, 0.2) * m_noche + \
        (dsp.reverb(radio, hall, 0.25) + dsp.reverb(musica, hall, 0.4)) * corte * duck
    nT = n_samples(T)
    out = mix[:nT].copy()
    tail = mix[nT:]
    out[:len(tail)] += tail
    # los silencios se aplican otra vez despues de doblar la cola del loop:
    # si no, la cola se mete en el hit-stop cuando cae al principio
    out *= corte[:nT]
    out = dsp.soft_clip(out * 1.1, 1.2)
    out = dsp.normalize(out, -1.0)
    dst = ROOT / "out" / f"{TL['name']}.wav"
    dst.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(dst, SR, (out * 32767).astype(np.int16))
    print(f"-> {dst}  ({len(out) / SR:.2f} s)")
    rms = lambda a, b: 20 * np.log10(np.sqrt(np.mean(out[n_samples(a):n_samples(b)] ** 2)) + 1e-9)  # noqa: E731
    for s in S:
        print(f"  {s:12s} {rms(S[s], fin(s)):6.1f} dB")
    if tiene("07_duende"):
        a, b = at("07_duende", 2), at("07_duende", 4)
        sil = out[n_samples(a) + 10:n_samples(b) - 10]
        print(f"  hit-stop          pico {np.abs(sil).max():.5f}")
    print(f"  final del loop    {rms(T - 1.0, T):6.1f} dB | arranque {rms(0, 1.0):6.1f} dB")


if __name__ == "__main__":
    main()
