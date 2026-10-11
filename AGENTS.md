# AGENTS.md — PROCEDURAL ANIME

Shorts verticales estilo anime (cel-shading, línea de tinta, color plano, neón) hechos
**100 % con código**: Blender 5.2 headless + Python, banda sonora sintetizada. Sin IA que
genere imagen o video, sin samples de audio. Un agente de código (o una persona) corre todo el
pipeline; quien dirige lo hace con instrucciones.

**Al empezar:** leé este archivo y `docs/PRODUCCION.md` (reglas, trampas de Blender 5.2,
rendimiento, sonido y criterio de dirección).
**Al terminar una sesión:** corregí `docs/PRODUCCION.md` si algo de lo que dice dejó de ser cierto.

---

## Mapa del repo

| Archivo | Para qué |
|---|---|
| [docs/PRODUCCION.md](docs/PRODUCCION.md) | **Todo lo aprendido**: look, reflejos, animación, post, rendimiento, trampas de Blender 5.2, sonido, criterio de dirección |
| [motor/escena.py](motor/escena.py) | Entrada de Blender: lee el JSON, arma las piezas en orden (`PIEZAS`) y renderiza |
| [motor/piezas/](motor/piezas) | Las piezas: `base` (utilidades), `materiales`, `mundo` (cielo, luces, reflejo, tinta, cámara, render), `ciudad`, `plaza`, `obelisco`, `eventos` (apagón, destello), `colectivo`, `espacio`, `despiece` |
| [motor/piezas/mecanica.py](motor/piezas/mecanica.py) | Engranajes: dientes reales, tics, trabas, forcejeo, giro libre, ejes, diente que salta |
| [motor/colision.py](motor/colision.py) | Traspasos entre mallas frame por frame (BVH, sin render): `python motor/colision.py episodios/<ep> <plano>` |
| [motor/engrane.py](motor/engrane.py) | Engrane sin penetración entre pares de engranajes, frame por frame |
| [motor/plano.py](motor/plano.py) | Carga de planos con `extends`/`drop`. Una sola implementación para escena, post, render y banda |
| [motor/render.py](motor/render.py) | **Un comando por plano**: Blender + verificación + post. `--draft`, `--frames` |
| [motor/post.py](motor/post.py) | Composición 2D: ondas, brillo, lluvia, líneas de velocidad, glitch, aberración, grano, encode |
| [motor/montaje.py](motor/montaje.py) | Pega los planos del `timeline.json` y mezcla el `.wav` |
| [motor/audio/dsp.py](motor/audio/dsp.py) | Primitivas de síntesis: aditiva con límite de banda, campanas, pads, reverb por convolución |
| `episodios/<ep>/shots/*.json` | Los planos. `timeline.json` = orden del montaje |
| `episodios/<ep>/banda.py` | Partitura y diseño sonoro del episodio (a medida) |
| `episodios/<ep>/render/`, `out/` | Frames y videos (ignorados por git: se regeneran desde los JSON) |

**Episodio de ejemplo y plantilla: `episodios/nodo_404/`.**

## Requisitos

Blender 5.2 (EEVEE), Python 3.13 con `pip install -r requirements.txt`, y `ffmpeg` en el PATH.
Blender se busca en la variable `BLENDER`, en el PATH o en `C:/Program Files/Blender Foundation`.
Desarrollado y probado en Windows; en otros sistemas debería andar, pero no está probado.

## Comandos

```bash
python motor/render.py episodios/<ep> <plano> --frames 1 40 72   # prueba: frames sueltos + lámina en out/_prueba_<plano>.png
python motor/render.py episodios/<ep> <plano> --draft            # borrador 540x960 en _draft_<plano> (no pisa el final)
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
5. **Cada plano**: frames de prueba → corregir → plano entero en segundo plano → lámina de
   contacto con 4-6 frames → mostrar el resultado con lo que quedó flojo, sin maquillar.
6. **Loop**: el último cuadro del último plano = el primero del primero. Verificarlo midiendo
   (diferencia media 0.0 sobre los frames crudos).
7. **Sonido** (`banda.py`): eventos anclados a (plano, frame). Leer la curva RMS que imprime.
8. **Montaje** → mostrar el corte → correcciones → publicar solo con confirmación de
   visibilidad y metadatos.

## El JSON de un plano (lo que entiende `escena.py`)

| Clave | Qué arma |
|---|---|
| `width`, `height`, `fps`, `frames`, `samples` | Render (1080×1920, 12 fps únicos → 24 fps en doses, 8 muestras) |
| `extends`, `drop` | Hereda otro plano; `drop` borra claves heredadas |
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
| `camera` | `from`/`to` lineal o `keys` con `ease` |
| `post` | `glow`, `rain`, `rain_dim`, `ripples`, `speedlines`, `glitch`, `grain`, ... |
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

## Qué decide el humano

- La idea, el lugar y el juicio estético (si un plano "transmite").
- El ritmo y la sincronía música/imagen. Un agente no puede escuchar: mide el RMS, pero qué
  suena bien lo juzga una persona.
- Visibilidad y metadatos antes de publicar. Las credenciales nunca las ingresa el agente.
