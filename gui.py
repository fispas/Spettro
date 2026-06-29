"""
Stem Splitter - interfaccia grafica desktop (Tkinter, nessuna dipendenza extra).

Finestra nativa: scegli un file o incolla un link YouTube, seleziona il modello,
premi "Separa". La separazione gira in un thread separato cosi' la finestra non
si blocca, con log dei progressi in tempo reale.

Avvio:  python gui.py
"""
import os
import queue
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from separate import MODELS, DEFAULT_MODEL, download_youtube, separate


class StemSplitterGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Stem Splitter")
        root.geometry("660x560")
        root.minsize(560, 480)

        self.log_q: queue.Queue = queue.Queue()
        self.result_dir: Path | None = None
        self.worker: threading.Thread | None = None

        self._build()
        self._poll_queue()

    # ---------- costruzione UI ----------
    def _build(self):
        frm = ttk.Frame(self.root, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        # File audio
        ttk.Label(frm, text="File audio:").grid(row=0, column=0, sticky="w", pady=4)
        self.file_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.file_var).grid(row=0, column=1, sticky="we", padx=6)
        ttk.Button(frm, text="Sfoglia...", command=self._browse_file).grid(row=0, column=2)

        # Link YouTube
        ttk.Label(frm, text="oppure link YouTube:").grid(row=1, column=0, sticky="w", pady=4)
        self.url_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.url_var).grid(row=1, column=1, columnspan=2, sticky="we", padx=6)

        # Modello
        ttk.Label(frm, text="Modello:").grid(row=2, column=0, sticky="w", pady=4)
        self.model_var = tk.StringVar(value=DEFAULT_MODEL)
        ttk.Combobox(frm, textvariable=self.model_var, values=list(MODELS),
                     state="readonly", width=18).grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(frm, text="htdemucs_6s isola anche chitarra e piano",
                  foreground="#777").grid(row=2, column=1, columnspan=2, sticky="e")

        # Cartella output
        ttk.Label(frm, text="Cartella output:").grid(row=3, column=0, sticky="w", pady=4)
        self.out_var = tk.StringVar(value=str(Path("separated").resolve()))
        ttk.Entry(frm, textvariable=self.out_var).grid(row=3, column=1, sticky="we", padx=6)
        ttk.Button(frm, text="...", width=4, command=self._browse_out).grid(row=3, column=2)

        # Pulsanti azione
        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=3, sticky="we", pady=10)
        self.run_btn = ttk.Button(btns, text="Separa", command=self._start)
        self.run_btn.pack(side="left")
        self.open_btn = ttk.Button(btns, text="Apri cartella risultati",
                                   command=self._open_result, state="disabled")
        self.open_btn.pack(side="right")

        # Barra di avanzamento
        self.prog = ttk.Progressbar(frm, mode="indeterminate")
        self.prog.grid(row=5, column=0, columnspan=3, sticky="we", pady=(0, 8))

        # Log
        ttk.Label(frm, text="Log:").grid(row=6, column=0, sticky="w")
        self.log = tk.Text(frm, height=15, wrap="word", state="disabled",
                           background="#111", foreground="#ddd", insertbackground="#ddd")
        self.log.grid(row=7, column=0, columnspan=3, sticky="nsew")
        sb = ttk.Scrollbar(frm, command=self.log.yview)
        sb.grid(row=7, column=3, sticky="ns")
        self.log["yscrollcommand"] = sb.set
        frm.rowconfigure(7, weight=1)

    # ---------- handler ----------
    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Scegli un file audio",
            filetypes=[("Audio", "*.mp3 *.wav *.flac *.m4a *.ogg *.aac"), ("Tutti i file", "*.*")],
        )
        if path:
            self.file_var.set(path)

    def _browse_out(self):
        path = filedialog.askdirectory(title="Scegli la cartella di output")
        if path:
            self.out_var.set(path)

    def _start(self):
        if self.worker and self.worker.is_alive():
            return
        file = self.file_var.get().strip()
        url = self.url_var.get().strip()
        if not file and not url:
            messagebox.showwarning("Input mancante",
                                   "Scegli un file oppure inserisci un link YouTube.")
            return
        if file and not Path(file).exists():
            messagebox.showerror("File non trovato", f"Non esiste: {file}")
            return

        self._set_running(True)
        self._clear_log()
        args = (file, url, self.model_var.get(), self.out_var.get().strip() or "separated")
        self.worker = threading.Thread(target=self._work, args=args, daemon=True)
        self.worker.start()

    def _work(self, file, url, model, out):
        try:
            if url:
                self.log_q.put("Scarico l'audio da YouTube...")
                tmp = Path(tempfile.mkdtemp(prefix="stems_"))
                audio = download_youtube(url, tmp, on_log=self.log_q.put)
            else:
                audio = Path(file)
            self.log_q.put(f"Separazione con '{model}' (puo' richiedere qualche minuto)...")
            stems = separate(audio, model=model, out_dir=out, on_log=self.log_q.put)
            result_dir = Path(out) / model / Path(audio).stem
            self.log_q.put("")
            self.log_q.put("Fatto. Stem creati:")
            for name, p in stems.items():
                self.log_q.put(f"  - {name}: {p.name}")
            self.log_q.put(("__done__", str(result_dir)))
        except subprocess.CalledProcessError as e:
            self.log_q.put(("__error__", f"Demucs ha restituito un errore (codice {e.returncode})."))
        except Exception as e:
            self.log_q.put(("__error__", str(e)))

    # ---------- coda thread-safe ----------
    def _poll_queue(self):
        try:
            while True:
                item = self.log_q.get_nowait()
                if isinstance(item, tuple):
                    kind, payload = item
                    if kind == "__done__":
                        self.result_dir = Path(payload)
                        self._set_running(False)
                        self.open_btn["state"] = "normal"
                    elif kind == "__error__":
                        self._set_running(False)
                        messagebox.showerror("Errore", payload)
                else:
                    self._append(item)
        except queue.Empty:
            pass
        self.root.after(120, self._poll_queue)

    def _append(self, text: str):
        self.log["state"] = "normal"
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log["state"] = "disabled"

    def _clear_log(self):
        self.log["state"] = "normal"
        self.log.delete("1.0", "end")
        self.log["state"] = "disabled"

    def _set_running(self, running: bool):
        if running:
            self.run_btn["state"] = "disabled"
            self.open_btn["state"] = "disabled"
            self.prog.start(12)
        else:
            self.run_btn["state"] = "normal"
            self.prog.stop()

    def _open_result(self):
        if not self.result_dir or not self.result_dir.exists():
            messagebox.showinfo("Nessun risultato", "La cartella dei risultati non esiste.")
            return
        p = str(self.result_dir)
        try:
            if sys.platform.startswith("win"):
                os.startfile(p)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", p])
            else:
                subprocess.run(["xdg-open", p])
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile aprire la cartella:\n{e}")


def main():
    root = tk.Tk()
    StemSplitterGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
