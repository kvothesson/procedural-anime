# NUNCA SE APAGAN (nombre de trabajo)

San Isidro, en el futuro. Un papá camina de la mano con su hija por Av. del Libertador; ella ve
la catedral encendida y pregunta qué es. Entran: está llena de servidores. Él no sabe por qué,
pero deja los guiños: el frío y una palabra que la gente venía a escuchar. Universo AUSTRAL
(la Catedral de Servidores de RITUAL_404; el frío computa, el calor recuerda; el Verbo se roza,
no se dice).

Publicado el 2026-10-18: https://youtube.com/shorts/l4ME0NIQwVI

Escenario: la catedral, los servidores y el barrio de `episodios/catedral/` (piezas
`catedral`, `servidores`, `entorno`; datos en `../catedral/data/`).

## Decisiones

- **Cámara POV del papá.** Nunca se lo ve; solo su brazo y su mano llevando la de la nena.
- **Diálogo en texto, sin voces.** Subtítulos con aparición palabra por palabra (`timeline.subs`),
  un color para cada uno; cuando ella habla, su visor late.
- **La nena: visor + poncho.** Visor de realidad aumentada sobre los ojos, poncho con guardas y
  capucha. Casi siempre de espaldas o de 3/4: cara, boca y pelo son lo que peor sale con este
  método (docs/PRODUCCION.md), y el visor y la capucha los esquivan.
- **Estilo:** gradiente térmico. Afuera el barrio cálido al atardecer (ventanas ámbar); la
  catedral fría (cian y magenta). Al cruzar la puerta cambia la temperatura de color y aparece la
  niebla fría a ras del piso.
- Sin IA generativa de imagen (regla del repo). NanoBanana para texturas queda como respaldo y
  solo con el OK de quien dirige.

## Guion (~50 s)

| # | Plano | Diálogo |
|---|---|---|
| 1 | Libertador, POV de la mano | **Ella:** Papá, ¿qué es eso? |
| 2 | Contrapicado a la torre | **Él:** Una catedral. ¿Querés entrar? |
| 3 | Puerta, sale la niebla fría | **Ella:** ¡Qué frío! · **Él:** Las iglesias siempre fueron frías. |
| 4 | Nave entre racks | **Ella:** ¿Es una iglesia o una computadora? · **Él:** Las dos. |
| 5 | Caminando | **Ella:** ¿Para qué la usan? · **Él:** Los domingos hay misa. Los otros días rezan ellas. |
| 6 | Núcleo | **Ella:** ¿Por qué las pusieron acá? · **Él:** Nadie se acuerda. Dicen que antes la gente venía a escuchar una palabra. |
| 7 | Bajo la bóveda | **Ella:** ¿Qué palabra? · **Él:** No sé. Pero ellas la siguen escuchando. *(los leds laten todos juntos, una vez)* |

## Planos (storyboard, 54 s, 12 fps únicos → 24 en doses)

Los genera `planos.py` (`planos_del_short()`): recorrido real por el medio de Libertador, el
atrio frente a la torre, la escalinata, bajo el coro alto y el pasillo central hasta el núcleo.
Claves cada 3 cuadros (piernas alternadas, la cámara se mece al paso); el diálogo va en cada JSON
(`"dialogo"`: quién, texto, frames) y de ahí saldrán los subtítulos del montaje y el visor
encendido mientras ella habla.

| # | JSON | Cuadros | Qué pasa |
|---|---|---|---|
| 1 | `01_libertador` | 72 | Caminan de la mano; ella se adelanta y señala la torre: "Papá, ¿qué es eso?" |
| 2 | `02_torre` | 60 | Contrapicado a la torre fría; "Una catedral. ¿Querés entrar?"; ella se da vuelta hacia él |
| 3 | `03_atrio` | 84 | El atrio, la escalinata y la portada; ella tira de la mano |
| 4 | `04_umbral` | 72 | Bajo el coro alto (estilo adentro): "¡Qué frío!" / "Las iglesias siempre fueron frías." |
| 5 | `05_nave` | 84 | Pasillo entre racks: "¿Es una iglesia o una computadora?" / "Las dos." |
| 6 | `06_misa` | 84 | "¿Para qué la usan?" / "Los domingos hay misa. Los otros días rezan ellas." |
| 7 | `07_nucleo` | 96 | El núcleo: "¿Por qué las pusieron acá?" / "Nadie se acuerda. Dicen que antes la gente venía a escuchar una palabra." |
| 8 | `08_boveda` | 96 | Bajo la bóveda: "¿Qué palabra?" / "No sé. Pero ellas la siguen escuchando." Los leds laten juntos |

Puertas de dos hojas en la portada (`catedral.puertas.abre`: se abren en el plano 3, abiertas
adentro). Latido de los leds (`servidores.latido`): en el plano 8, cuadros 85-95, todos los leds de
todos los racks se encienden juntos en blanco frío y el núcleo sube. 

## Sonido (`banda.py`) y subtítulos

Síntesis pura, eventos anclados a (plano, frame). Afuera (cálido): viento, grillos, el Tren de la
Costa lejos a la izquierda (abajo de la barranca), los pasos de los dos (de las claves reales de la
nena; él más grave y desfasado) y un pad de Re add9 con arpegio pulsado; la puerta cruje en el
plano 3. El corte al plano 4 calla la calle: zumbido de los racks (50 Hz + ventiladores), pad frío
de Si sus2, campanitas de vidrio y pasos con la reverb larga de la nave. Un blip por línea (agudo
ella, grave él). El latido: una vocal de coro de muchas voces al mismo tiempo que los leds.

Curva medida: arranque −27,6 dB → afuera −23,5 → al entrar −22,4 → nave −20 → **latido −16,1** (lo
más fuerte; el short corta ahí). Corte: −12,7 LUFS, pico −1,0 dBTP.

Subtítulos: `planos.py` escribe `shots/subs.json` desde el `"dialogo"` de cada plano (tiempo
absoluto, palabra por palabra), ella en cian (su visor), él en ámbar.

```bash
python episodios/nunca_se_apagan/planos.py         # planos, subs.json y timeline
python motor/render.py episodios/nunca_se_apagan <plano>
python episodios/nunca_se_apagan/banda.py
python motor/montaje.py episodios/nunca_se_apagan  # -> out/nunca_se_apagan.mp4
```

No es loop (el montaje avisa: el empalme 08 → 01 difiere); el short termina en el latido.

## Estilo

`estilos/cyberpunk.json` (afuera, hora azul) y `estilos/cyberpunk_adentro.json` (hereda y pisa:
niebla oscura y cercana, ambiente bajo). El sol ya se puso: en el marco de la escena el oeste queda
atrás a la derecha de la caminata y un sol bajo entibiaría la fachada. El barrio se ilumina con sus
ventanas ámbar; la catedral, con reflectores fríos sin sombra (`catedral.reflectores`) y sus
vitrales. Pruebas: `_estilo` (caminando; señalando la torre a ~40 m, donde pasa por arriba de los
árboles) y `_estilo_adentro` (pasillo de la nave).

## Prototipo de riesgo: la nena

Pieza `nena` en `piezas.py` (con el brazo del papá, `papa_brazo`). Criterio:

- Se lee como una nena de ~6 años (1,12 m) desde la altura de los ojos de un adulto.
- Poncho con guardas y capucha; visor que brilla; botas y medias.
- La mano de la nena en la mano del papá, que entra en cuadro desde abajo a la derecha.
- Tres poses: caminando de espaldas; girando la cabeza hacia arriba (habla, visor encendido);
  señalando la catedral.

## Bitácora

| Fecha | Qué se pidió | Qué se cambió |
|---|---|---|
| 2026-10-17 | Short POV papá e hija; texto en vez de voces; nena con visor y poncho; el papá no sabe por qué hay servidores pero da los guiños | Guion; "¿Y la encontraron?" no tenía sentido (la nena no sabía de qué palabra) → "¿Qué palabra?" |
| 2026-10-17 | Prototipo de la nena en POV | Brazos salían del hombro (palos sobre la espalda) → nacen adentro del poncho. Iba adelante del papá → al lado, y en la pose 3 se adelanta un paso para señalar. En la vereda los árboles y las casas tapaban → camina por el medio de Libertador. `planos.py` busca la mira con la nena en cuadro |
| 2026-10-17 | Cara (flequillo bajo la capucha, visor más fino, mejillas) y brazos del costado del poncho | Flequillo en zigzag desparejo (parejo parecía corona), visor de 2 cm, rubor sin tinta. El brazo salía de la espalda porque ella iba adelante: va al costado (0,65 m) y apenas adelante; los brazos nacen abajo y al costado dentro del poncho. `encuadrar()` busca giro e inclinación de la cabeza del papá |
| 2026-10-17 | Pasar al estilo | Hora azul con gradiente térmico. Señalando a 80 m la torre no se veía (árbol, y de noche sin luz propia) → reflectores fríos y el gesto a ~40 m; reflectores al 60 % (quemaban). Adentro salía lavado con la niebla de afuera → estilo `cyberpunk_adentro` (los estilos ahora heredan con `extends`). Charcos de luz de los racks gigantes → energía 12. Paredes del barrio menos rosas |
| 2026-10-17 | Corregir el exterior del storyboard: la nena visible en 1 y 3, plano 2 distinto, fachada sin quemar, árboles que no tapen la torre | Objetivo de mira `encuadre` (la cabeza de la nena en un lugar de la pantalla). Plano 2 desde el borde del atrio: nena → torre → nena. 5 árboles de relleno cortaban la vista a la torre: se quitan. Reflectores puntuales a ras del piso pintaban un cuadrado magenta → conos apuntados; subirles energía no cambiaba nada (el toon topea) → `brillos` en la piedra, chico en la base (quemaba la escalinata) |
| 2026-10-17 | Puertas, latido de leds y render de los planos | Puertas que se abren y latido. En el 8 la cámara miraba la bóveda en el latido (no se veía) → baja a los racks del brazo derecho. Borradores: ella miraba al papá un instante (se interpolaba la posición entre "papá" y un punto lejano) → sostiene la mirada durante su línea; el papá la miraba desde arriba en picada → `encuadre` con la nave adelante; luz del núcleo pintaba un disco cian en el piso → 150 |
| 2026-10-18 | Subtítulos y banda | `subs.json` desde el diálogo; `banda.py` con el gradiente también en el sonido; montaje verificado: 1080×1920, 24 fps, 54,0 s, estéreo 48 kHz |
