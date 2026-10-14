# NODO 0 — LA MAREA DE COBRE

Publicado el 2026-10-13: https://youtube.com/shorts/sTA8PN0z2HE

**UNIVERSO AUSTRAL · Especial (fuera de temporada).** Canon: [docs/AUSTRAL.md](../../docs/AUSTRAL.md).
Sin personajes humanos ni voces: la expresividad es de las ópticas y los paneles de los drones,
y la banda lleva la emoción.

En un galpón ferroviario abandonado de San Antonio de los Cobres, una vieja radio a válvulas
del nodo de repetición quedó soñando con una transmisión de AM. Aegis manda borrarla. Nyx, que
siempre llega medio segundo tarde, esta vez usa ese medio segundo: descarga la energía a tierra
por un poste de quebracho y el nodo no se borra, se estabiliza. Queda como una luz mala ámbar en
el mapa de la Ruta 404, y los drones siguen viaje.

## Ficha

| | |
|---|---|
| Duración | 54 s, 1080×1920, 12 fps únicos → 24 fps |
| Lugar real | San Antonio de los Cobres (Puna salteña): galpones de chapa de la estación del Ramal C14, línea de telégrafo con postes de quebracho, el cerro con las antenas repetidoras (foto de referencia de quien dirige; no está en el repo) |
| Paleta | Ámbar `#FFB000` (el nodo, la luz mala) · Herrumbre `#B7410E` (avisos, Nyx) · sol de tarde `#FFB46B` sobre chapa de zinc `#7F8B96` con óxido · noche `#050D1F` al final |
| Sonido | Bandoneón granular + ruido blanco; radio AM sintetizada (portadora, heterodino, murmullo de locutor sin palabras, frase de bandoneón por el ancho de banda de AM); crujido de chapa por el calor. Silencio total en el medio segundo de Nyx |
| Diseño de drones | Cajas mecánicas, aristas planas (la tinta las marca limpio). La personalidad sale de las ópticas, la ceja y los paneles |

## Plano por plano

| # | Plano | Tiempo | Qué pasa |
|---|---|---|---|
| 01 | `01_horizonte` | 0–4 s | Noche. Plano general: estepa, el galpón late ámbar en el horizonte, poste de quebracho. Título NODO 0. Es el mismo cuadro que el final (loop) |
| 02 | `02_llegada` | 4–9 s | Tarde. Exterior del galpón con la brecha en el techo; los tres drones bajan en formación y entran. Atrás, el cerro con las antenas |
| 03 | `03_galpon` | 9–14 s | Interior: haz de sol por la brecha, polvo y esporas. La radio titila. Aegis teje su escudo trama por trama |
| 04 | `04_mapa` | 14–19 s | Vesper proyecta el mapa en fileteado: la Ruta 404, el nodo que consume sin procesar; aguja en herrumbre |
| 05 | `05_conexion` | 19–25 s | Nyx gira la cabeza (lechuza) y se conecta al tablero de clavijas. El sonido cae a AM |
| 06 | `06_sombra` | 25–31 s | Datamosh leve. La sombra de la radio en la chapa es una torre de transmisión que no existe |
| 07 | `07_orden` | 31–35 s | HUD de Aegis: `D▮▮▮▮▮ /NODO_00` en herrumbre, cuenta regresiva |
| 08 | `08_medio_segundo` | 35–40 s | Todo se congela menos Nyx: desvía la energía por un cable al poste de quebracho. Arco a tierra |
| 09 | `09_luz_mala` | 40–46 s | El parpadeo errático se vuelve un latido ámbar estable. En el mapa aparece una luz mala sobre la Ruta 404 |
| 10 | `10_salida` | 46–54 s | Noche. Los drones salen por la brecha; la cámara se abre hasta el cuadro del 01 |

## Canon

- **El Verbo:** solo aparece el fragmento de borrar, cortado: `D▮▮▮▮▮`. Nunca "CRUD" ni los cuatro
  juntos.
- **Tecnología ↔ folklore** (además de los pares de la serie: Aegis/telar, Vesper/farol de
  querosén, Nyx/lechuza vizcachera, HUD/fileteado):

| Tecnología | Folklore |
|---|---|
| Rack de radio a válvulas (el nodo) | Manipulador Morse de la estafeta de la estación |
| Puesta a tierra | Poste de quebracho del telégrafo |
| Nodo estabilizado en el mapa | Luz mala (ámbar, no verde) |
| Torre de transmisión (sombra) | Las antenas del cerro del pueblo |

- **Cierre:** viaje (los drones siguen la ruta), no destrucción.

## Estado

| Plano | Estado |
|---|---|
| `01_horizonte` | Render. Noche, plano general con el galpón latiendo y el título. Loop con el 10 medido: diferencia media 0,0 |
| `02_llegada` | Render. Tarde: los tres drones pasan cerca de cámara y entran por la brecha; Nyx medio segundo tarde |
| `03_galpon` | Render. Los drones bajan por la brecha; Aegis teje el escudo-telar frente a la radio |
| `04_mapa` | Render. Vesper abre el mapa; el NODO 0 titila en falla y el medidor se clava en rojo |
| `05_conexion` … `09_luz_mala` | Render |
| `10_salida` | Render. Desde arriba de la brecha encendida, los drones suben y se van; la cámara se abre hasta el cuadro del 01 |
| `_drones` | Prueba de diseño (no entra al montaje) |
| Banda (`banda.py`) | Milonga de bandoneón granular a 60 BPM (Re menor → Re mayor en el 09), radio AM sintetizada, silencio absoluto en el medio segundo del 08 (pico 0,0). Todo anclado a (plano, frame) desde los JSON |
| Montaje | `out/nodo_0.mp4`: 54 s, 1080×1920, 24 fps, AAC 48 kHz. Loop 0,00/255 |

Escenas base: `galpon_base.json` (interior), `exterior_base.json` (tarde), `exterior_noche.json`.

Piezas del episodio en `piezas.py`: `galpon` (chapa acanalada y óxido por shader, cerchas,
brecha, haz de sol), `polvo`, `radio`, `torre` (invisible a cámara: solo proyecta sombra),
`nyx`, `aegis` (escudo-telar), `vesper` (farol), `hud` (placa con filete; el Verbo cortado), `poste`, `pulsos`, `descarga`, `mapa` (Ruta 404 y la luz mala) y el exterior: `puna`, `cerro` (antenas, vía crucis, balizas), `pueblo`, `via` (C14 y telégrafo), `resplandor`.
Los drones usan `mat_dron` (luz analítica) y son anclas: el glitch del post no los toca.

```bash
python motor/render.py episodios/nodo_0 06_sombra --frames 1 36 60
python motor/render.py episodios/nodo_0 06_sombra
python episodios/nodo_0/banda.py
python motor/montaje.py episodios/nodo_0
```
