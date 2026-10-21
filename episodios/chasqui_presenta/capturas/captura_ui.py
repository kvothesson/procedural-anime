"""Captura la ventana real de chasqui ui en un modo dado (necesita chasqui instalado).

    python captura_ui.py <adapter> <salida.png> [running] [idiomas] [compacta] [par=es-ja]

par: los idiomas de la ventana (I SPEAK - THEY SPEAK): es-ja, en-ja, ja-en o ja-es.
running: estado ON ROUTE con dos turnos inyectados, leidos de las tomas reales
(eventos.json: lo que chasqui transcribio y tradujo, con la latencia que midio).
No es texto inventado. Sin running, la ventana queda en reposo, tal como abre.
idiomas: despliega la lista de idiomas y la captura junto con la ventana.
compacta: la forma chica de la ventana (sin el panel BUFFER), la del medidor de costo.
No guarda las preferencias del usuario.
"""
import ctypes
import ctypes.wintypes as wt
import json
import re
import sys
import time
import tkinter
from pathlib import Path

ctypes.windll.shcore.SetProcessDpiAwareness(2)
from PIL import ImageGrab

from chasqui.adapters import ADAPTER_LABELS
from chasqui.ui.app import ChasquiApp, _lang_label
from chasqui.ui.runner import TurnLine

adapter, out, flags = sys.argv[1], sys.argv[2], set(sys.argv[3:])
par = next((f[4:] for f in flags if f.startswith("par=")), "es-ja")
EP = Path(__file__).resolve().parents[2]
# (tu turno, el de ellos): cada uno es la toma cuyo original habla ese lado
TURNOS = {"es-ja": ("chasqui_relevo/voz/ida_c", "chasqui_relevo/voz/vuelta_f"),
          "en-ja": ("chasqui_presenta/voz/ida_en_a", "chasqui_presenta/voz/vuelta_en_a"),
          "ja-en": ("chasqui_presenta/voz/vuelta_en_a", "chasqui_presenta/voz/ida_en_a"),
          "ja-es": ("chasqui_presenta/voz/ida_ja_c", "chasqui_presenta/voz/vuelta_es_a")}


def turno(take, direction):
    p = json.loads((EP / take / "eventos.json").read_text(encoding="utf-8"))["pares"][0]
    # la misma limpieza que los subtitulos (subs.py de El relevo): espacios y puntos repetidos
    clean = lambda t: re.sub(r"。+", "。", re.sub(r"(?<=[　-鿿＀-￯])\s+|\s+(?=[　-鿿＀-￯])",
                                                "", re.sub(r"\s+", " ", t).strip()))
    return TurnLine(clean(p["src"]), clean(p["tgt"]), p["latency_ms"], direction)


app = ChasquiApp(tkinter)
app._save_settings = lambda: None
app.var_adapter.set(ADAPTER_LABELS[adapter])
app._on_adapter_change()
left, right = par.split("-")
app.var_left.set(_lang_label(left))
app.var_right.set(_lang_label(right))
app.var_details.set("compacta" not in flags)
app.var_show_devices.set(False)
app._apply_size()
if "running" in flags:
    app._set_state("running")
    mine, theirs = TURNOS[par]
    app._log_turn(turno(mine, "out"))
    app._log_turn(turno(theirs, "in"))
    app.root.update_idletasks()
    app.log.see("end")       # como en la app con el log abajo: se ve lo ultimo que entro
app._update_footer()      # el gasto acumulado real (sin esto dice "no traffic yet")
app.root.attributes("-topmost", True)
app.root.update()
time.sleep(0.8)
app.root.update()


def rect(widget_id):
    hwnd = ctypes.windll.user32.GetAncestor(widget_id, 2)     # GA_ROOT: la ventana de arriba
    r = wt.RECT()
    # DWMWA_EXTENDED_FRAME_BOUNDS = 9: el rectangulo visible, sin la sombra invisible
    ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r))
    return r.left, r.top, r.right, r.bottom


box = rect(app.root.winfo_id())
if "idiomas" in flags:
    cmb = app.cmb_right
    app.root.tk.call("ttk::combobox::Post", str(cmb))
    app.root.update()
    time.sleep(0.5)
    app.root.update()
    # el desplegable es una ventana de Tk sin objeto de Python: se pregunta por su ruta
    pop = app.root.tk.call("ttk::combobox::PopdownWindow", str(cmb))
    q = lambda what: int(app.root.tk.call("winfo", what, pop))
    x, y = q("rootx"), q("rooty")
    box = (min(box[0], x), min(box[1], y), max(box[2], x + q("width")), max(box[3], y + q("height")))
img = ImageGrab.grab(bbox=box, all_screens=True)
img.save(out)
print(out, img.size)
app.root.destroy()
