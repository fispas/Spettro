"""
Stem Splitter - logica principale.

Scarica l'audio (opzionalmente da YouTube) e lo separa in singoli strumenti/voce
con Demucs. Usabile come libreria (import) o da riga di comando.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Modelli Demucs disponibili e gli stem che producono.
MODELS = {
    "htdemucs":    ["vocals", "drums", "bass", "other"],                       # qualita' migliore, 4 stem
    "htdemucs_ft": ["vocals", "drums", "bass", "other"],                       # fine-tuned: piu' lento, leggermente migliore
    "htdemucs_6s": ["vocals", "drums", "bass", "guitar", "piano", "other"],    # 6 stem: aggiunge chitarra e piano
}

DEFAULT_MODEL = "htdemucs"


def _check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "FFmpeg non trovato nel PATH. Installalo:\n"
            "  Windows: winget install Gyan.FFmpeg\n"
            "  macOS:   brew install ffmpeg\n"
            "  Linux:   sudo apt install ffmpeg"
        )


def download_youtube(url: str, out_dir: Path, on_log=None) -> Path:
    """Scarica la migliore traccia audio da un link YouTube e ritorna il percorso del file.

    on_log: callback opzionale (str) -> None per ricevere i progressi (usata dalla GUI).
    """
    _check_ffmpeg()
    try:
        from yt_dlp import YoutubeDL
    except ImportError as e:
        raise RuntimeError("yt-dlp non installato. Esegui: pip install yt-dlp") from e

    def _hook(d):
        if not on_log:
            return
        if d.get("status") == "downloading":
            on_log(f"Download {d.get('_percent_str', '').strip()}")
        elif d.get("status") == "finished":
            on_log("Download completato, estrazione audio...")

    out_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(out_dir / "%(title)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }],
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_hook] if on_log else [],
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        base = Path(ydl.prepare_filename(info))
        mp3 = base.with_suffix(".mp3")  # dopo il postprocessing l'estensione diventa .mp3
        return mp3 if mp3.exists() else base


def separate(audio_path: str | Path,
             model: str = DEFAULT_MODEL,
             out_dir: str | Path = "separated",
             on_log=None) -> dict[str, Path]:
    """
    Separa un file audio negli stem con Demucs.
    Ritorna un dizionario {nome_stem: percorso_wav}.

    on_log: callback opzionale (str) -> None. Se fornita, l'output di Demucs viene
    trasmesso riga per riga (utile per la GUI); altrimenti l'esecuzione e' silenziosa.
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(audio_path)
    if model not in MODELS:
        raise ValueError(f"Modello sconosciuto: {model}. Scegli tra {list(MODELS)}")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, "-m", "demucs",
           "-n", model,
           "-o", str(out_dir),
           str(audio_path)]

    if on_log is None:
        subprocess.run(cmd, check=True)
    else:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                on_log(line)
        proc.wait()
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd)

    # Demucs scrive in: <out_dir>/<model>/<nome_brano>/<stem>.wav
    stem_dir = out_dir / model / audio_path.stem
    stems: dict[str, Path] = {}
    for name in MODELS[model]:
        p = stem_dir / f"{name}.wav"
        if p.exists():
            stems[name] = p
    return stems


def process(source: str,
            is_url: bool = False,
            model: str = DEFAULT_MODEL,
            out_dir: str | Path = "separated",
            on_log=None) -> dict[str, Path]:
    """Flusso completo: scarica eventualmente da YouTube, poi separa."""
    if is_url:
        work = Path(tempfile.mkdtemp(prefix="stems_"))
        audio = download_youtube(source, work, on_log=on_log)
    else:
        audio = Path(source)
    return separate(audio, model=model, out_dir=out_dir, on_log=on_log)


def _cli() -> None:
    import argparse
    ap = argparse.ArgumentParser(
        description="Isola voce e strumenti di una canzone (Demucs)."
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("-f", "--file", help="Percorso a un file audio locale")
    src.add_argument("-u", "--url", help="Link YouTube")
    ap.add_argument("-m", "--model", default=DEFAULT_MODEL, choices=list(MODELS),
                    help="Modello Demucs (htdemucs_6s isola anche chitarra e piano)")
    ap.add_argument("-o", "--out", default="separated", help="Cartella di output")
    args = ap.parse_args()

    stems = process(args.file or args.url,
                    is_url=bool(args.url),
                    model=args.model,
                    out_dir=args.out)

    print("\nStem creati:")
    for name, path in stems.items():
        print(f"  {name:8} -> {path}")


if __name__ == "__main__":
    _cli()
