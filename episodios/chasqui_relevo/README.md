# EL RELEVO (chasqui)

Short para [chasqui](https://github.com/kvothesson/chasqui), traductor simultáneo en tiempo
real. Los chasquis corrían el Qhapaq Ñan llevando mensajes de posta en posta; acá el mensaje es
una luz que sale de una apacheta en los Andes, cruza el puente de soga, corre el camino
encendiendo los tambos, atraviesa el Pacífico y llega a un callejón de Tokio. La respuesta
vuelve por el mismo camino. Loop exacto.

Publicado el 2026-10-11: https://youtube.com/shorts/FaAWaL6D5Vg

**Las voces y los subtítulos son la salida real de chasqui** (no actuada ni corregida): ver
`voz/`. Hielo = español, violeta = japonés, los mismos colores de la app.

## Planos (30 s, 1080×1920, 12 fps únicos → 24 fps en doses)

| # | Plano | JSON | Dur. | Qué pasa |
|---|---|---|---|---|
| 1 | Apacheta | `01_apacheta` (extends `andes_base`) | 3 s | El cristal late; destello; sale el mensaje |
| 2 | Puente | `02_puente` | 4 s | Q'eswachaka. A mitad del puente la luz pasa a violeta: frame 23 = entra la voz japonesa real |
| 3 | Camino | `03_camino` | 4 s | Cámara que sigue al mensaje; cada tambo enciende su baliza |
| 4 | Órbita | `04_orbita` | 5 s | Círculo máximo Cusco → Tokio sobre la Tierra de noche (el globo gira, la cámara queda quieta) |
| 5 | Tokio | `05_tokio` | 8 s | Callejón bajo las vías, lluvia, tren. El farol hexagonal recibe; la respuesta; frame 38 = entra el español real, el farol pasa a hielo y la luz sube |
| 6 | Cierre | `06_cierre` (extends `andes_base`) | 6 s | La respuesta baja al cristal; título; la cámara termina en el primer cuadro del plano 1 |

`andes_base.json` es el mundo andino entero (ruta, terreno, puente, tambos, apacheta).
`_vista.json` es una vista aérea de prueba; no entra al montaje.

## Voces (`voz/`)

`voz/grabar.py` sintetiza la frase original (TTS) y la pasa por el `Pipeline` de chasqui a
velocidad real, guardando la salida ubicada por tiempo de llegada y cada delta de
transcripción. Tomas usadas (las únicas versionadas):

| Toma | Original | Lo que devolvió chasqui |
|---|---|---|
| `ida_c` (es→ja) | Hola, ¿llegaste bien a Tokio? Te extraño. | こんにちは。無事に東京に着きましたか。寂しいです。 |
| `vuelta_f` (ja→es) | もしもし。東京に着いたよ。こっちは雨だけど、元気だよ。 | Hola. Ya llegué a Tokio. Aquí está lloviendo, pero estoy bien. |

Se grabaron otras siete tomas y se descartaron porque el modelo *respondió* o inventó en vez
de traducir (`¿Llegaste bien?` → 「ついに着いたよ」, "llegué al albergue"): la deriva
conversacional que documenta chasqui. Frases más largas, con más contexto, derivan menos.
Demora medida: la traducción arranca ~1,6 s después del original y se superponen.

`voces.json` dice en qué segundo del corte cae cada toma; lo leen `banda.py` y `subs.py`, así
audio y texto no se pueden desfasar.

## Reconstruir todo

```bash
sh episodios/chasqui_relevo/render_todo.sh          # 6 planos, uno por vez (~10 min)
for s in 01_apacheta 02_puente 03_camino 04_orbita 05_tokio 06_cierre; do
  python motor/post.py episodios/chasqui_relevo $s --no-video
done
python episodios/chasqui_relevo/banda.py            # musica sintetizada + voces reales
python episodios/chasqui_relevo/subs.py             # subtitulos desde las transcripciones
python motor/montaje.py episodios/chasqui_relevo    # corte + subtitulos + chequeo del loop
```
