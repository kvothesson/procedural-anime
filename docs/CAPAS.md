# Capas del repo: qué va dónde y cómo se extiende

Para quien entra por primera vez (agente o persona). Acá está la organización: qué hay en cada
capa, dónde vive, cómo se agrega o se cambia. Las reglas de look, las trampas de Blender y el
criterio de dirección están en [PRODUCCION.md](PRODUCCION.md); el formato del JSON de un plano,
en [AGENTS.md](../AGENTS.md).

## Las capas, de abajo hacia arriba

| # | Capa | Qué es | Dónde vive | Se extiende con |
|---|---|---|---|---|
| 0 | **Motor** | Arma la escena, renderiza, post, montaje, chequeos | `motor/*.py` | Código (raro: casi todo entra por las capas de arriba) |
| 1 | **Piezas genéricas** | Cosas parametrizadas que sirven en cualquier lugar | `motor/piezas/` (ver tabla abajo) | `build_<cosa>(e, colls)` + una clave del JSON |
| 2 | **Datos de un lugar real** | OSM, relieve SRTM, huellas de Microsoft, río, alturas medidas, monumentos, pasados a metros en el marco de la escena | Código: `motor/osm.py`. Receta: `<escenario>/data/osm.json`. Salida: `<escenario>/data/entorno.json` | Editar `osm.json` y correr `python motor/osm.py episodios/<escenario>` |
| 3 | **Escenario** | Un lugar armado y recorrible: el entorno de la capa 2, las piezas hechas a mano para ese lugar (un edificio real) y un plano base con sus vistas | Piezas de lugar en `motor/piezas/`, config y datos en `episodios/<escenario>/` (hoy: `episodios/catedral/`) | Ver receta "Nuevo lugar real" |
| 4 | **Estilo** | El look entero: cielo, niebla, toon, luces, tinta, post y los colores de cada pieza | `episodios/<ep>/estilos/<nombre>.json` | Copiar uno, o uno nuevo con `extends` |
| 5 | **Hora y clima** | Sol real del lugar por fecha y hora; despejado, nublado, lluvia, niebla, tormenta | `motor/cielo.py`; claves `hora`, `fecha`, `clima`, `lugar`, `interior` | Paletas por altura del sol en el estilo (`horas`) |
| 6 | **Episodio** | La historia: planos (cámara, acción, personajes), banda, subtítulos, montaje | `episodios/<ep>/` | Ver receta "Nuevo episodio" |

### Qué es cada pieza de `motor/piezas/`

| Tipo | Módulos | Atado a un lugar |
|---|---|---|
| Utilidades | `base` (color, mallas, claves, texto 3D), `materiales` (toon, neón, piso mojado, velos), `ctx` (config del plano), `mundo` (cielo, luces, reflejo, tinta, cámara, render) | No |
| Genéricas | `ciudad` (calle mojada, hileras, megatorres, faroles, cables), `plaza` (óvalo, árboles, bandera), `eventos` (apagón, Luz Mala), `mecanica` (engranajes), `despiece`, `viaje` (mensaje de luz por una ruta), `espacio` (estrellas, Tierra), `colectivo`, `entorno` (cualquier lugar con `entorno.json`) | No |
| Paisaje por ruta | `andes` (terreno, cordillera, camino, puente, tambos, apacheta, luna; todo por `s` sobre `camino.pts`) | A medias: es una ruta inventada con forma andina; sirve para otra ruta |
| De un lugar | `catedral` (San Isidro), `servidores` (sale de las medidas de `catedral`), `obelisco` (Buenos Aires), `tokio` (callejón de Yurakucho) | Sí, por diseño: un edificio real es uno solo |

Las piezas que solo usa un episodio van en `episodios/<ep>/piezas.py` (ver receta "Nueva pieza").

## Cómo se resuelve un plano

`motor/plano.py` (`load_shot`), en este orden; lo de más abajo gana:

1. **Estilo** (`"estilo"`): `<ep>/estilos/<nombre>.json`, con su cadena de `extends`. Su bloque
   `piezas` solo colorea piezas que el plano ya tiene: un estilo no agrega objetos.
2. **Hora y clima** (`cielo.aplicar`): encima del estilo.
3. **El plano**: su cadena de `extends` (relativa al archivo) con `drop`. Lo que el plano dice
   explícito gana siempre, también sobre hora y clima.

Después `motor/escena.py` arma, en orden: las `PIEZAS` del motor (el orden fija nombres de
objetos y el azar del apagón: agregar al final), luces, Obelisco y Luz Mala (van después de las
luces por el cristal y el apagón), las `PIEZAS` de `<ep>/piezas.py`, `power` = 1 en todo,
apagón, reflejo, tinta y cámara.

**Rutas: ojo.** `extends` es relativo al archivo que lo declara. Todo lo demás (`estilo`,
`entorno.datos`, `<ep>/piezas.py`) se busca desde la carpeta del episodio **del plano que se
renderiza** (`ctx.EPISODIO` = la carpeta padre de `shots/`), aunque la clave venga heredada de
otro episodio. Por eso un episodio que reusa la catedral escribe `"datos":
"../catedral/data/entorno.json"`.

## Recetas

### Nuevo lugar real (escenario)

1. Carpeta `episodios/<lugar>/` con `README.md`: fuentes (ids de OSM, folletos, fotos con su
   licencia), ejes de la escena y criterio de aceptación. Modelo: `episodios/catedral/README.md`.
2. `data/osm.json`, copiando el de la catedral y cambiando lo del lugar:
   - Obligatorio: `centro` [lat, lon] y `radio` (m) de lo que se baja; `origen` [lat, lon] que
     cae en `origen_local` [x, y] de la escena; `rumbo_deg` (hacia dónde apunta +y, grados desde
     el este, antihorario).
   - Opcional: `excluir` (ids de OSM que modela una pieza a mano), `zonas_libres`,
     `zonas_sin_arboles`, `relleno` (casas y árboles inventados donde OSM no tiene), `seed`,
     `terreno` (relieve SRTM: `ref_m` = cota del piso de la escena, `paso`, `lado`, `plataformas`
     que aplanan bajo una pieza), `huellas` (Microsoft Building Footprints), `bosque`, `agua`,
     `alturas` (edificios medidos), `monumentos`. El detalle de cada una, en el docstring de
     `motor/osm.py`.
3. `python motor/osm.py episodios/<lugar>` → `data/entorno.json`. Leer los conteos que imprime y
   comparar el relieve contra el mapa (escaleras, vías, barrancas).
4. Un plano base `shots/vistas.json` con `"estilo": "maqueta"`, `"entorno": {"datos":
   "data/entorno.json"}` y una cámara por frame (`camera.keys`, `storyboard` con todos los
   frames). `python motor/render.py episodios/<lugar> vistas --frames 1 2 3`.
5. Si el lugar tiene un protagonista (un edificio que se recorre): pieza a mano en
   `motor/piezas/<lugar>.py` con un docstring de fuentes y ejes, sus ids en `excluir` y una
   `plataforma` del terreno debajo. Antes, escribir en el README por qué no alcanza `entorno`.
6. Contrastar contra lo real, no a ojo:
   - Planta contra foto aérea: `episodios/catedral/aerea.py` (hoy atado a la catedral: copiarlo y
     cambiar `EP` y el plano `_qa_aerea`; ver propuesta P4).
   - Ronda de cámaras como las fotos: `episodios/catedral/progreso.py` (las fotos van en `ref/`,
     que no se commitea; agregar `episodios/<lugar>/ref/` al `.gitignore`).
7. Estilos: `maqueta` (grises, para forma) y el del show. Ver "Nuevo estilo".
8. Hora y clima salen solos: la `georef` de `entorno.json` le da a `cielo.py` la latitud y el
   rumbo. Probar 3 horas con la misma cámara (como `_clima_*.json` de la catedral).

### Nuevo estilo

1. Copiar un estilo de `episodios/<ep>/estilos/` o crear uno con `"extends": "<otro>"` que pise
   lo que cambia (así se hace `cyberpunk_adentro` sobre `cyberpunk`).
2. `"_desc"` en una línea: qué look es y para qué.
3. Claves: `sky`, `fog`, `toon`, `lights`, `line`, `post`, `horas` (paleta por altura del sol) y
   `piezas` (`{"catedral": {"colores": ...}, "entorno": {...}}`: colores por pieza).
4. Probarlo cambiando una palabra en un plano de prueba (`"estilo": "<nuevo>"`), con los mismos
   cuadros clave que el estilo anterior. Ningún plano de historia se toca.
5. Los estilos viven en la carpeta del episodio que renderiza: si otro episodio lo usa, hoy hay
   que copiarlo (ver propuesta P2). Un estilo publicado se congela con otro nombre
   (`_base_cyberpunk.json` en la catedral es el de NUNCA SE APAGAN).

### Nueva pieza

- **Solo de un episodio**: `episodios/<ep>/piezas.py` con `PIEZAS = [("clave", build_fn)]`. Se
  arma después de las del motor y puede importar `from piezas.base import ...`.
- **Reutilizable**: `build_<cosa>(e, colls)` en el módulo que corresponda de `motor/piezas/` (o
  uno nuevo con docstring: qué arma, ejes, ejemplo del JSON), importarla en `motor/escena.py` y
  sumarla **al final** de `PIEZAS`. Una fila en la tabla del JSON de `AGENTS.md`.
- Colecciones (`colls`): `main` (con tinta), `neon`, `refl`, `veil`, `lights` (sin tinta).
- Lo que emite multiplica la propiedad `power` del objeto (apagones, latidos).
- Colores: que el estilo los pueda pisar (leer de `e["colores"]` con valores por defecto).
- Promover una pieza de episodio al motor cuando un segundo episodio la necesita (no antes).
  Mientras tanto, otro episodio la puede importar con `importlib` (ver
  [episodios/README.md](../episodios/README.md)).

### Nuevo episodio

1. Diseño en conversación (AGENTS.md, "Cómo se hace un video nuevo").
2. `episodios/<ep>/` con `README.md`, `shots/` (planos + `timeline.json`), `banda.py`. Plantilla
   chica: `episodios/nodo_404/`.
3. Muchos planos con poses calculadas → `planos.py` que escribe los JSON y chequea el encuadre
   (`episodios/duende_rojo/planos.py`, `episodios/nunca_se_apagan/planos.py`).
4. Storyboard, plano por plano, banda, montaje: AGENTS.md.

### Nuevo episodio que reusa un escenario (San Isidro)

Así lo hace `episodios/nunca_se_apagan/`:

- En cada plano: `"catedral": {...}`, `"servidores": {...}` y `"entorno": {"datos":
  "../catedral/data/entorno.json", ...}`. La ruta es relativa al episodio nuevo.
- Estilos: copiar los que se usen de `episodios/catedral/estilos/` a `episodios/<ep>/estilos/` y
  anotar en el README de qué commit salieron (se separan: hoy los dos `cyberpunk.json` ya
  difieren).
- Alturas del piso para cámara y personajes: muestrear la grilla `terreno` de `entorno.json`
  (función `H(x, y)` en `nunca_se_apagan/planos.py`).
- `"extends": "../../catedral/shots/vistas.json"` también funciona, pero trae sus 8 cámaras y su
  `"datos": "data/entorno.json"`, que se buscaría en el episodio nuevo: pisarlos en el plano.
- No se toca nada de `episodios/catedral/`: si el escenario necesita un cambio, se hace ahí y se
  revisa con su ronda de fotos.

## Dónde toco para cambiar...

| Quiero cambiar | Toco |
|---|---|
| Colores, cielo, niebla, tinta, post de muchos planos | El estilo (`estilos/*.json`) |
| La hora o el clima de un plano | `hora`, `fecha`, `clima` en el plano |
| Un edificio, calle o árbol del lugar | `data/osm.json` (`alturas`, `excluir`, zonas) y `motor/osm.py`; no editar `entorno.json` a mano (se regenera) |
| La forma de la catedral | `motor/piezas/catedral.py` + ronda `progreso.py` |
| Cámara, acción, duración de un plano | El JSON del plano (o `planos.py` si lo genera: editar el generador, no el JSON) |
| El orden de los planos | `shots/timeline.json` |
| Un efecto 2D | `post` en el plano o el estilo; `python motor/post.py ... --frames` (segundos, sin Blender) |
| Sonido | `episodios/<ep>/banda.py`; síntesis común en `motor/audio/dsp.py` |
| Algo que vale para todos los episodios | El motor, y una línea en PRODUCCION.md |

## Propuestas grandes (no hechas: las decide quien dirige)

**P1. `escenarios/` como carpeta propia.** Mover `episodios/catedral/` a
`escenarios/san_isidro/` (data, estilos, ref, plano base, `aerea.py`, `progreso.py`) y dejar
`episodios/` solo para shorts.
- A favor: el escenario se ve como unidad reutilizable; un agente nuevo entiende que no es un
  short; los episodios lo nombran (`"escenario": "san_isidro"`) en vez de `../catedral/data/...`.
- En contra: hay que tocar `ctx.EPISODIO`, `plano.lugar`, `entorno.datos` y todos los planos de
  `nunca_se_apagan`; el merge choca con las sesiones que hoy tocan `catedral/`. Conviene después
  de mergear lo que está en curso.

**P2. Estilos que se buscan en cadena.** Que `find_estilo` busque en `<ep>/estilos/`, después en
las carpetas de los planos de la cadena de `extends` y por último en el escenario
(`"escenario"` o un `estilos_de`). 
- A favor: se terminan las copias que derivan (`nunca_se_apagan/estilos` vs `catedral/estilos`).
- En contra: un cambio en el estilo del escenario cambia episodios ya publicados; habría que
  congelar los publicados con nombre propio (como `_base_cyberpunk`).

**P3. Rutas relativas al archivo que las declara.** Resolver `entorno.datos` (y futuras rutas)
contra el JSON donde están escritas, no contra el episodio que renderiza.
- A favor: `extends` entre episodios funcionaría sin pisar rutas.
- En contra: cambia el significado de JSON existentes (hoy `nunca_se_apagan` escribe la ruta
  desde su carpeta); habría que migrar o aceptar las dos formas por un tiempo.

**P4. Comparación contra lo real en el motor.** `motor/comparar.py` con dos modos: `aerea`
(cenital + bordes sobre foto aérea, con la georef) y `fotos` (ronda de cámaras desde
`<escenario>/ref/items.json`: foto, posición, mira, lente). Generaliza `episodios/catedral/aerea.py`
y `progreso.py`, que hoy tienen las cámaras y la catedral adentro del código.
- A favor: un lugar nuevo se valida desde el día uno sin copiar scripts.
- En contra: hay que mover las cámaras de `progreso.py` a datos y volver a comparar una ronda
  para verificar que da lo mismo.

**P5. Utilidades de generador de planos y personajes recurrentes en el motor.** Altura del
terreno, ojos, pie y chequeo de encuadre están repetidos en `nunca_se_apagan/planos.py`,
`catedral/progreso.py` y `duende_rojo/planos.py`; los drones de AUSTRAL (Nyx, Aegis, Vesper)
viven en `nodo_0/piezas.py` y `duende_rojo` los importa por ruta. La rama
`claude/sleepy-dijkstra-e06749` ya tiene `motor/pov.py` y `motor/piezas/personajes.py` (la nena):
mergear eso primero y sumar ahí los drones.
- En contra: `nodo_0/piezas.py` es de un episodio publicado; moverlo obliga a re-renderizar un
  cuadro de cada plano de `nodo_0` y `duende_rojo` para comparar.

**P6. Lo de la catedral fuera de `cielo.py`.** `cielo.aplicar` sabe de `catedral.reflectores`,
`brillos` y `vidrios`. Mejor que cada pieza declare qué se enciende de noche (por ejemplo una
clave `noche` en su bloque: lista de rutas y cómo escalan) y `cielo.py` lo aplique sin conocer
la pieza.
- En contra: toca el contrato de las piezas; con un solo caso todavía no hace falta. Hacerlo con
  el segundo edificio que tenga luces propias.

**P7. Dos catedrales de San Isidro.** `episodios/el_relojero/piezas.py` tiene su propia
`build_catedral` (la vieja, de un short publicado) y el motor tiene la nueva. No unificar: el
episodio publicado tiene que seguir saliendo igual. Solo dejarlo escrito (lo está en
`episodios/README.md`).

**P8. `PIEZAS` declaradas por cada módulo.** Hoy `escena.py` importa cada `build_*` a mano y la
lista mezcla genéricas y de lugar. Cada módulo podría exportar su `PIEZAS` y `escena.py`
concatenarlas en un orden fijo.
- En contra: el orden fija nombres y el azar del apagón; cualquier cambio obliga a comparar
  frames de todos los episodios. Poco beneficio por ahora.
