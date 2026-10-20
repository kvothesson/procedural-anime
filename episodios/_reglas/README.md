# _reglas: demos de las reglas de producción

No es un episodio: cada demo muestra una regla de `docs/PRODUCCION.md` con un par mal / bien
hecho con el motor. Los planos salen de `planos.py`.

| Plano | Regla | Criterio de aceptación |
|---|---|---|
| giro_mal | §3b Giro continuo y cadencia | La rueda avanza 14° por cuadro (paso de 15°): en pantalla se ve casi quieta, retrocediendo 1° por cuadro |
| giro_bien | §3b Giro continuo y cadencia | Mismas ruedas a 4° por cuadro (0,27 pasos): el giro se lee hacia adelante y parejo |

El engrane está verificado con `motor/engrane.py` (0,0 mm de penetración en los dos).

## Cómo se regenera

```bash
python episodios/_reglas/planos.py
python motor/engrane.py episodios/_reglas giro_mal rueda:pinon
python motor/render.py episodios/_reglas giro_mal --draft
python motor/render.py episodios/_reglas giro_bien --draft
```

## Bitácora

| Plano | Qué se pidió | Qué se cambió |
|---|---|---|
