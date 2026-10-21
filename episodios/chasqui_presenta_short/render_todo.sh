#!/bin/sh
# Renderiza todos los planos del timeline, uno por vez (2 GB de VRAM: nunca dos Blender juntos).
cd "$(dirname "$0")/../.."
for s in 01_apacheta 02_puente 03_orbita 04_tokio 05_tambos 06_ida_vuelta 07_cierre; do
  python motor/render.py episodios/chasqui_presenta_short $s --no-post || exit 1
done
echo TODO_RENDERIZADO
