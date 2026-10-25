#!/usr/bin/env bash
# Renders finales de LA BANDERA, uno por vez (2 GB de VRAM: nunca dos Blender a la vez).
cd "$(dirname "$0")/../.."
for s in 01_crisalida 02_despliegue 03_puerto 04_reserva 05_entrega 06_enjambre 06b_gris 07_loop; do
  t0=$(date +%s)
  python motor/render.py episodios/mariposa_bandera "$s" > "episodios/mariposa_bandera/out/_log_$s.txt" 2>&1
  echo "$s exit=$? $(( $(date +%s) - t0 ))s $(tail -1 episodios/mariposa_bandera/out/_log_$s.txt)"
done
echo FIN
