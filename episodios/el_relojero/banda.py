"""
banda.py - Banda de sonido de EL RELOJERO. Sintesis pura: ni un sample.

    python episodios/el_relojero/banda.py   # -> episodios/el_relojero/out/el_relojero.wav (48 kHz, estereo)

Todo gira alrededor del tic del reloj:
  - El tic-tac suena en cada tic REAL de los engranajes de cada plano: se calcula
    con tick_count del motor y las trabas ("stop") de cada JSON. Si un plano
    cambia, el sonido se reacomoda solo.
  - Una cajita de musica en La menor, a tempo con el tic (corcheas a 120), entra
    con la ciudad, se frena desafinando cuando se rompe el pinon (plano 4), calla
    durante el sacrificio y vuelve cuando el corazon engrana (plano 6d, frame 81).
  - Cada evento se ancla a (plano, frame de la escena). Los planos que reparten
    una misma accion con render_frames duran lo que se renderiza, no "frames".
  - Loop: se renderiza con cola y la cola se suma al principio.

Instrumentos compartidos con NODO 404 (campana, colchon, lluvia, glitch, rele,
latido, colectivo, filtros): se importan de su banda sin tocarla.
"""

from __future__ import annotations

import importlib.util
import json
import math
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

np.random.seed(1916)
TAIL = 5.0
FPS = 12


# ------------------------------------------------------------------ tiempos

def ventana(shot):
    """(primer frame de la escena, cantidad de frames) que muestra el plano."""
    c = load_shot(ROOT / "shots" / f"{shot}.json")
    if c.get("render_frames"):
        a, b = c["render_frames"]
        return a, b - a + 1
    return 1, c["frames"]


TL = json.loads((ROOT / "shots" / "timeline.json").read_text(encoding="utf-8"))
S, W = {}, {}
_t = 0.0
for _s in TL["shots"]:
    S[_s] = _t
    W[_s] = ventana(_s)
    _t += W[_s][1] / FPS
T = _t


def at(shot, frame):
    """Tiempo absoluto del frame (de la escena) de un plano."""
    return S[shot] + (frame - W[shot][0]) / FPS


def ticks(shot):
    """Frames de la escena donde arranca un tic (dentro de lo que se ve):
    cuando la parte entera del tiempo efectivo del reloj sube."""
    c = load_shot(ROOT / "shots" / f"{shot}.json")
    E = c.get("engranajes")
    if E:
        tick, stop = E.get("tick", {"bps": 1.0}), E.get("stop")
    elif c.get("pulso"):
        tick, stop = {"bps": c["pulso"].get("bps", 1.0)}, None
    else:
        return []
    bps = tick.get("bps", 1.0)

    def te(f):
        if stop:
            f0, f1 = stop
            f = f if f < f0 else (f0 if f < f1 else f - (f1 - f0))
        return (f - 1) / FPS * bps + tick.get("offset", 0.0)

    a, n = W[shot]
    out = []
    for f in range(a, a + n):
        moving = not stop or not (stop[0] <= f < stop[1])
        # tic: arranca el reloj (frame 1 o se suelta la traba) o sube la parte entera del tiempo
        suelta = stop and f == stop[1]
        if moving and (f == 1 or suelta or math.floor(te(f) + 1e-9) > math.floor(te(f - 1) + 1e-9)):
            out.append(f)
    return out


# ------------------------------------------------------------------ instrumentos

def tictac(tock=False):
    """Escape de reloj: click seco + cuerpo metalico corto; el tac mas grave."""
    n = n_samples(0.12)
    t = time_axis(n)
    click = dsp.highpass(np.random.uniform(-1, 1, n), 3000) * np.exp(-t / 0.0025)
    f = 1650 if not tock else 1180
    ring = (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.71 * t)) * np.exp(-t / 0.018)
    knock = np.sin(2 * np.pi * (210 if not tock else 160) * t) * np.exp(-t / 0.025)
    return 0.55 * click + 0.35 * ring + 0.5 * knock


def cajita(freq, dur=2.2):
    """Cajita de musica: pua sobre peine metalico (agudos brillantes que caen
    rapido, un poco inarmonico) + una octava arriba muy suave."""
    a = dsp.struck(freq, dur, decay=1.1, bright=0.9, inharmonicity=0.0016, partials=9)
    b = dsp.struck(freq * 2.0, dur * 0.6, decay=0.5, bright=0.8, inharmonicity=0.002, partials=5)
    return 0.8 * a + 0.2 * np.pad(b, (0, len(a) - len(b)))


def paso_metal():
    """Pie de metal sobre escalon de madera: golpe sordo + chapa que suena."""
    n = n_samples(0.4)
    t = time_axis(n)
    thud = np.sin(2 * np.pi * (110 + 60 * np.exp(-t / 0.02)) * t) * np.exp(-t / 0.06)
    clank = (np.sin(2 * np.pi * 640 * t) + 0.6 * np.sin(2 * np.pi * 1410 * t)) * np.exp(-t / 0.05)
    wood = dsp.bandpass(np.random.uniform(-1, 1, n), 300, 1800) * np.exp(-t / 0.03)
    return 0.8 * thud + 0.35 * clank + 0.4 * wood


def ping_metal(f=2600, dur=1.4, decay=0.6):
    """Diente que se parte / pieza chica de bronce: campana chica inarmonica."""
    return dsp.struck(f, dur, decay=decay, bright=0.85, inharmonicity=0.012, partials=8)


def clac(f=420, dur=0.35):
    """Pieza que encaja: golpe metalico corto con cuerpo."""
    n = n_samples(dur)
    t = time_axis(n)
    body = (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.3 * t)) * np.exp(-t / 0.05)
    click = dsp.highpass(np.random.uniform(-1, 1, n), 2000) * np.exp(-t / 0.004)
    return 0.7 * body + 0.5 * click


def chirrido(dur):
    """Forcejeo: metal contra metal, ruido estrecho que tiembla y una sierra grave."""
    n = n_samples(dur)
    t = time_axis(n)
    x = nodo.sweep_band(np.random.uniform(-1, 1, n), lambda u: 1800 + 900 * np.sin(2 * np.pi * 4 * u), q=0.15)
    grind = dsp.lowpass(dsp.bl_saw(70 + 15 * np.sin(2 * np.pi * 9 * t).mean(), n), 600)
    trem = 0.6 + 0.4 * np.sin(2 * np.pi * 14 * t)
    return (0.8 * x / max(np.abs(x).max(), 1e-9) + 0.5 * grind) * trem * dsp.adsr(n, 0.05, 0.1, 0.9, 0.05)


def trinquete(t0, dur, rate0, tau):
    """La rueda desbocada: clicks de trinquete que arrancan rapido y frenan."""
    out = []
    tt = 0.0
    while tt < dur:
        r = rate0 * math.exp(-tt / tau)
        if r < 2.0:
            break
        out.append(t0 + tt)
        tt += 1.0 / r
    return out


def zumbido(dur, f0=110.0, sube=True):
    """Ojo: zumbido electrico que sube (se enciende) o baja (se apaga)."""
    n = n_samples(dur)
    t = time_axis(n)
    u = t / dur
    f = f0 * (1 + (2.5 * u if sube else 2.5 * (1 - u)))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sign(np.sin(ph)) * 0.3 + np.sin(ph) + 0.4 * np.sin(2 * ph)
    x = dsp.lowpass(x, 2400)
    env = u ** 0.6 if sube else (1 - u) ** 1.5
    return x * env * dsp.adsr(n, 0.01, 0.1, 1.0, 0.05)


def resorte():
    """El corazon sale sobre su eje: boing corto de resorte."""
    n = n_samples(0.5)
    t = time_axis(n)
    f = 330 + 140 * np.sin(2 * np.pi * 9 * t) * np.exp(-t / 0.12)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.15)


# ------------------------------------------------------------------ partitura

# cajita: corcheas a 120 (dos por tic), La menor. Silencio = None.
TEMA = ["A4", "C5", "E5", "A5", "G5", "E5", "D5", "E5",
        "C5", "E5", "A5", "C6", "B5", "G5", "E5", None,
        "F5", "A5", "C6", "A5", "G5", "E5", "D5", "C5",
        "B4", "D5", "E5", "G5", "E5", "D5", "B4", None]
# mayor, cuando el corazon engrana: la misma figura en La mayor
TEMA_MAYOR = [n.replace("C5", "C#5").replace("C6", "C#6").replace("G5", "G#5").replace("F5", "F#5")
              if n else None for n in TEMA]


def cajita_tramo(bus, t0, t1, tema, gain, t_ref, pan=0.15):
    """Coloca el tema entre t0 y t1, con las corcheas alineadas al tic de t_ref."""
    i0 = math.ceil((t0 - t_ref) / 0.5)
    i = i0
    while t_ref + i * 0.5 < t1:
        nm = tema[i % len(tema)]
        if nm:
            place(bus, stereo(cajita(note(nm)) * gain * (1.0 if i % 2 == 0 else 0.8), pan), t_ref + i * 0.5)
        i += 1


def musica(Ttot):
    bus = np.zeros((n_samples(Ttot), 2))
    ref = at("02_ciudad", 1)                       # un tic de la ciudad: la grilla del tema
    # entra con la ciudad y sigue hasta que se parte el diente
    snap = at("04_falla", 40)
    cajita_tramo(bus, ref, snap, TEMA, 0.32, ref)
    # la cajita se frena desafinando: las ultimas notas bajan de tono y se espacian
    for k, nm in enumerate(("E5", "C5", "A4")):
        f = note(nm) * (0.97 - 0.05 * k)
        place(bus, stereo(cajita(f, 1.6) * (0.3 - 0.07 * k)), snap + 0.05 + k * (0.35 + 0.2 * k))
    # colchon grave en La menor durante la ciudad y la subida
    c_end = at("04_falla", 37)
    pad = nodo.chord_pad(["A2", "E3", "A3", "C4"], c_end - ref + 1.5, attack=2.0, release=1.2, cutoff=1300)
    place(bus, stereo(pad * 0.55), ref)
    place(bus, stereo(dsp.sub(note("A1"), c_end - ref + 1.0, attack=1.5) * 0.35), ref)

    # sacrificio: la revelacion del corazon (es la misma pieza) -> acorde tibio
    rev = at("06c_pecho", 53)
    place(bus, stereo(nodo.chord_pad(["F2", "C3", "A3", "E4"], 4.5, attack=0.8, release=2.0, cutoff=1600) * 0.5), rev)
    for k, nm in enumerate(("A5", "C6", "E6")):
        place(bus, stereo(nodo.bell(note(nm), 4.0) * 0.18, (-0.3, 0.0, 0.3)[k]), rev + 0.25 + k * 0.45)

    # el corazon engrana: vuelve la cajita, ahora en mayor, y sigue hasta el final (y el loop)
    back = at("06d_eje", 81)
    cajita_tramo(bus, back, Ttot, TEMA_MAYOR, 0.3, back)
    pad2 = nodo.chord_pad(["A2", "E3", "A3", "C#4", "E4"], Ttot - back, attack=1.2, release=2.5, cutoff=1500)
    place(bus, stereo(pad2 * 0.5), back)
    place(bus, stereo(dsp.sub(note("A1"), Ttot - back, attack=0.8) * 0.3), back)
    return bus


def sfx(Ttot):
    bus = np.zeros((n_samples(Ttot), 2))
    rnd = np.random.default_rng(12)

    # el tic-tac en cada tic real de cada plano (tic y tac alternan)
    for shot in TL["shots"]:
        if shot == "05_desincronia":
            continue
        g = {"02_ciudad": 0.5, "03_subida": 0.42, "04_falla": 0.6, "07_nacimiento": 0.45,
             "01_gancho": 0.45}.get(shot, 0.5)
        for f in ticks(shot):
            tock = ((f - 1) // FPS) % 2 == 1
            place(bus, stereo(tictac(tock) * g, -0.15), at(shot, f))
            if shot == "02_ciudad":      # la ciudad late con el reloj
                place(bus, stereo(nodo.thump(52, 0.9) * 0.35), at(shot, f))
            if shot == "03_subida":      # un escalon por tic
                place(bus, stereo(paso_metal() * 0.55, 0.1), at(shot, f) + 0.12)

    # 1: el ojo se enciende (titila en 87, prende en 90)
    place(bus, stereo(zumbido(0.25) * 0.25), at("01_gancho", 87))
    place(bus, stereo(zumbido(0.5) * 0.35), at("01_gancho", 89))
    place(bus, stereo(nodo.bell(note("E6"), 3.0) * 0.18, 0.2), at("01_gancho", 90))

    # 4: forcejeo, se parte el diente, rebota en el piso, la rueda se desboca
    place(bus, stereo(chirrido(0.3) * 0.5, -0.2), at("04_falla", 37))
    place(bus, stereo(ping_metal(2900) * 0.6, -0.1), at("04_falla", 40))
    place(bus, stereo(nodo.relay(1.3) * 0.6), at("04_falla", 40))
    for k, (df, g) in enumerate(((7, 0.35), (10, 0.22), (12, 0.12))):
        place(bus, stereo(ping_metal(3400 + 300 * k, 0.6, 0.15) * g, 0.4), at("04_falla", 40 + df))
    for tt in trinquete(at("04_falla", 40) + 0.04, 1.6, 26.0, 0.45):
        place(bus, stereo(tictac(True) * 0.28, -0.25), tt)
    place(bus, stereo(nodo.thump(40, 1.2) * 0.6), at("04_falla", 41))

    # 5: cada luz con su propio ritmo -> tics desparejos, glitches, el colectivo se apaga
    a5, b5 = at("05_desincronia", 1), at("05_desincronia", 60)
    for f in ticks("05_desincronia"):
        if f < 18:
            place(bus, stereo(tictac(((f - 1) // FPS) % 2 == 1) * 0.5, -0.15), at("05_desincronia", f))
    for _ in range(26):
        tt = rnd.uniform(at("05_desincronia", 18), b5)
        place(bus, stereo(tictac(rnd.random() < 0.5) * rnd.uniform(0.12, 0.4), rnd.uniform(-0.9, 0.9)),
              tt)
    for f0, f1, _ in load_shot(ROOT / "shots" / "05_desincronia.json")["post"]["glitch"]:
        place(bus, stereo(nodo.glitch_burst((f1 - f0 + 1) / FPS + 0.05, seed=f0) * 0.4), at("05_desincronia", f0))
    st, t0 = nodo.bus_pass(at("05_desincronia", 18), dur=4.0, v=9.0, d=9.0)
    n0 = n_samples(at("05_desincronia", 30) - t0)
    st = st.copy()
    st[n0:] *= np.linspace(1, 0, len(st) - n0)[:, None] ** 2     # frena y se apaga
    place(bus, st * 0.6, t0)
    # un zumbido grave que se queda sin compas
    n = n_samples(b5 - a5)
    tt = time_axis(n)
    drone = np.sin(2 * np.pi * 55 * tt) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.7 * tt))
    place(bus, stereo(drone * np.clip((tt - 1.4) / 1.0, 0, 1)[:] * 0.25), a5)

    # 6: el sacrificio
    place(bus, stereo(clac(900, 0.2) * 0.35, 0.2), at("06_sacrificio", 14))          # agarra el pinon
    place(bus, stereo(nodo.sweep_band(np.random.uniform(-1, 1, n_samples(0.5)),
                                      lambda u: 2500 - 1200 * u, q=0.2) * 0.12, 0.2), at("06_sacrificio", 14))
    place(bus, stereo(ping_metal(2300, 1.0, 0.25) * 0.5, 0.3), at("06_sacrificio", 38))  # el pinon cae
    place(bus, stereo(ping_metal(2500, 0.6, 0.12) * 0.25, 0.3), at("06_sacrificio", 39))
    place(bus, stereo(clac(1300, 0.15) * 0.3, 0.1), at("06c_pecho", 44))               # perilla
    place(bus, stereo(nodo.sweep_band(np.random.uniform(-1, 1, n_samples(0.5)),
                                      lambda u: 700 + 500 * u, q=0.25) * 0.15), at("06c_pecho", 45))  # bisagra
    place(bus, stereo(clac(260, 0.4) * 0.45), at("06c_pecho", 51))                     # la tapa cae
    place(bus, stereo(resorte() * 0.3), at("06c_pecho", 50))                           # el corazon asoma
    place(bus, stereo(clac(900, 0.2) * 0.3, 0.2), at("06c_pecho", 62))                 # lo toma
    place(bus, stereo(nodo.sweep_band(np.random.uniform(-1, 1, n_samples(0.35)),
                                      lambda u: 1800 + 800 * u, q=0.2) * 0.12), at("06d_eje", 76))  # entra en el eje
    place(bus, stereo(clac(520, 0.5) * 0.6), at("06d_eje", 80))                        # engrana
    # 6b: el ojo titila y se apaga
    for f in (86, 89):
        place(bus, stereo(zumbido(0.12, 140) * 0.18), at("06b_ojo", f))
    place(bus, stereo(zumbido(0.9, 120, sube=False) * 0.35), at("06b_ojo", 90))

    # 7: cada pieza que encaja hace clac (las grandes, mas grave); el corazon nuevo, campanita
    c7 = load_shot(ROOT / "shots" / "07_nacimiento.json")["relojero"]["despiece"]["partes"]
    for name, spec in c7.items():
        f1 = spec["span"][1]
        if f1 > W["07_nacimiento"][0] + W["07_nacimiento"][1] - 1:
            continue
        grande = name in ("torso", "pelvis", "craneo", "ribete_alto", "ribete_bajo")
        f = rnd.uniform(380, 520) if grande else rnd.uniform(700, 1500)
        place(bus, stereo(clac(f, 0.35) * (0.45 if grande else 0.2), rnd.uniform(-0.4, 0.4)),
              at("07_nacimiento", f1))
    place(bus, stereo(nodo.bell(note("A5"), 4.0) * 0.3), at("07_nacimiento", c7["corazon"]["span"][1]))
    place(bus, stereo(nodo.bell(note("E6"), 4.0) * 0.18, 0.2), at("07_nacimiento", c7["corazon"]["span"][1]) + 0.3)
    return bus


# ------------------------------------------------------------------ mezcla

def main():
    Ttot = T + TAIL
    print(f"timeline {T:.2f} s: " + ", ".join(f"{k} @{v:.1f}" for k, v in S.items()))
    hall = dsp.make_ir(dur=4.0, decay=1.9, damping=5200, predelay=0.03)
    room = dsp.make_ir(dur=1.4, decay=0.5, damping=7000, predelay=0.01)

    m = musica(Ttot)
    # dramaturgia: la cajita entra suave con la ciudad, crece en la subida y se corta al romperse
    m *= nodo.envelope(Ttot, [(0, 1.0), (at("02_ciudad", 1), 0.7), (at("03_subida", 1), 0.9),
                              (at("04_falla", 30), 1.05), (Ttot, 1.05)])
    m = dsp.reverb(m, hall, 0.35)
    fx = dsp.reverb(sfx(Ttot), room, 0.2)

    # lluvia: afuera fuerte, adentro (sala de maquinas, escalera) apagada detras del vidrio
    rain = nodo.rain_bed(Ttot)
    afuera = [(at("02_ciudad", 1), at("02_ciudad", 60)), (at("05_desincronia", 1), at("05_desincronia", 60))]
    pts = [(0, 0.35)]
    for a, b in afuera:
        pts += [(a - 0.15, 0.35), (a, 0.9), (b, 0.9), (b + 0.15, 0.35)]
    pts.append((Ttot, 0.35))
    rain *= nodo.envelope(Ttot, pts)
    rain = np.stack([dsp.lowpass(rain[:, c], 5200) for c in range(2)], axis=1)
    city = nodo.city_hum(Ttot)
    city *= nodo.envelope(Ttot, [(0, 0.0), (afuera[0][0], 0.0), (afuera[0][0] + 0.5, 0.3), (afuera[0][1], 0.3),
                                 (afuera[0][1] + 0.2, 0.0), (afuera[1][0], 0.25), (afuera[1][1], 0.1),
                                 (afuera[1][1] + 0.2, 0.0), (Ttot, 0.0)])

    mix = 0.9 * m + 0.9 * fx + 0.3 * rain + 0.25 * city

    # loop: la cola despues de T se suma al principio (la lluvia ya es continua)
    nT = n_samples(T)
    out = mix[:nT].copy()
    tail = (0.9 * m + 0.9 * fx)[nT:]
    out[:len(tail)] += tail
    out = dsp.soft_clip(out * 1.1, 1.2)
    out = dsp.normalize(out, -1.0)

    dst = ROOT / "out" / f"{TL['name']}.wav"
    dst.parent.mkdir(parents=True, exist_ok=True)       # en un clon limpio no existe
    wavfile.write(dst, SR, (out * 32767).astype(np.int16))
    print(f"-> {dst}  ({len(out) / SR:.2f} s)")

    rms = lambda a, b: 20 * np.log10(np.sqrt(np.mean(out[n_samples(a):n_samples(b)] ** 2)) + 1e-9)  # noqa: E731
    for s in S:
        d = W[s][1] / FPS
        print(f"  {s:16s} {rms(S[s], S[s] + d):6.1f} dB  ({len(ticks(s))} tics)")
    snap = at("04_falla", 40)
    print(f"  antes de romperse  {rms(snap - 1.0, snap):6.1f} dB | despues {rms(snap + 1.5, snap + 3.0):6.1f} dB")
    back = at("06d_eje", 81)
    print(f"  sacrificio (calla) {rms(at('06_sacrificio', 1), back - 0.5):6.1f} dB | vuelve {rms(back, back + 1.0):6.1f} dB")
    print(f"  final del loop     {rms(T - 1.0, T):6.1f} dB | arranque {rms(0, 1.0):6.1f} dB")


if __name__ == "__main__":
    main()
