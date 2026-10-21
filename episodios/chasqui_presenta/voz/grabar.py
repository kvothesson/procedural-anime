"""
grabar.py - Voces en ingles y japones de chasqui_presenta, pasadas por chasqui
de verdad. Es el grabador de El relevo (../../chasqui_relevo/voz/grabar.py, por
importlib) con otras tomas y la key de chasqui (load_config: OPENAI_API_KEY,
chasqui.yaml o la que guardo la ventana), sin tener que exportarla.

    python episodios/chasqui_presenta/voz/grabar.py ida_en [etiqueta]
    python episodios/chasqui_presenta/voz/grabar.py vuelta_en [etiqueta]
    python episodios/chasqui_presenta/voz/grabar.py ida_ja | vuelta_es [etiqueta]   # version japonesa

Escribe en voz/<etiqueta>/ lo mismo que El relevo: entrada.wav, salida.wav y
eventos.json (transcripciones con su tiempo). Requiere chasqui instalado.
"""

import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "grabar_relevo", HERE.parents[1] / "chasqui_relevo" / "voz" / "grabar.py")
rel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rel)

TOMAS = {
    # ida: la pregunta sale de los Andes, en ingles
    "ida_en": {"src": "en", "tgt": "ja", "text": "Hi, did you get to Tokyo okay? I miss you.", "voice": "coral",
               "how": "Warm voice of a young person, asking with affection and a little anxiety. "
                      "Natural, not acted."},
    # vuelta: la misma respuesta de El relevo, ahora hacia el ingles
    "vuelta_en": {"src": "ja", "tgt": "en", "text": "もしもし。東京に着いたよ。こっちは雨だけど、元気だよ。",
                  "voice": "sage", "how": "東京に住む若い人の自然な声。ほっとして、少しうれしそうに。"},
    # version japonesa: la voz original es japonesa y conversa con espanol
    "ida_ja": {"src": "ja", "tgt": "es", "text": "もしもし、東京には無事に着いた？さみしいよ。", "voice": "sage",
               "how": "若い人の自然な声。愛情をこめて、少し心配そうにたずねる。演技っぽくなく。"},
    "vuelta_es": {"src": "es", "tgt": "ja", "text": "Hola, sí, ya llegué a Tokio. Acá llueve, pero estoy bien.",
                  "voice": "coral", "how": "Voz cálida de una persona joven de Buenos Aires, acento rioplatense, "
                                           "aliviada y contenta. Natural, no actuado."},
}


def main():
    name = sys.argv[1]
    tag = sys.argv[2] if len(sys.argv) > 2 else name
    if not os.environ.get("OPENAI_API_KEY"):
        from chasqui.core.config import load_config
        os.environ["OPENAI_API_KEY"] = load_config(os.environ.get("CHASQUI_YAML")).api_key
    rel.TOMAS = TOMAS
    # el grabador de El relevo escribe junto a su propio archivo: se lo apunta aca
    rel.__file__ = str(HERE / "grabar.py")
    sys.argv = [sys.argv[0], name]
    rel.main()
    if tag != name:
        (HERE / name).rename(HERE / tag)
        print(f"-> {HERE / tag}")


if __name__ == "__main__":
    main()
