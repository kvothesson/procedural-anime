# CATEDRAL (escenario)

La Catedral de San Isidro (Buenos Aires) a escala real y recorrible por dentro y por fuera, para
usar de escenario en los shorts. En el futuro se llenó de servidores; por qué, no se sabe. Pieza del motor:
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

## Entorno (OpenStreetMap)

Los alrededores salen de OSM en el mismo marco que la catedral: `data/osm.json` dice qué bajar
(450 m alrededor) y dónde cae (el vértice del frente de la nave en x = 5, y = 0; el eje de la nave
a −27,5° del este). `python motor/osm.py episodios/catedral` convierte `data/osm_raw.json` (cache de
Overpass; `--bajar` lo renueva) en `data/entorno.json`, que arma la pieza `entorno`.

OSM trae bien calles, Plaza Mitre, el Tren de la Costa y los edificios grandes, pero solo 28 de
192 edificios tienen altura y faltan casi todas las casas. Lo que falta se completa y queda
marcado `"src": "relleno"`: altura por tipo de edificio, 450 casas de 1-3 pisos sobre la línea
municipal donde no hay nada (con techo a dos aguas) y árboles de vereda y de plaza.
`"relleno": false` en `osm.json` o en la pieza deja solo lo de OSM.

**Relieve.** La catedral está al borde de la barranca: SRTM (30 m, vía tiles de Mapzen; el MDE-Ar
del IGN es de la misma resolución y no hay uno más fino para San Isidro) da ~28 m sobre el mar en la
meseta, y a ~60 m del costado de la catedral el terreno baja ~20 m en ~150 m hasta el Tren de la
Costa (~8 m). Verificado contra OSM: el escalón corre junto a las vías y las escaleras de OSM caen
sobre la pendiente. La grilla (cada 5 m, suavizada 10 m) va en `entorno.json` → `terreno`, con
z = cota − 29 m; bajo la catedral se aplana a −1 (su zócalo). Calles, edificios, árboles y vías se
apoyan en ella; cada edificio nace de su punto más bajo. Con 30 m de resolución la barranca sale
más suave que la real.

Datos © colaboradores de OpenStreetMap, licencia ODbL (openstreetmap.org/copyright). Elevación: Mapzen Terrain Tiles (SRTM, NASA/USGS, dominio público).

## Ejes y alturas

x a lo ancho (0 = eje), y a lo largo (0 = frente interior, la torre en y < 0, ábside hacia +y),
z = piso interior (la vereda está a −1 m, con escalinata). Columnas a x = ±4,7 cada 5,27 m;
capitel a 7,2; arcos formeros hasta 10,9; triforio 11,15-13; bóveda alta de 13,2 a 19; bóveda
lateral hasta 11; muro alto a 20,8; cumbrera 28,2; torre 68,65.

## Estilos (intercambiables)

El look no está en los planos: cada plano dice `"estilo": "<nombre>"` y el resto sale de
`estilos/<nombre>.json` (cielo, niebla, toon, luces, tinta, post y, en `piezas`, los colores de la
catedral, los vitrales y los servidores). Geometría y cámaras no cambian.

| Estilo | Qué es |
|---|---|
| `maqueta` | Grises por familia, sin post: para revisar forma |
| `cyberpunk` | High-end cyberpunk anime: cel-shading, tinta fina, noche violeta, neón cian/magenta de racks y vitrales, luz de los vitrales en las bóvedas, brillo y aberración en el post |

Para un estilo nuevo (por ejemplo `real`, con la piedra clara y la luz de día de las fotos) se
copia uno y se cambian los valores; ningún plano se toca.

## Hora del día y clima

Cualquier plano del escenario acepta `"hora": "HH:MM"` (con `"fecha"`) y `"clima"` (`despejado`,
`nublado`, `lluvia`, `niebla`, `tormenta`); ver `motor/cielo.py`. El sol sale de la posición real
para San Isidro (la `georef` de `data/entorno.json`), así que las sombras caen como caerían ese día
a esa hora; de su altura salen cielo, luz, niebla, cuántas ventanas del barrio están prendidas y si
los reflectores de la fachada están encendidos. Pruebas con la misma cámara: `_clima_dia` (11:00),
`_clima_atardecer_lluvia` (18:50), `_clima_noche_niebla` (22:00), `_clima_tormenta` (16:00, cuadro
del relámpago). La paleta por defecto es natural; un estilo puede traer la suya en `horas`.

## Planos

| JSON | Qué es |
|---|---|
| `vistas` | 8 vistas, una por frame: nave a la altura de los ojos, dron 3/4, fachada desde la plaza, costado, desde el altar, nave lateral, dron dentro de la nave, crucero |
| `cenital` | `"techo": false`: sin techos ni bóvedas, planta en cruz desde arriba y en 3/4 |
| `entorno` | 6 vistas del barrio: dron alto, Plaza Mitre, Av. del Libertador, cenital, dron bajo desde el bajo hacia la barranca, la barranca de costado |
| `estilo_cyberpunk` | Prueba del estilo: 3 cuadros clave (nave, núcleo, exterior de noche) |

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

## Criterio de aceptación (estilo cyberpunk)

- Nave: pasillo entre racks con leds de colores; las bóvedas se leen por la luz de los vitrales.
- Núcleo: el núcleo cian en el crucero con cables que suben a la clave y a los pilares.
- Exterior: la catedral de noche con los vitrales encendidos.

## Bitácora

| Fecha | Qué se pidió | Qué se cambió |
|---|---|---|
| 2026-10-17 | Replicar la catedral en 3D, solo la geometría, sin texturas ni estética | Pieza `catedral.py` (planta OSM, alturas del folleto); vistas y cenital. Bóveda lateral a 11 m y techo lateral como losa (la cuña cortaba la bóveda). `lens_keys` en la cámara y `--blend` en escena.py |
| 2026-10-17 | Llenarla de servidores; estilo cyberpunk anime, fácil de cambiar por otro (el real después) | Pieza `servidores.py`; vitrales con luz; `estilo` en plano.py con `estilos/maqueta.json` y `estilos/cyberpunk.json`. Prueba de 3 cuadros: arriba oscuro → luz por vitral; cámara 2 estaba dentro de un rack |
| 2026-10-17 | Falta todo lo que rodea a la iglesia, hacerlo con OpenStreetMap | `motor/osm.py` + pieza `entorno`; relleno de casas y árboles donde OSM no tiene. Anexos de la catedral estaban espejados (corregido con OSM). Árboles de plaza a la mitad (tapaban la catedral) |
| 2026-10-17 | Buscar niveles: esa parte de San Isidro tiene inclinación y alturas | Terreno SRTM en `osm.py` (grilla de 5 m, aplanada bajo la catedral); todo el entorno apoyado en el relieve. Cámaras a 1,6 m sobre el terreno real; desde el bajo los edificios tapaban la barranca → dron bajo |

Pendiente: la barranca es más suave que la real (SRTM de 30 m); el entorno todavía no tiene colores en el estilo cyberpunk. Falta de la referencia: tracería de ventanas y rosetón, bancos y mobiliario,
torre sin el ahusamiento real, anexos como bloques simples.

| 2026-10-18 | Hora del día y clima configurables | `motor/cielo.py` (sol astronómico, paleta por altura del sol, climas con lluvia del post y relámpagos), `hora`/`clima` en `plano.py`, `hacia` y `energia_keys` en las luces, `georef` en `entorno.json`. 4 cuadros con la misma cámara |
