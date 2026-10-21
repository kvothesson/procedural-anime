"""
versiones.py - La presentacion en otro idioma: identica, con los textos traducidos
y las voces en ingles <-> japones (voz/ida_en_a, voz/vuelta_en_a, salida real de chasqui).

    python episodios/chasqui_presenta/versiones.py en    # -> episodios/chasqui_presenta_en/
    python episodios/chasqui_presenta/versiones.py ja    # -> episodios/chasqui_presenta_ja/
    python episodios/chasqui_presenta/versiones.py en episodios/chasqui_presenta_short   # -> ..._short_en/

Ingles: voces ingles <-> japones. Japones: la voz original es japonesa y conversa con
espanol (voz/ida_ja_c, voz/vuelta_es_a). El segundo argumento es el episodio base
(por defecto, este): los shorts verticales salen igual, de chasqui_presenta_short.

El render 3D no tiene texto (todo va en el post), asi que una version no se
renderiza: su render/ es un enlace (junction) al de chasqui_presenta y solo se
rehacen post, subtitulos, banda y montaje. Cada plano de la version hereda del
original ("extends") y pisa post.textos. Las capturas son las de la version
(<version>/capturas/, con capturas/captura_ui.py par=en-ja o par=ja-en): la
ventana con ese par de idiomas y los turnos de las tomas nuevas.

Las voces se corren para que la traduccion entre en el mismo instante que en la
version en espanol (ahi la luz cambia de color): at_nuevo = at_es + (salida_es - salida_nueva).

Despues:
    for s in <planos>; do python motor/post.py episodios/chasqui_presenta_<l> $s --no-video; done
    python episodios/chasqui_presenta/subs.py  episodios/chasqui_presenta_<l>
    python episodios/chasqui_presenta/banda.py episodios/chasqui_presenta_<l>
    python motor/montaje.py episodios/chasqui_presenta_<l>
"""

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "motor"))
from plano import load_shot  # noqa: E402

# lo que dice la version en espanol -> en / ja (lo que no esta aca no se traduce: chasqui, pip, URL)
TEXTOS = {
    "Hace 500 años, los chasquis corrían\nlos Andes llevando mensajes.":
        ("500 years ago, the chasquis ran\nthe Andes carrying messages.",
         "500年前、チャスキたちは\nアンデスを走り、知らせを運んだ。"),
    "Videollamadas, ida y vuelta": ("Video calls, both ways", "ビデオ通話、双方向で"),
    "Tu voz sale traducida.": ("Your voice goes out translated.", "あなたの声は翻訳されて届き、"),
    "La del otro te llega traducida.": ("Theirs comes back translated.", "相手の声も翻訳されて返ってくる。"),
    "Videos y streams": ("Videos and streams", "動画と配信"),
    "Traduce lo que suena en tu compu:": ("Translates whatever your computer plays:", "パソコンで流れる音声を翻訳:"),
    "YouTube, podcasts, clases.": ("YouTube, podcasts, lectures.", "YouTube、ポッドキャスト、授業。"),
    "Micrófono virtual": ("Virtual microphone", "仮想マイク"),
    "Tu voz traducida, en cualquier app": ("Your translated voice, in any app", "翻訳されたあなたの声を、"),
    "que use micrófono.": ("that uses a microphone.", "マイクを使うどのアプリにも。"),
    "12 idiomas": ("12 languages", "12の言語"),
    "Español, inglés, japonés, chino, coreano...": ("Spanish, English, Japanese, Chinese, Korean...",
                                                    "スペイン語、英語、日本語、中国語、韓国語…"),
    "en cualquier combinación.": ("in any combination.", "どの組み合わせでも。"),
    "Tu clave, tu costo": ("Your key, your cost", "自分のキー、自分のコスト"),
    "Usás tu propia API key de OpenAI.": ("You use your own OpenAI API key.", "自分のOpenAI APIキーを使います。"),
    "La app te muestra cuánto gastás.": ("The app shows what you're spending.", "使った金額はアプリに表示されます。"),
    "Las dos voces, al mismo tiempo.": ("Both voices, at the same time.", "ふたつの声を、同時に。"),
    "ES → JA      JA → ES": ("EN → JA      JA → EN", "JA → ES      ES → JA"),
    "Hoy cruzan idiomas.": ("Today they cross languages.", "いま、言葉を越えて。"),
    "traducción simultánea, en tiempo real": ("real-time simultaneous translation", "リアルタイム同時通訳"),
}
ETIQUETAS = {
    "en": {"orig": "{src} · ORIGINAL", "vivo": "{tgt} · CHASQUI, LIVE", "font": "mono"},
    # Consolas no tiene kana: las etiquetas en japones van en la letra de los textos
    "ja": {"orig": "{src} · 原文", "vivo": "{tgt} · CHASQUI リアルタイム翻訳", "font": "texto"},
}
TOMAS = {
    "en": {"ida": ("ida_en_a", "en", "ja"), "vuelta": ("vuelta_en_a", "ja", "en")},
    # ida_ja_a derivo (agrego "Osaka"); ida_ja_b cambio la pregunta: se usa la c, fiel
    "ja": {"ida": ("ida_ja_c", "ja", "es"), "vuelta": ("vuelta_es_a", "es", "ja")},
}
VOZ = HERE / "voz"


def traducir(t, lang):
    t = dict(t)
    if t["text"] in TEXTOS:
        t["text"] = TEXTOS[t["text"]][0 if lang == "en" else 1]
    # Consolas no tiene kana ni kanji (las flechas si: esas se quedan en mono)
    if t.get("font", "texto").startswith("mono") and re.search(r"[぀-ヿ一-鿿]", t["text"]):
        t["font"] = "texto"
    return t


def salida0(take_dir):
    """Segundo (desde t = 0 de la toma) en que llega la primera transcripcion de la traduccion."""
    ev = json.loads((take_dir / "eventos.json").read_text(encoding="utf-8"))
    return next(d["t"] for d in ev["deltas"] if "output" in d["type"])


def main():
    lang = sys.argv[1]
    base = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else HERE
    dst = base.parent / f"{base.name}_{lang}"
    (dst / "shots").mkdir(parents=True, exist_ok=True)
    tl = json.loads((base / "shots" / "timeline.json").read_text(encoding="utf-8"))
    falta = set()
    for s in tl["shots"]:
        cfg = load_shot(base / "shots" / f"{s}.json")
        out = {"extends": f"../../{base.name}/shots/{s}.json"}
        P = cfg.get("post", {})
        if P.get("textos"):
            out["post"] = {"textos": [traducir(t, lang) for t in P["textos"]]}
            falta |= {t["text"] for t in P["textos"] if t["text"] not in TEXTOS and not t["text"].isascii()}
        for I in P.get("imagenes", []):
            if not (dst / I["src"]).exists():
                falta.add(f"captura {dst / I['src']}")
        (dst / "shots" / f"{s}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    if falta:
        raise SystemExit(f"Sin traduccion: {sorted(falta)}")
    (dst / "shots" / "timeline.json").write_text(
        json.dumps(dict(tl, name=f"{base.name}_{lang}"), ensure_ascii=False, indent=1), encoding="utf-8")

    # voces: la traduccion entra donde entraba la del espanol
    ves = json.loads((base / "voces.json").read_text(encoding="utf-8"))
    rel_dir = (base / ves["dir"]).resolve()
    v = {"_desc": f"Version {lang} de {base.name} (generada por versiones.py). Tomas reales de chasqui, "
                  "corridas para que la traduccion entre donde entraba la del espanol.",
         "dir": f"../{HERE.name}/voz", "etiquetas": ETIQUETAS[lang]}
    # lo demas de las voces de la base (p. ej. donde van los subtitulos en vertical) se hereda
    v.update({k: x for k, x in ves.items() if k not in ("_desc", "dir", "ida", "vuelta", "subs_fin_s", "etiquetas")})
    for k, (take, src, tgt) in TOMAS[lang].items():
        at = ves[k]["at"] + salida0(rel_dir / ves[k]["take"]) - salida0(VOZ / take)
        v[k] = {"take": take, "at": round(at, 2), "src": src, "tgt": tgt}
    # la vuelta en ingles termina mas tarde: los subtitulos siguen hasta que entra la primera tarjeta
    t, fps = 0.0, tl["fps_unique"]
    for s in tl["shots"]:
        if s == "05_tambos":
            break
        t += load_shot(base / "shots" / f"{s}.json")["frames"] / fps
    first = load_shot(base / "shots" / "05_tambos.json")["post"]["imagenes"][0]["frames"][0]
    v["subs_fin_s"] = round(t + (first - 1) / fps - 0.1, 2)
    (dst / "voces.json").write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")

    # el mismo render: un junction (sin permisos de administrador en Windows)
    if not (dst / "render").exists():
        subprocess.run(["cmd", "/c", "mklink", "/J", str(dst / "render"), str(base / "render")],
                       check=True, stdout=subprocess.DEVNULL)
    print(f"-> {dst}  (ida {v['ida']['at']} s, vuelta {v['vuelta']['at']} s, subs hasta {v['subs_fin_s']} s)")


if __name__ == "__main__":
    main()
