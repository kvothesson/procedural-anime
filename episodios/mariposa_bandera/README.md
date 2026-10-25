# LA BANDERA (en construcción)

Short vertical, UNIVERSO AUSTRAL. Una mariposa mecánica basada en la **"bandera argentina"**
(*Morpho epistrophus argentinus*), la Morpho blanca y celeste nacarada de la ribera porteña, en
peligro. Nace de una crisálida colgada del cable de una grúa en Puerto Madero, vuela hasta la
Reserva Ecológica y despierta a las crisálidas apagadas con la luz de sus alas. Cierra tejiendo
una crisálida nueva en el cable: el último cuadro es el primero.

**Foco pedido por quien dirige (2026-10-24):** que la mariposa se vea espectacular y se mueva
bien. Estilo cyberpunk de AUSTRAL: folklore argentino y tecnología, glitch como poesía.

## Qué tiene que hacer sentir (aprobado 2026-10-24: agridulce y en loop)

**La luz no se guarda: se pasa.** Una sola mariposa viva en una ciudad que no la mira, que gasta
toda su luz en despertar a las demás y queda gris. Una de las nuevas vuelve al cable y se vuelve
la crisálida del principio: el video empieza otra vez.

Por qué funciona con este público: cuenta lo mismo que El relevo (algo que pasa de mano en mano)
y EL RELOJERO (alguien que arregla algo), los dos videos del motor que mejor anduvieron; y la
mariposa es real y está en peligro (dato a verificar antes de publicar).

| Plano | Cuadros (24 fps) | Qué pasa | Qué se siente |
|---|---|---|---|
| `01_crisalida` | 60 (2,5 s) | La crisálida late, se sacude, una raja de luz sube y estalla (impacto blanco) | Intriga (gancho) |
| `02_despliegue` | 72 (3 s) | Colgada de la cáscara vacía, cabeza arriba: las alas arrugadas se llenan de luz; las abre | Asombro |
| `03_puerto` | 132 (5,5 s) | Sale de la punta del cable de la grúa y se aleja sobre el dique hasta ser un punto | Soledad |
| `04_reserva` | 168 (7 s) | Árbol seco lleno de crisálidas grises. Toca una: nada. Otra: un parpadeo que se apaga. Pierde color | Desesperanza |
| `05_entrega` | 144 (6 s) | Se posa, abre las alas y vuelca su luz: baja por las ramas y despierta a las crisálidas. Queda gris | Entrega |
| `06_enjambre` | 144 (6 s) | Revientan; el enjambre celeste y blanco sube sobre el río | Alivio |
| `06b_gris` | 60 (2,5 s) | Ella, gris y quieta; atrás se van las luces. Cae una última escama | Lo agridulce |
| `07_loop` | 120 (5 s) | Una de las nuevas llega al cable, donde espera otra crisálida apagada; la toca con las antenas, le deja una chispa y se va. Último cuadro = primero del plano 1, que arranca con ese latido | Continuidad |

Total: 37,5 s. Los planos 3 a 7 los genera `planos.py` (el árbol sale de `arbol.py`, el mismo
que usa la pieza, así las cámaras apuntan a crisálidas reales).

Sonido: un motivo de caja de música de cristal que nace con la grieta, se desafina cuando ella
pierde luz, silencio total cuando queda gris, y el acorde del enjambre entra con la primera
crisálida que revienta.

Banda (`banda.py`, generada): curva de RMS por plano 1 -16,9 dB (gancho) · 2 -18,9 · 3 -19,6 ·
4 -25,0 (desesperanza) · 5 -20,7 (entrega) · pausa de 0,7 s antes del primer estallido
con la lluvia sola (-37,8 dB) · 6 -15,4 (alivio, lo más alto) · 6b -21,4 · 7 -24,4. Corte final -13,9 LUFS.

**Continuidad entre 1 y 2 (pedido de quien dirige):** una mariposa recién salida no aparece
arriba del cable: sale por la punta de la crisálida y queda colgada de la cáscara, cabeza
arriba, con las alas colgando mientras se llenan. Mismo cable y misma crisálida en los dos planos.

## La mariposa (`piezas.py`)

Por qué una pieza nueva: no había ningún personaje alado ni membranas en el motor (los drones de
`nodo_0` son rígidos).

- **Alas**: abanico desde la bisagra con UV (u del cuerpo al borde, v a lo largo del contorno),
  contornos medidos a ojo sobre Morpho epistrophus (ala anterior con ápice redondeado, posterior
  con borde festoneado). Dorso iridiscente en escalones de cel según el ángulo de vista
  (blanco nacarado → celeste → azul → violeta → magenta de canto), base más azul; borde y costa
  oscuros con lunares de neón; nervaduras de luz con un pulso que viaja de la base al borde;
  escamas como grilla de píxeles, algunas destellan (glitch). Reverso bronce oscuro con ocelos de
  neón naranja.
- **Aleteo** (calculado por cuadro): bajada en el 42 % del ciclo, ala posterior atrasada y con
  menos recorrido, punta que se dobla contra el movimiento (shape key), torsión del borde de
  ataque, barrido hacia adelante en la bajada; el cuerpo sube con cada golpe y cabecea; abdomen y
  antenas con retraso.
- **Fondo**: `bokeh`, luces de ciudad y torres oscuras desenfocadas (cámara con `dof`, nuevo en
  `motor/piezas/mundo.py`).

## Criterio de aceptación de `02_alas` (cuadros 13-24, un ciclo)

| Cuadro | Qué se tiene que ver |
|---|---|
| 13 | Alas arriba: el reverso con ocelos de un lado, el dorso del otro |
| 16 | Bajada: el dorso de frente destella blanco pero conserva nervaduras y lunares |
| 18 | El ala de atrás llega tarde respecto de la de adelante |
| 21-22 | Abajo: puntas dobladas, el dorso pasa a azul y violeta |

## Criterio de aceptación de `02_despliegue` (72 cuadros)

| Cuadro | Qué se tiene que ver |
|---|---|
| 1-10 | Posada en el cable, alas chicas y arrugadas que tiemblan; la crisálida vacía colgando atrás |
| 26-42 | La luz entra desde la base del ala: atrás de la onda blanca el color y las nervaduras, adelante membrana opaca |
| 50-58 | Ala estirada del todo; la abre y se ve el dorso blanco celeste |
| 62-72 | Primer golpe: caen escamas de luz del borde |

## Bitácora

| Plano | Qué se pidió / vio | Qué se cambió |
|---|---|---|
| 02_alas | La mariposa chica en el cuadro | Cámara a 17 cm: en la bajada las puntas salen del cuadro (primer plano) |
| 02_alas | Ala celeste saturada, no blanca nacarada | Rampa del dorso: blanco y celeste dominan, violeta y magenta solo de canto |
| 02_alas | El dorso blanco se quemaba en el post | La luz puntual de las alas estaba a milímetros de la membrana: `luz` 0.002; `dorso_k` 0.74; `glow.threshold` 0.82 |
| 02_alas | Ala lila | La tiñe el sol magenta de contraluz: principal más blanca, magenta 0.45 |
| 02_alas / 02_despliegue | Cuerpo más presente | Tórax y abdomen más gruesos, escudo con franja celeste-blanca-celeste de neón, collar, ojos compuestos más grandes; abdomen más corto y juntas más finas (de perfil leía a libélula) |
| 02_despliegue | Despliegue de alas | Nuevo plano: `despliegue` [[frame, 0..1]] escala el ala desde la bisagra, estira la shape key `arruga` y en el shader la luz inunda desde la base con una onda blanca |
| 02_despliegue | Estela de escamas | `estela`: cubitos de luz que salen del borde con la velocidad del ala en cada bajada, frenan, giran y caen; una malla por cuadro |
| 02_despliegue | Arranque chico y vacío; estela que casi no se veía; onda que quemaba; ala fuera de cuadro al final | Cámara a 9,5 cm al empezar y lente de 45 a 34 mm; estela 42 por golpe + 1,2 por cuadro, escamas más grandes; onda celeste a 1,5; crisálida con ventana abierta del lado de cámara |
| 01_crisalida | Crisálida que se lea | Gota rolliza (fina arriba, punta redonda), jade oscuro, costuras de neón, `latido`, `sacude` y una raja en zigzag quebrado que sube desde la punta (`grieta`); cierra con impacto blanco |
| 02_despliegue | La mariposa aparecía arriba del cable, raro si salió de una crisálida colgada | Colgada de la cáscara abierta por la punta (`agarre`, `pliegue`: alas barridas hacia atrás que cuelgan), mismo cable que el plano 1; luz principal del lado de la cámara para que el dorso abierto no quede lila |
| todos | Varias mariposas y crisálidas por plano | `mariposa` y `crisalida` aceptan listas; `lejos` (menos detalle, materiales compartidos por `grupo`), `aparece`/`desaparece`, `apaga` (la luz se retira del borde a la base, sin onda), `abre` (la cerrada se cambia por la abierta), `forma` (el capullo crece desde el enganche) |
| 04_reserva | Las alas salían arrugadas en planos sin despliegue | La shape key nueva nace con valor 1: se pone en 0 al crearla |
| 03_puerto | La mariposa no se veía; la cámara estaba metida en el cable de la grúa; agua plana | Mariposa `sin_tinta` (la tinta en metros la volvía una mancha negra a 40 cm); cámara que la acompaña 44 cuadros y la deja ir, lente de 45 a 24 mm; `halo` desde el cuadro 56 y estela grande para que de lejos sea un punto con cola; agua semitransparente con ondas y el dique espejado debajo con sus materiales (las ventanas se reflejan) |
| 06_enjambre | Papel picado de píxeles: no se leían mariposas | Destino del enjambre a 2 m y cámara que sube entre ellas: pasan a 20-60 cm; foco fijo a 70 cm |
| 06b_gris | La rama encendida tapaba todo | Las venas de las ramas se apagan (0,55 → 0,08) cuando la luz pasa al enjambre |
| 07_loop | El último cuadro no empalmaba (diferencia media 8,7) | Heredaba `grieta` y `sacude` del plano 1 y la estela seguía soltando escamas: claves en 0 y `estela.hasta`. Quedó en 0,0007 |
| 07_loop | Quedaba raro que al final se convirtiera en huevo | Ya no se transforma: llega al cable donde espera otra crisálida apagada, la toca con las antenas (le deja un latido) y se va volando. El plano 1 empieza con ese latido: la luz se pasa otra vez |
| todos | La mariposa traspasaba cosas | `colision.py` ahora mide con la malla evaluada (alas dobladas por shape keys) y las curvas (ramas, cable, antenas), y con `--entre-raices` ignora las piezas de una misma mariposa. Arreglos: antenas giradas hacia atrás colgada (`antenas`); los toques se hacen con las antenas, de frente a la crisálida y con las alas paralelas a la rama, solo en crisálidas con aire alrededor (`planos.toque`, `elegir_intentos`); posada a lo largo de la rama con las alas en V; el enjambre nace debajo de su cáscara, baja hasta un paso libre y sale de la copa antes de subir, cada una a su lugar en una esfera; crisálidas separadas 7 cm |
| banda | Sumar el sonido | `banda.py`: lluvia continua (la cola se suma al principio para el loop), latidos y raja de vidrio en el 1, arpegio que sube con la onda de luz en el 2, ciudad y bocina en el 3, motivo desafinado y toques en el 4, una campanita por crisálida que despierta en el 5 (del mismo árbol), silencio total, acorde del enjambre y motivo armonizado en el 6, menor en el 6b, el mismo latido en el 7. Aleteos desde las claves `aleteo` |
| banda | Corte de sonido entre 2,21 y 2,23 s | La raja terminaba en el cuadro 52 y el estallido entraba en el 53: 40 ms a -24 dB que se oían como un corte, y un latido caía encima del golpe. Ahora la raja dura hasta el impacto, un soplo crece hasta el golpe y no suenan latidos después de la grieta. Chequeo: ningún tramo de 10 ms cae 9 dB bajo los 100 ms anteriores fuera del silencio buscado |
| banda | "Sigue el hueco" | En 2,2 s el audio no tiene huecos (medido cada 4 ms). El único tramo en cero era el silencio total buscado (22,29-23,00 s, cuando ella queda gris), que se oía como un corte: ahora se apaga la música en 80 ms y la lluvia sigue al 35 %. Ningún tramo del mp4 queda en cero (el más largo, 0,04 ms) |
| montaje | ¿Está recortado el cuadro repetido para que loopee perfecto en YouTube? | No lo estaba. `"loop": true` en el timeline: el corte tiene 899 cuadros (sin el último, igual al primero) y la banda dura 37,458 s. Además el audio quedaba 19 ms corto por `-shortest`: ahora video y audio duran 37,458 s |
