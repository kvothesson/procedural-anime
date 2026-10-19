"""Analisis de la cancion para cortar el video a la musica.

    python episodios/guardan_una_palabra/audio/analizar.py

1. Separa la voz con demucs (htdemucs) -> audio/voz.wav (sin commitear).
2. Transcribe la voz sola con faster-whisper, sin pista de letra (con la
   letra como pista, whisper la repite donde no se canta) -> letra_tiempos.json
3. Donde hay voz (RMS de la voz por cuarto de segundo) -> voz_activa.json
4. Pulsos y tempo con librosa sobre la mezcla -> beats.json
"""
import json
import subprocess
import wave
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
MP3 = Path.home() / "Downloads" / "Guardan una palabra.mp3"


def leer(path):
    w = wave.open(str(path))
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    return x.reshape(-1, w.getnchannels()).T, w.getframerate()


def guardar(path, x, sr):
    x = np.clip(x, -1, 1)
    w = wave.open(str(path), "wb")
    w.setnchannels(x.shape[0])
    w.setsampwidth(2)
    w.setframerate(sr)
    w.writeframes((x.T * 32767).astype(np.int16).tobytes())
    w.close()


def separar():
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model
    est = AQUI / "estereo44.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(MP3), "-ac", "2", "-ar", "44100", str(est)], check=True)
    x, sr = leer(est)
    m = get_model("htdemucs")
    m.eval()
    ref = x.mean(0)
    xt = torch.from_numpy((x - ref.mean()) / ref.std())[None]
    with torch.no_grad():
        out = apply_model(m, xt, device="cpu", split=True, overlap=0.25, progress=False)[0]
    voz = out[m.sources.index("vocals")].numpy() * ref.std() + ref.mean()
    guardar(AQUI / "voz.wav", voz, sr)
    est.unlink()


def main():
    if not (AQUI / "voz.wav").exists():
        separar()
    v, sr = leer(AQUI / "voz.wav")
    v = v.mean(0)
    paso = sr // 4
    rms = [float(np.sqrt((v[i:i + paso] ** 2).mean())) for i in range(0, len(v) - paso, paso)]
    db = 20 * np.log10(np.array(rms) + 1e-9)
    activa = (db > db.max() - 24).tolist()
    json.dump({"paso_s": 0.25, "db": [round(float(d), 1) for d in db], "activa": activa},
              open(AQUI / "voz_activa.json", "w"))
    from faster_whisper import WhisperModel
    mod = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = mod.transcribe(str(AQUI / "voz.wav"), language="es", word_timestamps=True, vad_filter=True,
                             condition_on_previous_text=False, beam_size=5)
    out = []
    for s in segs:
        out.append({"t0": round(s.start, 2), "t1": round(s.end, 2), "texto": s.text.strip(),
                    "palabras": [[round(w.start, 2), round(w.end, 2), w.word.strip()] for w in s.words]})
    json.dump(out, open(AQUI / "letra_tiempos.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    import librosa
    y, sr2 = librosa.load(str(AQUI / "mono.wav"), sr=22050)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr2)
    bt = librosa.frames_to_time(beats, sr=sr2)
    json.dump({"tempo": float(np.atleast_1d(tempo)[0]), "beats": [round(float(b), 3) for b in bt]},
              open(AQUI / "beats.json", "w"))
    for s in out:
        print(f"{s['t0']:6.1f}-{s['t1']:6.1f} {s['texto']}")
    print("tempo", float(np.atleast_1d(tempo)[0]), "pulsos", len(bt))


if __name__ == "__main__":
    main()
