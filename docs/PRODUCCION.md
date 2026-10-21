# Producción — todo lo aprendido

Reglas verificadas haciendo NODO 404 (el episodio de ejemplo de este repo) y otro episodio con
un personaje mecánico (cuyo código no está acá: la sección 3b conserva las lecciones). Cada
regla salió de ver un frame fallar, no de planificar. Si algo deja de ser cierto (otra
versión de Blender, otra PC), corregilo acá mismo.

---

## 1. El look: cel-shading anime con código

**Objetivo de referencia:** *high-end cyberpunk anime style, cel-shaded, sharp line art,
vibrant colors, Studio aesthetic, flat color, 9:16.* Sin personajes, este método llega
a ~65-70 % de ese prompt. Lo que sale mejor: ciudad, luz, lluvia, arquitectura, máquinas.
Lo que sale peor: caras, pelo, actuación de personajes. Diseñar alrededor de eso.
Cada plano se contrasta contra este objetivo, no contra el plano anterior: comparando entre
planos, el look se va corriendo de a poco.

- **Todo material termina en Emission.** El sombreado toon se calcula a mano en el
  nodo: Shader to RGB → rampa **CONSTANTE** sobre la luminancia → la luz se reescala
  para **conservar su tono**. Cuantizar por canal mete colores fuera de paleta.
- **Rampa toon:** 3 escalones para escenas encendidas (`0.25 / 0.6 / 1.0`). Para
  escenas oscuras hace falta un **escalón negro** (`[0, 0.05], [0.02, 0.25], ...`):
  si el mínimo es 0.25, nada llega nunca a oscuro.
- **Línea:** Grease Pencil Line Art sobre la colección `main`, color tinta `#0d0b24`
  (nunca negro puro). El radio va **en metros**: 0.035–0.045 a 1080 de ancho. Lejos
  se afina sola, como en un fondo de anime. Neón, reflejo y velos van excluidos.
- **Cel para la forma, aerógrafo para la luz.** La rampa parte *toda* luz en
  escalones: está bien para el volumen (luna, reflectores), pero el **resplandor de
  una fuente emisiva** se ve en capas. En el anime ese brillo se pinta suave encima.
  `mat_toon(..., glows=[...])` suma resplandores `fuerza / (1 + (d/caída)²)` de un
  punto o de un anillo, sin escalones, y a la fuente se le saca la luz puntual sobre
  esa superficie con light linking.
- **Un emisivo de EEVEE sin GI no ilumina nada.** Si un neón tiene que teñir algo
  (se nota enseguida), hay que dárselo explícito: luz puntual o glow.
- **Ventanas por shader**, no por geometría: grilla en la fachada + hash por celda.
  **Redondear la normal antes del hash**, o la ventana sale rayada (la normal
  interpolada varía en el último decimal y cada píxel saca otro azar).
- **Niebla por distancia dentro del shader**: determinista y separa planos. El neón
  recibe 2,5 veces menos niebla.
- **Fondos de anime:** luz cálida abajo (vidrieras, faroles), fachadas frías arriba.
  Las vidrieras derraman su color en la vereda con una luz puntual sin sombra.
- **Conos de luz** de faroles: malla cónica translúcida con alfa ~0.035 y **una sola
  cara** (backface culling). Con las dos caras se ve el doble de denso.

## 2. Piso mojado y reflejos

- Charcos = huecos con alfa binario en el asfalto + **copia espejada del mundo** debajo
  (las copias cuelgan de un vacío con escala z = -1, sin `matrix_parent_inverse`).
- Lo que emite se refleja con su color; el resto se refleja como silueta oscura.
- **Lo que está a ras del piso (< 0,5 m) no se espeja:** su copia queda justo bajo el
  charco y tapa todo el reflejo (pasó con el camino de la plaza).
- Los objetos con padre no se espejan (perderían al padre). Si hace falta, construirlos
  sin padre.
- **Charcos fijos** (`spots` en coordenadas de mundo) para el charco de empalme entre
  planos: el azar no sirve. Si el charco cruza dos superficies, los dos llevan el hueco.
- **Ángulo:** para ver en el charco algo a altura H y distancia D, la cámara a altura h
  tiene que estar a h·D/H del charco.

## 3. Animación y eventos

- **Propiedad `power` por objeto** (0..1, animable con keyframes). Todo lo que emite la
  multiplica vía nodo Attribute OBJECT. Así un apagón se programa por objeto aunque el
  material sea compartido. **Todo objeto necesita la propiedad** (sin ella vale 0 y el
  emisivo sale apagado): `escena.py` la pone en 1 por defecto.
- **Apagón en cascada** (`blackout`): frame de corte según distancia al origen + azar fijo
  + parpadeo. Interpolación CONSTANTE: la luz se corta, no se desvanece. `mode: "on"` es
  el reencendido (los tubos dudan: prenden, se apagan, prenden). Bajan también luna,
  ambiente y el resplandor del cielo.
- **Cámara:** `keys` (frame, pos, aim) con `ease: true`. Sin grilla de píxeles, el easing
  le da peso. Lineal para travellings constantes.
- **Bandera:** modificador Wave (dos frentes) + grupo de vértices con peso 0 en el mástil.
  El sol va dentro de la malla (material por cara) para que ondee con la tela. Malla de
  48×27 o el sol sale como una cruz.
- **Pantallas con contenido:** `mat_screen` = barras que corren, dos tonos planos, con el
  tiempo en un nodo Value animado lineal (función pura del frame).
- **Texto 3D:** nace en el plano XY mirando a -y; rotación (90°, 0, 0) lo pone de frente a -y.
  Para que mire a ±x leyendo bien: z = ±90° según el lado (si sale espejado, invertir el signo).
- **Plano quieto** (`still: true`): si la cámara y la escena no se mueven y todo el
  movimiento es del post, se renderiza un frame y se copia (el plano 1 de NODO 404: un
  render en vez de 36).

### 3b. Personajes mecánicos y mecanismos (aprendido en otro episodio; ese código no está en este repo)

- **Robot = piezas rígidas colgadas de pivotes** (vacíos), sin esqueleto. Pose por
  articulación con claves en el JSON. Lee bien: un ojo-luz, visera de ceja, postura.
- **Las manos van por IK, no por ángulos a ojo.** Rotando articulaciones la mano nunca toca
  nada y se nota ("el pecho se abre solo"). IK analítica de dos tramos
  (una función `_ik_arm` en el `piezas.py` del episodio, no incluida): objetivos en mundo (`to`), en ejes del
  robot (`rel`) o pegados a un objeto que se mueve (`obj` + `off`: la mano sigue a la
  perilla mientras la tapa se abre). `pole` orienta el codo; `palm` orienta la palma (si no,
  lo que sostiene queda en cualquier ángulo y atraviesa los dedos).
- **Caminar = pies apoyados, nunca el cuerpo moviendo las piernas en el aire.** El robot que
  subía entero y se deslizaba "se veía raro". Piernas con rodilla y tobillo, IK de piernas
  (una función `_two_bone`, no incluida) con objetivos en el piso/escalón, el
  pie que se mueve en arco y el cuerpo continuo; el tobillo deja el pie plano. Antes de
  animar, cuentas de alcance: la pierna de atrás no puede pedir más que su largo.
- **Agarrar = traspaso a una copia hija de la mano** que toma la matriz exacta del original
  en ese frame (`_catch`): no salta. Soltar = copia que cae con gravedad y queda plana.
- **Las articulaciones necesitan luz:** el tramo de brazo y el de antebrazo no llegan al codo
  (la bola cubre la unión) o al doblar más de 90° uno entra en el otro. Igual la muñeca.
- **Caras a la misma altura** (tapa del torso = tapa del ribete) dan manchas y líneas de
  tinta sueltas. Que una sobresalga. Tapas de cilindro con sombreado plano.
- **Mecanismos que el público entiende:** cada pieza que se rompe o se arregla tiene que
  estar haciendo algo visible. Una rueda que no engrana con nada no puede romperse; el
  repuesto tiene que ser *la misma pieza* que se rompió (el corazón = el piñón).
- **Engrane real** (`motor/piezas/mecanica.py`): pasos, forcejeo y giro libre en razón
  inversa a los dientes y con signo opuesto; fases calculadas con la misma `gear_angle` que usa la escena. Perfil con la punta en 29 % del paso
  (`PERFIL`) y centros a r1 + r2 − 0,9·profundidad: los dientes entran hasta el fondo. Con
  la punta ancha había que dejar holgura y se nota: "no parecen encajar".
- **Nada de engranajes sueltos de decoración:** cada rueda en cuadro engrana con otra y el
  tren se lee (piñón → escape → piñón coaxial → rueda grande), en un mismo plano.
- **Verificar el engrane:** `python motor/engrane.py episodios/<ep> <plano> a:b c:d` mide
  la penetración entre contornos de dientes frame por frame (colision.py no sirve: dos
  ruedas engranadas se tocan desde el frame 1). Probado: 1° de fase mal = 12 mm.
- **Un tic tiene que durar ~0,4 s** (5 cuadros únicos con rebote) y avanzar medio diente.
  Con 0,18 s y un diente entero, como los dientes son iguales, el ojo lee teletransporte.
- **Giro continuo y cadencia:** lo mismo vale para una rueda que gira sin parar. Por cuadro
  único tiene que avanzar menos de medio paso de diente (o de rayo): cerca de un paso entero
  se ve quieta, a saltos o girando al revés. La velocidad se elige con la `fps` del plano.
- **Una acción, varias cámaras:** un plano base con la acción completa y planos que lo
  heredan con otra cámara y su tramo (`render_frames`). El montaje pega lo que haya.
- **Chequeo de traspasos:** `python motor/colision.py episodios/<ep> <plano>` (BVH por
  frame, sin render). Lo que se toca en el frame 1 es la base; los contactos buscados van en
  `"colision_ok"`. Mirar frames no alcanza: un traspaso de tres frames no se ve en la lámina.
- **Luz que se mueve con un objeto: resplandor por shader, no luz puntual.** Una luz puntual
  cerca de superficies curvas moteaba el cel (aun sin sombra). `glow_follow`: distancia a un
  vacío vía coordenadas de objeto, intensidad en un nodo Value animado.
- **Sombras de rayos y engranajes** sobre un personaje se ven como ruido: `visible_shadow =
  False` en lo que está entre la luz y el personaje. Paredes de interior tampoco proyectan.

## 4. Post (`motor/post.py`)

Orden: ondas → brillo → líneas de velocidad → lluvia → glitch → aberración → viñeta → grano.
**Nada aleatorio por frame**: gotas con posición y velocidad fijas (frame = f(t)), grano que
cicla 3 patrones, glitch y líneas de velocidad con semilla por frame.

- `glow.threshold`: 0.55 por defecto. **Subirlo (0.72–0.8) en planos donde una superficie
  clara iluminada se quema** (pasó con el Obelisco dos veces).
- `rain_dim`: la lluvia se atenúa cuando la ciudad se apaga (la lluvia "se ve" por la luz).
- `ripples`: gota + ondas en un charco en perspectiva (`aspect` ≈ seno del ángulo de cámara).
  Calcular cada onda solo en su caja; sobre la imagen entera el post tardaba 3 veces más.
- `speedlines`: trazos horizontales en una banda, durante un rango de frames.
- `imagenes`: capturas reales (la ventana de una app) pegadas después de la viñeta, nítidas,
  con borde, halo y entrada que sube. `src` va relativo al episodio. Una tarjeta al costado
  tapa lo que haya de ese lado: ponerla **del lado contrario** a lo que se enciende.
- Textos con `align` izquierda/derecha: cada renglón se alinea como el bloque y la letra
  empieza en `pos` (el margen del halo no cuenta). Antes los renglones salían centrados y corridos.
- `render.py --frames` arma la lámina **sin post**: para juzgar textos o capturas, usar
  `storyboard.py` (en horizontal arma miniaturas de 16:9).
- **Loop con latido:** si un plano de cierre cambia de largo, recalcular `latido.phase` para
  que `(frames - 1 + phase)` sea múltiplo de `beat_frames`, o el cristal empalma a mitad de un pulso.
- **Nada apoyado en la cresta flota:** lo que se pone al costado del camino toca la ruta pero
  la ladera cae. Los tambos tienen `"terraza": true` (andén de pirca hasta `andes.alturas()`).
- **Un mensaje que vuelve por la ruta** (claves con `s` que baja) lleva la estela del otro lado:
  `viaje.py` mira el sentido cuadro a cuadro. Antes la estela iba siempre hacia `s` menor y la
  cabeza de la luz que volvía quedaba atrás.
- **Shorts: zona segura.** YouTube tapa la franja de abajo (~26%: canal, descripción, suscribirse),
  la columna de botones a la derecha (~16% de ancho, entre 42% y 74% de alto) y un poco arriba. Lo
  que se tiene que leer (títulos, capturas, links, subtítulos) va entre 12% y 70% de alto y lejos del
  borde derecho. Probarlo dibujando esas zonas encima de cuadros del mp4, no a ojo.
- **Subtítulos en vertical:** el original ocupa dos renglones; el bloque de la traducción tiene que
  dejar lugar para los dos (`subs_layout.gap` en `voces.json`), o los pisa.
- **Kinsoku:** en japonés un renglón no empieza con 。、！？」…; `textos._wrap` los deja pegados
  al renglón anterior aunque lo pase un poco.
- **Versiones en otro idioma sin renderizar:** si el render 3D no tiene texto (todo va en el post),
  una versión es una carpeta con planos que heredan (`extends`) y pisan `post.textos`, y `render/`
  como junction al original (`chasqui_presenta/versiones.py`). Rehacer solo post, subtítulos, banda
  y montaje: minutos, no horas.
- **El color de los subtítulos sigue a la luz, no al idioma** (ida: original en hielo, traducción en
  violeta; vuelta al revés): así cualquier par de idiomas coincide con el render compartido.
- **Una captura de app muestra solo datos reales:** texto y latencia salen de `eventos.json` de la
  toma. Un "1600 ms" puesto a mano era otra medida (demora hasta la traducción), no lo que muestra la app.
- Los borradores (`--draft`) se reescalan a la resolución final **antes** de los efectos.
  Viven en `render/_draft_<plano>/` y `out/_draft_<plano>/`: nunca pisan el plano final
  ni entran al montaje.
- El post borra de `out/<plano>/` los frames que ya no están en `render/` (un render previo
  más largo los dejaba y el montaje los pegaba) y el mp4 arranca en el primer frame que
  haya (planos con `render_frames`).
- Con una esfera de reloj luminosa en cuadro, `glow.threshold` 0.9: a 0.7 se quemó en blanco.

## 5. Rendimiento en la PC de producción

Máquina de referencia: CPU de 4 núcleos · 16 GB de RAM · **GPU con 2 GB de VRAM** (el cuello
de botella).

| Perfil | s/frame | Plano de 96 frames |
|---|---|---|
| EEVEE por defecto | 6.2 | 10–14 min |
| `PERF` (en `motor/piezas/mundo.py`) | 2.2 | ~4 min |
| `--draft` (540×960, 4 muestras) | 1.5 | ~2.5 min |

`PERF`: pool de sombras de 256 MB a media resolución, un solo sol con sombra, sin GI ni
raytracing, `light_threshold` en 0.05. Diferencia visual media: 1,9/255.

- **Las luces de relleno van sin sombra** (`use_shadow = False`). Con sombra, 12 luces llenan
  el pool; con el pool en 2 GB Blender **se cae sin traceback** (exit 127).
- El borrador casi no gana: lo que queda es CPU (escena + Line Art).
- **Miles de copias: plantillas y numpy, no operadores de bmesh.** Cada operador recorre la
  malla entera, así que agregar árbol por árbol a una malla que crece es cuadrático: 2.400
  árboles de varias ramas tardaban 677 s en armarse. Unas pocas variantes por especie, armadas
  una vez y copiadas con numpy (`_Lote` en `piezas/entorno.py`): 0,8 s.
- **El sensor de 36 mm va al ALTO de la imagen** (`sensor_fit` VERTICAL en `mundo.build_camera`):
  en horizontal, el mismo lente ve el mismo alto y 1,78 veces más ancho. Pasar un plano de
  vertical a horizontal pide cerrar la lente (×1,4), no abrirla: con 11 mm el cuadro mide 120° y
  tuerce todo lo que está cerca de los bordes.
- **Edificios derechos: `camera.verticales`.** Con la mira hacia arriba, las verticales
  convergen y los edificios se ven chuecos. La cámara de arquitecto queda nivelada y corre el
  encuadre con `shift_y` (hasta 35° de inclinación; más que eso, inclina como siempre).
- **Line Art cobra por cara visible**: 7 mil árboles más (dos esferas y tronco cada uno) llevaron
  un cuadro de 3 a 14 min. De lejos, una copa sola de pocas caras y sin tronco: vuelve a ~3 min.
- El primer frame tras cambiar un ajuste de render tarda ~35 s (EEVEE recompila shaders).
- **Nunca dos renders de Blender a la vez**: con 2 GB de VRAM, se cuelga.
- **Iterar con frames sueltos** (`render.py --frames 1 40 66`, ~30-60 s) y tirar el plano
  entero recién con el look aprobado. Los renders largos van en segundo plano.

## 6. Trampas de Blender 5.2

- Motor: `BLENDER_EEVEE` (es EEVEE Next; el id viejo `BLENDER_EEVEE_NEXT` ya no existe).
- **Blender devuelve exit 0 aunque el script falle:** verificar frames y buscar `Traceback`
  (`render.py` lo hace).
- `bpy.data.materials.create_gpencil_data(m)` deja `show_stroke = False`: Line Art genera los
  trazos y no se dibuja nada.
- Un **spot mira a -Z**: para iluminar algo desde abajo, apuntarlo con Track To.
- Light linking: `light.light_linking.receiver_collection = coll` y
  `coll.collection_objects[i].light_linking.link_state = "EXCLUDE"` (**por índice**, no
  acepta nombre).
- `Material.use_nodes` / `World.use_nodes` tiran DeprecationWarning (se van en 6.0); por ahora andan.
- Las fcurves viven en `layers > strips > channelbags` desde 4.4 (`action_fcurves()` cubre las dos).
- `view_transform = "Standard"`: AgX desatura y levanta negros.
- Color: Blender espera **lineal**; todo hex del JSON pasa por `lin()`.

## 7. Sonido

Síntesis pura (`motor/audio/dsp.py`, copia de `pixelfilm/audio/dsp.py`): aditiva con límite de
banda, campanas inarmónicas, pads desafinados, reverb por convolución con IR generada.

- **Cada evento se ancla a (plano, offset o frame)**: si un plano cambia de duración, el sonido
  se reacomoda. Las duraciones salen del `frames` de cada JSON (no de contar PNGs: durante un
  re-render las carpetas están vacías).
- **Semilla fija.** **Las ganancias son dramaturgia:** el script imprime el RMS por momento y hay
  que leerlo. La primera versión de NODO 404 salió plana (todo a −12 dB) hasta poner una curva.
- **Silencio = silencio**: cortar también la cola de reverb de lo que se corta.
- **Loop de audio:** renderizar con cola (6 s) y sumarla al principio.
- **Doppler real** para lo que pasa: c = 343 m/s, velocidad y distancia de la escena.
- Mezcla final: AAC 320 kbps, **48 kHz** (`montaje.py`).
- **Lo que marca el ritmo en la imagen, se calcula, no se tipea:** en un episodio con un reloj, cada tic
  salía de `tick_count` y las trabas de cada JSON (una función `ticks()` en su banda), incluido el tic
  con que el reloj arranca al soltarse la traba (la parte entera del tiempo no cambia ahi).
- **Planos con `render_frames`** (una accion repartida en varias camaras) duran lo que se
  renderiza, no `frames`; los eventos se anclan al frame de la escena.
- Instrumentos de otro episodio: se importan de su `banda.py` (importlib) sin tocarlo.
- **Silencio que corta en seco:** si la imagen se desatura en dos cuadros, el sonido igual se corta
  en el primer cuadro del plano. Copiando la rampa de la imagen, el "silencio" medía -23 dB.
  Medir el pico del tramo, no solo el RMS (en nodo_0 quedó en 0,0).
- **Lo que suena dentro de un silencio va en otro bus,** que se suma después de la máscara (el de Nyx
  en el 08). Así la máscara también corta las colas de reverb del resto.

## 8. Criterio de dirección (lecciones de las correcciones)

Salieron de cada vez que quien dirigía miró un frame y dijo "esto no". Pesan tanto como lo técnico:

- **Nada de cyberpunk de catálogo.** Carteles verticales de neón con palabras sueltas (BAR,
  HOTEL, TANGO) leen a cliché; los de texto cotidiano, peor. El sabor local tiene que salir de
  **lugares reales y reconocibles**, no de palabras en neón.
- **Fidelidad a la referencia real:** con una foto del lugar (plaza de pasto, edificios crema,
  bandera) el pedido es que se parezca, no "más cyberpunk". Con un personaje basado en uno
  real (un animal), las proporciones se miden sobre la foto, no a ojo: forma de la cara,
  tamaño y separación de las orejas, frente. La expresión se escribe explícita en el criterio
  del plano ("contenta sin sonreír").
- **Mirar la luz con ojo de fotógrafo:** toda fuente de luz tiene que afectar su entorno
  (anillos de neón que tiñen la piedra) y el brillo va en degradé, no en capas.
- **Continuidad:** dos planos que se sienten de lugares distintos son un error. Lo que se ve por
  una ventana tiene que ser la misma noche y el mismo clima que los planos de afuera. Lo mismo
  con la cámara: si un movimiento sigue después del corte, el plano siguiente arranca donde
  terminó el anterior o más adelante, nunca antes (se lee como un salto para atrás). Se revisa
  en el storyboard con el último cuadro de uno y el primero del otro.
- **Lo estático se nota:** la bandera tiene que ondear.
- **Gancho en los primeros 3 segundos:** el primer plano ya tiene que tener acción o algo que
  intrigue. Un plano de ambiente vacío al arranque hace que la gente pase de largo. Como el
  primer cuadro es también el empalme del loop, se diseña junto con el final.
- **El tiempo importa:** mostrar avances con frames de prueba, no tirar renders largos sin
  necesidad y optimizar para la máquina real.
- **Sonido a medida:** música hecha para los eventos de la imagen, no un loop genérico.
- **Ficción antes que documental:** el lugar real puede inspirar, no atar.
- **La causalidad se lee sin palabras:** si algo se rompe, se ve qué lo rompe; si algo lo
  arregla, se ve por qué encaja.
- **Se notan los traspasos y lo que se mueve solo** (una tapa que se abre sin que la mano la
  toque, dedos dentro de una pieza) y **los movimientos a saltos** (un tic de 2 cuadros parece
  teletransporte).
- **Publicar lo decide el humano:** visibilidad y metadatos se proponen y se confirman antes de
  subir.

## 10. Paisaje, viajes y texto (aprendido en chasqui_relevo)

- **Una ruta manda.** Terreno, camino, tambos, puente y mensaje salen de la misma polilínea
  medida por longitud de arco (`s`). Ubicar cosas por `s` evita que floten o se entierren.
- **Terreno: color por shader, no por cara.** Con el color por cara (grilla de 2 m) el pasto
  salía en bloques tipo Minecraft. Umbrales sobre la normal suave, la altura y un ruido de
  mundo dan bordes duros pero curvos, que es como se pinta un fondo.
- **La caída de una cresta necesita fondo** (`max_drop`). Sin tope, a 150 m el valle quedaba
  220 m abajo y por debajo del horizonte se veía cielo con estrellas. Lo mismo para una
  quebrada: que se cierre lejos (`gorge.open`), o se abre al vacío en el borde del terreno.
- **Calzada sin geometría por laja.** Con una caja por laja la línea de tinta dibujaba cada una
  y el camino parecía una pila de cajones. Una cinta barrida con juntas pintadas (Voronoi a
  distancia del borde) se lee como piedra.
- **Line Art y esferas:** con `crease_deg` 150 se contorneaba cada triángulo de una icoesfera;
  120 alcanza.
- **`clip_end` por defecto (500) recorta picos lejanos** y una luna a 1500 m. Subirlo en planos
  de paisaje.
- **Emisivo apagado = agujero negro.** Una baliza con `power` 0 se ve negra; apagada va en
  ~0.12 (`relevo.off`).
- **La luz del mensaje se apaga cuando el mensaje no está** (`from_frame`/`to_frame` también
  cortan su energía): si no, alumbraba la apacheta antes de salir y rompía el empalme del loop.
- **Sobre un globo, la cámara no orbita: gira el globo.** Con Track To el "arriba" es +Z del
  mundo y el cuadro salía girado 90 grados. `arco.spin` cuelga Tierra y mensaje de un pivote
  que rota para que la cabeza pase siempre por +Z; el lado de noche (calculado en el mundo)
  queda fijo respecto de la cámara.
- **Una estela de 8 cm no existe a 160 m.** El grosor se elige para la distancia del plano.
- **`hex_prism`:** `create_cone` ya pone un vértice en +y; girado 90° en x queda punta arriba.

### Texto

- **Subtítulos sobre el corte, no por plano:** una frase cruza cortes. `montaje.py` los quema
  con tiempo absoluto (`timeline.subs`); los títulos de un plano van en `post.textos`.
- **Que el texto sea el real.** Los subtítulos salen de los deltas de transcripción grabados
  con su tiempo y se escriben de a poco, como en la app. No se corrigen.
- **Reservar dos líneas por bloque:** una frase que se corta pisaba la etiqueta de abajo.
- **El texto narrativo va donde la imagen está vacía** (el piso oscuro), no sobre la luna.
- Fuentes: Yu Gothic Bold cubre latino y japonés con la misma letra; Consolas para lo que
  "dice la máquina".

### Voces reales en la banda

- **Una sola fuente de tiempos para audio y texto** (`voces.json`).
- **Nombres propios y cifras en TTS se escuchan antes del render final:** el agente no puede
  oír, así que se le pasan a quien dirige. Las cifras van escritas en letras en el texto que
  se sintetiza y los nombres difíciles, con grafía de ayuda si hace falta; el subtítulo lleva
  la grafía real. Pasó con un topónimo mal leído y con un número grande que salió deformado.
- La traducción simultánea se superpone al original: original a la izquierda y traducción a
  la derecha, el original baja cuando entra la traducción, la música se corre debajo de las
  voces.

## 11. Sombras que cuentan algo (aprendido en nodo_0)

- **Un objeto que solo existe en la sombra:** `visible_camera = False` (y diffuse/glossy en
  False) y en una colección con Line Art `EXCLUDE`, o la tinta lo dibuja igual. Proyecta sombra
  con el sol como cualquier otro. Aparece a saltos con claves de escala CONSTANT (de 0,001,
  no 0) sincronizadas con el glitch del post.
- **Una sombra solo se ve donde hay luz.** Para que una sombra de 7 m entre en un muro, el muro
  tiene que estar iluminado hasta esa altura: se calcula con la pendiente del rayo
  (tan(elevación)/cos(azimut)) desde el borde que tapa (alero, cumbrera). Por eso el galpón de
  nodo_0 tiene 7 m de muro y la brecha en el faldón del lado del sol.
- **Las sombras de la estructura compiten.** Las cerchas y correas sobre el muro iluminado
  son lindas, pero tapaban la silueta de la torre: en ese plano la estructura va con
  `visible_shadow = False` (`galpon.sombra_estructura`). La pantalla tiene que estar limpia.
- **Correr la sombra del objeto que la "proyecta":** con el sol casi detrás de la cámara la
  sombra cae justo detrás del objeto y él la tapa. El azimut del sol se elige para que la
  sombra caiga al costado, sobre una parte del muro que se vea.
- Manchas de óxido por ruido con umbral: con escala baja y alto contraste salen formas que
  parecen letras. Escala más alta, umbral más alto y un óxido apagado.
- **Datamosh** (`post.datamosh: [[f0, f1, amt]]`): el cuadro anterior a f0 se arrastra en
  macrobloques con el flujo óptico del cuadro actual (Farneback a 1/4), algunos bloques sangran
  hacia abajo, y los bloques se resuelven hacia f1. Sin estado: cada frame lee el cuadro clave
  del disco, así sigue andando con el post en paralelo. Con `--frames` no hay cuadro clave y
  no se aplica: probarlo con el plano entero.
- **Anclas:** un objeto con `ob["ancla"] = True` (los drones de nodo_0) no
  recibe glitch ni datamosh. `escena.py` proyecta a pantalla la caja de sus mallas en cada
  frame (`render/<plano>/anclas.json`, con Line Art apagado mientras mide) y el post restaura
  esos rectángulos. Solo se calcula si el plano tiene glitch o datamosh.
- **Personajes de caja con luz analítica** (`mat_dron`): con el cel de la escena, las sombras
  de las cerchas manchaban a los drones y el rojo poncho salía bordó. Lambert contra la
  dirección del sol del plano, sombra violeta, brillo en caras de frente al sol y filo cálido
  en el contorno. `luz` (0..1) los apaga si están en la penumbra.
- **Máscara exacta de los anclas** (`"mascara_anclas": true`): después del render, una segunda
  pasada solo con los anclas sobre fondo transparente (`m_####.png`). El post la usa (dilatada
  unos px para que entre la tinta) en lugar del rectángulo. Hace falta cuando el efecto tiñe todo
  el cuadro: con el rectángulo, el borde de la caja se ve. Cuesta poco: los anclas son pocos objetos.
- **Tiempo congelado** (`post.congelar: {"keys": [[frame, 0..1]], "tint"}`): el mundo pierde el
  color y se enfría; los anclas (el que actúa, sus cables, sus pulsos) siguen a color. En la
  escena, lo que se detiene se detiene de verdad: polvo con `quieto`, radio sin titilar.
- **Un HUD translúcido tapa la tinta de lo que tiene detrás** solo si su placa está en una
  subcolección de `main` con Line Art `OCCLUSION_ONLY`. Si va en `velo`, las líneas de las cerchas
  lo atraviesan.
- **Un HUD que mira siempre a cámara:** TRACK_TO hacia un vacío en la posición de la cámara. Pegado
  al dron, desde un contrapicado se leía torcido y chico.
- **La lámina de `--frames` no pasa por el post:** el datamosh y el congelado se juzgan con el
  plano entero.
- **Exterior de día:** con cielo claro, `glow.threshold` 0.95. A 0.7 el cielo florecía y todo
  el cuadro salía lavado.
- **Un halo de luz no se hace con una esfera translúcida** (salió como un huevo amarillo opaco),
  ni con un haz que sube contra el cielo de noche (se lee como una losa marrón). Lo emisivo +
  el brillo del post + una luz puntual sin sombra que tiña el piso alrededor alcanzan.
- **Antes de poner la cámara lejos, medir el terreno ahí:** a 190 m la estepa ya ondulaba y la
  cámara del plano final quedó enterrada (el cuadro salió dado vuelta).
- **Latido con claves de power:** base en f-1, golpe en f, base en f+3. Con solo golpe y base
  la luz subía en rampa entre latido y latido.

## 12. Luz que no es superficie y planos de sakuga (aprendido en duende_rojo)

- **Luz aditiva:** Transparent BSDF + Emission sumados (Add Shader, `BLENDED`) se suman al cielo
  sin taparlo. Es la base del duende, del halo, de la tormenta lejana.
- **Brillo en degradé sobre una esfera:** la distancia al centro en la superficie vale siempre 1
  (no hay degradé); se usa `Layer Weight > Facing` con sombreado **suave** (con caras planas cada
  faceta da un escalón: bandas). Para un disco chato visto de canto, el radio en el plano del
  disco (coordenadas de objeto x, y).
- **Crecimiento de una descarga por shader:** cada punto guarda en un atributo cuándo lo alcanza
  la cabeza (`nace`); una propiedad animada (`fase`) lo revela, con un pico en la cabeza y un
  brillo sostenido que se apaga. Una sola malla, cero objetos por cuadro.
- **Lo fino se afina hasta un hilo de ~medio píxel** (`radio * (1-u)^1.35`, con mínimo): grosor
  parejo se lee como fideos. Ojo con `(1-u)**x` si u pasa de 1: da un número complejo.
- **Escala de un fenómeno lejano:** con los ángulos reales y un 35 mm el duende ocupaba un quinto
  del cuadro. Las fotos que impresionan son con teleobjetivo: el tele aplana el cerro contra el
  cielo. Se calcula qué asoma sobre un cerro (elevación con curvatura de la Tierra) antes de
  componer.
- **La tinta va en metros:** 3 cm sirven a 40 m; en un primer plano a 1 m son trazos de 90 px que
  tapan la cara (parecía un error de material). `line.radius` por plano según la distancia.
- **Personajes de caja de noche:** no hay curvatura donde aparezca un filo de luz; se encienden las
  caras que miran a la fuente. Con el brillo del post, en un primer plano iluminado, subir
  `glow.threshold` (0.8) o la cara sale lavada.
- **Impact frames** (`post.impacto`): dos tonos (la tinta = lo oscuro, lo que brilla invertido)
  sobre fondo rojo, negro o blanco cada dos cuadros a 24 fps, con líneas de foco. Hit-stop:
  cuadros sin cambio en la escena y **silencio exacto** en la banda.
- **Cadencias mezcladas en el montaje:** cada plano declara `fps` (12 en doses, 24 el sakuga) y el
  montaje repite cuadros para llevarlo a la cadencia del corte. La banda lee la misma `fps`.
- **Sonoridad:** el montaje normaliza a -14 LUFS (`loudnorm`), el estándar de YouTube. La banda
  normalizada por pico dejaba cada episodio a un volumen distinto.
- **Un silencio se aplica también después de doblar la cola del loop:** si no, la cola se mete en
  el silencio cuando cae al principio. Medir el pico, y que la rampa de vuelta empiece en el cuadro
  del golpe, no antes.
- **Un fenómeno que "no encaja con el cielo"** (quien dirige): el halo en anillo y la campana en
  óvalo tenían contorno limpio y color parejo, y se leían pegados encima. El aire que se tiñe
  alrededor de una fuente se hace en el post a partir de la forma real de la fuente
  (`post.resplandor`: lo de color dominante, difuminado en radios grandes), sin borde.
- **"Me lo imaginaba llenando el cielo":** antes de exagerar la escala, buscar lo que la física
  permite. Los duendes salen en grupo sobre una tormenta grande y se encienden en cadena; una
  tormenta más cerca los sube y los agranda. Con eso y el encuadre, llenan el cuadro sin mentir.
- **Storyboard antes que planos enteros** (`motor/storyboard.py`): un cuadro clave por plano con
  el post y la acción. Encontró tres planos con el protagonista fuera de cuadro y una luz que
  quedaba prendida donde no debía.
- **Chequeo de encuadre en el generador de planos** (`episodios/duende_rojo/planos.py`):
  proyectar a pantalla a los personajes en cada cuadro clave y avisar si quedan afuera o al
  borde. Más barato que renderizar para descubrirlo.
- **El loop también es el lente:** dos planos que empalman en la misma toma tienen que tener el
  mismo lente (no se anima), además de cámara, pose y estado de cada luz. Con un 50 mm contra un
  32 mm, el empalme difería 37/255.
- **Llegar tarde se mide:** si un personaje "llega medio segundo tarde", lo que mira tiene que
  haber desaparecido antes de que termine de girar. Con un resto rojo de un segundo, parecía que
  lo había visto.
- **Lo que aparece desde varios ángulos tiene que leerse desde todos** (quien dirige: "cuando se
  ve a Nyx arriba, la pasarela desapareció"). El techo de la calle techada estaba, pero era una
  losa plana y oscura: desde abajo se leía por las luces colgadas; desde arriba era igual a la
  calle. Un techo de chapa a dos aguas con tragaluces encendidos se lee de los dos lados. En el
  storyboard, si un elemento del lugar se ve de lados distintos, mirarlo en un cuadro de cada lado.

## 13. Lugares reales, estilos y primera persona (aprendido en catedral / nunca_se_apagan)

- **Un lugar real sale de OpenStreetMap + SRTM** (`motor/osm.py`): planta, calles, plazas, vías y
  relieve en el marco de la escena. OSM casi nunca trae alturas y en barrios bajos faltan las
  casas: se completan y quedan marcadas `relleno`. Verificar el relieve contra el mapa (el escalón
  de la barranca tiene que caer donde OSM tiene escaleras y vías).
- **El estilo va en un archivo aparte** (`<ep>/estilos/<nombre>.json`, `"estilo"` en el plano, con
  `extends` entre estilos): adentro y afuera de la misma escena son dos estilos, y el corte de la
  puerta coincide con el cambio.
- **El toon topea la luz en el 100 % del color:** más energía no hace "más encendido", solo cambia
  el tono. Una superficie encendida por reflectores se logra con `glows` (el aerógrafo sumado sobre
  el cel), no subiendo la luz. Cerca de la cámara el glow quema: chico y suave donde se camina.
- **Una luz puntual a ras del piso pinta un charco duro** (un cuadrado de color en el toon). Para
  lavar una fachada, un cono (`SPOT`) que apunte a lo que ilumina.
- **Primera persona:** la mira se calcula para que la cabeza del personaje caiga donde se pide en
  pantalla (búsqueda de giro e inclinación); si además se exige otro punto en cuadro y no entra,
  aflojar esa exigencia en ese cuadro. Un chico de la mano va al costado, no adelante: adelante, su
  brazo sale de la espalda.
- **Acercarse a lo real se mide contra fotos:** una ronda fija de cámaras puestas como fotos de
  referencia, con el render debajo de cada una, en cada iteración (`episodios/catedral/progreso.py`).
  Para comparar estructura, luz neutra de día y sin lo que tapa (los racks); para el interior, ambiente
  bajo y un sol sin sombra desde arriba: sin GI, EEVEE ilumina adentro con todo el cielo y sale blanco.
- **Donde OSM no tiene casas, Microsoft sí:** Global ML Building Footprints (ODbL) trae las huellas
  reales; se baja el tile en streaming y se filtra por un rectángulo (el tile entero pesa cientos de
  MB). No traen altura: por tamaño, fija por posición.
- **Un detalle que sale del contorno de otra cosa (la tracería del vidrio) hereda su altura:** al
  sumarle la del arco se va al cielo. Ver siempre un primer plano después de agregar piezas chicas.
- **Árboles de relleno que tapan una vista que el plano necesita se sacan** calculando qué copas
  cortan la línea de vista (no se tocan los de OSM).
- **La costa no sale de SRTM:** el agua y el bajo miden casi lo mismo (0-3 m). El río va de OSM
  (multipolígono `natural=water`, anillos armados uniendo tramos) hundiendo el terreno adentro, y
  un plano a la cota del agua. Una relación grande (el Río de la Plata) baja entera y no pesa.
- **Una huella de Microsoft puede ser la manzana entera:** un edificio medido (`alturas` en
  `osm.json`) va con su propia huella de OSM, no con la altura pisada sobre la de Microsoft.
- **La planta se mide contra una foto aérea** (`episodios/catedral/aerea.py`): una cenital lejana
  con teleobjetivo, con sus bordes en rojo sobre la foto en el mismo marco. Un corrimiento parejo
  de calles y edificios es de la imagen; lo que vale es lo relativo. La foto queda en `ref/`, sin
  commitear.
- **Cámaras de comparación puestas donde se paró el fotógrafo:** muy cerca y bajo, la perspectiva
  esconde la aguja detrás de la torre y un árbol de vereda tapa la puerta que se quería ver.
- **"No se ve como high-end cyberpunk anime, flat color"** (quien dirige, sobre la catedral): lo que
  más alejaba no era la paleta sino lo que ablanda: reflectores que lavaban todo parejo (sin lado
  de luz y de sombra), tinta fina que de lejos desaparece, niebla cercana que degrada cada cara,
  aberración y viñeta. Dos tonos duros, tinta casi negra y gruesa, niebla lejos y post limpio.
- **De noche la luna va en un escalón medio del toon** (`[0, 0.1], [0.25, 0.5], [0.8, 1.0]`): con
  el tope en 1.0 una piedra clara sale blanca aunque la luna sea débil (el toon topea en el 100 %
  del color). El tope queda para lo que toca un reflector.
- **Luz de color sobre colores reales:** una luna cian vuelve verde menta la piedra crema. Para
  conservar los colores reales, luna casi blanca (lavanda) y el neón en las fuentes.
- **Ladrillo con franjas por shader** (`mat_toon(franjas=...)`, `colores.ladrillo` en la catedral):
  bandas en z solo en caras verticales. Franjas cada 1,1 m hacen cebra desde un dron; cada ~2 m.
- **La lámina de `--frames` sale sin post:** para juzgar un estilo copiar los cuadros a
  `render/<plano>/` y correr `post.py --frames`; el brillo cambia mucho el cuadro (de día lo lavaba).
- **Sol de día que entra por los vitrales** (`gobo` en el estilo + `vidrios.sombra: false`): el
  vidrio no hace sombra y el toon tiñe lo que recibe sol con un mosaico proyectado contra la
  dirección del sol (`materiales._gobo`); el contorno lo ponen muros y tracería. Antes de elegir el
  ángulo, raycast desde el piso que la cámara ve hacia el sol: en la catedral real solo ~5 % del
  pasillo central recibe sol, y solo con el sol bajo y de costado (`rot [20, 0, 80]`).
- **Adentro, los reflectores de afuera sin sombra cruzan los muros:** un estilo interior los vacía
  (`reflectores: []`). Y la palidez de una nave "en penumbra" suele ser el escalón bajo del toon
  (normaliza la luz a ese valor), no el ambiente: bajar el primer escalón, no la luz.

- **Árboles de fondo de anime por shader:** la luz del toon multiplicada por celdas de Voronoi (una
  mata por celda) corta la sombra en grumos; del lado del sol no alcanza (no cambia de escalón) y
  hace falta el borde de cada mata pintado más oscuro. Abollar solo las plantillas (6 por especie)
  da silueta en matas sin multiplicar el costo por árbol.
- **Un piso deja de ser plano con lo pintado, no con relieve:** juntas de baldosa en x, y, línea
  central desde un UV a lo largo de la cinta, y charcos que muestran un color de reflejo sin recibir
  luz. Charcos grandes y saturados se leen como pintura derramada: chicos y del tono del cielo.

- **Charcos de noche sin raytracing:** el reflejo de las luces de la ciudad en un fondo de anime son
  trazos verticales de color; por shader, barras por la x de pantalla (`TexCoord > Window`) con un
  azar por barra, onduladas con ruido del piso, solo dentro del charco. No coinciden con las luces
  reales: las estelas del post ponen las que sí.
- **Borde de neón en el follaje:** `Layer Weight > Facing` en escalón; fino (0,1). Grueso, cada bola
  de la copa queda contorneada como un tubo y los árboles lejanos se vuelven una alfombra de color.

- **Reflejos alineados sin raytracing:** una pasada de máscara barata (todo en negro plano, el piso
  con la mancha de charco en blanco, mitad de resolución, una muestra) y en el post lo que brilla se
  estira hacia abajo solo dentro de la máscara: cada reflejo cae debajo de su luz.
- **Lo que no está en la tinta no tapa líneas:** con el piso fuera de la colección de Line Art, el
  contorno de la parte enterrada de un tronco se dibujaba sobre el pasto. El piso va dentro de
  `main` con `OCCLUSION_ONLY` (y no costó tiempo). Mallas que se cruzan a propósito (bolas de una
  copa, tramos de rama) van con `lineart.usage = "NO_INTERSECTION"`; los tubos, con tapa.

## 9. Publicar

El motor no sube nada: `montaje.py` deja `episodios/<ep>/out/<ep>.mp4` (H.264 + AAC a 48 kHz,
1080×1920, 24 fps), que sirve tal cual para YouTube Shorts, X y Reddit (todas piden MP4
H.264/AAC).

- Si automatizás la subida: **nunca dejes tokens ni credenciales en el repo.**
- **Antes de reintentar una subida que "falló", verificá qué quedó publicado.** En Windows, un
  script que imprime caracteres no ASCII puede fallar al *imprimir* (cp1252) después de subir
  bien: `PYTHONIOENCODING=utf-8` lo evita y listar los últimos videos evita el duplicado.
