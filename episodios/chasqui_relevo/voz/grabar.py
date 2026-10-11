"""
grabar.py - Las voces del short, pasadas por chasqui de verdad.

    OPENAI_API_KEY=... python episodios/chasqui_relevo/voz/grabar.py ida
    OPENAI_API_KEY=... python episodios/chasqui_relevo/voz/grabar.py vuelta

Cada toma: TTS de la frase original -> Pipeline de chasqui (el mismo que usa
la app) alimentado a VELOCIDAD REAL (un BytesStream lo manda todo de golpe y
la demora no se pareceria a la de una charla) -> se guarda lo que vuelve.

Escribe en voz/<toma>/:
  entrada.wav        la frase original (24 kHz mono)
  salida.wav         la salida tal como llega, con la entrada como t = 0:
                     cada pedazo de audio se ubica en el instante en que llego
  eventos.json       transcripciones con su tiempo (s desde t = 0)

Requiere chasqui instalado (pip install -e D:/repos/chasqui).
"""

import json
import sys
import threading
import time
import wave
from pathlib import Path

import numpy as np

from chasqui.core.audio import AudioStream
from chasqui.core.pipeline import Pipeline

SR = 24000
BPS = SR * 2            # PCM16 mono

TOMAS = {
    # ida: la pregunta sale de los Andes
    "ida": {"src": "es", "tgt": "ja", "text": "¿Llegaste bien?", "voice": "coral",
            "how": "Voz cálida de una persona joven de Buenos Aires, acento rioplatense, "
                   "pregunta con cariño y un poco de ansiedad. Natural, no actuado."},
    # vuelta: la respuesta vuelve desde Tokio
    "vuelta": {"src": "ja", "tgt": "es", "text": "うん、着いたよ。ありがとう！", "voice": "sage",
               "how": "東京に住む若い人の自然な声。ほっとして、少しうれしそうに。"},
}

PRE_S, POST_S = 1.0, 9.0      # silencio antes y despues (el endpoint necesita seguir oyendo)
CHUNK = 2400 * 2              # 100 ms


class PacedStream(AudioStream):
    """Entrega el PCM a velocidad real; despues, silencio hasta que se cierre."""

    def __init__(self, pcm, t0_box):
        self.pcm = pcm
        self.pos = 0
        self.t0_box = t0_box

    def read(self, chunk_size=CHUNK):
        if self.t0_box.get("t0") is None:
            self.t0_box["t0"] = time.time()
        due = self.t0_box["t0"] + self.pos / BPS
        wait = due - time.time()
        if wait > 0:
            time.sleep(wait)
        chunk = self.pcm[self.pos:self.pos + CHUNK]
        if len(chunk) < CHUNK:
            chunk = chunk + b"\x00" * (CHUNK - len(chunk))
        self.pos += CHUNK
        return chunk


class TimedSink(AudioStream):
    def __init__(self, t0_box):
        self.t0_box = t0_box
        self.parts = []          # (t llegada, bytes)

    def write(self, data):
        self.parts.append((time.time() - (self.t0_box.get("t0") or time.time()), data))


def tts(client, toma):
    r = client.audio.speech.create(model="gpt-4o-mini-tts", voice=toma["voice"], input=toma["text"],
                                   instructions=toma["how"], response_format="pcm")
    return r.content


def write_wav(path, pcm):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm)


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "ida"
    toma = dict(TOMAS[name])
    tag = name
    if len(sys.argv) > 2:          # variante: grabar.py ida "otra frase" ida_b
        toma["text"] = sys.argv[2]
        tag = sys.argv[3] if len(sys.argv) > 3 else name + "_b"
    out = Path(__file__).resolve().parent / tag
    out.mkdir(parents=True, exist_ok=True)
    from openai import OpenAI
    client = OpenAI()
    speech = tts(client, toma)
    pcm = b"\x00" * int(PRE_S * BPS) + speech + b"\x00" * int(POST_S * BPS)
    pcm = pcm[:len(pcm) // 2 * 2]
    write_wav(out / "entrada.wav", pcm)
    print(f"{name}: frase {len(speech) / BPS:.2f} s, toma {len(pcm) / BPS:.2f} s")

    box = {"t0": None}
    events = []
    orig_print = print

    def on_tr(ev):
        events.append({"t": time.time() - box["t0"], "src": ev.source_text, "tgt": ev.target_text,
                       "latency_ms": ev.latency_ms})
        orig_print(f"  [{events[-1]['t']:.2f}s] {ev.source_text!r} -> {ev.target_text!r}")

    pipe = Pipeline(source_lang=toma["src"], target_lang=toma["tgt"],
                    api_key=client.api_key, model="gpt-realtime-translate", on_translation=on_tr)
    # ademas de los pares, cada delta de transcripcion con su tiempo
    deltas = []
    import chasqui.core.pipeline as P
    orig_loads = P.json.loads

    def spy(raw, *a, **k):
        ev = orig_loads(raw, *a, **k)
        t = ev.get("type", "") if isinstance(ev, dict) else ""
        if "transcript" in t and box["t0"]:
            deltas.append({"t": time.time() - box["t0"], "type": t,
                           "text": ev.get("delta") or ev.get("transcript") or ""})
        return ev

    P.json.loads = spy
    sink = TimedSink(box)
    th = threading.Thread(target=pipe.run, args=(PacedStream(pcm, box), sink), daemon=True)
    th.start()
    time.sleep(len(pcm) / BPS + 2.0)
    pipe.stop()
    th.join(timeout=5)
    P.json.loads = orig_loads

    # salida ubicada por tiempo de llegada (el endpoint manda silencio tambien:
    # se respeta el orden, y nunca se pisa un pedazo con el siguiente)
    buf = np.zeros(int((len(pcm) / BPS + 4) * SR), np.int16)
    cur = 0
    for t, data in sink.parts:
        a = np.frombuffer(data, np.int16)
        start = max(cur, int(t * SR) - len(a))   # llego al final del pedazo
        start = max(start, 0)
        end = min(len(buf), start + len(a))
        buf[start:end] = a[:end - start]
        cur = end
    write_wav(out / "salida.wav", buf.tobytes())
    (out / "eventos.json").write_text(json.dumps({"toma": toma, "pares": events, "deltas": deltas,
                                                  "audio_parts": len(sink.parts)},
                                                 ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
