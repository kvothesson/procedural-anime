# GUARDAN UNA PALABRA (video de la canción)

Video horizontal (1920×1080) de 3:00 para la canción "Guardan una palabra" (Suno, de Kvothesson, hecha a partir
del short `nunca_se_apagan`). Escenario: la Catedral de San Isidro llena de servidores
(`episodios/catedral`). La idea: **mostrar el motor mientras suena la canción**: cada sección
enseña una capa (lugar real, relieve, río, árboles por especie, servidores, hora, clima, estilo,
post), con cortes en el compás.

El audio no se sintetiza: es la canción (`~/Downloads/Guardan una palabra.mp3`, sin commitear),
pasada a `out/guardan_una_palabra.wav`; `montaje.py` la mezcla a -14 LUFS.

## La canción (`audio/`)

`audio/analizar.py`: voz separada con demucs, transcripción con faster-whisper, voz activa por
cuarto de segundo. Tempo: **120 bpm justos**, primer tiempo en 0,19 s, sin deriva (se midió la fase
en cuatro tramos). Compás = 2 s.

| Tiempo | Qué suena |
|---|---|
| 0:00-0:16 | Campanas y órgano |
| 0:16-0:48 | Coros sin letra ("ah"), crece |
| 0:48-1:02 | Primer pico instrumental |
| 1:02-1:18 | Verso: "En la barranca, sobre el río…" |
| 1:18-1:34 | "Nadie sabe por qué" ×2 |
| 1:34-1:50 | Estribillo |
| 1:50-2:24 | Coros fuertes y segundo pico |
| 2:24-2:32 | Puente: trueno, glitch, "Una palabra" ×2 |
| 2:32-2:52 | Estribillo final |
| 2:52-3:00 | Golpe final |

Whisper no transcribe bien la voz de Suno (en los coros inventa, y con la letra como pista la
repite donde no se canta): los tiempos de la letra salen de cruzar la voz activa, la
transcripción por tramos con el modelo `medium` y la estructura de la letra.

## Planos (`planos.py` los genera; no editar los JSON a mano)

Cortes en una grilla de 1/6 s (cuadro 4 + 48 por compás a 24 fps): sirve igual para planos en
cuatros (6 fps, las tomas lentas de afuera), en doses (12) y sakuga (24, la órbita al núcleo). El
timeline va a 24 únicos: `montaje.py` repite cuadros según el `fps` de cada plano.

| Compases | Planos | Muestra |
|---|---|---|
| 0-8 | Desde el río al atardecer; dron que sube la barranca | río de OSM, relieve SRTM, hora |
| 8-24 | Plaza Mitre bajo las tipas; la torre de la base a la aguja; cenital sin techo; las puertas se abren | árboles de la zona, catedral, `techo: false`, `puertas` |
| 24-31 | Un corte por compás adentro (racks, cables, vitrales, núcleo, coro, nave lateral, bóveda); los leds laten en cada pulso | servidores, `latido` |
| 31-39 | Cada verso con su imagen: barranca y río, fachada, tipas con niebla, la nave | clima |
| 39-47 | "Nadie sabe por qué": la nave quieta, latido lento | |
| 47-55 | "Nunca se apagan": la misma toma a ocho horas (07 a 05:45) | hora real |
| 55-63 | La misma toma: maqueta gris, estilo de día, de noche, lluvia, niebla | capa de estilo y clima |
| 63-72 | Órbita al núcleo a 24 fps; dolly rápido con líneas de velocidad; cenital bajando | sakuga, post |
| 72-76 | Tormenta con relámpagos en los truenos; "Una palabra": impact frames, congelado, datamosh | `relampagos`, post |
| 76-86 | Un corte por compás, lo mejor de noche | |
| 86-90 | El dron se aleja hasta el río: termina en el primer cuadro (loop) | |

## Criterio de aceptación

- Cada corte cae en un compás (o en un pulso); los leds laten con la música.
- La letra aparece solo donde se canta, palabra por palabra, abajo al centro; "palabra" en magenta.
- Cada capa del motor se ve al menos una vez y se entiende sin explicación: lugar real, hora,
  clima, estilo, adentro y afuera.
- El último cuadro es el primero (loop medido, diferencia media 0,0).
- 1920×1080, 3:00, audio presente (ffprobe).

## Bitácora

| Fecha | Qué se pidió | Qué se cambió |
|---|---|---|
| 2026-10-19 | Video de la canción mostrando el motor, letra solo en las frases cantadas | Análisis de la canción, 48 planos por compás, letra con `reveal`. Motor: `relampagos` [cuadros] en un plano pone los relámpagos de la tormenta donde se pidan (antes, al azar) |
| 2026-10-19 | ¿Por qué vertical? | Pasa a horizontal 1920×1080 (videoclip para YouTube; un Short vertical se recorta después del estribillo). Lentes abiertas ×0,75 (×0,62 en la torre y la fachada): el sensor cubre el lado largo. Motor: post y textos escalan con el lado corto, no con el ancho |
