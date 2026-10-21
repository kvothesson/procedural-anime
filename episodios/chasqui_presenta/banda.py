"""
banda.py - Banda de la presentacion horizontal de chasqui. Los instrumentos son
los de El relevo (../chasqui_relevo/banda.py, por importlib) y las voces, sus
mismas tomas reales (voces.json). Lo nuevo es la partitura de los tambos y de
la ida y vuelta.

    python episodios/chasqui_presenta/banda.py   # -> out/chasqui_presenta.wav (48 kHz, estereo)

  - Andes: quena y charango en re menor pentatonico. Tokio: el mismo motivo en koto.
  - Tambos: un pulso de carrera suave (las tarjetas se leen) y, cuando cada
    baliza se enciende (= entra su tarjeta), una nota que sube + campana.
  - Ida y vuelta: quena (hielo, izquierda) y koto (violeta, derecha) tocan el
    motivo a la vez; campana donde las luces se cruzan.
  - Loop: se renderiza con cola y la cola se suma al principio.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("banda_relevo", ROOT.parent / "chasqui_relevo" / "banda.py")
rel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rel)

import dsp  # noqa: E402  (rel ya puso motor/audio en el path)
from plano import load_shot  # noqa: E402
from dsp import SR, n_samples, place, stereo  # noqa: E402

np.random.seed(11)
TAIL, FPS = 5.0, 12
D, MOTIF = rel.D, rel.MOTIF
quena, charango, strum, koto, bell, thump = rel.quena, rel.charango, rel.strum, rel.koto, rel.bell, rel.thump
swept, wind, rain, rumble = rel.swept, rel.wind, rel.rain, rel.rumble


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


def beacon_frames(shot):
    """Cuadro en que se enciende cada baliza (misma cuenta que viaje.relevo)."""
    c = cfg(shot)
    keys, rv = c["mensaje"]["keys"], c.get("relevo", {})
    out = []
    for t in sorted(c["tambos"]["list"], key=lambda t: t["s"]):
        sb = t["s"] + t.get("beacon_ahead", 2.0)
        fs = [f for f in range(1, c["frames"] + 1) if np.interp(f, *zip(*keys)) + rv.get("lead", 0) >= sb]
        if fs:
            out.append(fs[0] + rv.get("delay", 0))
    return out


def main():
    total = T + TAIL
    music = np.zeros((n_samples(total), 2))
    amb = np.zeros_like(music)
    ir = dsp.make_ir(3.6, 2.0, 5200)
    ir_city = dsp.make_ir(1.6, 0.8, 4000)

    # --- 1 apacheta: viento, latido del cristal, la quena; destello y salida
    place(amb, stereo(wind(T) * 0.10, 0.0), 0.0)
    c1 = cfg("01_apacheta")
    lt, fl = c1["apacheta"]["latido"], c1["mensaje"]["from_frame"]
    for k in range(8):
        f = 1 + lt["beat_frames"] * (k + 0.5) - lt.get("phase", 0)
        if f < fl - 2:
            place(music, stereo(thump() * 0.30, 0.0), at("01_apacheta", f))
    place(music, stereo(quena(D["D5"], 2.6) * 0.16, -0.15), at("01_apacheta", 6))
    place(music, stereo(quena(D["A4"], 2.2) * 0.12, -0.15), at("01_apacheta", 36))
    place(music, stereo(bell(D["A5"], 3.0) * 0.20, 0.1), at("01_apacheta", fl))
    place(amb, stereo(swept(1.6, 500, 4000) * 0.08, 0.3), at("01_apacheta", fl))

    # --- 2 puente: charango; la campana cae donde la luz cambia de color
    for k in range(8):
        ch = [D["D4"], D["A4"], D["D5"], D["F5"]] if k < 4 else [D["C4"], D["G4"], D["C5"], D["F5"]]
        strum(music, ch if k % 2 == 0 else ch[1:], at("02_puente") + 0.5 * k, pan=-0.2, gain=0.10 if k % 2 else 0.14)
    sw = cfg("02_puente")["mensaje"]
    f_sw = next(f for f in range(1, 49) if np.interp(f, *zip(*sw["keys"])) >= sw["colors"][1][0])
    place(music, stereo(bell(D["D6"], 4.0) * 0.22, 0.25), at("02_puente", f_sw))
    place(music, stereo(bell(D["A5"], 4.0) * 0.12, -0.25), at("02_puente", f_sw, 0.04))
    place(amb, stereo(swept(4.0, 300, 900, 1.4) * 0.05, 0.0), at("02_puente"))

    # --- 3 orbita: el aire se abre; quintas largas y la quena arriba
    o0 = at("03_orbita")
    for f, g in ((D["D3"], 0.10), (D["A3"], 0.08), (D["D4"], 0.06), (D["A4"], 0.04)):
        place(music, stereo(dsp.pad(f, 6.0, cutoff=1800, attack=1.0, release=2.0) * g, 0.0), o0 - 0.3)
    place(music, stereo(quena(D["A5"], 3.2, depth=0.008) * 0.10, -0.2), o0 + 0.8)
    place(music, stereo(quena(D["D6"], 1.6, depth=0.008) * 0.07, -0.2), o0 + 3.6)
    place(amb, stereo(swept(5.0, 2000, 400, 2.0) * 0.06, 0.0), o0)

    # --- 4 tokio: lluvia, ciudad, el tren; el motivo en koto
    t4, c4 = at("04_tokio"), cfg("04_tokio")
    place(amb, stereo(rain(8.0) * 0.06, -0.3) + stereo(rain(8.0) * 0.06, 0.3), t4)
    place(amb, stereo(rumble(8.0, 90) * 0.06, 0.0), t4)
    tr = c4["viaducto"]["tren"]
    tr0, tr1 = at("04_tokio", tr["frames"][0]), at("04_tokio", tr["frames"][1])
    n = n_samples(tr1 - tr0 + 1.0)
    tt = dsp.time_axis(n)
    pas = np.exp(-((tt - (tr1 - tr0) * 0.45) / ((tr1 - tr0) * 0.3)) ** 2)
    clack = np.zeros(n)
    for i in range(0, n - 2000, n_samples(0.36)):
        clack[i:i + 2000] += thump(2000 / SR, 140, 90)[:2000] * 0.5
    train = (rumble(n / SR, 220) + clack) * pas
    pan_t = np.linspace(-0.7, 0.7, n)
    place(amb, np.stack([train * np.cos((pan_t + 1) * np.pi / 4), train * np.sin((pan_t + 1) * np.pi / 4)], 1) * 0.10, tr0)
    place(music, stereo(bell(D["A5"], 3.0) * 0.18, 0.0), at("04_tokio", c4["mensaje"][0]["keys"][-1][0]))
    for i, (nm, dt, du) in enumerate(MOTIF * 2):
        place(music, stereo(koto(D[nm] / (1 if i < 3 else 2), 2.6) * 0.16, 0.25), t4 + 0.4 + dt + (2.6 if i >= 3 else 0))
    sw4 = c4["farol_hex"]["colors"][1][0]
    place(music, stereo(bell(D["D6"], 4.0) * 0.20, 0.2), at("04_tokio", sw4))
    place(amb, stereo(swept(1.4, 600, 5000) * 0.07, 0.0), at("04_tokio", sw4))
    for k in range(3):
        place(music, stereo(koto(D[["D4", "A4", "C5"][k]], 2.6) * 0.10, -0.25), at("04_tokio", sw4) + 1.2 + 0.9 * k)

    # --- 5 tambos: pulso de carrera, acordes de charango; una nota por baliza
    t5, dur5 = at("05_tambos"), cfg("05_tambos")["frames"] / FPS
    place(amb, stereo(wind(dur5) * 0.06, 0.0), t5)
    for f, g in ((D["D3"], 0.06), (D["A3"], 0.04)):
        place(music, stereo(dsp.pad(f, dur5, cutoff=1200, attack=2.0, release=2.0) * g, 0.0), t5)
    beat = 0.5
    for k in range(int(dur5 / beat)):
        place(music, stereo(thump(0.5, 80, 50) * (0.16 if k % 2 == 0 else 0.08), 0.0), t5 + beat * k)
    prog = [[D["D4"], D["A4"], D["D5"]], [D["C4"], D["G4"], D["C5"]], [D["F4"], D["A4"], D["C5"]], [D["D4"], D["A4"], D["D5"]]]
    for k in range(int(dur5 / 2.0)):
        strum(music, prog[k % 4], t5 + 2.0 * k, pan=0.2, gain=0.08)
    scale = ["D5", "F5", "G5", "A5", "D6"]
    for i, fb in enumerate(beacon_frames("05_tambos")):
        tb = at("05_tambos", fb)
        place(music, stereo(charango(D[scale[i % 5]], 1.8) * 0.22, -0.4 + 0.2 * i), tb)
        place(music, stereo(bell(D[scale[i % 5]] * 2, 2.0) * 0.07, 0.3), tb)
        place(amb, stereo(swept(0.8, 800, 3000) * 0.04, 0.0), tb)

    # --- 6 ida y vuelta: el motivo en quena (ida) y en koto (vuelta), a la vez
    c6 = cfg("06_ida_vuelta")
    t6 = at("06_ida_vuelta")
    ka, kb = c6["mensaje"][0]["keys"], c6["mensaje"][1]["keys"]
    f_x = next(f for f in range(1, c6["frames"] + 1) if np.interp(f, *zip(*ka)) >= np.interp(f, *zip(*kb)))
    for nm, dt, du in MOTIF:
        place(music, stereo(quena(D[nm], du + 0.4) * 0.14, -0.45), t6 + 0.6 + dt)
        place(music, stereo(koto(D[nm] / 2, 2.6) * 0.16, 0.45), t6 + 0.6 + dt)
    place(music, stereo(bell(D["D6"], 4.5) * 0.22, 0.0), at("06_ida_vuelta", f_x))
    place(music, stereo(bell(D["A5"], 4.5) * 0.12, 0.0), at("06_ida_vuelta", f_x, 0.05))
    for k in range(4):
        strum(music, [D["D4"], D["A4"], D["D5"], D["F5"]], t6 + 3.5 + 0.8 * k, pan=-0.1, gain=0.09)
    place(amb, stereo(swept(c6["frames"] / FPS, 300, 900, 1.4) * 0.05, 0.0), t6)

    # --- 7 cierre: la luz baja; destello; quena y charango resuelven; vuelve el viento
    t7, c7 = at("07_cierre"), cfg("07_cierre")
    place(amb, stereo(wind(c7["frames"] / FPS) * 0.08, 0.0), t7)
    place(amb, stereo(swept(2.4, 4000, 500) * 0.07, 0.0), t7)
    tf = at("07_cierre", c7["apacheta"]["latido"]["flash"][1][0])
    place(music, stereo(bell(D["D6"], 5.0) * 0.24, 0.0), tf)
    place(music, stereo(thump(0.9, 60, 38) * 0.35, 0.0), tf)
    for nm, dt, du in MOTIF:
        place(music, stereo(quena(D[nm], du + 0.4) * 0.15, -0.15), tf + 0.6 + dt)
    strum(music, [D["D4"], D["A4"], D["D5"], D["F5"] * 2 ** (1 / 12)], tf + 2.1, pan=0.15, gain=0.13, dur=3.0)
    place(music, stereo(quena(D["D5"], 2.4) * 0.12, -0.15), tf + 2.6)

    music = dsp.reverb(music, ir, 0.32)
    amb_city = np.zeros_like(amb)
    i4, i5 = n_samples(S["04_tokio"]), n_samples(S["05_tambos"])
    amb_city[i4:i5] = amb[i4:i5]
    amb[i4:i5] = 0
    amb = amb + dsp.reverb(amb_city, ir_city, 0.25)

    # --- voces reales (las de El relevo): original a la izquierda, chasqui a la derecha
    v = json.loads((ROOT / "voces.json").read_text(encoding="utf-8"))
    vdir = (ROOT / v["dir"]).resolve()
    voices = np.zeros_like(music)
    duck = np.zeros(len(music))
    for key in ("ida", "vuelta"):
        tk = vdir / v[key]["take"]
        src0, out = rel.read_wav(tk / "entrada.wav"), rel.read_wav(tk / "salida.wav")
        a_out = rel.active(out)
        m = min(len(src0), len(a_out))
        src = src0[:m] * (1 - 0.6 * a_out[:m])               # el original baja cuando entra chasqui
        src = src / max(np.abs(src).max(), 1e-9) * 0.62
        out = out / max(np.abs(out).max(), 1e-9) * 0.78
        place(voices, stereo(src, -0.28), v[key]["at"])
        place(voices, stereo(out, 0.28), v[key]["at"])
        a_in = rel.active(src0)
        k = min(len(a_in), len(a_out))
        seg = np.maximum(a_in[:k], a_out[:k])
        i0 = n_samples(v[key]["at"])
        j = min(len(duck), i0 + len(seg))
        duck[i0:j] = np.maximum(duck[i0:j], seg[:j - i0])
    voices = dsp.reverb(voices, dsp.make_ir(0.6, 0.25, 6000), 0.08)
    mix = (music + amb) * (1 - 0.55 * duck)[:, None] + voices

    # loop: la cola vuelve al principio
    tail = mix[n_samples(T):]
    mix = mix[:n_samples(T)].copy()
    mix[:len(tail)] += tail
    mix = dsp.soft_clip(mix * 1.1, 1.2)
    mix = dsp.normalize(mix, -1.0)

    print("RMS por plano (dB):")
    names = list(S)
    for a, b in zip(names, names[1:] + [None]):
        seg = mix[n_samples(S[a]):n_samples(S[b] if b else T)]
        print(f"  {a:16s} {S[a]:5.1f}s  {20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9):6.1f}")
    out = ROOT / "out" / "chasqui_presenta.wav"
    out.parent.mkdir(exist_ok=True)
    wavfile.write(out, SR, (mix * 32767).astype(np.int16))
    print(f"-> {out} ({len(mix) / SR:.1f} s)")


if __name__ == "__main__":
    main()
