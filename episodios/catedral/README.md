# CATEDRAL (escenario)

La Catedral de San Isidro (Buenos Aires) a escala real y recorrible por dentro y por fuera, para
usar de escenario en los shorts. En el futuro se llenó de servidores; por qué, no se sabe. Pieza del motor:
`motor/piezas/catedral.py`, clave `"catedral"` en el JSON del plano.

Por qué una pieza nueva: el motor no tenía interiores; las piezas existentes son calles,
plazas y paisajes abiertos.

Para usarlo en un short sin tocar esta carpeta: receta "Nuevo episodio que reusa un escenario"
en [docs/CAPAS.md](../../docs/CAPAS.md) (así lo hace `nunca_se_apagan`).

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

**Huellas reales.** OSM no tiene casi ninguna casa del barrio: `data/ms_huellas.geojsonl` son los
edificios de **Microsoft Global ML Building Footprints** (detectados en imágenes satelitales,
licencia ODbL; tile `210321300`, versión 2026-02-03) alrededor de la catedral. `osm.py` suma los
que no pisan un edificio de OSM (451 dentro de los 450 m); no traen altura, así que va por tamaño
(1-2 pisos las chicas, 2 las medianas, 3-4 las grandes, fija por posición) y llevan techo a dos
aguas si la planta es casi un rectángulo. Donde hay huellas no se inventan casas.

**Barranca, árboles y monumentos.** La barranca es monte: árboles donde la pendiente SRTM supera el
12 % y no hay edificios, calles ni vías. Tipas de plaza de 15-20 m, árboles de vereda de ~10 m;
el atrio frente a la escalinata, empedrado y sin árboles (fotos 67 y 74). Monumentos de OSM en sus
coordenadas (`osm.json` → `monumentos`): la fuente de Plaza Mitre y el busto de Andrés Rolón.

**El río.** SRTM no ve bien la costa (el agua mide 0-3 m y el bajo casi lo mismo), así que el agua
sale de OSM: el multipolígono del Río de la Plata (relation/3474227) y los espejos `natural=water`
cercanos (`data/agua_raw.json`). Adentro de ellos el terreno baja 1,5 m bajo el agua, y un plano a
la cota `agua.cota_m` (2,4 m sobre el mar → z −26,6) hace de río. La grilla cubre 3,4 km cada 10 m
para llegar a la costa (~1 km al noreste). Más allá del barrio modelado (450 m) va una arboleda
rala hasta 1150 m (`bosque.lejos`, árboles `"lejos"`): de lejos San Isidro es un monte continuo
(foto 45). `"agua": false` / `"lejos": false` en `entorno` los sacan.

**Alturas medidas.** `osm.json` → `alturas`: un punto y una altura pisan la del edificio que lo
contiene. Tribunales de San Isidro (1977), el bloque alto que se ve desde el río junto a la torre:
42 m, medidos en la foto 45 contra la torre (sin dato publicado).

## Ejes y alturas

x a lo ancho (0 = eje), y a lo largo (0 = frente interior, la torre en y < 0, ábside hacia +y),
z = piso interior (la vereda está a −1 m, con escalinata). Columnas de ~1,15 m de diámetro a
x = ±4,7 cada 5,27 m; capitel a 8; arcos formeros hasta 12; triforio 12,25-13,7; bóveda alta de 14
a 19; bóveda lateral hasta 11,8; muro lateral a 11,2; muro alto a 20,8; cumbrera 28,2.
Torre (fotos 12 y 74): cuerpo hasta 28 (portada, gablete con tres óculos, rosetón); campanario
28-41 con tres lancetas con persianas por cara en un arco rehundido; reloj en gabletes 41-47,5;
cuatro torrecillas de esquina hasta 55; linterna ochavada calada 45,6-52; aguja hasta 68,65 con
gabletes al pie y buhardillas; contrafuertes escalonados hasta 41 m.

## Estilos (intercambiables)

El look no está en los planos: cada plano dice `"estilo": "<nombre>"` y el resto sale de
`estilos/<nombre>.json` (cielo, niebla, toon, luces, tinta, post y, en `piezas`, los colores de la
catedral, los vitrales y los servidores). Geometría y cámaras no cambian.

| Estilo | Qué es |
|---|---|
| `maqueta` | Grises por familia, sin post: para revisar forma |
| `cyberpunk` | High-end cyberpunk anime: cel-shading, tinta fina, noche violeta, neón cian/magenta de racks y vitrales, luz de los vitrales en las bóvedas, brillo y aberración en el post |
| `studio_noche`, `studio_dia` | Afuera, de noche y de día (ver abajo). Heredan de `_studio` |
| `studio_adentro`, `studio_adentro_dia` | Adentro, de noche y de día (`interior`) |

### Estilo `studio` (propuesta, 2026-10-18)

Pedido: *high-end cyberpunk anime style, cel-shaded, sharp line art, vibrant colors, Studio
aesthetic*. Lo que fallaba en `cyberpunk`: piedra, piso y cielo caían en el mismo violeta medio, sin
contraste de valor; el neón no tenía contra qué brillar y los árboles eran manchas grises. Y lo que
más lo alejaba del pedido (quien dirige: "no se ve como high-end cyberpunk anime... flat color"):
reflectores que lavaban la catedral pareja (sin lado de luz y lado de sombra), tinta casi invisible,
niebla a 320 m que degradaba cada superficie y aberración y viñeta que ablandaban el cuadro.

- **Color plano y tinta:** dos tonos duros por superficie (afuera de noche, tres: sombra, luna y lo
  que toca un reflector), tinta casi negra y gruesa (0,05 m en el dron, 0,025 a pie, 0,016 adentro),
  niebla lejos (700 m), sin aberración, viñeta y grano mínimos.

- **Valores:** de noche, la mayor parte del cuadro en tinta índigo (nunca negro), poco medio tono y
  el neón como lo único claro. De día, al revés: luz dura, sombras azul índigo, color saturado.
- **Tres luces con dueño:** cian = la máquina (racks, núcleo, reflectores), magenta = la señal
  (vitrales), ámbar = la gente (ventanas y faroles del barrio). El barrio cálido contra la catedral
  fría, como en AUSTRAL.
- **La catedral con sus colores reales** (quien dirige: "se mantuvieron en el tiempo"), medidos en
  las fotos 12, 30, 39 y 67 e iguales de día y de noche: piedra arenisca crema `#ecd7b0`, paños de
  ladrillo `#b5604a` con franjas de piedra (muros cada 2,2 m; la torre casi toda piedra, ladrillo
  de 45 cm cada 1,6 m), techo de cobre con verdín `#5f8577`. La noche la hace la luz: una luna
  lavanda sin tope de color y el neón en vitrales, reflectores y ventanas. `colores.ladrillo`,
  `franjas` y `franjas_torre` en la pieza `catedral` (shader, sin geometría).
- **Vitrales:** los faroles de la catedral de noche (magenta, cian, violeta, ámbar); de día, oscuros
  desde afuera y, desde adentro, haces de color que cruzan la nave.
- **Racks y núcleo:** cuerpos negros, leds casi todos cian con algo de magenta y ámbar (sin verde);
  el núcleo blanco cian. Adentro de noche no hay otra luz: las bóvedas se leen por los vitrales.
- **Barrio:** de noche oscuro con ventanas ámbar encendidas; de día fachadas claras.
- **Río:** espejo negro azulado de noche, café con leche de día (el Río de la Plata).
- **Árboles:** de noche siluetas verde petróleo, los jacarandás en violeta oscuro, los liquidámbares
  vino; de día verdes vivos, tipas verde amarillento y jacarandás en flor lila (octubre).
- **Faroles:** ámbar sodio con cono; apagados de día.
- **Post:** de noche brillo fuerte (umbral 0,6), `resplandor` rosado alrededor de lo magenta y ámbar,
  `estelas` en el piso pulido de adentro, aberración y grano leves. De día brillo solo en lo que
  quema (umbral 0,95, fuerza 0,2), sin resplandor ni estelas.
- Cualquier `hora` sobre un estilo `studio` usa su propia paleta (`horas` en `_studio`): atardecer
  rosa y naranja, noche índigo con el horizonte magenta.

Banco: `shots/_estilo_afuera_noche`, `_estilo_afuera_dia` (dron 3/4 y Plaza Mitre),
`_estilo_adentro_noche`, `_estilo_adentro_dia` (nave y núcleo), con `--frames 1 2`.

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

## Rondas de progreso contra fotos

`python episodios/catedral/progreso.py <n>` arma la ronda: 8 cámaras puestas como fotos de
Wikimedia Commons (frente desde la plaza, 3/4, costado desde Libertador, hastial del crucero, desde
el río, nave, presbiterio, nave lateral), render neutro de día (`maqueta`, 15:30) con el interior
sin servidores, y una hoja con la foto arriba y el render abajo en `out/_progreso_<n>.png`. Las
fotos van en `ref/` (no se versionan: se bajan de la categoría *San Isidro Cathedral* de Commons,
numeradas como en `ref/items.json`).

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

## Criterio de aceptación (estilo studio)

- Noche afuera: el cielo y el barrio más oscuros que la catedral; piedra crema y ladrillo
  reconocibles bajo la luna; vitrales y ventanas ámbar como los puntos más claros; árboles en
  silueta que no se confundan con el piso.
- Día afuera: cielo cian, sombras azules duras, la catedral como en las fotos (crema, ladrillo,
  techo verde), jacarandás lila reconocibles, nada lavado por el brillo.
- Adentro de noche: los racks y el núcleo son lo único claro; bóvedas leídas por el color de los
  vitrales, piso con estelas.
- Adentro de día: haces de color de los vitrales sobre racks y piso; la nave sigue en penumbra.

## Bitácora

| Fecha | Qué se pidió | Qué se cambió |
|---|---|---|
| 2026-10-17 | Replicar la catedral en 3D, solo la geometría, sin texturas ni estética | Pieza `catedral.py` (planta OSM, alturas del folleto); vistas y cenital. Bóveda lateral a 11 m y techo lateral como losa (la cuña cortaba la bóveda). `lens_keys` en la cámara y `--blend` en escena.py |
| 2026-10-17 | Llenarla de servidores; estilo cyberpunk anime, fácil de cambiar por otro (el real después) | Pieza `servidores.py`; vitrales con luz; `estilo` en plano.py con `estilos/maqueta.json` y `estilos/cyberpunk.json`. Prueba de 3 cuadros: arriba oscuro → luz por vitral; cámara 2 estaba dentro de un rack |
| 2026-10-17 | Falta todo lo que rodea a la iglesia, hacerlo con OpenStreetMap | `motor/osm.py` + pieza `entorno`; relleno de casas y árboles donde OSM no tiene. Anexos de la catedral estaban espejados (corregido con OSM). Árboles de plaza a la mitad (tapaban la catedral) |
| 2026-10-17 | Buscar niveles: esa parte de San Isidro tiene inclinación y alturas | Terreno SRTM en `osm.py` (grilla de 5 m, aplanada bajo la catedral); todo el entorno apoyado en el relieve. Cámaras a 1,6 m sobre el terreno real; desde el bajo los edificios tapaban la barranca → dron bajo |

Pendiente (después de la iteración 17, 2026-10-18): la barranca es más suave que la real (SRTM
de 30 m; no hay un modelo abierto más fino); las huellas de Microsoft no traen altura (va por
tamaño) y algunas juntan varias casas; más allá de 450 m no hay edificios, solo la arboleda. Los
árboles de vereda siguen algo más chicos que en la foto aérea; las tipas de plaza ya tienen su
tamaño (la copa va alta, así que no tapan la catedral desde el suelo). Faltan los retablos de las naves
laterales, el piso calcáreo (es estilo) y el leve ahusamiento de la torre.

| 2026-10-18 | Iterar el escenario 5 horas, guiado por datos e imágenes, cada vez más cerca de la realidad | Rondas de progreso contra 8 fotos de Commons. Barrio: 451 huellas reales de Microsoft en vez de casas inventadas, árboles a su tamaño, atrio sin árboles, barranca boscosa por pendiente, monumentos de OSM. Torre rehecha (campanario, reloj en gabletes, torrecillas, linterna calada, aguja con buhardillas), óculos, rosetón con tracería, torrecillas de escalera, buhardillas, balaustradas caladas, tracería en todas las ventanas, portadas laterales del crucero, casa parroquial a la mansarda. Interior: columnas más gruesas, arcada y bóvedas más altas, molduras, capiteles con hojas, órgano, escalera caracol, ábside con arquería ciega, Cristo Pascual. Errores en el camino: la tracería flotaba en el cielo (altura sumada dos veces); la vista frontal tapaba la aguja (cámara muy baja); los interiores salían blancos (EEVEE sin GI ilumina adentro con todo el cielo) |
| 2026-10-18 | Hora del día y clima configurables | `motor/cielo.py` (sol astronómico, paleta por altura del sol, climas con lluvia del post y relámpagos), `hora`/`clima` en `plano.py`, `hacia` y `energia_keys` en las luces, `georef` en `entorno.json`. 4 cuadros con la misma cámara |
| 2026-10-18 | (iteración 11) Desde el río no se veía agua | El agua sale de OSM (Río de la Plata y espejos), no de SRTM: la costa está a ~1 km. Grilla de 3,4 km, arboleda lejana (copas simples: con dos esferas y tronco el cuadro pasaba de 3 a 14 min), Tribunales con su huella de OSM y 42 m medidos en la foto 45 (la huella de Microsoft juntaba la manzana), ventanas en sacristía, capilla y casa parroquial |
| 2026-10-18 | (iteración 12) Ábside y flancos contra las fotos 61, 50, 70 y 31 | Ábside: un arco ciego alto por cara sobre columnillas, la galería del triforio sigue alrededor, sagrario de madera, dos hornacinas con su santo, ambón y sede. Terceletes en las bóvedas de la nave. Sin árboles inventados en el flanco oeste ni en la esquina de la torre sobre Libertador (las fotos muestran vereda despejada) |
| 2026-10-18 | (iteración 13) Costado contra la foto 31 y una foto aérea (Esri, solo referencia, en `ref/`, sin commitear) | Arbotantes macizos en cuña con albardilla (eran arcos); un techito a dos aguas por tramo sobre las naves laterales, con la cumbrera de través (la aérea muestra la hilera). La vista frontal de la ronda estaba muy cerca y baja: la aguja quedaba tapada; la cámara va a 46 m como la foto 67 |
| 2026-10-18 | (iteración 14) Planta contra la foto aérea; casa parroquial y costado contra las fotos 39, 30 y 31 | `aerea.py`: la cenital lejana con sus bordes en rojo sobre la foto aérea. Planta, techitos por tramo y calles coinciden; todo corrido ~8 m parejo (la georreferencia de la imagen). Lo que no coincide: las copas reales cubren las calles enteras (los árboles del modelo van chicos a propósito, ver abajo). Casa parroquial: siete ejes, balcón central y cuatro gabletes con óculo en la mansarda. Puerta lateral recta con escalones en el cuarto tramo sobre Libertador, ventana más corta encima. Vereda de la catedral sobre Libertador sin árboles (fotos 30 y 31); la cámara del costado cruza la avenida como las fotos |
| 2026-10-18 | (iteración 15) Arcada contra la foto 57; cámaras de la ronda como las fotos | Enjutas: un triángulo enmarcado entre arco y arco, punta abajo sobre la columna, en las dos caras. La cámara del costado cruza Libertador más adelante (torre a la izquierda, como la 31) y la de la nave lateral mira la arcada de enfrente |
| 2026-10-18 | (iteración 16) Estilo y Plaza Mitre | El banco de estilo (`cyberpunk`) sigue andando con toda la geometría nueva (vitrales, racks, núcleo, barrio). Fuente de Plaza Mitre: explanada empedrada sin árboles y cantero en trébol de cuatro lóbulos, como en la foto aérea |
| 2026-10-18 | (iteración 17) Torre de cerca contra las fotos 12, 30 y 31 | Relojes con aro, doce marcas y agujas (eran un disco liso del color de la piedra). El arco que enmarca las tres lancetas del campanario quedaba por debajo de sus puntas y flotaba sin jambas: ahora las encierra y baja hasta el pie |
| 2026-10-18 | Que los árboles se vean mejor y se parezcan a los de la zona | Especies reales: tipas en las plazas (foto 44 de Plaza Mitre: horqueta baja, ramas que se abren y vuelven a abrir, copa alta en paraguas; la catedral se ve entre los troncos), veredas con la mezcla del censo de arbolado de San Isidro (fresno, liquidámbar cónico, jacarandá, plátano, paraíso, tilo) y monte en la barranca. Plazas en grilla cada ~13 m (la copa es continua en la aérea), veredas de 9-13 m. Color por especie en el estilo (`copa_<especie>`). Detalle por distancia (`arboles_finos`, 200 m). Se arman con plantillas y numpy: de 677 s a 0,8 s |
| 2026-10-18 | Capa de estilo: *high-end cyberpunk anime, cel-shaded, sharp line art, vibrant colors, flat color*; afuera, los colores reales de la catedral | Estilos `studio_noche`, `studio_dia`, `studio_adentro`, `studio_adentro_dia` (base `_studio`, con su paleta por hora). Colores medidos en las fotos; ladrillo con franjas por shader (`mat_toon(franjas=...)`). Tres rondas: v1 seguía monocroma; v2 con luz cian la piedra salía verde menta y las franjas cada 1,1 m hacían cebra; v3 luna lavanda, toon de tres escalones de noche (la luna en el medio, el tope para los reflectores), post de día casi sin brillo. Lámina `out/_estilo_studio.png`. Flojo: adentro de día sale quemado en rosa y el sol no entra (los vitrales le hacen sombra); los reflectores de colores quedaron débiles; faltan elementos cyberpunk en el barrio (carteles, pantallas, cables) |
| 2026-10-18 | El frente: las franjas rojas en la real se cortan en las columnas y la base no tiene ladrillo | Franjas de la torre solo en los paños de las esquinas (`franjas.esquinas`: el centro, con portada, gablete y rosetón, va de piedra, como en la foto 74), entre 10,5 y 41 m (`franjas.z`: base lisa); muros desde 1,4 m (zócalo); la aguja de pizarra gris (`franjas.aguja`). Comparación con las fotos 74 y 67 en `out/_estilo_frente.png` (plano `_estilo_frente`). Falta: los filos de piedra que cortan cada franja en los contrafuertes escalonados y el beige algo más oscuro de la piedra real |
