# CHASQUI, PRESENTACIÓN (horizontal)

Video horizontal (1920×1080, ~60 s) que presenta [chasqui](https://github.com/kvothesson/chasqui).
Reusa el mundo de [El relevo](../chasqui_relevo/README.md): el mensaje de luz corre el camino
inca y **cada tambo que enciende es una función de la app**, con su tarjeta y una captura
real de la ventana. Textos en español. Hielo = español, violeta = japonés (los colores de la app).

## Planos (~62 s, 1920×1080, 12 fps únicos → 24 fps en doses)

| # | JSON | Dur. | Qué pasa |
|---|---|---|---|
| 1 | `01_apacheta` | 6 s | El cristal late. "Hace 500 años, los chasquis corrían los Andes llevando mensajes." Sale el mensaje |
| 2 | `02_puente` | 4 s | La luz cruza el puente y pasa de hielo a violeta (cuadro 23 = entra la voz japonesa real) |
| 3 | `03_orbita` | 5 s | Círculo máximo Cusco → Tokio sobre la Tierra de noche |
| 4 | `04_tokio` | 8 s | Callejón bajo las vías; el farol recibe y la respuesta sale en español (cuadro 38) |
| 5 | `05_tambos` | 25 s | Cinco tambos, cinco funciones (tabla abajo) |
| 6 | `06_ida_vuelta` | 7 s | Dos luces, hielo y violeta, se cruzan sobre el puente. "Las dos voces, al mismo tiempo." |
| 7 | `07_cierre` | 8 s | Vuelve a la apacheta: "Hoy cruzan idiomas.", wordmark, `pip install chasqui-translate`, GitHub. Loop al cuadro 1 |

Los planos 2, 3 y 4 salen de los de El relevo, con la lente ×1,4 (el sensor va al alto). Las
voces irán como en El relevo (`voces.json`): la ida arranca en el segundo ~5,1 y la vuelta
en el ~14,95, que es donde caen los mismos cuadros.

### Tambos (plano `05_tambos`, 300 cuadros)

La cabeza va de s=100 a s=240; el tambo k enciende con la cabeza a 14 m, y ahí entra su tarjeta.
La tarjeta va del lado contrario al tambo (alternan).

| # | Tambo (s) | Entra (cuadro) | Función | Captura |
|---|---|---|---|---|
| 1 | 120 | 16 | Videollamadas, ida y vuelta (headset) | `ui_headset.png` (en ruta, dos turnos reales) |
| 2 | 146 | 71 | Videos y streams (media) | `ui_media.png` |
| 3 | 171 | 125 | Micrófono virtual | `ui_mic.png` |
| 4 | 201 | 189 | 12 idiomas | `ui_idiomas.png` (la lista desplegada) |
| 5 | 231 | 253 | Tu clave, tu costo (BYOK + medidor) | `ui_costo.png` (la forma compacta, con el gasto) |

Los tambos van con `"terraza": true`: un andén de pirca baja de la casa (y del poste) hasta la
ladera. Sin eso la casa quedaba en el aire donde la cresta cae (`_vista_tambo` vs
`_vista_tambo_sin`). En El relevo sigue apagado, así el publicado no cambia.

**Copy honesto:** no se dice "funciona en Meet" (esa prueba está pendiente en chasqui), y son
**12 idiomas**, los que ofrece la app (`LANG_NAMES`), no "más de 70". Los
turnos de las capturas son salidas reales de chasqui (tomas `ida_c` y `vuelta_f` de El relevo).

## Reconstruir todo

```bash
sh episodios/chasqui_presenta/render_todo.sh       # 7 planos, uno por vez (~30 min con 2 GB de VRAM)
for s in 01_apacheta 02_puente 03_orbita 04_tokio 05_tambos 06_ida_vuelta 07_cierre; do
  python motor/post.py episodios/chasqui_presenta $s --no-video
done
python episodios/chasqui_presenta/banda.py         # musica + voces reales de El relevo
python episodios/chasqui_presenta/subs.py          # subtitulos desde las transcripciones
python motor/montaje.py episodios/chasqui_presenta # corte + subtitulos + chequeo del loop
```

Corte del 2026-10-20: `out/chasqui_presenta.mp4`, 1920×1080, 63,0 s, con audio; loop 0,00/255.

## Capturas

`capturas/captura_ui.py <adapter> <salida.png> [running] [idiomas] [compacta]` abre la ventana real de `chasqui ui`
(con chasqui instalado), elige el modo, pone es/ja, inyecta los dos turnos reales y captura la
ventana con su barra de título (DWM, sin la sombra). No guarda las preferencias del usuario.

## Criterio de aceptación

- 1 (cuadro 40): la apacheta y el cristal a la izquierda, el camino al puente al fondo; el texto
  abajo, legible, sin tapar el cristal.
- 5 (cuadro 45): el tambo 1 encendido en cuadro, la luz en el camino; de un lado "01 / 05" y
  el título; del otro la captura nítida, con borde hielo, sin tapar la luz.
- 7 (cuadro 70): wordmark, bajada, `pip install` y GitHub legibles, sin chocar con la apacheta.
- Montaje: último cuadro = primero (diferencia 0.0); `ffprobe` 1920×1080, ~60 s, con audio.

## Bitácora

| Plano | Pedido | Cambio |
|---|---|---|
| 07 | (revisión propia) El wordmark pisaba la bajada y todo tapaba la apacheta | Bloque de título a la derecha (x 0,70), alturas recalculadas con el margen del halo |
| 05 | (revisión propia) La tarjeta tapaba el tambo encendido | Tarjeta del lado contrario al tambo (alternan con `side`); texto subido al cielo |
| 05 | (revisión propia) Texto alineado a la izquierda salía corrido y con renglones centrados | `textos.py`: `align` alinea cada renglón y descuenta el margen del halo (solo lo usa este episodio) |
| 01 | (revisión propia) El texto rozaba las piedras | x 0,70 |
| 05 | Las casas flotan: tocan el camino pero están en una ladera | `andes.py`: `alturas()` sale de `build_terreno` y los tambos con `terraza` bajan hasta el terreno |
| 02, 06 | (storyboard) En horizontal el puente quedaba chico y la mira apuntaba al fondo de la quebrada | Lente 38 / 36 y mira subida al tablero del puente |
| 05 | (revisión propia) "Más de 70 idiomas" no es cierto | "12 idiomas"; se saca "detecta el idioma solo" (no verificado) |

Ojo: `render.py --frames` arma la lámina **sin post**; para ver textos y capturas, copiar los
`f_*.png` de `render/_prueba_<plano>/` a `render/<plano>/` y correr `post.py --frames N N`,
o usar `motor/storyboard.py`, que sí aplica el post.
