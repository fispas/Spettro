"""
Stem Splitter - web app con mixer.

Avvia un piccolo server Flask che:
  - serve la pagina del mixer (mixer.html);
  - riceve un file caricato o un link YouTube ed esegue la separazione (Demucs);
  - serve gli stem risultanti come file audio.

Il mixer (riproduzione sincronizzata, muto/solo, forma d'onda, spettro, loop A-B,
export del mix) e' interamente lato browser, con la Web Audio API. Il backend si
occupa solo della parte pesante: la separazione.

Ottimizzazioni:
  - cache per impronta dell'input: lo stesso file/link con lo stesso modello non
    viene rielaborato (la separazione richiede minuti);
  - pulizia automatica: si conservano solo gli ultimi MAX_JOBS lavori.

Avvio:  python server.py   ->   http://127.0.0.1:5000
"""
import hashlib
import os
import shutil
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory, send_file
from werkzeug.utils import secure_filename

from separate import MODELS, DEFAULT_MODEL, download_youtube, separate

BASE = Path(__file__).resolve().parent
STEMS_ROOT = BASE / "separated" / "web"
STEMS_ROOT.mkdir(parents=True, exist_ok=True)
MAX_JOBS = 20  # quanti lavori conservare prima di eliminare i piu' vecchi

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024  # upload massimo 300 MB


def _cleanup(keep: int = MAX_JOBS) -> None:
    dirs = [p for p in STEMS_ROOT.iterdir() if p.is_dir()]
    dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for old in dirs[keep:]:
        shutil.rmtree(old, ignore_errors=True)


def _find_cached(job_dir: Path, model: str):
    """Se esiste gia' un risultato completo per (input, modello), restituiscilo."""
    mdir = job_dir / model
    if not mdir.is_dir():
        return None
    subs = [d for d in mdir.iterdir() if d.is_dir()]
    if not subs:
        return None
    track_dir = subs[0]
    found = {name: track_dir / f"{name}.wav"
             for name in MODELS[model]
             if (track_dir / f"{name}.wav").exists()}
    return found or None


def _friendly(err: Exception) -> str:
    s = str(err)
    low = s.lower()
    if "ffmpeg" in low:
        return s  # messaggio gia' esplicito (vedi separate._check_ffmpeg)
    if any(k in low for k in ("private", "unavailable", "removed", "age", "sign in", "login")):
        return "Impossibile scaricare il video: privato, rimosso o con restrizioni."
    if "unsupported url" in low or "is not a valid url" in low:
        return "Link non valido o non supportato."
    return s


@app.get("/")
def index():
    return send_file(BASE / "mixer.html")


@app.get("/models")
def models():
    return jsonify({"models": list(MODELS), "default": DEFAULT_MODEL})


@app.post("/separate")
def do_separate():
    model = request.form.get("model", DEFAULT_MODEL)
    if model not in MODELS:
        return jsonify({"error": f"Modello sconosciuto: {model}"}), 400

    url = (request.form.get("url") or "").strip()
    upload = request.files.get("file")

    # impronta dell'input -> nome cartella deterministico (per la cache)
    if upload and upload.filename:
        h = hashlib.sha1()
        for chunk in iter(lambda: upload.stream.read(1 << 20), b""):
            h.update(chunk)
        upload.stream.seek(0)
        key = hashlib.sha1(f"{model}|file|{h.hexdigest()}".encode()).hexdigest()[:16]
        kind = "file"
    elif url:
        key = hashlib.sha1(f"{model}|url|{url}".encode()).hexdigest()[:16]
        kind = "url"
    else:
        return jsonify({"error": "Fornisci un file o un link YouTube."}), 400

    job_dir = STEMS_ROOT / key
    job_dir.mkdir(parents=True, exist_ok=True)

    cached = _find_cached(job_dir, model)
    if cached:
        stems = cached
        track = next(iter(cached.values())).parent.name
    else:
        try:
            if kind == "file":
                name = secure_filename(upload.filename) or "audio"
                audio = job_dir / name
                upload.save(str(audio))
            else:
                audio = download_youtube(url, job_dir)
            stems = separate(audio, model=model, out_dir=job_dir)
            track = Path(audio).stem
        except Exception as e:
            shutil.rmtree(job_dir, ignore_errors=True)  # non conservare lavori rotti
            return jsonify({"error": _friendly(e)}), 500

    os.utime(job_dir, None)  # aggiorna mtime per la politica LRU
    _cleanup()

    result = [
        {"name": name, "url": f"/stems/{key}/{model}/{track}/{path.name}"}
        for name, path in stems.items()
    ]
    return jsonify({"track": track, "stems": result})


@app.get("/stems/<path:relpath>")
def stems(relpath):
    return send_from_directory(STEMS_ROOT, relpath)


if __name__ == "__main__":
    print("Stem Splitter — mixer su http://127.0.0.1:5000")
    print("Nota: alla prima separazione con un nuovo modello, Demucs lo scarica")
    print("      (qualche minuto); sembra fermo ma sta lavorando.")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
