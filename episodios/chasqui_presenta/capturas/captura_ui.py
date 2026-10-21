"""Captura la ventana real de chasqui ui en un modo dado (necesita chasqui instalado).

    python captura_ui.py <adapter> <salida.png> [running] [idiomas] [compacta]

running: estado ON ROUTE con dos turnos inyectados. Son salidas reales de chasqui
(tomas ida_c y vuelta_f de El relevo), no texto inventado. Sin running, la ventana
queda en reposo, tal como abre.
idiomas: despliega la lista de idiomas y la captura junto con la ventana.
compacta: la forma chica de la ventana (sin el panel BUFFER), la del medidor de costo.
No guarda las preferencias del usuario.
"""
import ctypes
import ctypes.wintypes as wt
import sys
import time
import tkinter

ctypes.windll.shcore.SetProcessDpiAwareness(2)
from PIL import ImageGrab

from chasqui.adapters import ADAPTER_LABELS
from chasqui.ui.app import ChasquiApp, _lang_label
from chasqui.ui.runner import TurnLine

adapter, out, flags = sys.argv[1], sys.argv[2], set(sys.argv[3:])

app = ChasquiApp(tkinter)
app._save_settings = lambda: None
app.var_adapter.set(ADAPTER_LABELS[adapter])
app._on_adapter_change()
app.var_left.set(_lang_label("es"))
app.var_right.set(_lang_label("ja"))
app.var_details.set("compacta" not in flags)
app.var_show_devices.set(False)
app._apply_size()
if "running" in flags:
    app._set_state("running")
    app._log_turn(TurnLine("Hola, ¿llegaste bien a Tokio? Te extraño.",
                           "こんにちは。無事に東京に着きましたか。寂しいです。", 1600, "out"))
    app._log_turn(TurnLine("もしもし。東京に着いたよ。こっちは雨だけど、元気だよ。",
                           "Hola. Ya llegué a Tokio. Aquí está lloviendo, pero estoy bien.", 1600, "in"))
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
