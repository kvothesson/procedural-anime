# EL QUE CARGA (publicado 2026-11-22: https://youtube.com/shorts/cep3wtHE0XA)

Short vertical, UNIVERSO AUSTRAL. **Un Hombre-Tanque (gaucho de silicio que gotea aceite negro)
carga sobre los hombros el laboratorio flotante y camina por la Ruta 404.** Arriba nadie lo mira.

Nace del análisis cuadro por cuadro de un corto 2D de otro autor (The Man Under The City, DoodletmeGO).
Se toman técnicas, no la historia: 12 fps reales, color plano con textura de papel, una paleta por
mundo, la roca como silueta que tapa medio cuadro, caminata sobre fondo fijo con cortes de bioma
y un cambio de estilo para la leyenda (acá, filete porteño en vez de tapiz).

Por qué un mecha y no un hombre: el motor resuelve mal caras, pelo y actuación
(`docs/PRODUCCION.md` §1) y las personas por código se ven muñecos. Las máquinas salen bien.

Técnica: se itera sobre el motor (Blender + cel + tinta). Lo nuevo es chico: `papel` en
`motor/post.py` (textura multiplicada) y las piezas de este episodio. La leyenda es 2D
(`leyenda.py`, numpy + PIL, reusa las espirales de `el_fileteador/filete.py`) porque el filete
es dibujo plano y no necesita cámara.

## Criterio de aceptación de los 3 cuadros de prueba

1. **Revelación** (`01_revelacion`): la panza de la roca, casi negra y violeta, ocupa al menos el
   45 % de arriba del cuadro; su punta cae sobre las manos del Hombre-Tanque. Él mide menos de
   1/4 del alto y se lee como gaucho de silicio por silueta sola: sombrero de ala, poncho en
   triángulo, visor encendido. Pampa abajo, cielo claro con nubes. Papel visible sin ensuciar.
2. **Caminata en bioma** (`02_puna`): misma pareja roca y Hombre-Tanque de perfil, en zancada.
   Otro mundo de color (Puna al atardecer: cerros rojos y violetas, suelo ocre). Se entiende
   que camina y que es otro lugar sin texto.
3. **Leyenda en filete** (`03_leyenda`): fondo negro, marco de cintas celeste y blanca, volutas
   y hojas de acanto en las esquinas, el Hombre-Tanque cargando el laboratorio como ícono
   central y un título con letra de volumen. Tiene que parecer un cartel fileteado.

## Plano por plano (34 s, 12 fps únicos)

Gancho en el primer segundo: una montaña que flota y se apoya en algo. Duración pensada para el
rango que mejor retiene (31 a 38 s). Sin voz: cuentan la imagen, el cartel y el sonido.

| # | Plano | Tiempo | Qué pasa | Técnica del corto que toma |
|---|---|---|---|---|
| 01 | `01_revelacion` | 0–4 s | Arranca todo violeta (la panza de la roca) y la cámara baja hasta encontrar al Hombre-Tanque en la pampa | Paneo vertical sobre una sola silueta; revelación de escala |
| 02 | `02_cima` | 4–7 s | Arriba: el borde con pasto y las torres del laboratorio, ventanas cian, nubes y sol. Calma | Contraste arriba/abajo por paleta; plano fijo largo |
| 03 | `03_pie` | 7–10 s | Detalle: la bota vendada pisa, el aceite gotea y mancha la tierra | Plano detalle sobre fondo de un color (rojo) |
| 04 | `04_puna` | 10–13,5 s | Camina por la Puna al atardecer | Caminata sobre fondo fijo, bioma por paleta |
| 05 | `05_nieve` | 13,5–17 s | Camina en la nieve patagónica | Mismo plano, otro mundo; nieve como capa del post |
| 06 | `06_salinas` | 17–20 s | Camina sobre las Salinas Grandes, blanco y azul profundo | Mismo plano, otro mundo |
| 07 | `07_leyenda` | 20–25 s | Cartel fileteado: "El que carga, leyenda del Hombre-Tanque" | Cambio de estilo para la leyenda (filete en vez de tapiz) |
| 08 | `08_visor` | 25–29 s | Primer plano del visor: se glitchea (en sus ojos solo hay errores de renderizado) | Primer plano casi quieto; glitch del canon |
| 09 | `09_lejos` | 29–34 s | Muy lejos: la roca como una columna oscura sobre el horizonte, él diminuto | Rima con el plano general del corto; cierre por escala |

Animación: camina de verdad (`tanque.ciclo`: paso doble de 18 cuadros, zancada 0,85 m) y avanza
a 4·zancada/18 m por cuadro, así el pie apoyado no patina; la cámara lo acompaña a esa velocidad
(`planos.sigue`) y la roca avanza con él. Las claves son constantes (12 fps en unos).
Loop: en el 09 la lente se cierra de 85 a 1400 mm sobre la panza de la roca hasta que el cuadro
es todo violeta, el mismo del primer cuadro del 01.

## Bitácora

- 2026-11-22: primera prueba de los 3 cuadros.
- 2026-11-22, resultado: lámina en `out/prueba_3_cuadros.png`. Cumplen el criterio: roca ~55 % del
  cuadro, Hombre-Tanque ~1/7 del alto y legible por sombrero, poncho y visor; Puna con otra paleta y
  en zancada; cartel fileteado con marco, volutas, acanto, cinta y título con volumen.
  Flojo: la caminata de 3/4 cruza un brazo sobre la cara; la roca es silueta pura sin textura
  pintada (el papel es leve); el pasto del primer plano es ralo; en el cartel sobra negro a los
  lados del ícono y la mancha de aceite no se ve sobre el fondo negro.
  Aprendido: la cámara del motor corta a 500 m (`camera.clip_end`), los cerros lejanos y las nubes
  necesitan 3000; `post.glow.threshold` mayor a 1 rompe la imagen.
- 2026-11-22, correcciones del storyboard (pedido: todo lo flojo + el aceite tiene que dejar
  camino): caminata animada con cámara que acompaña; rastro de aceite bajo cada rodilla (lo
  viejo en una malla, lo nuevo aparece cuando él pasa), gota colgando de cada rodilla y gotas
  que caen; bota con suela, caña, puntera y espuela; cabeza con mandíbula, remaches, tornillos
  de oreja, barbijo y píxeles muertos al lado del visor; la roca sin tinta propia
  (`lineart.usage = OCCLUSION_ONLY`); loop 09 → 01 medido: diferencia media 0,44 sobre 255
  (el 09 va sin niebla y con el violeta que la niebla del 01 le da a la roca); banda con
  pisadas sacadas del ciclo, gotas, bandoneón por bioma, viento, glitch del 08 (final
  -20,2 dB, arranque -18,4 dB).
