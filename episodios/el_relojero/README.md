# EL RELOJERO

En un San Isidro futuro, todo late al compás del reloj de la catedral. Un viejo
robot lo cuida. Una noche se parte el piñón que mueve el reloj y no hay repuesto: el robot
se abre el pecho y su corazón es exactamente esa pieza. Lo monta, el reloj vuelve a andar y
él se apaga. El reloj, a cambio, arma un relojero nuevo (loop).

El reloj está en la torre de la **Catedral de San Isidro** (pedido del director, con foto de referencia): ladrillo rosado con franjas crema, aguja, nave con vitrales, árboles; por las ventanas, copas de árboles y lluvia. Final melancólico.

| Plano | Qué pasa | Estado |
|---|---|---|
| 01_gancho | En la oscuridad, el ojo de un relojero nuevo titila y se enciende (frames 80-108 de la escena del nacimiento: su primer cuadro es el último del 07) | hecho |
| 02_ciudad | La catedral de noche bajo la lluvia: vitrales, faroles y el reloj laten con el tic | hecho |
| 03_subida | Corte de la torre: el robot sube la escalera caracol, un escalón por tic | hecho |
| 04_falla | El piñón empuja a la rueda; en un tic se traba, forcejea, se le parte el diente; la rueda se desboca y se clava | hecho |
| 05_desincronia | La catedral pierde el compás: luces fuera de fase, el reloj se apaga, el colectivo frena en el aire | hecho |
| 06_sacrificio | Saca el piñón roto, lo mira, lo suelta | hecho |
| 06c_pecho | Abre la tapa: su corazón es la misma pieza. Lo saca | hecho |
| 06d_eje | Lo monta en el eje; engrana y el reloj vuelve a andar | hecho |
| 06b_ojo | El ojo titila y se apaga; la cabeza cae | hecho |
| 07_nacimiento | El viejo desplomado, su corazón girando en el reloj; el reloj arma uno nuevo pieza por pieza y le da un corazón nuevo; la cámara llega a su cara apagada | hecho |

## Cómo se regenera

```bash
python episodios/el_relojero/planos.py             # JSON de 04 y 06 (06, 06c, 06d, 06b)
python episodios/el_relojero/fases.py              # fases de engrane y continuidad 04 -> 06
python episodios/el_relojero/planos_nacimiento.py  # 07 y 01 (usa las fases del 06)
python episodios/el_relojero/planos_subida.py      # 03
python episodios/el_relojero/planos_ciudad.py      # 02 y 05 + orden del montaje (timeline.json)
python motor/colision.py episodios/el_relojero <plano>
python motor/render.py episodios/el_relojero <plano>
```

Piezas propias en `piezas.py`: `relojero` y `relojero_viejo` (robot por pivotes con prefijo
de nombres, IK del brazo con palma, agarre, despiece), `esfera` (reloj desde adentro), `sala`.
`catedral`, `escalera` (corte), `pulso` (todo late con el tic). Engranajes: `motor/piezas/mecanica.py`; verificar engrane con `motor/engrane.py`.
