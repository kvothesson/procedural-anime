#!/usr/bin/env bash
# Choques (colision.py) y renders de los planos que cambiaron, uno por vez.
cd "$(dirname "$0")/../.."
EP=episodios/mariposa_bandera
OPC="--cada 2 --entre-raices --sin-base --solo ala_,abd_,torax,cabeza,pata_,antena_ --ignorar vena_,bokeh,torre_bokeh,escamas,halo"
for s in 02_despliegue 04_reserva 05_entrega 06b_gris 07_loop 06_enjambre; do
  python motor/colision.py $EP $s $OPC > $EP/out/_col_$s.txt 2>&1
  echo "choques $s: $(grep -c ' x ' $EP/out/_col_$s.txt)"
done
for s in ${PLANOS:-02_despliegue 04_reserva 05_entrega 06_enjambre 06b_gris 07_loop}; do
  t0=$(date +%s)
  python motor/render.py $EP "$s" > "$EP/out/_log_$s.txt" 2>&1
  echo "render $s exit=$? $(( $(date +%s) - t0 ))s"
done
echo FIN
