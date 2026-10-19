"""planos.py - Genera los planos de GUARDAN UNA PALABRA (video de la cancion).

La cancion va a 120 bpm justos: pulso cada 0,5 s, compas cada 2 s, primer
tiempo en 0,19 s (audio/beats.json). Los cortes caen en el compas, en una
grilla de 1/6 s (cuadro 4 + 48 por compas a 24 fps), que sirve igual para
planos en cuatros (6 fps), en doses (12) o sakuga (24).

    python episodios/guardan_una_palabra/planos.py      # escribe shots/*.json, timeline y subs

El escenario es el de episodios/catedral (no se toca desde aca).
"""

import json
from pathlib import Path

EP = Path(__file__).resolve().parent
ENT = json.loads((EP.parent / "catedral" / "data" / "entorno.json").read_text(encoding="utf-8"))
T = ENT["terreno"]
FIN = 4320                      # 180 s a 24 fps
PULSO0, PULSO = 0.19, 0.5       # primer tiempo y pulso (s)
TORRE = [0.0, -3.6, 62.0]
NUCLEO = [0.0, 35.6, 3.0]
FECHA = "2026-10-17"
ANCHO, ALTO = 1920, 1080        # horizontal: videoclip para YouTube
# El motor fija el sensor de 36 mm al ALTO de la imagen (sensor_fit VERTICAL):
# en horizontal, el mismo lente ve el mismo alto y 1,78 veces mas ancho. Las
# lentes de abajo estan pensadas como en vertical; se cierran con este factor
# para no caer en gran angulares de 120 grados que tuercen los bordes
# (menos en lo alto: torre, fachada). Las camaras van con "verticales":
# niveladas y con descentramiento, como un fotografo de arquitectura.
LENTE_K, LENTE_ALTO, LENTE_RIO = 1.4, 1.1, 1.6


def H(x, y):
    n = T["n"]
    fx = min(max((x - T["x0"]) / T["paso"], 0), n - 1.001)
    fy = min(max((y - T["y0"]) / T["paso"], 0), n - 1.001)
    i, j = int(fx), int(fy)
    ax, ay = fx - i, fy - j
    g = T["z"]
    return ((g[j * n + i] * (1 - ax) + g[j * n + i + 1] * ax) * (1 - ay)
            + (g[(j + 1) * n + i] * (1 - ax) + g[(j + 1) * n + i + 1] * ax) * ay)


def ojo(x, y, h=1.6):
    return [x, y, round(H(x, y) + h, 2)]


def corte(compas):
    """Cuadro (a 24 fps, desde 0) donde empieza el compas dado."""
    return 0 if compas == 0 else min(FIN, 4 + 48 * compas)


def cam(pos, aim, lens, n, ease=True, mid=None, k=LENTE_K):
    """Camara de pos[0]->pos[1] mirando aim[0]->aim[1], lente lens (o
    [l0, l1]) a lo largo de n cuadros; mid: (frac, pos, aim) intermedio."""
    keys = [{"frame": 1, "pos": pos[0], "aim": aim[0]}]
    if mid:
        keys.append({"frame": max(2, round(1 + mid[0] * (n - 1))), "pos": mid[1], "aim": mid[2]})
    keys.append({"frame": n, "pos": pos[-1], "aim": aim[-1]})
    l0, l1 = (lens, lens) if not isinstance(lens, list) else lens
    l0, l1 = round(l0 * k, 1), round(l1 * k, 1)
    return {"keys": keys, "lens": l0, "lens_keys": [[1, l0], [n, l1]], "ease": ease, "clip_start": 0.05,
            "clip_end": 3200, "verticales": True}


def latido(t0, n, fps, cada=1, fuerza=1.0, base=0.12):
    """Los leds de todos los racks se prenden en blanco en cada pulso (o cada
    `cada` pulsos) y caen: [[cuadro, 0..1], ...]."""
    keys = [[1, base]]
    k = 0
    while True:
        tb = PULSO0 + PULSO * k
        k += 1
        if tb < t0:
            continue
        f = round((tb - t0) * fps) + 1
        if f > n:
            break
        if (k - 1) % cada:
            continue
        caida = max(1, round(fps * 0.22))
        keys += [[max(1, f - 1), base], [f, fuerza], [f + caida, base]]
    return keys


EXT = {"estilo": "studio_noche", "fecha": FECHA,
       "catedral": {"techo": True, "anexos": True, "suelo": 0}, "servidores": {},
       "entorno": {"datos": "../catedral/data/entorno.json", "z": -1.0, "piso": 6000, "radio": 450}}
INT = {"estilo": "studio_adentro", "catedral": {"techo": True, "anexos": True, "suelo": 0}, "servidores": {}}

# ------------------------------------------------------------------ planos
# (nombre, compas inicial, compas final, fps, base, que pasa, armar(n, t0) -> dict)
P = []


def plano(nombre, c0, c1, fps, base, desc, **kw):
    P.append(dict(nombre=nombre, c0=c0, c1=c1, fps=fps, base=base, desc=desc, **kw))


# INTRO: campanas y organo
plano("01_rio", 0, 4, 6, EXT, "Desde el Rio de la Plata al atardecer: la barranca, la arboleda y la torre",
      hora="19:40", line=0.2,
      camara=lambda n: cam([[-2300.0, 480.0, -24.0], [-2050.0, 445.0, -23.6]], [[0, 20, 30], [0, 20, 30]], [140, 150], n, k=LENTE_RIO))
plano("02_barranca", 4, 8, 6, EXT, "Dron que sube la barranca boscosa y revela la catedral; anochece",
      hora="20:05", line=0.04,
      camara=lambda n: cam([[-260.0, 40.0, -15.0], [-140.0, 22.0, 26.0]], [[0, -3.6, 40], [0, 2, 26]], 24, n))
# COROS sin letra
plano("03_plaza", 8, 12, 6, EXT, "Plaza Mitre bajo las tipas, avanzando hacia la fachada; faroles prendidos",
      hora="20:30", line=0.02,
      camara=lambda n: cam([ojo(-14, -80), ojo(-9, -63)], [[0, -7, 22], [0, -6, 24]], 15, n))
plano("04_torre", 12, 16, 6, EXT, "La torre de la base a la aguja: portada, roseton, campanario, relojes",
      hora="21:00", line=0.025,
      camara=lambda n: cam([ojo(6, -42), ojo(5, -39)], [[0, -7, 6], TORRE], 18, n, k=LENTE_ALTO))
plano("05_cenital", 16, 20, 6, dict(EXT, catedral={"techo": False, "anexos": True, "suelo": 0}),
      "Cenital sin techo: la catedral llena de racks vista desde arriba, bajando", hora="21:30", line=0.05,
      camara=lambda n: cam([[-3.0, 20.0, 150.0], [3.0, 28.0, 95.0]], [[0, 24.6, 0], [0, 24.4, 0]], 30, n))
plano("06_puertas", 20, 24, 12, dict(INT, catedral={"techo": True, "anexos": True, "suelo": 0,
                                                     "puertas": {"abre": [[1, 0], [18, 0], [80, 82]]}},
                                      entorno=EXT["entorno"]),
      "Desde adentro, las puertas se abren a la plaza de noche", line=0.012,
      camara=lambda n: cam([[0.0, 10.0, 1.7], [0.0, 5.0, 1.7]], [[0, -20, 3], [0, -20, 3.5]], 18, n))
# PICO: un corte por compas adentro, los leds laten en cada pulso
ADENTRO_PICO = [
    ("07a_racks", "Dolly bajo por el pasillo central", [[0, 6, 0.5], [0, 11, 0.5]], [[0, 30, 2], [0, 30, 2]], 14),
    ("07b_cables", "Los cables suben a los capiteles", [[0.4, 12, 1.5], [0.2, 13, 1.6]], [[-4.7, 15.8, 8.2], [-4.7, 15.8, 8.6]], 18),
    ("07c_vitrales", "Los vitrales de la nave lateral sobre los racks", [[-5.6, 9, 1.4], [-5.6, 11, 1.5]], [[-9.4, 14, 6], [-9.4, 16, 6.5]], 16),
    ("07d_nucleo", "El nucleo del crucero, girando", [[2.5, 31.5, 2.0], [-2.5, 31.5, 2.3]], [NUCLEO, NUCLEO], 20),
    ("07e_alto", "Desde el triforio: la nave llena de racks", [[3.4, 5, 12.4], [3.4, 8, 12.4]], [[0, 30, 1], [0, 32, 1]], 18),
    ("07f_lateral", "La nave lateral con sus racks", [[-6.8, 2, 1.6], [-6.8, 8, 1.6]], [[-6.8, 40, 4], [-6.8, 40, 4]], 16),
    ("07g_boveda", "Desde el crucero hacia la boveda", [[0.5, 33, 1.5], [-0.5, 33, 1.5]], [[0.6, 36.5, 19], [-0.6, 36.5, 19]], 14),
]
for i, (nom, desc, pos, aim, lens) in enumerate(ADENTRO_PICO):
    plano(nom, 24 + i, 25 + i, 12, dict(INT, drop=["entorno"]), desc, line=0.012, latido_cada=1,
          camara=(lambda pos, aim, lens: lambda n: cam(pos, aim, lens, n))(pos, aim, lens))
# VERSO
plano("08_barranca_rio", 31, 33, 6, EXT, "\"En la barranca, sobre el rio\": aereo sobre el bajo, la barranca y la catedral",
      hora="23:00", line=0.06,
      camara=lambda n: cam([[-330.0, -60.0, 25.0], [-300.0, 60.0, 28.0]], [[0, 10, 20], [0, 10, 20]], 35, n))
plano("09_fachada", 33, 35, 6, EXT, "\"La catedral no duerme mas\": la fachada con los vitrales encendidos",
      hora="23:10", line=0.02,
      camara=lambda n: cam([ojo(3, -34), ojo(2, -28)], [[0, -7, 13], [0, -6, 18]], 18, n, k=LENTE_ALTO))
plano("10_tipas_niebla", 35, 37, 6, EXT, "\"Bajo las tipas, el frio\": Plaza Mitre con niebla",
      hora="23:20", clima="niebla", line=0.02,
      camara=lambda n: cam([ojo(-30, -62), ojo(-26, -58)], [[0, -7, 20], [0, -7, 22]], 15, n))
plano("11_nave", 37, 39, 12, dict(INT, drop=["entorno"]), "\"Mil luces rezan sin parar\": travelling por la nave",
      line=0.012, latido_cada=2, latido_fuerza=0.7,
      camara=lambda n: cam([[0, 4, 1.6], [0, 16, 1.6]], [[0, 46, 6], [0, 46, 6]], 15, n))
# PRE: "Nadie sabe por que"
plano("12_nave_quieta", 39, 43, 6, dict(INT, drop=["entorno"]), "\"Nadie sabe por que\": la nave desde el presbiterio, quieta",
      line=0.012, latido_cada=4, latido_fuerza=0.6,
      camara=lambda n: cam([[0, 44, 2.5], [0, 41, 2.5]], [[0, 0, 6], [0, 0, 6]], 16, n))
plano("13_lateral", 43, 47, 6, dict(INT, drop=["entorno"]), "La nave lateral, lento, hacia una columna con su lampara",
      line=0.012, latido_cada=4, latido_fuerza=0.6,
      camara=lambda n: cam([[6.8, 3, 1.6], [6.8, 7, 1.6]], [[4.7, 20, 8], [4.7, 20, 8]], 16, n))
# ESTRIBILLO 1: la misma camara a ocho horas; las luces nunca se apagan
HORAS = [("06:40", "studio_dia"), ("12:00", "studio_dia"), ("18:50", "studio_dia"), ("19:40", "studio_noche"),
         ("21:00", "studio_noche"), ("00:00", "studio_noche"), ("03:00", "studio_noche"), ("05:45", "studio_noche")]
for i, (hora, est) in enumerate(HORAS):
    a = i / 8
    b = (i + 1) / 8
    p0 = [-52 + 8 * a, -58 + 12 * a, 40 - 4 * a]
    p1 = [-52 + 8 * b, -58 + 12 * b, 40 - 4 * b]
    plano(f"14{'abcdefgh'[i]}_hora", 47 + i, 48 + i, 6, dict(EXT, estilo=est),
          f"\"Nunca se apagan\": la misma toma a las {hora}", hora=hora, line=0.04,
          camara=(lambda p0, p1: lambda n: cam([p0, p1], [[0, 20, 12], [0, 20, 12]], 26, n, ease=False))(p0, p1))
# COROS FUERTES: la capa de estilo y el clima, con la misma toma
CAPAS = [("15a_maqueta", 1, "maqueta", "15:30", "despejado", "La maqueta gris: la estructura sola"),
         ("15b_dia", 1, "studio_dia", "15:30", "despejado", "El estilo de dia"),
         ("15c_noche", 2, "studio_noche", "22:00", "despejado", "El mismo encuadre de noche"),
         ("15d_lluvia", 2, "studio_noche", "22:00", "lluvia", "Lluvia"),
         ("15e_niebla", 2, "studio_noche", "22:00", "niebla", "Niebla")]
c = 55
for nom, nb, est, hora, clima, desc in CAPAS:
    a, b = (c - 55) / 8, (c + nb - 55) / 8
    p0 = [55 - 10 * a, -30 + 10 * a, 30 - 4 * a]
    p1 = [55 - 10 * b, -30 + 10 * b, 30 - 4 * b]
    plano(nom, c, c + nb, 6, dict(EXT, estilo=est), desc, hora=hora, clima=clima, line=0.035,
          camara=(lambda p0, p1: lambda n: cam([p0, p1], [[0, 15, 15], [0, 15, 15]], 24, n, ease=False))(p0, p1))
    c += nb
# PICO 2
plano("16_orbita", 63, 67, 24, dict(INT, drop=["entorno"]), "Orbita rapida al nucleo (sakuga, 24 fps); late en cada pulso",
      line=0.012, latido_cada=1, orbita=True)
plano("17_racks_rapido", 67, 69, 12, dict(INT, drop=["entorno"]), "Dolly rapido y bajo por el pasillo, lineas de velocidad",
      line=0.012, latido_cada=1, speedlines=True,
      camara=lambda n: cam([[0, 2, 0.8], [0, 26, 0.8]], [[0, 40, 1.5], [0, 60, 1.5]], 14, n, ease=False))
plano("18_cenital_baja", 69, 72, 12, dict(EXT, catedral={"techo": False, "anexos": True, "suelo": 0}),
      "Cenital sin techo, bajando hacia el nucleo", hora="23:50", line=0.04,
      camara=lambda n: cam([[0, 30, 120], [0, 34, 40]], [[0, 35.6, 0], [0, 35.7, 0]], 24, n))
# PUENTE: trueno, glitch, "Una palabra"
plano("19_tormenta", 72, 74, 12, EXT, "Tormenta sobre la torre; relampagos en los truenos; \"Una palabra\"",
      hora="00:30", clima="tormenta", line=0.02, relampagos_t=[144.35, 145.4, 146.5, 147.75],
      impacto_t=(146.5, 147.1), glitch_t=[(147.8, 148.2, 0.6)],
      camara=lambda n: cam([ojo(8, -44), ojo(6, -40)], [[0, -3.6, 40], [0, -3.6, 44]], 16, n, k=LENTE_ALTO))
plano("20_palabra", 74, 76, 12, dict(INT, drop=["entorno"]), "\"(Una palabra)\": el nucleo de frente, impacto y congelado",
      line=0.012, latido_cada=1, impacto_t=(150.5, 151.2), datamosh_t=(151.3, 152.1),
      camara=lambda n: cam([[0, 30.5, 2.4], [0, 32.5, 2.6]], [[0, 35.6, 3.2], [0, 35.6, 3.2]], 22, n))
# ESTRIBILLO FINAL: un corte por compas, lo mejor de noche
FINAL = [
    ("21a_rio", EXT, "Aereo sobre el rio hacia la barranca", dict(hora="00:40", line=0.1),
     lambda n: cam([[-700.0, 200.0, 10.0], [-600.0, 180.0, 12.0]], [[0, 15, 25], [0, 15, 25]], 40, n)),
    ("21b_plaza", EXT, "Bajo las tipas de Plaza Mitre", dict(hora="00:40", line=0.02),
     lambda n: cam([ojo(-5, -46), ojo(-3, -40)], [[0, -7, 24], [0, -6, 26]], 15, n)),
    ("21c_fachada", EXT, "La fachada y la torre", dict(hora="00:40", line=0.02),
     lambda n: cam([ojo(2, -30), ojo(1, -27)], [[0, -7, 14], [0, -4, 40]], 16, n, k=LENTE_ALTO)),
    ("21d_nave", dict(INT, drop=["entorno"]), "La nave con los racks", dict(line=0.012, latido_cada=1),
     lambda n: cam([[0, 8, 1.6], [0, 12, 1.6]], [[0, 46, 6], [0, 46, 6]], 15, n)),
    ("21e_nucleo", dict(INT, drop=["entorno"]), "El nucleo latiendo", dict(line=0.012, latido_cada=1),
     lambda n: cam([[-3.0, 32.0, 1.5], [3.0, 32.0, 1.8]], [NUCLEO, NUCLEO], 18, n)),
    ("21f_cenital", dict(EXT, catedral={"techo": False, "anexos": True, "suelo": 0}), "Cenital sin techo",
     dict(hora="00:40", line=0.05),
     lambda n: cam([[3.0, 26.0, 110.0], [-3.0, 22.0, 100.0]], [[0, 24.5, 0], [0, 24.5, 0]], 30, n)),
    ("21g_aguja", EXT, "La aguja de cerca, desde el aire", dict(hora="00:40", line=0.02),
     lambda n: cam([[14.0, -20.0, 56.0], [10.0, -22.0, 60.0]], [TORRE, TORRE], 24, n, k=LENTE_ALTO)),
    ("21h_libertador", EXT, "Desde Libertador", dict(hora="00:40", line=0.02),
     lambda n: cam([ojo(31, 22), ojo(30, 18)], [[8, 6, 18], [8, 6, 18]], 15, n)),
    ("21i_boveda", dict(INT, drop=["entorno"]), "Las bovedas y los vitrales", dict(line=0.012, latido_cada=1),
     lambda n: cam([[0, 20, 2], [0, 22, 2]], [[0, 22, 19], [0, 24, 19]], 14, n)),
    ("21j_dron", EXT, "El dron se aleja", dict(hora="00:40", line=0.04),
     lambda n: cam([[-40.0, -45.0, 34.0], [-90.0, -90.0, 60.0]], [[0, 20, 12], [0, 20, 12]], 24, n)),
]
for i, (nom, base, desc, kw, camf) in enumerate(FINAL):
    plano(nom, 76 + i, 77 + i, 12, base, desc, camara=camf, **kw)
# SALIDA: vuelve al primer cuadro (loop)
plano("22_salida", 86, 90, 12, EXT, "Campanas: el dron se aleja hasta el rio; termina en el primer cuadro",
      hora="19:40", line=0.2,
      camara=lambda n: cam([[-650.0, 190.0, 30.0], [-2300.0, 480.0, -24.0]], [[0, 20, 30], [0, 20, 30]], [40, 140], n, k=LENTE_RIO))


# ------------------------------------------------------------------ letra
LETRA = [  # (t0, t1, texto), de audio/letra_tiempos.json y de la escucha por tramos.
    # Despues de "(una palabra)" no se canta nada (lo corrigio quien escucho el corte)
    (62.4, 65.6, "En la barranca, sobre el río,"),
    (66.4, 69.4, "la catedral no duerme más."),
    (70.2, 74.0, "Bajo las tipas, el frío,"),
    (74.6, 77.8, "mil luces rezan sin parar."),
    (78.4, 82.0, "Nadie sabe por qué,"),
    (85.7, 90.2, "nadie sabe por qué..."),
    (95.4, 98.4, "Nunca se apagan, nunca se apagan,"),
    (98.4, 101.6, "guardan una palabra."),
    (103.7, 106.8, "Nunca se apagan, nunca se apagan,"),
    (106.8, 110.2, "la noche no les gana."),
    (123.0, 126.0, "Nunca se apagan, nunca se apagan,"),
    (126.0, 129.2, "guardan una palabra."),
    (131.3, 134.4, "Nunca se apagan, nunca se apagan,"),
    (134.4, 137.8, "la noche no les gana."),
    (146.4, 148.6, "Una palabra..."),
    (150.4, 152.3, "(una palabra)"),
]


def subs():
    out = []
    for t0, t1, txt in LETRA:
        palabras = txt.split()
        dur = max(0.4, (t1 - t0) * 0.7)
        reveal = [[round(t0 + dur * k / len(palabras), 3), " ".join(palabras[:k + 1])] for k in range(len(palabras))]
        clave = "palabra" in txt
        out.append({"t0": round(t0, 3), "t1": round(t1 + 0.25, 3), "fade_s": 0.18, "items": [{
            "font": "texto", "size": 60 if clave else 54, "outline": 8, "glow": 0.55 if clave else 0.4,
            "max_w": 0.86, "color": "#ff7ad9" if clave else "#e9fbff", "pos": [0.5, 0.87], "reveal": reveal}]})
    return out


# ------------------------------------------------------------------ armar
def armar(p):
    f0, f1 = corte(p["c0"]), corte(p["c1"]) if p["c1"] < 90 else FIN
    t0 = f0 / 24
    paso = 24 // p["fps"]
    assert (f1 - f0) % paso == 0, (p["nombre"], f1 - f0, paso)
    n = (f1 - f0) // paso
    j = json.loads(json.dumps(p["base"]))
    j.update({"_desc": p["desc"], "width": ANCHO, "height": ALTO, "fps": p["fps"], "frames": n, "samples": 8,
              "storyboard": [max(1, n // 2)], "_t": [round(t0, 3), round(f1 / 24, 3)]})
    if "hora" in p:
        j["hora"] = p["hora"]
        j["fecha"] = FECHA
    if "clima" in p:
        j["clima"] = p["clima"]
    j["line"] = {"radius": p.get("line", 0.02)}
    if p.get("orbita"):
        import math
        keys = []
        for k in range(9):
            a = -math.pi / 2 + 2 * math.pi * k / 8
            keys.append({"frame": 1 + round((n - 1) * k / 8),
                         "pos": [round(4.6 * math.cos(a), 3), round(35.6 + 4.6 * math.sin(a), 3), 2.2 + 0.6 * math.sin(2 * a)],
                         "aim": NUCLEO})
        j["camera"] = {"keys": keys, "lens": 22, "lens_keys": [[1, 22], [n, 22]], "ease": False, "clip_start": 0.05,
                       "clip_end": 3200}
    else:
        j["camera"] = p["camara"](n)
    if p.get("latido_cada"):
        j["servidores"] = dict(j.get("servidores", {}),
                               latido=latido(t0, n, p["fps"], p["latido_cada"], p.get("latido_fuerza", 1.0)))
    fr = lambda t: max(1, min(n, round((t - t0) * p["fps"]) + 1))  # noqa: E731
    post = {}
    if p.get("relampagos_t"):
        j["relampagos"] = [fr(t) for t in p["relampagos_t"]]
    if p.get("impacto_t"):
        a, b = p["impacto_t"]
        post["impacto"] = {"frames": [fr(a), fr(b)], "centro": [0.5, 0.42], "cada": 1}
        post["congelar"] = {"keys": [[fr(a) - 1, 0.0], [fr(b) + 1, 0.8], [fr(b) + 4, 0.0]]}
    if p.get("glitch_t"):
        post["glitch"] = [[fr(a), fr(b), g] for a, b, g in p["glitch_t"]]
    if p.get("datamosh_t"):
        a, b = p["datamosh_t"]
        post["datamosh"] = [[fr(a), fr(b), 0.8]]
    if p.get("speedlines"):
        post["speedlines"] = {"frames": [1, n], "count": 70, "band": [0.15, 0.85]}
    if post:
        j["post"] = post
    return j, n


def main():
    shots = EP / "shots"
    shots.mkdir(exist_ok=True)
    ext = 0
    costo, nombres, prev = 0.0, [], 0
    for p in P:
        j, n = armar(p)
        f0 = corte(p["c0"])
        assert f0 == prev, (p["nombre"], f0, prev)
        prev = corte(p["c1"]) if p["c1"] < 90 else FIN
        (shots / f"{p['nombre']}.json").write_text(json.dumps(j, indent=1, ensure_ascii=False), encoding="utf-8")
        nombres.append(p["nombre"])
        afuera = "entorno" in j and "entorno" not in j.get("drop", [])
        costo += n * (30 if afuera else 10) + 60
        ext += n if afuera else 0
    assert prev == FIN, prev
    (shots / "timeline.json").write_text(json.dumps({"name": "guardan_una_palabra", "fps_unique": 24, "fps_out": 24,
                                                     "shots": nombres, "subs": "subs.json"}, indent=1), encoding="utf-8")
    (shots / "subs.json").write_text(json.dumps(subs(), indent=1, ensure_ascii=False), encoding="utf-8")
    total = sum(armar(p)[1] for p in P)
    print(f"{len(P)} planos, {total} cuadros unicos ({ext} de afuera), render estimado {costo / 3600:.1f} h")


if __name__ == "__main__":
    main()
