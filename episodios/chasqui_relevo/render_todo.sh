#!/bin/sh
# Renderiza todos los planos del timeline, uno por vez (2 GB de VRAM: nunca dos Blender juntos).
cd "$(dirname "$0")/../.."
for s in 01_apacheta 02_puente 03_camino 04_orbita 05_tokio 06_cierre; do
  python motor/render.py episodios/chasqui_relevo $s --no-post || exit 1
done
echo TODO_RENDERIZADO
