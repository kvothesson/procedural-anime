# DUENDE ROJO

Publicado el 2026-10-14: https://youtube.com/shorts/Tgr1W6OtBoU (versión final). Versiones
anteriores en `meta.json` (`versiones_anteriores`): la primera tenía un salto entre el 07 y el 08;
la segunda, un techo de la calle techada que no se leía desde arriba.

**UNIVERSO AUSTRAL.** Canon: [docs/AUSTRAL.md](../../docs/AUSTRAL.md).

Nyx, el dron que siempre llega medio segundo tarde, quiere ver un duende rojo (un *red
sprite*), algo que dura tres milisegundos. Mirando no puede. Lo logra cuando deja de
reaccionar y aprende a escuchar la tormenta: el rayo que dispara al duende se oye en radio
(VLF) milisegundos antes, y la tormenta tiene un ritmo.

## Ficha

| | |
|---|---|
| Duración | ~55 s, 1080×1920; el duende (07) a 24 fps únicos, el resto en doses |
| Lugar real | Capilla del Monte, Córdoba: la calle techada con el arco "Pueblo Uritorco" y el cerro Uritorco detrás (foto de referencia de quien dirige; no está en el repo) |
| Elenco | Nyx (protagonista) y Vesper |
| Sonido | Tormenta en radio VLF sintetizada (*sferics*, *tweeks*, *whistlers*), bandoneón mínimo, sin trueno: a cientos de km no se oye. El 07 es casi silencio |

## Física que manda

- El duende sale a 50-90 km de altura sobre una tormenta lejana, en cielo despejado. Arriba
  es rojo (nitrógeno); las puntas de los tentáculos, azuladas. Primero un halo difuso; después
  cabezas que bajan y se abren en tentáculos con cuentas brillantes.
- Desde la calle techada, el Uritorco tapa el horizonte hasta ~10° (azimut 61°, a 5,7 km). Un
  duende **asoma sobre el cerro solo si la tormenta está a 150-300 km** en esa dirección
  (base a 8-18°, cima a 15-30°). Más lejos queda detrás del cerro.

## Plano por plano

| # | Tiempo | Qué pasa |
|---|---|---|
| 01 | 0–4 | Primer plano de una lente de Nyx que se abre, con la calle techada reflejada; la cámara se abre al arco y al Uritorco. En el fondo, un duende de **un solo cuadro** que Nyx no ve (para la segunda vuelta del loop) |
| 02 | 4–9 | Nyx y Vesper posados en el arco. Nyx abre las alas como antenas: chasquidos de radio. Vesper cuenta los relámpagos con su llama |
| 03 | 9–15 | Primer intento: chasquido y destello en el horizonte en el mismo cuadro; Nyx gira tarde. Cielo vacío y un resto rojo pintado |
| 04 | 15–20 | Segundo intento, igual. Vesper proyecta el registro de los chasquidos: hay un ritmo |
| 05 | 20–28 | Nyx apaga las lentes y escucha. La banda se vuelve el ritmo |
| 06 | 28–30 | Nyx gira **antes** del chasquido (giro en seco, un solo intermedio) |
| 07 | 30–42 | **El duende.** Hit-stop en silencio (0,12 s) → impact frames rojo/negro (0,5 s: los 3 ms reales) → cámara lenta (halo, cabezas que bajan) → corte a las lentes de Nyx con el duende reflejado → los tentáculos abiertos, el pueblo teñido de rojo → se apaga en un cuadro |
| 08 | 42–47 | Pausa. Nyx mira el cielo vacío: esta vez lo vio |
| 09 | 47–55 | Un punto rojo nuevo en el mapa de Vesper, junto a la luz mala de NODO 0. Se van. Nyx cierra las lentes: el último cuadro es la lente cerrada (loop con el 01) |

## Tecnología ↔ folklore

| Tecnología | Folklore |
|---|---|
| Sprite | El Duende del folklore del norte: aparece un instante y desaparece |
| Receptor VLF de Nyx | La lechuza que escucha |
| El rayo que dispara al duende | La copla de la tormenta que "anda buscando" |
| El punto rojo en el mapa | La luz mala de NODO 0 |

## Idea para después: pronóstico de duendes

No se puede predecir **el** duende, pero sí las noches favorables: tormenta fuerte a 150-300 km
al noreste (azimut ~45-77°), rayos reales en esa zona (satélite GOES-19, sensor de rayos, datos
públicos de NOAA), cielo despejado en Capilla del Monte y sin luna. Una página que se actualice
sola cada tarde ("¿Hay duendes esta noche sobre el Uritorco?"), con registro de lo que pasó
de verdad, siempre como "noche favorable" y nunca como promesa. Primera mirada (13 al 19 de
octubre de 2026, un solo modelo, Open-Meteo): ninguna noche favorable. La temporada es de
noviembre a marzo.

## Estado

Corte completo: `out/duende_rojo.mp4`, 54 s, 1080×1920, 24 fps (el 07 a 24 únicos, el resto en
doses), AAC 48 kHz a -14 LUFS. Loop 09 → 01 medido: 0,00/255. Hit-stop: silencio exacto.

Planos: `01_lente` … `06_antes`, `08_pausa`, `09_mapa` salen de `planos.py` (cámaras y poses
calculadas en el marco de la calle, con chequeo de encuadre); `07_duende`, `07_lentes`,
`07_hombro` son a mano. Storyboard: `python motor/storyboard.py episodios/duende_rojo`.

Pruebas: `_duende.json` (el duende solo sobre el Uritorco), `_calle.json` (la calle techada de
noche con el duende), `_hombro.json`. Piezas: `uritorco`, `tormenta`, `duende` (halo, campana,
descargas con filamentos, cuentas, luz roja), `calle` (fachadas, arco con el cartel, techado,
cables, faroles, árbol), `nyx` y `vesper` con material de noche, `reflejo`.

```bash
python motor/render.py episodios/duende_rojo 07_duende
python episodios/duende_rojo/banda.py
python motor/montaje.py episodios/duende_rojo
```
