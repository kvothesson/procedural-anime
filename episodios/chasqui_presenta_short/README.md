# CHASQUI, PRESENTACIÓN · shorts verticales

La [presentación](../chasqui_presenta/README.md) en 1080×1920 y 53 s, para Shorts. Mismo recorrido
con las cámaras verticales de [El relevo](../chasqui_relevo/README.md): apacheta (4 s), puente (4 s),
órbita (5 s), Tokio (8 s), tambos (20 s), ida y vuelta (6 s) y cierre con la landing (6 s).

**Zona segura:** todo lo que se tiene que leer va entre el 12% y el 70% de alto y lejos del borde
derecho (YouTube tapa la franja de abajo y la columna de botones). Los subtítulos van más arriba
(`subs_layout` en `voces.json`) y dejan lugar para un original de dos renglones.

Publicados el 2026-10-21: ES https://youtu.be/M51gFEndVuU · EN https://youtu.be/vsdIe_2KCZw ·
JA https://youtu.be/3gEKrd1jbmA. Inglés y japonés son versiones (`_en`, `_ja`) que reusan este render.

```bash
sh episodios/chasqui_presenta_short/render_todo.sh            # 7 planos verticales (~35 min)
for s in 01_apacheta 02_puente 03_orbita 04_tokio 05_tambos 06_ida_vuelta 07_cierre; do
  python motor/post.py episodios/chasqui_presenta_short $s --no-video
done
python episodios/chasqui_presenta/subs.py  episodios/chasqui_presenta_short
python episodios/chasqui_presenta/banda.py episodios/chasqui_presenta_short
python motor/montaje.py episodios/chasqui_presenta_short
# versiones: copiar chasqui_presenta_<l>/capturas a chasqui_presenta_short_<l>/capturas, y
python episodios/chasqui_presenta/versiones.py en episodios/chasqui_presenta_short   # y ja
```
