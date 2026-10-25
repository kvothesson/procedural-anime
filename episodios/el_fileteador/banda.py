"""banda.py - Banda de sonido de EL FILETEADOR. Sintesis pura: ni un sample.

    python episodios/el_fileteador/banda.py   # -> out/el_fileteador.wav (48 kHz, estereo)

Milonga-synth en La menor: contrabajo pulsado en 3-3-2, guitarra que marca el
acorde y el bandoneon (de nodo_404/banda.py) que es la voz del fileteador.

Lo que manda la imagen:
  - Cada pincelada del 03 suena cuando el pincel la pinta: los horarios salen
    de filete.motivo (el mismo que arma la geometria), no de una lista a mano.
    Contorno: una frase del bandoneon; muescas: staccato; rellenos: el
    acorde que se abre; brillos y bolitas: campanitas; firulete: glissando.
  - El barrido cian es ruido filtrado que se come la musica (se cierra el
    filtro y se rompe en bloques) mientras la linea cruza la chapa (01) y un
    zumbido que se acerca por la calle (02, 04).
  - 05: una nota por fachada que recupera el color (cuando la punta de la
    banda pasa por cada lote, de calle.lotes), en escala que sube; golpe
    cuando la banda alcanza a la cortina y la apaga.
  - Silencio de un cuadro antes de la firma (06); la firma son cinco
    toquecitos agudos; el acorde final cae sobre el barrido del 01 (loop).

El compas: 35 s = 28 compases de 2/4 de 1,25 s (96 negras por minuto), asi el
loop cierra en el tiempo fuerte. Semilla fija.
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

import calle  # noqa: E402
import filete  # noqa: E402

np.random.seed(1959)          # el anio en que se nombro Caminito
TAIL = 6.0


def _nodo404():
    """Instrumentos de nodo_404/banda.py: bandoneon, campana, pads, ruidos."""
    spec = importlib.util.spec_from_file_location("banda_nodo404", ROOT.parent / "nodo_404" / "banda.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


N4 = _nodo404()
bandoneon, bell, chord_pad = N4.bandoneon, N4.bell, N4.chord_pad
glitch_burst, riser, envelope = N4.glitch_burst, N4.riser, N4.envelope
sweep_band, sweep_lowpass = N4.sweep_band, N4.sweep_lowpass


# ------------------------------------------------------------------ tiempos

TL = json.loads((ROOT / "shots" / "timeline.json").read_text(encoding="utf-8"))
CFG = {s: load_shot(ROOT / "shots" / f"{s}.json") for s in TL["shots"]}
S, t = {}, 0.0
for s in TL["shots"]:
    S[s] = t
    t += CFG[s]["frames"] / TL["fps_unique"]
T = t
BAR = T / 28.0


def at(shot, frame=1):
    return S[shot] + (frame - 1) / TL["fps_unique"]


# ------------------------------------------------------------------ instrumentos

def bajo(freq, dur=0.9):
    """Contrabajo pulsado: cuerda grave golpeada, corta."""
    return dsp.lowpass(dsp.struck(freq, dur, decay=0.45, bright=0.55, partials=8), 900)


def rasgueo(notes, dur=0.35, bright=0.7):
    """Guitarra: el acorde rasgueado (notas apenas corridas)."""
    out = np.zeros(n_samples(dur + 0.05))
    for k, nm in enumerate(notes):
        x = dsp.struck(note(nm), dur, decay=0.35, bright=bright, partials=10)
        i = n_samples(0.012 * k)
        out[i:i + len(x)] += x[:len(out) - i]
    return out / len(notes)


def staccato(freq, g=1.0):
    return bandoneon(freq, 0.24, attack=0.02, release=0.12) * g


def respiro(dur, lo=500, hi=2500):
    """El fuelle que toma aire: ruido de banda que crece."""
    n = n_samples(dur)
    u = time_axis(n) / dur
    return dsp.bandpass(np.random.uniform(-1, 1, n), lo, hi) * u ** 1.5 * (1 - u) ** 0.3


def zumbido(dur):
    """El barrido a lo lejos: ruido grave con un tono digital que late."""
    n = n_samples(dur)
    tt = time_axis(n)
    base = dsp.bandpass(np.random.uniform(-1, 1, n), 60, 420)
    tono = np.sin(2 * np.pi * 110 * tt) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 6 * tt)))
    return 0.8 * base / max(np.abs(base).max(), 1e-9) + 0.12 * tono


def barrido_cerca(dur):
    """El barrido que cruza la chapa: siseo que baja de agudo a grave."""
    x = np.random.uniform(-1, 1, n_samples(dur))
    return sweep_band(x, lambda u: 7000 * (1 - u) ** 2 + 400, q=0.9)


# ------------------------------------------------------------------ armonia

ACORDES = {"Am": ["A2", "C4", "E4", "A4"], "E7": ["E2", "B3", "D4", "G#4"],
           "Dm": ["D2", "D4", "F4", "A4"], "F": ["F2", "C4", "F4", "A4"]}
BAJO = {"Am": ("A1", "E2", "G#1"), "E7": ("E1", "B1", "D#2"), "Dm": ("D2", "A1", "C#2"),
        "F": ("F1", "C2", "E2")}
GRILLA = ["Am", "Am", "E7", "E7", "Am", "Am", "Dm", "E7"]
ESCALA = ["A3", "B3", "C4", "D4", "E4", "F4", "G#4", "A4", "B4", "C5", "D5", "E5", "F5", "G#5", "A5",
          "B5", "C6", "D6", "E6"]


def milonga(bus, t0, t1, g_bajo=1.0, g_guit=1.0):
    """3-3-2 sobre la grilla global de compases, entre t0 y t1."""
    k0 = int(np.ceil(t0 / BAR - 1e-6))
    k1 = int(np.floor(t1 / BAR))
    sem = BAR / 8
    for k in range(k0, k1):
        ac = GRILLA[k % len(GRILLA)]
        tb = k * BAR
        r, q, ap = BAJO[ac]
        for off, nm, g in ((0, r, 1.0), (3, q, 0.8), (6, ap, 0.6)):
            place(bus, stereo(bajo(note(nm)) * 0.9 * g * g_bajo, -0.1), tb + off * sem)
        for off, g in ((0, 0.7), (3, 0.5), (6, 0.45)):
            place(bus, stereo(rasgueo(ACORDES[ac]) * g * g_guit, 0.35), tb + off * sem + 0.01)


# ------------------------------------------------------------------ partitura

def musica(Ttot):
    bus = np.zeros((n_samples(Ttot), 2))
    # 02-03: la milonga entra en la calle, contenida
    milonga(bus, at("02_calle"), at("04_duda"), 0.75, 0.6)
    # 04: se corta; queda un acorde suspendido del bandoneon (la duda)
    t4 = at("04_duda")
    for nm in ("E3", "A3", "B3"):
        place(bus, stereo(bandoneon(note(nm), 3.6, attack=0.4, release=1.2) * 0.22, -0.2), t4 + 0.05)
    # 05: vuelve entera cuando la banda toca la pared
    t5 = at("05_banda", 8)
    milonga(bus, t5, at("06_firma"), 1.0, 0.9)
    place(bus, stereo(chord_pad(["A2", "E3", "A3", "C4", "E4"], 3.0, attack=0.05, release=2.0) * 0.8), t5)
    for nm in ("A2", "E3", "A3", "C4"):
        place(bus, stereo(bandoneon(note(nm), 2.0, attack=0.04, release=1.0) * 0.25, 0.1), t5)
    # 06: la milonga sigue, mas baja, y cierra en La menor sobre el loop
    t6 = at("06_firma")
    milonga(bus, t6, at("06_firma", 40), 0.6, 0.5)
    cierre = at("06_firma", 40)
    for nm in ("A2", "E3", "A3", "C4", "E4"):
        place(bus, stereo(bandoneon(note(nm), 4.0, attack=0.3, release=3.0) * 0.2, 0.15), cierre)
    place(bus, stereo(chord_pad(["A2", "E3", "A3", "C4", "E4", "B4"], 6.0, attack=0.6, release=4.0) * 0.9),
          cierre)
    return bus


def pinceladas(bus):
    """03: cada pieza del filete suena cuando el pincel la pinta."""
    fil = CFG["03_filete"]["filete"]
    P = filete.motivo(fil)
    frase = ["E4", "A4", "C5", "B4", "A4", "G#4", "A4", "E5", "D5", "C5", "B4", "A4"]
    brillo_k = 0
    for i, p in enumerate(P):
        f0, f1 = p["f"]
        t0, t1 = at("03_filete", f0), at("03_filete", f1)
        dur = max(0.2, t1 - t0)
        if p["capa"] == "linea" and p["col"] == "linea" and dur > 1.0:
            # el contorno: una frase de bandoneon a lo largo del trazo
            for k, nm in enumerate(frase):
                tk = t0 + dur * k / len(frase)
                place(bus, stereo(bandoneon(note(nm), dur / len(frase) * 1.3, attack=0.05, release=0.25) * 0.3,
                                  -0.15), tk)
        elif p["capa"] == "linea" and p["col"] == "linea":
            place(bus, stereo(staccato(note(("A5", "E5", "C5", "A4")[i % 4]), 0.22), 0.2), t0)
        elif p["capa"] == "fondo" and p["col"] == "verde":
            place(bus, stereo(chord_pad(["A3", "C4", "E4", "B4"], dur + 1.5, attack=dur * 0.7, release=1.2) * 0.5), t0)
        elif p["capa"] == "tono" and p["col"] == "verde_osc":
            place(bus, stereo(chord_pad(["F3", "A3", "C4"], dur + 1.2, attack=dur * 0.6, release=1.0) * 0.4), t0)
        elif p["capa"] == "brillo" and p["col"] in ("brillo", "rojo_brillo") and not p.get("bolita"):
            nm = ("E5", "A5", "B5", "C6", "E6", "A6", "E6", "C6")[brillo_k % 8]
            brillo_k += 1
            place(bus, stereo(bell(note(nm), 2.5) * 0.18, np.sin(brillo_k) * 0.6), t0)
        elif p["capa"] == "fondo" and p["col"] == "rojo":
            place(bus, stereo(bandoneon(note("A2"), dur + 0.6, attack=0.1, release=0.5) * 0.35), t0)
            place(bus, stereo(bandoneon(note("E3"), dur + 0.6, attack=0.1, release=0.5) * 0.25), t0)
        elif p["col"] == "firulete" and p["capa"] == "firulete":
            # glissando: una nota que sube mientras corre el firulete
            n = n_samples(dur)
            u = time_axis(n) / dur
            f = note("A4") * 2 ** (u * 1.0)
            x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * u) ** 0.5
            place(bus, stereo(x * 0.12, 0.3), t0)
        elif p["col"] == "rulo":
            place(bus, stereo(staccato(note("E6"), 0.18), 0.4), t0)
        elif p["capa"] == "sombra" and p["kind"] == "relleno":
            place(bus, stereo(dsp.sub(note("A1"), dur + 1.0, attack=0.4) * 0.35), t0)
        elif p.get("bolita") and p["capa"] == "bolita":
            k = sum(1 for q in P[:i] if q.get("bolita") and q["capa"] == "bolita")
            place(bus, stereo(bell(note(("A5", "C6", "E6", "A6", "C7")[k % 5]), 2.0) * 0.22, 0.5 - 0.25 * k), t0)


def cascada(bus):
    """05: una nota por fachada que recupera el color, en escala que sube."""
    cfg = CFG["05_banda"]
    B = cfg["banda_larga"]
    fr, ss = zip(*B["keys"])
    C = calle.cargar(ROOT, cfg["caminito"].get("datos", "data/entorno.json"))
    plan = calle.lotes(C, cfg["caminito"])
    lotes = sorted([lo for lo in plan if lo["lado"] == B["lado"] and B["hasta"] < lo["s1"] < B["desde"]],
                   key=lambda lo: -lo["s1"])
    # la punta baja en s: el cuadro en que pasa por el borde de cada lote
    sr, frr = np.array(ss)[::-1], np.array(fr)[::-1]
    for k, lo in enumerate(lotes):
        f = float(np.interp(lo["s1"], sr, frr))
        tk = at("05_banda", f)
        nm = ESCALA[min(k, len(ESCALA) - 1)]
        place(bus, stereo(staccato(note(nm), 0.32), -0.6 + 1.2 * (k % 5) / 4), tk)
        place(bus, stereo(bell(note(nm) * 2, 1.6) * 0.1, 0.3), tk + 0.01)
    return len(lotes)


def efectos(Ttot):
    bus = np.zeros((n_samples(Ttot), 2))
    # 01: la linea cruza la chapa (corte de la x 0,37 a -0,70 entre los cuadros 1 y 20)
    c = CFG["01_gancho"]["corte"]
    a0, a1 = at("01_gancho", c[0][0]), at("01_gancho", c[-1][0])
    place(bus, stereo(barrido_cerca(a1 - a0 + 0.3) * 0.5, 0.2), a0)
    place(bus, stereo(glitch_burst(a1 - a0, seed=21) * 0.16), a0 + 0.2)
    # 01: entra el pincel (cuadros 22-36): el fuelle toma aire
    place(bus, stereo(respiro(1.1) * 0.35), at("01_gancho", 24))
    # 02 y 04: el zumbido del barrido que se acerca por la calle
    z0, z1 = at("02_calle"), at("05_banda")
    zz = zumbido(z1 - z0) * envelope(z1 - z0, [(0, 0.10), (at("03_filete") - z0, 0.18),
                                                (at("03_filete") - z0 + 0.4, 0.05),
                                                (at("04_duda") - z0, 0.22), (z1 - z0, 0.45)])[:, 0]
    place(bus, stereo(zz, 0.0), z0)
    # 04: levanta el pincel (10), lo guarda y saca la banda (35): virola y fuelle
    place(bus, stereo(staccato(note("B4"), 0.25)), at("04_duda", 10))
    place(bus, stereo(N4.relay(1.4) * 0.35, 0.3), at("04_duda", 33))
    place(bus, stereo(respiro(1.4, 300, 1800) * 0.5), at("04_duda", 36))
    place(bus, stereo(riser(at("05_banda", 8) - at("04_duda", 36)) * 0.35), at("04_duda", 36))
    # 05: el zumbido sigue hasta que la banda alcanza la cortina y la apaga
    ch = CFG["05_banda"]["caminito"]["barrido"]["hasta"][0]
    z2 = at("05_banda", ch)
    zz = zumbido(z2 - z1 + 0.2) * envelope(z2 - z1 + 0.2, [(0, 0.45), (z2 - z1, 0.6), (z2 - z1 + 0.2, 0.0)])[:, 0]
    place(bus, stereo(zz), z1)
    place(bus, stereo(glitch_burst(0.35, seed=7) * 0.35), z2)
    place(bus, stereo(N4.boom(2.5) * 0.5), z2 + 0.02)
    # 06: la firma, cinco toquecitos de repique; el barrido vuelve a asomar al final
    g0, g1 = CFG["06_firma"]["filete"]["firma"]
    for k in range(5):
        tk = at("06_firma", g0 + (g1 - g0) * k / 5)
        place(bus, stereo(staccato(note(("E6", "C6", "A5", "C6", "E6")[k]), 0.2), 0.4), tk)
    c6 = CFG["06_firma"]["corte"]
    t_as = at("06_firma", c6[-2][0])
    # siseo agudo y parejo que crece hasta el nivel con que arranca el barrido
    # del 01 (que empieza en 7 kHz): el loop no salta ni de tono ni de volumen
    d = T - t_as
    hiss = sweep_band(np.random.uniform(-1, 1, n_samples(d)), lambda u: 7000.0, q=0.9)
    place(bus, stereo(hiss * envelope(d, [(0, 0.0), (d, 0.5)])[:, 0], 0.2), t_as)
    return bus


# ------------------------------------------------------------------ mezcla

def main():
    Ttot = T + TAIL
    print(f"timeline {T:.2f} s, compas {BAR:.3f} s: " + ", ".join(f"{k} @{v:.2f}" for k, v in S.items()))
    hall = dsp.make_ir(dur=3.6, decay=1.6, damping=5200, predelay=0.02)
    room = dsp.make_ir(dur=1.2, decay=0.45, damping=7000, predelay=0.01)

    m = musica(Ttot)
    pinceladas(m)
    n_notas = cascada(m)
    # 01: el barrido se come la musica (la cola del 06 que cae sobre el 01):
    # el filtro se cierra mientras la linea cruza y queda cerrado hasta que entra el pincel
    c = CFG["01_gancho"]["corte"]
    a0, a1 = at("01_gancho", c[0][0]), at("01_gancho", c[-1][0])
    m = dsp.reverb(m, hall, 0.32)
    fx = dsp.reverb(efectos(Ttot), room, 0.2)

    nT = n_samples(T)
    mus = m[:nT].copy()
    mus[:len(m) - nT] += m[nT:]
    fxx = fx[:nT].copy()
    fxx[:len(fx) - nT] += fx[nT:]
    # el filtro arranca caliente con el ultimo segundo del loop: sin eso, su
    # estado en cero meteria un salto justo en el empalme
    pre = n_samples(1.0)
    fc = lambda tt: 11000 if tt < a0 else (max(300.0, 11000 * (1 - (tt - a0) / (a1 - a0)) ** 2 + 300)
                                           if tt < a1 else (300.0 if tt < at("01_gancho", 30) else 11000))
    mus = sweep_lowpass(np.r_[mus[-pre:], mus], lambda tt: 11000 if tt < 1.0 else fc(tt - 1.0),
                        blocks=600)[pre:]
    out = 0.95 * mus + 0.85 * fxx
    # silencio de un cuadro antes de la firma
    g0 = CFG["06_firma"]["filete"]["firma"][0]
    s0, s1 = at("06_firma", g0) - 1 / 12, at("06_firma", g0)
    out *= envelope(T, [(0, 1), (s0 - 0.01, 1), (s0, 0), (s1, 0), (s1 + 0.01, 1), (T, 1)])
    out = dsp.soft_clip(out * 1.1, 1.2)
    out = dsp.normalize(out, -1.0)
    dst = ROOT / "out" / f"{TL['name']}.wav"
    dst.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(dst, SR, (out * 32767).astype(np.int16))
    print(f"-> {dst}  ({len(out) / SR:.2f} s), {n_notas} notas en la cascada del 05")

    rms = lambda a, b: 20 * np.log10(np.sqrt(np.mean(out[n_samples(a):n_samples(b)] ** 2)) + 1e-9)
    for s in S:
        print(f"  {s:12s} {rms(S[s], S[s] + 1.0):6.1f} dB (primer s)")
    print(f"  barrido 01         {rms(a0, a1):6.1f} dB")
    print(f"  antes del pincel   {rms(a1, at('01_gancho', 24)):6.1f} dB")
    print(f"  cascada 05         {rms(at('05_banda', 20), at('05_banda', 100)):6.1f} dB")
    print(f"  silencio firma     {rms(s0 + 0.005, s1 - 0.005):6.1f} dB")
    print(f"  final del loop     {rms(T - 1.0, T):6.1f} dB   | arranque {rms(0, 1.0):6.1f} dB")


if __name__ == "__main__":
    main()
