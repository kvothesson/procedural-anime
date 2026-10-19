# AGENTS.md — PROCEDURAL ANIME

Shorts verticales estilo anime (cel-shading, línea de tinta, color plano, neón) hechos
**100 % con código**: Blender 5.2 headless + Python, banda sonora sintetizada. Sin IA que
genere imagen o video, sin samples de audio. Un agente de código (o una persona) corre todo el
pipeline; quien dirige lo hace con instrucciones.

**Al empezar:** leé este archivo, `docs/CAPAS.md` (qué va en cada capa: motor, piezas, datos de
un lugar, escenario, estilo, hora y clima, episodio; con recetas para crear y modificar cada
una) y `docs/PRODUCCION.md` (reglas, trampas de Blender 5.2, rendimiento, sonido y criterio de
dirección).
**Al terminar una sesión:** corregí `docs/PRODUCCION.md` si algo de lo que dice dejó de ser cierto.

---

## Mapa del repo

| Archivo | Para qué |
|---|---|
| [docs/CAPAS.md](docs/CAPAS.md) | **Cómo está organizado**: las capas, dónde vive cada una, recetas (nuevo lugar real, estilo, pieza, episodio que reusa un escenario) y propuestas pendientes |
| [episodios/README.md](episodios/README.md) | Índice de episodios y escenarios: qué es cada uno, estado, qué reusa de quién |
| [docs/PRODUCCION.md](docs/PRODUCCION.md) | **Todo lo aprendido**: look, reflejos, animación, post, rendimiento, trampas de Blender 5.2, sonido, criterio de dirección |
| [docs/AUSTRAL.md](docs/AUSTRAL.md) | Canon de la serie UNIVERSO AUSTRAL (el mundo, el Verbo, Rendous, reglas, personajes) |
| [motor/escena.py](motor/escena.py) | Entrada de Blender: lee el JSON, arma las piezas en orden (`PIEZAS`) y renderiza |
| [motor/piezas/](motor/piezas) | Las piezas: `base` (utilidades), `materiales`, `mundo` (cielo, luces, reflejo, tinta, cámara, render), `ciudad`, `plaza`, `obelisco`, `eventos` (apagón, destello), `colectivo`, `espacio`, `despiece` |
| [motor/piezas/mecanica.py](motor/piezas/mecanica.py) | Engranajes: dientes reales, tics, trabas, forcejeo, giro libre, ejes, diente que salta |
| [motor/piezas/andes.py](motor/piezas/andes.py) | Andes: una ruta (`camino.pts`) de la que sale todo: terreno con cresta y quebrada, cordillera, calzada de lajas, tambos con baliza, puente colgante, apacheta, luna |
| [motor/piezas/viaje.py](motor/piezas/viaje.py) | Mensaje de luz con estela por una ruta, un arco sobre la Tierra o puntos; `relevo` (enciende lo que tiene `relevo_s` al pasar); cámara `follow`; globo que gira (`arco.spin`) |
| [motor/piezas/tokio.py](motor/piezas/tokio.py) | Callejón bajo las vías: viaducto con tren, faroles de papel, expendedoras, farol hexagonal |
| [motor/piezas/catedral.py](motor/piezas/catedral.py) | Catedral de San Isidro a escala real (planta OSM): nave, crucero, ábside, bóvedas con nervios, torre con aguja; recorrible, `"techo": false` para la cenital |
| [motor/piezas/servidores.py](motor/piezas/servidores.py) | Servidores dentro de la catedral: filas de racks con leds que parpadean (un shader, un atributo por rack), cables, bandejas y el núcleo del crucero |
| [motor/piezas/entorno.py](motor/piezas/entorno.py) | Alrededores reales sobre el relieve: calles con veredas, plazas, vías, edificios extruidos (techos a dos aguas en casas) y árboles, desde `<ep>/data/entorno.json` |
| [motor/osm.py](motor/osm.py) | Baja OpenStreetMap y lo pasa a metros en el marco de la escena (`<ep>/data/osm.json` → `entorno.json`); completa alturas, casas faltantes y árboles marcados como `relleno`; con `huellas` suma edificios reales de Microsoft Global ML Building Footprints; con `terreno` baja la elevación (SRTM, tiles de Mapzen) y deja una grilla de alturas; con `bosque` pone árboles donde hay mucha pendiente (y `lejos`, la arboleda más allá del barrio); `agua` hunde el río de OSM bajo su cota; `alturas` fija edificios medidos; `monumentos` (puntos de OSM): `python motor/osm.py episodios/<ep>` |
| [motor/cielo.py](motor/cielo.py) | Hora del día y clima: el sol real del lugar (elevación y azimut por fecha y hora), cielo, luz, niebla, ventanas y reflectores según la altura del sol; climas `despejado`, `nublado`, `lluvia`, `niebla`, `tormenta` (relámpagos) |
| [motor/textos.py](motor/textos.py) | Texto 2D: `post.textos` por plano y subtítulos del corte (`timeline.subs`, con `reveal` palabra por palabra) |
| [motor/colision.py](motor/colision.py) | Traspasos entre mallas frame por frame (BVH, sin render): `python motor/colision.py episodios/<ep> <plano>` |
| [motor/engrane.py](motor/engrane.py) | Engrane sin penetración entre pares de engranajes, frame por frame |
| [motor/plano.py](motor/plano.py) | Carga de planos con `extends`/`drop`. Una sola implementación para escena, post, render y banda |
| [motor/render.py](motor/render.py) | **Un comando por plano**: Blender + verificación + post. `--draft`, `--frames` |
| [motor/storyboard.py](motor/storyboard.py) | **Hoja de storyboard**: uno o más cuadros clave por plano (`"storyboard": [frames]` en su JSON), con el post y la acción del plano, en `out/storyboard.png` |
| [motor/post.py](motor/post.py) | Composición 2D: ondas, brillo, `resplandor` (el aire que se tiñe alrededor de una fuente de color), lluvia, líneas de velocidad, `glitch`, `datamosh`, `impacto` (impact frames con líneas de foco), `congelar` (tiempo detenido), aberración, grano, encode. Los objetos `ancla` quedan fuera del glitch, el datamosh y el congelado |
| [motor/montaje.py](motor/montaje.py) | Pega los planos del `timeline.json` (cadencias mezcladas: cada plano declara su `fps`, 12 en doses o 24 el sakuga) y mezcla el `.wav` a -14 LUFS |
| [motor/audio/dsp.py](motor/audio/dsp.py) | Primitivas de síntesis: aditiva con límite de banda, campanas, pads, reverb por convolución |
| `episodios/<ep>/shots/*.json` | Los planos. `timeline.json` = orden del montaje |
| `episodios/<ep>/banda.py` | Partitura y diseño sonoro del episodio (a medida) |
| `episodios/<ep>/planos.py` | (Opcional) Generador de los JSON de planos cuando hay muchas cámaras y poses calculadas; conviene que chequee el encuadre (ver `episodios/duende_rojo/planos.py`) |
| `episodios/<ep>/render/`, `out/` | Frames y videos (ignorados por git: se regeneran desde los JSON) |

**Episodio de ejemplo y plantilla: `episodios/nodo_404/`.** Otro episodio completo, con voces
reales y subtítulos: `episodios/chasqui_relevo/`.

## Requisitos

Blender 5.2 (EEVEE), Python 3.13 con `pip install -r requirements.txt`, y `ffmpeg` en el PATH.
Blender se busca en la variable `BLENDER`, en el PATH o en `C:/Program Files/Blender Foundation`.
Desarrollado y probado en Windows; en otros sistemas debería andar, pero no está probado.

## Comandos

```bash
python motor/render.py episodios/<ep> <plano> --frames 1 40 72   # prueba: frames sueltos + lámina en out/_prueba_<plano>.png
python motor/render.py episodios/<ep> <plano> --draft            # borrador 540x960 en _draft_<plano> (no pisa el final)
python motor/storyboard.py episodios/<ep>                        # storyboard: cuadros clave de todos los planos -> out/storyboard.png
python motor/render.py episodios/<ep> <plano>                    # plano final + post + mp4 del plano
python motor/post.py   episodios/<ep> <plano> --frames 1 3       # solo retocar post (segundos)
python episodios/<ep>/banda.py                                   # banda de sonido + medición RMS
python motor/montaje.py episodios/<ep>                           # corte final con sonido + chequeo del loop
```

Renders largos: en segundo plano y **uno por vez** si tenés poca VRAM (con 2 GB, dos Blender a
la vez se cuelgan).

## Cómo se hace un video nuevo

1. **Diseño en conversación** con quien dirige: idea en una línea, tabla plano por plano (tiempo,
   plano, qué pasa), reglas de look y sonido. Proponer un lugar **real y reconocible**. Pedir
   foto de referencia si existe. No construir sin una confirmación.
2. **Carpeta** `episodios/<ep>/` con `shots/`, `timeline.json` y un `README.md` del episodio.
3. **Prototipá el riesgo primero:** el plano más difícil, con 1-3 frames de prueba. Mirar cada
   PNG. Recién con el look aprobado, el resto.
4. **Reutilizá escenas con `extends`** (un plano hereda de otro y pisa lo que cambia).
5. **Storyboard antes de renderizar planos enteros** (`motor/storyboard.py`): con el riesgo
   aprobado, armar todos los planos (cámara, poses, tiempos), marcar en cada JSON sus cuadros
   clave (`"storyboard": [frames]`) y mostrar la hoja a quien dirige. Ahí se aprueban historia,
   encuadres y acciones; corregir un encuadre cuesta un frame, no un plano. Si los planos salen
   de un generador, que proyecte a los personajes a pantalla y avise si quedan afuera o al borde.
6. **Cada plano**: criterio de aceptación escrito en el README del episodio (qué se tiene que
   ver y en qué cuadro) → frames de prueba de los cuadros clave → corregir → plano entero en
   segundo plano → lámina de contacto con 4-6 frames → mostrar el resultado con lo que quedó
   flojo, sin maquillar. Si hay contacto entre mallas, `motor/colision.py` antes de aprobar.
   Las correcciones van de a un plano: se corrige y se sigue con el siguiente, y cada una se
   anota en la bitácora del README del episodio (plano, qué se pidió, qué se cambió), para no
   repetirla. Lo que generaliza pasa a `docs/PRODUCCION.md`.
7. **Loop**: el último cuadro del último plano = el primero del primero (cámara, **lente**, pose y
   estado de cada luz). Verificarlo midiendo (diferencia media 0.0 sobre los frames crudos).
8. **Sonido** (`banda.py`): eventos anclados a (plano, frame). Leer la curva RMS que imprime;
   medir el pico de los silencios.
9. **Montaje** → mostrar el corte → correcciones → publicar solo con confirmación de
   visibilidad y metadatos. Un plano o un corte no está terminado sin evidencia: frames
   revisados, y con `ffprobe` duración, 1080×1920 y pista de audio presente.

## El JSON de un plano (lo que entiende `escena.py`)

| Clave | Qué arma |
|---|---|
| `width`, `height`, `fps`, `frames`, `samples` | Render (1080×1920, 12 fps únicos → 24 fps en doses, 8 muestras) |
| `extends`, `drop` | Hereda otro plano; `drop` borra claves heredadas |
| `estilo` | Nombre de `<ep>/estilos/<nombre>.json`: el look entero (cielo, luces, tinta, toon, post y colores de cada pieza en `piezas`). Va debajo del plano; un estilo puede heredar de otro (`extends`); cambiar el look = cambiar una palabra |
| `hora`, `fecha`, `clima`, `lugar`, `interior` | Hora del día y clima (ver `motor/cielo.py`): van encima del estilo y debajo de lo que el plano fija. `lugar` {lat, lon, rumbo_deg, utc} o la `georef` de los datos del entorno; un plano o estilo con `"interior": true` no recibe lluvia ni cambia de cielo. Un estilo puede traer su paleta por altura del sol en `horas` |
| `storyboard` | Cuadros clave del plano para `motor/storyboard.py` (si no está, el del medio) |
| `mascara_anclas` | Segunda pasada solo con los objetos `ancla`: máscara exacta para que el post (congelar, glitch) no los toque |
| `render_list`, `render_frames`, `still` | Frames sueltos / rango / un solo frame copiado |
| `sky`, `fog`, `toon`, `lights`, `line`, `perf` | Cielo con resplandor, niebla, rampa toon, soles, tinta, perfil GPU |
| `street` | Asfalto mojado con charcos (`puddles`, `spots`), veredas, línea central con huecos |
| `blocks` | Hileras de edificios a los lados: balcones, cornisa, ventanas por shader, vidrieras, carteles de terraza, pantallas de fachada |
| `row_x` | Hilera de frente que cierra el fondo (con hueco de calle) |
| `skyline` | Megatorres lejanas con balizas |
| `lamps`, `cables` | Faroles con cono de luz, cables entre fachadas |
| `plaza`, `trees`, `flag` | Plaza oval (pasto, camino, cantero), árboles estilo anime, mástil con bandera que ondea |
| `obelisco` | Obelisco + reflectores + anillos holográficos + cristal hexagonal + resplandores (`glow`) |
| `colectivo` | Colectivo flotante con recorrido |
| `engranajes` | Engranajes de relojería (`list` con `r`, `teeth`, `step`/`spin`, `stop`, `strain`, `free`, `salta`, `axle`, `ghost`) |
| `luz_mala` | Destello verde en frames dados |
| `blackout` | Apagón en cascada o reencendido (`mode: "on"`), latido del cristal |
| `camera` | `from`/`to` lineal o `keys` con `ease`; `lens_keys` [[frame, mm]] cambia la lente |
| `catedral` | Catedral de San Isidro (`techo`, `anexos`, `suelo`, `colores`, `vidrios` con `luz`, `traceria`, `reflectores` puntuales o en cono, `brillos`, `puertas`, `rayos`, `niebla_piso`) |
| `servidores` | Racks, cables y núcleo dentro de la catedral (`colores`, `leds`, `nucleo`, `luces`, `filas`) |
| `entorno` | Alrededores de OSM sobre el relieve (`datos`, `terreno`, `piso`, `radio`, `relleno`, `arboles`, `escala_arboles`, `arboles_finos`, `quitar_arboles`, `lejos`, `agua`, `colores` (con `copa_<especie>`: tipa, fresno, liquidambar, jacaranda, platano, paraiso, tilo, monte, lejos), `ventanas`, `faroles` con cables) |
| `post` | `glow`, `rain` (`false` la apaga), `rain_dim`, `ripples`, `speedlines`, `glitch`, `grain`, `textos`, ... |
| `camino`, `terreno`, `cordillera`, `puente`, `tambos`, `apacheta`, `luna` | Andes (ver `piezas/andes.py`): todo se ubica por `s`, metros sobre la ruta |
| `mensaje`, `relevo` | Mensaje de luz (o lista de mensajes) con `keys` [[frame, s]], `colors` por tramo, `from_frame`/`to_frame`, `frac`; `relevo` lo enciende todo a su paso (`lead`, `delay`, `off`) |
| `viaducto`, `chochin`, `expendedoras`, `farol_hex` | Tokio (ver `piezas/tokio.py`) |
| `font` | Ruta a una fuente para los textos 3D (si no, Bahnschrift en Windows o la de Blender) |

Todas las claves son opcionales (sin `street` no hay piso mojado ni reflejo; sin `sky` va un
cielo nocturno por defecto).

**Agregar un elemento nuevo:**
- Reutilizable entre episodios → una función `build_<cosa>(e, colls)` en el módulo que
  corresponda de `motor/piezas/` (o uno nuevo) + una fila en `PIEZAS` de `escena.py`.
  **El orden de `PIEZAS` importa:** fija los nombres de objetos y, con ellos, el azar del
  apagón. Agregar al final; no reordenar sin volver a comparar frames.
- Solo de un episodio → `episodios/<ep>/piezas.py` con `PIEZAS = [("clave", build_fn)]`.
  Se arma después de las del motor y puede importar de `piezas.*`.
- Las piezas leen la config global en `piezas.ctx` (`ctx.CFG`, `ctx.FOG`, ...).
- **Antes de un motor o una técnica nueva**, escribir en el README del episodio por qué no
  alcanza lo que hay. Si no se puede decir, se itera sobre el motor actual.

## Qué decide el humano

- La idea, el lugar y el juicio estético (si un plano "transmite").
- El ritmo y la sincronía música/imagen. Un agente no puede escuchar: mide el RMS, pero qué
  suena bien lo juzga una persona.
- Visibilidad y metadatos antes de publicar. Las credenciales nunca las ingresa el agente.
