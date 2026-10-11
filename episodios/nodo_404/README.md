# NODO 404

Buenos Aires del futuro, de noche y con lluvia. El Obelisco tiene un cristal hexagonal que
late. La ciudad se apaga cuadra por cuadra; en el negro solo queda el cristal y, al fondo de la
avenida, la Luz Mala silba. Después todo vuelve a encenderse y la cámara baja hasta el charco
donde empezó. Loop exacto.

Publicado el 2026-10-10: https://youtube.com/shorts/0enpupe-v6Y

## Planos (34 s, 1080×1920, 12 fps únicos → 24 fps en doses)

| # | Plano | JSON | Dur. | Qué pasa |
|---|---|---|---|---|
| 1 | Charco | `01_charco` (extends 07, `still`) | 3 s | El cristal reflejado; cae una gota, ondas, lluvia picando el agua |
| 2 | Calle | `02_calle` | 6 s | Avance a ras del piso: edificios crema con balcones, faroles, vidrieras, charcos |
| 3 | Colectivo | `03_colectivo` (extends 02) | 4 s | Colectivo flotante 404 cruza con líneas de velocidad |
| 4 | Contrapicado | `04_contrapicado` (extends 06) | 6 s | Órbita al pie del Obelisco: anillos, torres con pantallas, bandera |
| 5+6 | Apagón | `06_apagon` | 8 s | Plaza de la República; cascada de apagón, glitch, negro, cristal latiendo, Luz Mala |
| 7 | Reencendido | `07_reencendido` (extends 06) | 7 s | La ciudad se enciende desde el Obelisco; la cámara baja al charco del plano 1 |

La escena base de la plaza es `06_apagon.json`; 01, 04 y 07 heredan de ella. La calle base es
`02_calle.json`. El empalme 07 → 01 se verifica midiendo (diferencia media 0.0).

## Sonido (`banda.py`)

| Plano | Música | Sonido |
|---|---|---|
| 1 | Bajo en Re bajo la lluvia | Gota + campana de cristal (La5, Mi6) |
| 2 | Re menor 9, contenido | Lluvia, rumor de ciudad, zumbido eléctrico |
| 3 | Si♭maj7(#11) | Colectivo con Doppler real, paneo izquierda → derecha |
| 4 | Fa/La → Do sus2 + arpegio pentatónico que crece | |
| 5+6 | Re menor 9 a pleno → filtro que se cierra → **corte seco** | Relés que se acercan, glitch, silencio; latido + campana por pulso; silbido de la Luz Mala |
| 7 | Bandoneón en Re menor, golpe grave → **Re mayor** con el motivo del cristal | Relés del centro hacia afuera, subida |

Curva medida: planos 3-4 ≈ −14,5 dB → apagón −8,6 → negro −27 → golpe −7,7 → final −11,1
(arranque −10,8).

## Reconstruir todo

```bash
for s in 02_calle 03_colectivo 04_contrapicado 06_apagon 07_reencendido 01_charco; do
  python motor/render.py episodios/nodo_404 $s
done
python episodios/nodo_404/banda.py
python motor/montaje.py episodios/nodo_404
```

~20 minutos en la PC de producción (el 01 se renderiza aparte: es la escena del 07 sin
apagón y con la cámara de su último cuadro; `montaje.py` mide el empalme y avisa si se rompe).
