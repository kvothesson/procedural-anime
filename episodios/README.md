# Episodios y escenarios

Cada carpeta es un short, un escenario o una demo. Cómo se organiza todo en capas:
[docs/CAPAS.md](../docs/CAPAS.md).

| Carpeta | Qué es | Estado | Piezas propias | Reusa de |
|---|---|---|---|---|
| [nodo_404](nodo_404/README.md) | Buenos Aires de noche, apagón y el Obelisco. **Plantilla** de episodio chico | Publicado 2026-10-10 | No (todo del motor: `ciudad`, `plaza`, `obelisco`, `eventos`, `colectivo`) | |
| [chasqui_relevo](chasqui_relevo/README.md) | Mensaje de luz de los Andes a Tokio, con voces reales y subtítulos | Publicado 2026-10-11 | No (`andes`, `viaje`, `tokio`, `espacio` del motor) | |
| [nodo_0](nodo_0/README.md) | La Puna, un galpón y tres drones (UNIVERSO AUSTRAL) | Publicado 2026-10-13 | Sí: puna, galpón, drones Nyx, Aegis y Vesper, HUD, mapa | Banda: instrumentos de `nodo_404/banda.py` |
| [duende_rojo](duende_rojo/README.md) | Un duende rojo sobre el Uritorco (AUSTRAL) | Publicado 2026-10-14 | Sí: Uritorco, tormenta, duende, calle techada | Drones de `nodo_0/piezas.py`; banda de `nodo_0/banda.py` |
| [el_relojero](el_relojero/README.md) | Un robot relojero en la torre de la catedral de San Isidro | Ver su README | Sí: robot, esfera, escalera, torre y **su propia catedral** (la vieja, no la del motor) | Engranajes y despiece del motor; banda de `nodo_404/banda.py` |
| [catedral](catedral/README.md) | **Escenario**, no un short: Catedral de San Isidro real (OSM, SRTM, fotos), servidores, estilos, hora y clima | Base para shorts | `motor/piezas/catedral.py`, `servidores.py`, `entorno.py` | |
| [nunca_se_apagan](nunca_se_apagan/README.md) | POV de un papá y su hija que entran a la catedral de servidores (AUSTRAL) | Publicado 2026-10-18 | Sí: la nena y el brazo del papá | Escenario `catedral`: `../catedral/data/entorno.json` y copias de sus estilos |
| [_reglas](_reglas/README.md) | Demos mal / bien de reglas de PRODUCCION.md | Demo | No | |

## Dependencias entre carpetas (no se ven en el motor)

Tocar un archivo de esta columna puede romper otro episodio:

| Archivo | Lo usa | Cómo |
|---|---|---|
| `nodo_0/piezas.py` | `duende_rojo/piezas.py` | `importlib` por ruta: drones (`build_nyx`, `build_vesper`, pisando `mat_dron`), helpers de malla y materiales (`_m`, `_mix`, `_noise`, `_mesh_obj`, `mat_toon_albedo`) |
| `nodo_0/banda.py` | `duende_rojo/banda.py` | `importlib` por ruta (instrumentos) |
| `nodo_404/banda.py` | `nodo_0/banda.py`, `el_relojero/banda.py` | `importlib` por ruta (instrumentos) |
| `catedral/data/entorno.json` | `nunca_se_apagan` (planos y `planos.py`) | Ruta `../catedral/data/entorno.json` |
| `catedral/estilos/*.json` | `nunca_se_apagan/estilos/` | Copia a mano (ya difieren; `catedral/estilos/_base_cyberpunk.json` es la versión publicada de NUNCA SE APAGAN) |

Los episodios publicados no se cambian: si algo compartido tiene que cambiar, se congela una copia
para el publicado o se re-renderiza un cuadro de cada plano afectado para comparar.

## Qué tiene cada carpeta

- `README.md`: idea, plano por plano, criterio de aceptación, bitácora de correcciones.
- `shots/*.json` + `shots/timeline.json`: los planos y el orden del montaje.
- `banda.py`: partitura y diseño sonoro.
- Opcionales: `piezas.py` (piezas propias), `planos.py` (generador de planos), `estilos/`,
  `data/` (datos de un lugar real), `meta.json` (título, descripción y tags para publicar),
  `subs.py` / `voces.json` (subtítulos y voces reales).
- `render/` y `out/` no van a git: se regeneran desde los JSON.
