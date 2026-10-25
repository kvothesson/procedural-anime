"""
banda.py - Banda de sonido de LA BANDERA. Sintesis pura: ni un sample.

    python episodios/mariposa_bandera/banda.py   # -> out/mariposa_bandera.wav (48 kHz, estereo)

La luz de la mariposa suena como vidrio: una caja de musica de cristal.
  - 01: lluvia; la crisalida late (golpe grave doble) y la raja sube como un
    crujido de vidrio que acelera y se afina; estalla con el impacto blanco.
  - 02: la membrana humeda cruje; mientras la luz inunda las alas sube un
    arpegio de cristal (una nota por escalon de la onda); al abrirlas, el acorde.
    Cada bajada del ala es un soplo.
  - 03: la ciudad: rumor grave, una bocina de barco lejos. El motivo suena una
    vez, lejos, con mucha reverb; el aleteo se pierde con la distancia.
  - 04: viento en ramas secas, ranas de la Reserva. El motivo se desafina a
    medida que ella pierde luz. Toque "nada": un golpecito de vidrio y nada.
    "Parpadeo": golpecito, medio latido y un zumbido que se muere.
  - 05: se posa, abre las alas y vuelca su luz: un colchon que se abre y una
    campanita por cada crisalida que despierta (en el orden y el cuadro en que
    despierta). Cuando queda gris: silencio total, hasta la lluvia.
  - 06: revientan: un estallido de vidrio por crisalida, el acorde del enjambre
    (alivio) y el motivo entero, armonizado; un murmullo de alas.
  - 06b: el acorde se apaga en menor (agridulce); una ultima nota.
  - 07: llega una nueva, toca la crisalida: el mismo latido del plano 1. Se va.
    Queda la lluvia: empalma con el principio.

Eventos anclados a (plano, frame) del timeline: si un plano cambia de duracion,
todo se reacomoda. Los aleteos salen de las claves "aleteo" de cada plano y el
despertar de las crisalidas del mismo arbol que usa la pieza (planos.py).
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
from dsp import SR, n_samples, note, place, stereo, time_axis  # noqa: E402
from plano import load_shot  # noqa: E402

_spec = importlib.util.spec_from_file_location("planos_ep", ROOT / "planos.py")
PL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PL)

np.random.seed(2087)
FPS = 24
TL = json.loads((ROOT / "shots" / "timeline.json").read_text(encoding="utf-8"))
SHOTS = {s: load_shot(ROOT / "shots" / f"{s}.json") for s in TL["shots"]}
S, T = {}, 0.0
for s in TL["shots"]:
    S[s] = T
    T += SHOTS[s]["frames"] / FPS
COLA = 6.0          # cola que se renderiza y se suma al principio (loop)
N = n_samples(T + COLA)


def at(shot, frame=1):
    return S[shot] + (frame - 1) / FPS


def bus():
    return np.zeros(N)


def envelope(points):
    t = np.arange(N) / SR
    xs, ys = zip(*points)
    return np.interp(t, xs, ys)


def tramo(keys, f):
    """Como _tramo de piezas.py: claves [[frame, valores...]] con suavizado."""
    if f <= keys[0][0]:
        return keys[0][1:]
    for k0, k1 in zip(keys, keys[1:]):
        if k0[0] <= f <= k1[0]:
            s = (f - k0[0]) / max(1e-6, k1[0] - k0[0])
            s = s * s * (3 - 2 * s)
            return [a + (b - a) * s for a, b in zip(k0[1:], k1[1:])]
    return keys[-1][1:]


# ------------------------------------------------------------------ instrumentos
def vidrio(f, dur=2.4, decay=1.4, bright=0.85):
    """Una nota de la caja de musica de cristal (parciales un poco inarmonicos)."""
    return dsp.struck(f, dur, decay=decay, bright=bright, inharmonicity=0.0025, partials=9)


def latido(fuerza=1.0):
    """Golpe grave doble (lub-dub) con un brillo de vidrio encima."""
    out = np.zeros(n_samples(0.9))
    for t0, g in ((0.0, 1.0), (0.22, 0.6)):
        n = n_samples(0.35)
        t = time_axis(n)
        f = 62 * np.exp(-t / 0.25)
        golpe = np.sin(2 * np.pi * np.cumsum(f) / SR) * dsp.exp_decay(n, 0.09)
        place(out, golpe * g, t0)
    place(out, vidrio(note("B5"), 0.6, decay=0.3, bright=0.6) * 0.08, 0.0)
    return out * 0.6 * fuerza


def crujido(dur, seed=5):
    """La raja que sube: chasquidos de vidrio cada vez mas seguidos y agudos,
    sobre un ruido que se abre."""
    rng = np.random.default_rng(seed)
    out = np.zeros(n_samples(dur + 0.3))
    t = 0.0
    while t < dur:
        x = t / dur
        f = 2400 + 3600 * x + rng.uniform(-300, 300)
        n = n_samples(0.03)
        tt = time_axis(n)
        place(out, np.sin(2 * np.pi * f * tt) * dsp.exp_decay(n, 0.006) * (0.15 + 0.25 * x), t)
        t += 0.12 * (1 - x) ** 1.5 + 0.012
    n = n_samples(dur)
    ruido = dsp.highpass(rng.standard_normal(n), 2500) * np.linspace(0, 1, n) ** 2 * 0.05
    place(out, ruido, 0.0)
    return out


def estallido(seed=9):
    """El impacto: golpe de ruido brillante y un acorde de cristal que queda."""
    rng = np.random.default_rng(seed)
    n = n_samples(1.6)
    golpe = dsp.highpass(rng.standard_normal(n), 1800) * dsp.exp_decay(n, 0.18) * 0.28
    acorde = sum(vidrio(note(nm), 1.6, decay=1.0) for nm in ("E5", "B5", "G#6")) * 0.18
    sub = np.sin(2 * np.pi * 45 * time_axis(n)) * dsp.exp_decay(n, 0.25) * 0.35
    return golpe + acorde + sub


def aspira(dur, seed=10):
    """Ruido que crece hasta el golpe (el aire que se junta antes de estallar)."""
    rng = np.random.default_rng(seed)
    n = n_samples(dur)
    x = dsp.bandpass(rng.standard_normal(n), 800, 7000)
    return x * np.linspace(0, 1, n) ** 3 * 0.35


def soplo(fuerza=1.0, seed=0):
    """Una bajada del ala: soplo corto de ruido filtrado."""
    rng = np.random.default_rng(seed)
    n = n_samples(0.22)
    x = dsp.bandpass(rng.standard_normal(n), 250, 1400)
    return x * np.sin(np.linspace(0, np.pi, n)) ** 2 * 0.22 * fuerza


def membrana(dur, seed=12):
    """El ala humeda que se estira: crujiditos finos de papel mojado."""
    rng = np.random.default_rng(seed)
    out = np.zeros(n_samples(dur))
    t = 0.0
    while t < dur - 0.05:
        n = n_samples(0.012)
        place(out, dsp.bandpass(rng.standard_normal(n), 1500, 6000) * np.hanning(n) * rng.uniform(0.02, 0.07), t)
        t += rng.uniform(0.01, 0.07)
    return out


def lluvia(dur, seed=21):
    rng = np.random.default_rng(seed)
    n = n_samples(dur)
    capa = dsp.bandpass(rng.standard_normal(n), 900, 9000) * 0.06
    gotas = np.zeros(n)
    for _ in range(int(dur * 40)):
        m = n_samples(0.01)
        place(gotas, dsp.highpass(rng.standard_normal(m), 3000) * np.hanning(m) * rng.uniform(0.02, 0.08),
              rng.uniform(0, dur - 0.02))
    return capa + gotas


def ciudad(dur, seed=4):
    """Rumor de ciudad lejos: grave, con un latido de trafico."""
    rng = np.random.default_rng(seed)
    n = n_samples(dur)
    t = time_axis(n)
    return dsp.lowpass(rng.standard_normal(n), 180) * (0.9 + 0.1 * np.sin(2 * np.pi * 0.17 * t)) * 0.5


def bocina(dur=2.6):
    """Bocina de barco en el puerto, lejos."""
    n = n_samples(dur)
    s = dsp.bl_saw(73.4, n, 0.0) + 0.7 * dsp.bl_saw(110.0, n, 0.003)
    return dsp.lowpass(s, 500) * dsp.adsr(n, 0.25, 0.3, 0.8, 0.9) * 0.18


def viento_ramas(dur, seed=8):
    rng = np.random.default_rng(seed)
    n = n_samples(dur)
    t = time_axis(n)
    w = dsp.bandpass(rng.standard_normal(n), 300, 1600) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.13 * t)) * 0.07
    roce = np.zeros(n)
    k = 0.3
    while k < dur - 0.1:
        m = n_samples(0.05)
        place(roce, dsp.bandpass(rng.standard_normal(m), 600, 2500) * np.hanning(m) * 0.05, k)
        k += rng.uniform(0.4, 1.6)
    return w + roce


def ranas(dur, seed=14):
    """Ranas de la Reserva: croar corto, pocas y lejos."""
    rng = np.random.default_rng(seed)
    out = np.zeros(n_samples(dur))
    t = 0.5
    while t < dur - 0.3:
        n = n_samples(0.16)
        tt = time_axis(n)
        f = rng.uniform(380, 520)
        c = np.sign(np.sin(2 * np.pi * f * tt)) * (np.sin(2 * np.pi * 28 * tt) > 0) * np.hanning(n)
        place(out, dsp.bandpass(c, 300, 2000) * 0.03, t)
        t += rng.uniform(0.7, 2.2)
    return out


MOTIVO = ["B4", "E5", "F#5", "G#5", "B5", "G#5", "F#5", "E5"]


def motivo(paso=0.32, desafina=0.0, armonia=False, gain=1.0):
    """El motivo de la caja de musica. desafina: cuanto se corre cada nota
    (la luz que se va); armonia: una tercera abajo (el enjambre)."""
    out = np.zeros(n_samples(paso * len(MOTIVO) + 3))
    rng = np.random.default_rng(31)
    for i, nm in enumerate(MOTIVO):
        f = note(nm) * 2 ** (desafina * rng.uniform(-1, 1) * (0.5 + i / len(MOTIVO)) / 12)
        place(out, vidrio(f) * 0.12 * gain, i * paso)
        if armonia:
            place(out, vidrio(f * 2 ** (-4 / 12)) * 0.08 * gain, i * paso + 0.01)
    return out


def colchon(notas, dur, cutoff=1600, attack=1.2, release=2.0):
    return sum(dsp.pad(note(nm), dur, voices=5, spread=0.005, cutoff=cutoff, attack=attack, release=release)
               for nm in notas) / len(notas)


def golpecito():
    return vidrio(note("E6"), 0.5, decay=0.15, bright=0.7) * 0.07


def zumbido_muere(dur=0.9):
    n = n_samples(dur)
    t = time_axis(n)
    z = np.sin(2 * np.pi * 220 * t) * (0.6 + 0.4 * (np.sin(2 * np.pi * 23 * t) > 0))
    return dsp.lowpass(z, 1200) * np.exp(-t / 0.3) * 0.08


# ------------------------------------------------------------------ eventos calculados
def aleteos(shot, fuerza_por_frame=None):
    """Un soplo por cada bajada del ala, de las claves "aleteo" del plano
    (la misma fase que integra piezas.py)."""
    A = SHOTS[shot].get("mariposa")
    if not isinstance(A, dict):
        return []
    keys = A.get("aleteo", [[1, 12, 60, 22]])
    p = A.get("fase0", 0.0)
    out = []
    for f in range(1, SHOTS[shot]["frames"] + 1):
        ciclo, amp, _ = tramo(keys, f)
        if f > 1:
            q = p + 1.0 / max(1.0, ciclo)
            if int(q) > int(p) and amp > 8:
                k = amp / 60.0 * (fuerza_por_frame(f) if fuerza_por_frame else 1.0)
                out.append((at(shot, f), k))
            p = q
    return out


def despertar():
    """Cuadros (del plano 5) en que despierta y revienta cada crisalida: la
    misma cuenta que build_reserva (sin el azar de unos cuadros)."""
    pose = PL.rama_para_posarse()[0]
    D = SHOTS["05_entrega"]["reserva"]["despierta"]
    ev = []
    for c in PL.COLG:
        d = sum((a - b) ** 2 for a, b in zip(c["at"], pose)) ** 0.5
        w = D["frame"] + d / D["vel"]
        ev.append((w, w + D["revienta"], c["at"]))
    return sorted(ev)


# ------------------------------------------------------------------ mezcla
def main():
    hall = dsp.make_ir(dur=5.0, decay=2.6, damping=5200, predelay=0.03)
    lejos = dsp.make_ir(dur=6.0, decay=3.5, damping=2600, predelay=0.08)

    # ambiente: lluvia todo el tiempo (sale de la cola y empalma), ciudad en el
    # puerto, ramas y ranas en la Reserva
    amb = stereo(lluvia(T + COLA), 0.0) * 0.9
    ciu = bus()
    place(ciu, ciudad(at("04_reserva") - at("03_puerto")), at("03_puerto"))
    place(ciu, bocina(), at("03_puerto", 30))
    amb += dsp.reverb(stereo(ciu, 0.0), lejos, 0.35) * envelope(
        [(0, 0), (at("03_puerto"), 0), (at("03_puerto") + 0.3, 1), (at("04_reserva") - 0.4, 1), (at("04_reserva"), 0), (T + COLA, 0)])[:, None]
    res = bus()
    place(res, viento_ramas(T - at("04_reserva")), at("04_reserva"))
    place(res, ranas(at("05_entrega") - at("04_reserva")), at("04_reserva"))
    amb += stereo(res, 0.1)

    m = bus()       # musica y luz (va a la sala)
    fx = bus()      # golpes cercanos (secos)

    # 01: latidos de la crisalida, la raja y el estallido
    C1 = SHOTS["01_crisalida"]["crisalida"]
    lat = C1["latido"]
    g0 = C1["grieta"][1][0]
    imp = SHOTS["01_crisalida"]["post"]["impacto"]["frames"][0]
    for (f0, v0), (f1, v1) in zip(lat, lat[1:]):
        # despues de que empieza la raja manda el crujido: un latido encima del
        # estallido se oye como un tropiezo
        if v1 >= 0.8 and v0 < 0.5 and f1 < g0:
            place(fx, latido(v1), at("01_crisalida", f1 - 1))
    # la raja crepita hasta el cuadro del impacto (si termina antes queda un
    # hueco que se oye como un corte) y un soplo que crece entra en el golpe
    place(fx, crujido((imp - g0) / FPS), at("01_crisalida", g0))
    place(m, aspira(0.6), at("01_crisalida", imp) - 0.6)
    place(m, estallido(), at("01_crisalida", imp))

    # 02: membrana, arpegio que sube con la luz, acorde al abrir
    A2 = SHOTS["02_despliegue"]["mariposa"]
    dk = A2["despliegue"]
    place(fx, membrana((dk[-1][0] - 1) / FPS) * 1.2, at("02_despliegue"))
    escala = ["E4", "G#4", "B4", "E5", "F#5", "G#5", "B5", "E6"]
    hecho = 0
    for f in range(1, SHOTS["02_despliegue"]["frames"] + 1):
        d = tramo(dk, f)[0]
        while hecho < len(escala) and d >= (hecho + 1) / (len(escala) + 0.5):
            place(m, vidrio(note(escala[hecho])) * 0.11, at("02_despliegue", f))
            hecho += 1
    t_abre = at("02_despliegue", 52)
    place(m, colchon(["E3", "B3", "E4", "G#4"], 3.5, attack=0.4) * 0.35, t_abre)
    for nm in ("E5", "G#5", "B5", "E6"):
        place(m, vidrio(note(nm)) * 0.08, t_abre)

    # 03: el motivo una vez, lejos; el aleteo se pierde con la distancia
    place(m, motivo(paso=0.42, gain=0.7), at("03_puerto", 26))
    lejania = lambda f: float(np.interp(f, [1, 44, 90, 132], [1.0, 0.45, 0.1, 0.02]))

    # 04: el motivo desafinado a medida que pierde luz; los toques
    place(m, motivo(paso=0.4, desafina=0.15, gain=0.6), at("04_reserva", 8))
    place(m, motivo(paso=0.46, desafina=0.6, gain=0.5), at("04_reserva", 120))
    for i, f, modo in SHOTS["04_reserva"]["reserva"]["intentos"]:
        place(fx, golpecito(), at("04_reserva", f))
        if modo == "parpadeo":
            place(fx, latido(0.35), at("04_reserva", f + 2))
            place(fx, zumbido_muere(), at("04_reserva", f + 4))

    # 05: se abre un colchon mientras vuelca la luz; una campanita por
    # crisalida que despierta; despues, silencio
    D5 = SHOTS["05_entrega"]["reserva"]["despierta"]
    place(m, colchon(["E3", "B3", "F#4", "G#4", "C#5"], (110 - D5["frame"]) / FPS + 1.5, cutoff=2400, attack=2.0, release=0.6) * 0.75,
          at("05_entrega", D5["frame"]))
    ev = despertar()
    pent = ["E5", "F#5", "G#5", "B5", "C#6", "E6"]
    zs = [e[2][2] for e in ev]
    z0, z1 = min(zs), max(zs)
    for w, b, p in ev:
        k = int((p[2] - z0) / max(1e-6, z1 - z0) * (len(pent) - 1))
        if w <= 144:
            place(m, vidrio(note(pent[k]), 1.6, decay=0.9) * 0.09, at("05_entrega", w))
    b_min = min(b for _, b, _ in ev)
    sil0 = at("05_entrega", 104)
    sil1 = at("05_entrega", int(b_min) - 2) if b_min <= 144 else at("06_enjambre", int(b_min - 144) - 2)
    sil1 = max(sil1, sil0 + 0.5)

    # 06: un estallido de vidrio por crisalida que revienta, el acorde del
    # enjambre, el motivo armonizado y un murmullo de alas
    t_alivio = sil1 + 2 / FPS
    for w, b, p in ev:
        t = at("05_entrega", 1) + (b - 1) / FPS
        if t >= t_alivio - 0.01 and t < at("06b_gris"):
            place(fx, vidrio(note("B6"), 0.6, decay=0.2, bright=0.9) * 0.05 + 0.0, t)
    place(m, colchon(["E3", "B3", "E4", "G#4", "B4", "E5"], at("06b_gris") - t_alivio + 1.5, cutoff=3000, attack=0.8, release=1.8) * 1.0,
          t_alivio)
    place(m, motivo(paso=0.34, armonia=True, gain=1.8), t_alivio + 0.6)
    place(m, motivo(paso=0.34, armonia=True, gain=1.5), t_alivio + 0.6 + 0.34 * 8)
    rng = np.random.default_rng(44)
    t = t_alivio
    while t < at("06b_gris") + 0.5:
        place(fx, soplo(rng.uniform(0.15, 0.4), seed=int(t * 100)), t)
        t += rng.uniform(0.03, 0.09)

    # 06b: se apaga en menor; una ultima nota
    place(m, colchon(["A3", "C4", "E4"], at("07_loop") - at("06b_gris") + 1.0, cutoff=1200, attack=0.6, release=1.2) * 0.3,
          at("06b_gris"))
    place(m, vidrio(note("E5"), 3.0, decay=2.0) * 0.1, at("06b_gris", 22))

    # 07: llega, toca, el mismo latido del plano 1; se va
    for f0, v0 in SHOTS["07_loop"]["crisalida"]["latido"]:
        if v0 >= 0.7:
            place(fx, latido(0.8), at("07_loop", f0 - 2))
    place(fx, golpecito(), at("07_loop", 50))

    # aleteos de todos los planos con mariposa
    for shot in ("02_despliegue", "03_puerto", "04_reserva", "05_entrega", "07_loop"):
        fz = lejania if shot == "03_puerto" else None
        for t, k in aleteos(shot, fz):
            place(fx, soplo(k, seed=int(t * 1000)), t)

    # mezcla: la musica en la sala; el silencio corta todo (lluvia y colas incluidas)
    mus = dsp.reverb(stereo(m, 0.0), hall, 0.38)
    gol = dsp.reverb(stereo(fx, 0.05), hall, 0.12)
    # cuando ella queda gris se apaga todo menos la lluvia (que baja): un
    # silencio total, lluvia incluida, se oia como un corte de sonido
    mascara = envelope([(0, 1), (sil0 - 0.08, 1), (sil0, 0), (sil1, 0), (sil1 + 0.01, 1), (T + COLA, 1)])
    lluvia_m = envelope([(0, 1), (sil0 - 0.08, 1), (sil0, 0.35), (sil1, 0.35), (sil1 + 0.3, 1), (T + COLA, 1)])
    mix = 0.8 * amb * lluvia_m[:, None] + (1.0 * mus + 0.9 * gol) * mascara[:, None]
    # loop: la cola despues del final se suma al principio
    cola = mix[n_samples(T):].copy()
    mix = mix[:n_samples(T)]
    mix[:len(cola)] += cola[:n_samples(T)]
    st = dsp.normalize(dsp.soft_clip(mix * 1.1, 1.2), -1.0)
    dst = ROOT / "out" / f"{TL['name']}.wav"
    dst.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(dst, SR, (st * 32767).astype(np.int16))
    out = st.mean(axis=1)
    print(f"-> {dst}  ({len(out) / SR:.2f} s, timeline {T:.2f} s)")

    def rms(a, b):
        x = out[n_samples(a):n_samples(b)]
        return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)
    for s in S:
        fin = S[s] + SHOTS[s]["frames"] / FPS
        print(f"  {s:14s} {rms(S[s], fin):6.1f} dB")
    print(f"  silencio {sil0:.2f}-{sil1:.2f} s (solo lluvia): {rms(sil0, sil1):6.1f} dB")
    print(f"  empalme del loop: ultimos 0,2 s {rms(T - 0.2, T):6.1f} dB | primeros 0,2 s {rms(0, 0.2):6.1f} dB")


if __name__ == "__main__":
    main()
