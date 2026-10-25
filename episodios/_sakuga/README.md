# _sakuga — banco de pruebas del rig humanoide

Duelo de un golpe en el callejón bajo las vías (piezas de Tokio). Tsubame (bufanda roja)
carga, embiste y conecta; Kiri (capucha) lo recibe. No es un episodio: es donde se prueban
técnicas de animación antes de llevarlas a uno.

- `shots/duelo.json`: el duelo original (poses sostenidas, un intermedio al 60 %).
- `shots/duelo_poses.json`: el mismo duelo con `motor/poses.py`.

## Por qué `motor/poses.py` y no seguir con lo que había

El rig de `piezas.py` ya tenía poses sostenidas e intermedio fijo al 60 %, pero todo el cuerpo
se movía junto (sin overlap), no había anticipación ni overshoot, y los pies patinaban cuando
cambiaba la pose. `poses.py` es ese mismo evaluador sacado del episodio (da exactamente lo mismo
con las claves viejas: diferencia 0,0 m en los 108 cuadros) más breakdown por rama, push,
retraso por rama y contactos por IK. La teoría viene de los editores de poses (Pivot,
StykAnimate, Blender, Spine), sin su interfaz.

`piezas.py` se reconstruyó desde el `.pyc` que quedó en `__pycache__` (el `.py` no estaba en git).

## Criterio de aceptación (duelo_poses, cuadros 31, 34, 41)

| Cuadro | Qué se tiene que ver |
|---|---|
| 31 | Anticipación: Tsubame agachado con el torso y los brazos echados para atrás, más que en la pose `carga`; el pie de adelante en el mismo lugar que en el cuadro 1 |
| 34 | Breakdown de la embestida: el torso ya va adelante y el brazo que va a pegar todavía atrás (overlap); la cabeza llega tarde |
| 41 | Golpe con follow-through: el torso se pasa hacia adelante y vuelve en los cuadros siguientes; el pie de adelante clavado |

## Bitácora

| Plano | Qué se pidió | Qué se cambió |
|---|---|---|
| duelo_poses | Sakuga con la teoría de StykAnimate | `motor/poses.py`; anticipación y overshoot sin piernas (empujar las piernas hacía que el suelo levantara el cuerpo); el overshoot del puño rotaba el brazo para arriba: en el golpe se pasa el torso, no el brazo |
