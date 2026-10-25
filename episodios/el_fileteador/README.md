# EL FILETEADOR (diseño, sin construir)

Short vertical de 35 s, UNIVERSO AUSTRAL. **Caminito se está quedando sin color y un robot
fileteador lo vuelve a pintar.**

Por qué este y no otro: en el análisis de los videos del motor (2026-10-24) los que anduvieron
fueron EL RELOJERO (un personaje que arregla algo, 1255 vistas, +3 subs) y El relevo (algo que
corre de mano en mano, 1341). Los de 31 a 38 s retienen más que los de 55 s, y la retención se
parte a la mitad antes del 25 % del video: el gancho manda. El público es 80-100 % argentino.

## Qué es Caminito (referencias reales)

- Calle museo de ~150 m en La Boca, 34°38'21" S 58°21'46" W. Serpentea porque sigue el cauce de
  un arroyo viejo; después fue un ramal de tren. En los años 50 los vecinos y Benito Quinquela
  Martín la recuperaron y la pintaron; se nombró Caminito en 1959 (por el tango de Filiberto y
  Coria Peñaloza).
- Los colores: según la tradición, los vecinos pintaban con lo que sobraba en los astilleros,
  por eso cada chapa de un color distinto. **Esto es el corazón del video: el color de
  Caminito es memoria de barrio.**
- Lo que se ve en las fotos (lámina `out/referencias.png`, fotos de Wikimedia Commons):
  - Conventillos de **chapa acanalada horizontal** de 2 o 3 pisos, cada piso o tramo de un
    color; algunos con planta baja de mampostería.
  - **Escaleras de hierro por fuera** y balcones con baranda de hierro con volutas; sombras
    duras de la baranda sobre la chapa.
  - Ventanas con postigos de madera; techos de chapa a un agua.
  - Piso de adoquines en curva, faroles de hierro de dos brazos, caballetes con cuadros de
    pintores y toldos.
  - Carteles fileteados (fondo oscuro, letras con volumen, cintas celestes y blancas).
- No va: los muñecos de personas reales en los balcones (Maradona, Evita, Gardel) ni marcas
  (hay un cartel de Havanna en la calle).

## Qué es el fileteado (técnica real, del *Manual del filete porteño* de Alfredo Genovese)

Lo que el motor tiene que respetar para que se lea como filete y no como "curvitas":

- **Partes:** borde o marco; **talón** (aire entre el borde y el dibujo, un poco más abajo para
  la sombra); **banda** (línea gruesa con volumen, paralela al borde, estructura todo junto con
  la hoja de acanto); **firulete** (línea fina sin volumen, paralela a la banda); **hoja de
  acanto** (o termina en voluta, o nace de la banda); flores (planas de 4-5 pétalos, tulipas,
  campanitas); **bolitas** para llenar huecos; pájaros; cintas celestes y blancas.
- **Composición:** simétrica casi siempre; si es asimétrica, el peso a la izquierda y la banda
  a la derecha. La parte de abajo más llena que la de arriba.
- **Volumen:** las hojas se pintan con tonos y un **brillo sobre la nervadura**; cada motivo
  proyecta su sombra sobre el fondo. Las hojas de un mismo follaje cambian un poco de forma y
  dirección (sin monotonía).
- **Letras:** frente, cuerpo en perspectiva hacia abajo a la izquierda, sombra a la derecha,
  "repiqué" (trazos cortos de brillo).
- **Pinceles:** el de filetear (pelo largo de oreja de vaca, virola redonda) y la **"banda"**:
  una virola sin mango con pelo de más de 5 cm para las líneas largas. Se apoya entera y se
  desliza. **Esa es la herramienta del clímax.**
- Esmalte sintético, colores fuertes sobre fondo oscuro.

## La historia (causalidad sin palabras)

Por qué se pierde el color: un **barrido cian** del Sur Glacial "comprime" la ciudad para
ahorrar memoria; detrás de la línea, el color se rompe en bloques (datamosh, que es literal un
artefacto de compresión) y queda gris. El Norte Ámbar guarda la memoria: el fileteador la
devuelve a mano. Par folklórico (regla 2): la tecnología es el holograma, el par es el
fileteado. Termina en construcción (regla 3).

## Plano por plano (35 s, 12 fps en doses)

| # | Tiempo | Plano | Qué pasa |
|---|---|---|---|
| 01_gancho | 0-3 s | Primer plano de una chapa celeste con un filete a medio pintar | El barrido cian cruza la chapa: el color se desarma en bloques y queda gris. Entra el pincel y de un trazo vuelve una voluta amarilla, y con ella el celeste alrededor |
| 02_calle | 3-8 s | Plano general de Caminito, desde la esquina de Pedro de Mendoza, cámara alta | Al fondo de la calle avanza la línea cian; atrás de ella todo gris. El robot, arriba de la escalera de hierro de un conventillo, pintando. Todavía no la vio |
| 03_filete | 8-15 s | Detalle: pincel y tablero | Pinta una hoja de acanto: primero la línea, después los tonos, por último el brillo en la nervadura. El color vuelve siguiendo el trazo. **Plano de riesgo** |
| 04_duda | 15-19 s | Robot de espaldas, la calle entera delante | La línea gris ya pasó medio Caminito. Él mira su pincel chico. Lo guarda. Saca la banda (pelo largo, sin mango) |
| 05_banda | 19-30 s | Travelling lateral a la altura de los balcones | Apoya la banda y tira **una sola línea larga** que sale del pincel y corre sola por todas las fachadas, sube escaleras, salta de balcón en balcón. Donde pasa, cada chapa recupera su color, en cascada. Se abren postigos con luz cálida. La línea alcanza al barrido cian y lo frena |
| 06_firma | 30-35 s | Vuelta a la chapa del plano 1 | La banda remata en el filete de la chapa celeste. Él firma con repiqué. Cuando la cámara se acerca, al borde del cuadro asoma otro barrido cian: es el cuadro 1 (loop) |

## Look

- Cel-shading con colores planos y saturados: los de verdad de Caminito (paleta en
  `out/referencias.png`). Tinta gruesa. Tarde de primavera, **un solo sol** bajo y cálido
  (`hora` ~18:30 con el sol real del lugar). Relleno sin sombra (2 GB de VRAM).
- Lo gris comprimido no es negro: gris azulado `#8b9196`, sin contraste, con bloques de 8 px.
- El filete brilla apenas, como esmalte fresco; el único holograma es el barrido cian.
- El robot: cuerpo del relojero (rig, IK del brazo, agarre), piel nueva: mameluco con
  chorreaduras de esmalte, una lata de esmalte colgada de la cintura, boina. Contento sin
  sonreír (no tiene boca: los ojos y la cabeza).

## Sonido

Milonga-synth: un bandoneón sintetizado (aditiva con fuelle) y contrabajo. Cada trazo es una
nota de bandoneón. El barrido cian es un barrido de ruido blanco filtrado que se come el
reverb. La línea de la banda (plano 5) es una escala que sube en cascada, una nota por fachada
que recupera el color. Silencio de un cuadro antes de la firma.

## Qué se reusa y qué es nuevo

| Qué | De dónde |
|---|---|
| Robot con IK del brazo y agarre | `el_relojero/piezas.py` (`_build_relojero`, `_ik_arm`) por `importlib`, con materiales nuevos |
| La línea que corre y se dibuja | Estela de `motor/piezas/viaje.py` (curva con `bevel_factor` por longitud) |
| Recuperar el color a medida que pasa | `relevo` de `viaje.py` (hoy enciende `power`; hay que sumarle el modo "color") |
| Bloques de compresión | `datamosh` de `motor/post.py` |
| Calles reales | `motor/osm.py` + `entorno.py` (La Boca) |
| Sol del lugar | `motor/cielo.py` |

**Nuevo, y por qué no alcanza lo que hay:**
- `conventillo` (chapa acanalada horizontal, colores por tramo, escalera exterior, balcón con
  baranda de volutas): `ciudad.blocks` hace edificios de mampostería con ventanas por shader;
  no tiene chapa, ni escaleras exteriores, ni color por tramo.
- `filete` (banda, firulete, hoja de acanto con voluta, bolitas, sombra proyectada, dibujado
  progresivo): no hay nada en el motor que dibuje ornamento. Se hace con curvas de Blender con
  bisel que crecen (`bevel_factor_end`), igual que la estela de `viaje`, más relleno plano para
  las hojas.
- `compresion` (color → gris detrás de una línea): un parámetro de mezcla por objeto en el
  shader toon, movido por la posición del barrido.

## Criterio de aceptación del plano de riesgo (03_filete, cuadros 20, 50, 80)

| Cuadro | Qué se tiene que ver |
|---|---|
| 20 | Sobre chapa acanalada gris, la línea de la hoja de acanto a medio trazar, saliendo de la punta del pincel (sin hueco entre pincel y línea). La chapa se lee como chapa: canaletas horizontales con sombra |
| 50 | La hoja entera, con tres tonos de verde y el contorno; la chapa alrededor del trazo ya volvió a celeste, con borde irregular (no un círculo perfecto) |
| 80 | Brillo sobre la nervadura, sombra proyectada de la hoja sobre la chapa, voluta y bolitas. Que un argentino la reconozca como filete sin explicarle |

## Título propuesto (sin hashtags)

EL FILETEADOR: Caminito se estaba quedando sin color 🇦🇷🎨

## Fuentes

- Caminito: [Turismo Buenos Aires](https://turismo.buenosaires.gob.ar/es/otros-establecimientos/calle-museo-caminito), [Urbipedia](https://www.urbipedia.org/hoja/Caminito), [Billiken](https://billiken.lat/interesante/por-que-los-conventillos-de-caminito-estan-pintados-de-distintos-colores/), fotos de [Wikimedia Commons](https://commons.wikimedia.org/wiki/Category:Calle_Caminito,_Buenos_Aires).
- Fileteado: [Manual del filete porteño, Alfredo Genovese](https://www.fileteado.com/wp-content/uploads/2020/06/Alfredo_Genovese_Manual_del_Filete_Porteno_ES.pdf), [Ciudad de Buenos Aires](https://buenosaires.gob.ar/laciudad/fileteado-porteno), fotos de [Wikimedia Commons](https://commons.wikimedia.org/wiki/Category:Fileteado).

## Bitácora

| Plano | Qué se pidió | Qué se cambió |
|---|---|---|
| (diseño) | "Dale el fileteador, buscá referencias, diseñá primero" | Este README y la lámina de referencias |
| 03_filete | Prototipo del plano de riesgo (cuadros 20, 50, 80) | `piezas.py`: `chapa`, `filete`, `pincel`. La primera hoja se leía como enredadera (hojitas sueltas): pasó a un solo follaje carnoso con lóbulos redondos, nacido de la voluta y enroscado en la punta. Sol de frente: la chapa no se leía; con sol alto y rasante, las canaletas se marcan. La sombra propia de la chapa salía serruchada (pool de 2 GB): la chapa no proyecta sombra y la canaleta sale de la normal |

| 03_filete | Rehacer el firulete con las reglas de las referencias | Firulete blanco crema que sigue a la banda por dentro a un ancho de banda, desde la última vuelta de la voluta hasta antes del remate, donde hace su propio rulo; va debajo de la hoja (capa propia). Rulo fino amarillo que sale de abajo de la hoja y se enrosca en el hueco; las bolitas se corrieron a su punta |
| 03_filete | Firulete: más contraste, más grueso, meterlo bajo la hoja, rulo más visible | El firulete pasó al lado de afuera de la banda (en el talón, como permite el manual): nace bajo la base de la hoja, rodea la voluta y corre bajo la banda; 5 mm; blanco `#fffaf0`. Firulete y rulo toman solo el 35 % de la luz toon (`LUZ` en `piezas.py`): en las franjas de sombra ya no se apagan. Rulo de 5 a 2,5 mm, amarillo `#ffd23a` |
| 03_filete | Sumar la mano del robot sosteniendo el pincel | `build_mano`: la mano del relojero (palma oscura, dedos de bronce, bola de muñeca) con piel crema y manga de mameluco azul con una gota de esmalte rojo, colgada del pincel. El antebrazo hacia la cámara salía enorme y tapaba la banda: va hacia abajo a la derecha. Los dedos rodeaban el mango por detrás y el mango quedaba apoyado encima: ahora cierran del lado de la cámara |
| 03_filete | Agarre de fileteador | De puño a agarre de lápiz justo arriba de la virola: pulgar e índice pinzan el mango, el mayor lo sostiene del lado de la chapa, anular recogido, meñique estirado apoyado en la chapa (debajo de la palma, adelante de las crestas). Dedos más finos (7,5 a 6 mm). El meñique apoyado bajo la palma quedaba tapado por el antebrazo: el apoyo va 1,6 cm hacia la punta y 3,6 cm abajo |
| 03_filete | Plano entero | El antebrazo hacia abajo a la derecha cruzaba todo el filete al pintar el lado izquierdo: ahora baja casi vertical (pasa por lo que todavía no está pintado) y es más fino. Los brillos de la hoja se pintan antes que la banda, así el brazo no cruza la banda terminada. El ruido del borde del color adelantaba el color hasta 10 cuadros antes de que pasara el pincel (mancha celeste en el cuadro 6): ahora solo lo atrasa. Plano: 84 cuadros, 7 s, 1080×1920, 24 fps |
| 03_filete | Brazo rígido y flotando, tapa la voluta, pincel que salta, cuadro 84 sucio | `build_brazo`: brazo de dos tramos (0,55 + 0,48 m) con codo por IK hacia abajo; la muñeca va con la mano y el hombro, fuera de cuadro abajo a la derecha, la sigue con retraso (media de ±6 cuadros); la manga sigue 0,6 m más allá del hombro, así el brazo siempre sale del cuadro. `_viajes`: entre trazos el pincel viaja 1 a 2,5 cuadros (9 cm por cuadro) en arco, y todo se reescala para terminar en el 80. Los dos bordes de la banda iban a la vez (el pincel saltaba de uno al otro): ahora uno detrás del otro. La mano entra y sale por abajo a la derecha: el 84 queda con el filete solo. Bola de muñeca más ancha y antebrazo más corto: la tapa del antebrazo asomaba entre los dedos |

Criterio del cuadro 20 después de los viajes: el contorno está al 90 % (no a la mitad); se lee
igual como "a medio trazar" porque faltan las muescas y no hay relleno.

| (storyboard) | Armar los demás planos y la hoja | `data/osm.json` (Caminito real de OSM), `datos.py` (entorno sin la franja de Caminito), `calle.py` (plan de lotes sin Blender), `caminito.py` (conventillos, gris por "frente", cortina del barrido), `planos.py` (01, 02, 04, 05, 06 y timeline). 01 y 06 heredan del 03: filete "terminado", "firma", "corte" (el barrido borra en bloques sobre la chapa). La cortina del 05 iba pegada a la punta y la cámara la miraba de frente (todo cian): se apaga cuando la banda la alcanza. El filete "terminado" no salía (clave en 0 en el cuadro 1). 02: cámara más cerca del balcón del robot. 04: tres cuartos por la izquierda (de espaldas, la cabeza tapaba la mano). Loop 06 → 01: diferencia media 0,0 sobre los cuadros crudos |
| 05_banda | Plano entero | El color no volvía detrás de la banda: el shader sacaba la s de cada punto proyectándolo sobre la cuerda de la calle, y en la curva se corría varios metros. Ahora cada vértice guarda su s real (la del punto más cercano de la calle, atributo "s"). 132 cuadros, 11 s, 1080×1920, 24 fps |
| 02_calle | Plano entero | La cortina cian quedaba en el punto de fuga, chiquita: en este plano es de 24 m de alto y más opaca (55 %), se lee por encima de los techos. 60 cuadros, 5 s |
| 04_duda | Plano entero | El robot quedaba cortado al borde derecho y el gesto no se leía: cámara centrada en él, la mano sube delante de la cara a 1,4 m con el pincel apuntando arriba (se recorta contra la cortina), la cabeza gira hacia la mano. 48 cuadros, 4 s |
| (banda) | Banda de sonido y montaje | `banda.py`: milonga-synth en La menor, 28 compases de 1,25 s (loop en tiempo fuerte); instrumentos de `nodo_404/banda.py`. Cada trazo del 03 suena con su horario de `filete.py` (el motivo pasó a un módulo sin Blender: 03 da diferencia 0,0 contra el aprobado). El final del loop subía de golpe (siseo que bajaba de tono contra uno que arrancaba agudo, y el filtro del 01 empezaba sin estado): siseo agudo parejo al final y filtro con un segundo de preroll. Corte: 35 s, 1080×1920, 24 fps, audio 48 kHz estéreo, -13,4 LUFS |
| 04_duda, 05_banda | "El robot a los 17 s tiene los pies enterrados" | La calle peatonal de Caminito (entorno, "camino") está 14 cm sobre el piso y el robot tenía los pies en z = 0. `build_robot` lo apoya en lo que haya debajo (rayo desde medio metro arriba de "at": calle, vereda o balcón). Medido: base de los pies = piso en 02 (3,10, balcón), 04 (0,14) y 05 (-0,01). Re-render del 04 y el 05 y montaje |
| 01_gancho, 06_firma | Planos enteros | Sin cambios. Loop 06 → 01: diferencia media 0,0 sobre los cuadros crudos. 36 y 60 cuadros |

## Criterio de aceptación de los planos de calle

| Plano | Cuadro | Qué se tiene que ver |
|---|---|---|
| 05_banda | 1-10 | El robot de espaldas apoya la banda en la fachada a la altura de su mano; la línea roja sale de ahí y sube |
| 05_banda | 56 | La punta roja corre por una baranda; detrás de ella las fachadas tienen color, delante siguen grises; el borde del color va en bloques |
| 05_banda | 110 | La línea siguió por varias fachadas sin cortarse; la cortina cian ya no está |
| 05_banda | todo | La cámara acompaña la punta sin saltos; la línea nunca queda fuera de cuadro |
| 02_calle | 1, 40, 60 | Caminito se reconoce (curva, chapas de colores, balcones, escaleras); la cortina cian avanza al fondo con gris detrás; el robot pinta en su balcón |
| 04_duda | 1, 18, 44 | El robot de tres cuartos; levanta el pincel, lo mira, lo cambia por la banda; la calle gris hasta la mitad |
| 01_gancho | 1, 12, 36 | Igual al último del 06; la línea cian borra el filete en bloques; al final entra el pincel |
| 06_firma | 14, 60 | Repiqué bajo el remate; la cámara se acerca; asoma la línea cian al borde (= primer cuadro del 01) |

## Cambios al plano por plano (storyboard)

- 01_gancho termina con el pincel entrando (sin pintar): el 03 arranca con la chapa vacía y,
  si el 01 dejaba un trazo, el 03 iba para atrás en el tiempo. El filete terminado se borra:
  el barrido lo comprime y lo deja gris. Es el mismo filete del 06: el loop es un ciclo.
- Duraciones: 01 36 cuadros (3 s), 02 60 (5 s), 03 84 (7 s), 04 48 (4 s), 05 132 (11 s),
  06 60 (5 s): 420 cuadros, 35 s.
- El gris viene desde Garibaldi (s = 0) hacia Magallanes: 02 de s 34 a 52, 04 de 64 a 74, 05
  hasta que la banda lo alcanza y lo empuja para atrás.

## Prototipo 03_filete: cómo quedó

- `piezas.py`: un solo motivo (`motivo()`) da la geometría, el horario de cada pincelada, el
  recorrido del pincel y el cuadro en que cada punto de la chapa recupera el color (`tc`, se
  contagia a 6 mm por cuadro desde lo pintado, con ruido de ±10 cuadros en el borde).
- La pintura va en la colección sin tinta: el Line Art no ve el shader y dibujaría el contorno
  de lo que todavía no se pintó. El contorno es una pincelada más.
- Pendiente: el brazo es rígido (se traslada con el pincel, no gira en el codo); entre trazos
  el pincel salta de un punto a otro en un cuadro.

## El firulete (referencias en `out/firuletes.png`, ilustraciones del manual de Genovese)

El del prototipo está mal: es una recta amarilla suelta, lejos de la banda, del mismo color que
las bolitas. Lo que muestran las referencias:

1. **Acompaña a la banda en todo su recorrido**, a distancia constante (más o menos un ancho de
   banda), del lado de adentro, incluidas las esquinas recortadas.
2. Fino y parejo, sin volumen ni sombra; se afina solo en las puntas.
3. De un color que contrasta con la banda y con el fondo (celeste sobre fondo oscuro con banda
   amarilla; blanco sobre rojo).
4. Donde la banda dobla o remata, el firulete hace lo mismo y termina en punta o en un rulo
   propio, metiéndose bajo la hoja.
5. Aparte del firulete: **rulos finos** que nacen de la hoja y terminan en espiral, y el
   **bigoteado** (líneas finas en pareja, en espejo, que se afinan y se cruzan; se hacen con el
   pincel "banda").
