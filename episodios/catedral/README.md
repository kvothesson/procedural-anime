# CATEDRAL (escenario)

La Catedral de San Isidro (Buenos Aires) a escala real y recorrible por dentro y por fuera, para
usar de escenario en los shorts (la idea: llenarla de servidores). Pieza del motor:
`motor/piezas/catedral.py`, clave `"catedral"` en el JSON del plano.

Por qué una pieza nueva: el motor no tenía interiores; las piezas existentes son calles,
plazas y paisajes abiertos.

## Fuentes

- Planta: OpenStreetMap, way 129970084 (nave), 434818620/621 (naves laterales), 434818618
  (torre), 434818612/617/622 (sacristía, capilla, casa parroquial). Llevada al eje de la nave:
  torre de 7,2 m, nave de 31,6 m en 6 tramos, laterales de 5,2 m, crucero de 30 × 9 m, coro y
  ábside: 59,7 m de punta a punta.
- Medidas: folleto de la parroquia (P. Oeyen): 60 m de largo, 18,5 m de ancho, 29 m en el
  crucero, 19 m de altura interior, torre de 68,65 m. Cruz latina, tres naves, ábside.
- Fotos: Wikimedia Commons (`Interior Catedral San Isidro.jpg`, `Catedral de San Isidro -
  Frontis.JPG`, `Catedral de San Isidro 02.JPG` y `04.JPG`) y catedraldesanisidro.org.

## Ejes y alturas

x a lo ancho (0 = eje), y a lo largo (0 = frente interior, la torre en y < 0, ábside hacia +y),
z = piso interior (la vereda está a −1 m, con escalinata). Columnas a x = ±4,7 cada 5,27 m;
capitel a 7,2; arcos formeros hasta 10,9; triforio 11,15-13; bóveda alta de 13,2 a 19; bóveda
lateral hasta 11; muro alto a 20,8; cumbrera 28,2; torre 68,65.

## Planos

| JSON | Qué es |
|---|---|
| `vistas` | 8 vistas, una por frame: nave a la altura de los ojos, dron 3/4, fachada desde la plaza, costado, desde el altar, nave lateral, dron dentro de la nave, crucero |
| `cenital` | `"techo": false`: sin techos ni bóvedas, planta en cruz desde arriba y en 3/4 |

`out/catedral.blend` (se regenera, no va a git) es la escena para recorrerla a mano en Blender:

```bash
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b -P motor/escena.py -- episodios/catedral/shots/vistas.json episodios/catedral/render/_blend --blend episodios/catedral/out/catedral.blend
```

## Criterio de aceptación (geometría base)

- Nave desde la entrada: columnas redondas con capitel, arcos apuntados, triforio, ventanales
  y bóveda de crucería con nervios y espinazo, como en la foto de Commons.
- Afuera: una sola torre con portada, rosetón, campanario de tres lancetas, reloj, linterna y
  aguja; naves laterales con contrafuertes, pináculos y arbotantes; crucero con hastial.
- Cenital sin techo: la cruz latina con tres naves, crucero, coro y ábside.

## Bitácora

| Fecha | Qué se pidió | Qué se cambió |
|---|---|---|
| 2026-10-17 | Replicar la catedral en 3D, solo la geometría, sin texturas ni estética | Pieza `catedral.py` (planta OSM, alturas del folleto); vistas y cenital. Bóveda lateral a 11 m y techo lateral como losa (la cuña cortaba la bóveda). `lens_keys` en la cámara y `--blend` en escena.py |

Pendiente (falta de la referencia): tracería de ventanas y rosetón, bancos y mobiliario,
torre sin el ahusamiento real, anexos como bloques simples.
