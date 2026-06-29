# Stem Splitter

Isola voce e singoli strumenti di una canzone. Caricala come file o incolla un link YouTube e ottieni le tracce separate (stem) scaricabili.

- Separazione: **[Demucs](https://github.com/adefossez/demucs)** (Meta AI), lo stato dell'arte open source.
- Download da YouTube: **yt-dlp**.
- Interfaccia web: **Gradio**.

## Premessa importante

A differenza di un'app a file singolo (tipo Canzoniere), questa **non** gira come pagina statica: la separazione richiede un modello ML (PyTorch). Di conseguenza:

- **Serve Python.**
- **GitHub Pages NON lo esegue** (niente backend ne' GPU): GitHub serve solo a ospitare il codice. Per eseguirlo: in locale, su **Google Colab** (GPU gratuita) o su **Hugging Face Spaces**.
- Su CPU funziona ma e' lento (qualche minuto a brano). Con una GPU NVIDIA e' molto piu' veloce.

## Stem disponibili

| Modello | Stem prodotti |
|---|---|
| `htdemucs` (default) | voce, batteria, basso, altro — qualita' migliore |
| `htdemucs_ft` | come sopra, piu' lento, leggermente migliore |
| `htdemucs_6s` | voce, batteria, basso, **chitarra**, **piano**, altro |

> `htdemucs_6s` aggiunge chitarra e piano (comodo per chi suona), ma la loro separazione e' sperimentale e meno pulita rispetto a voce/basso/batteria.

## Requisiti

- Python 3.9+
- **FFmpeg** nel PATH (richiesto da yt-dlp e per la gestione audio)
  - Windows: `winget install Gyan.FFmpeg`
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`

## Installazione

```bash
git clone https://github.com/<tuo-utente>/stem-splitter.git
cd stem-splitter
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
```

### GPU NVIDIA (opzionale, consigliato)

Installa prima la build CUDA di PyTorch, poi le altre dipendenze:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
```

## Uso

Ci sono quattro modi per usarlo:

### Mixer web (consigliato per mutare/isolare le tracce)

```bash
python server.py
```

Apri `http://127.0.0.1:5000`. Carica un file o incolla un link, premi **Separa**: a fine elaborazione ogni strumento diventa una channel strip. La separazione gira sul backend (Flask + Demucs); il mixer è interamente nel browser (Web Audio API).

Nel mixer puoi:

- **Muto / Solo / fader** per ogni traccia, con riproduzione sincronizzata e transizioni senza click;
- **forma d'onda** cliccabile (vedi la struttura del brano e vai a un punto preciso) e **spettro live** sotto;
- **loop A–B**: imposta A e B alla posizione attuale e ripeti una sezione (utile per studiare un passaggio);
- **Esporta mix**: salva l'ascolto attuale (muto/solo/volume) come WAV — es. muta la voce per avere una base su cui cantare, o tieni solo la chitarra;
- scorciatoie: **Spazio** = play/pausa.

Per provare il mixer senza separare nulla (e senza avviare il server), premi **Demo**: carica una traccia sintetica a 4 strumenti generata nel browser. Funziona anche aprendo `mixer.html` con un doppio click.

> Lo spettro e la forma d'onda di ogni traccia restano sempre visibili: il **colore** indica cosa stai sentendo (le tracce mutate o non in solo diventano grigie), le **barre** e il tracciato mostrano il contenuto.

> Cache: lo stesso file/link con lo stesso modello non viene rielaborato. I lavori più vecchi (oltre gli ultimi 20) vengono rimossi da `separated/web` automaticamente.

### App desktop (finestra nativa)

```bash
python gui.py
```

Interfaccia grafica nativa basata su Tkinter (incluso in Python): scegli un file o incolla un link YouTube, premi "Separa", segui i progressi nel log. Nessuna dipendenza extra.

> Su Linux, se Tkinter manca: `sudo apt install python3-tk`. Su Windows e macOS e' gia' incluso.

### Interfaccia web semplice (solo download dei singoli stem)

```bash
python app.py
```

Apri l'indirizzo locale che compare (di solito `http://127.0.0.1:7860`). Versione Gradio minimale: produce i singoli stem scaricabili, senza mixer.

### Da riga di comando

```bash
# da file locale
python separate.py -f canzone.mp3

# da YouTube, modello a 6 stem
python separate.py -u "https://youtu.be/..." -m htdemucs_6s

# cartella di output personalizzata
python separate.py -f canzone.mp3 -o risultati
```

Gli stem finiscono in `separated/<modello>/<nome_brano>/`.

## Eseguire su Google Colab (GPU gratuita)

In un notebook:

```python
!pip install demucs yt-dlp
# da file caricato nel Colab:
!python -m demucs -n htdemucs_6s "/content/canzone.mp3"
```

oppure clona il repo e usa le funzioni di `separate.py`.

## Nota legale

Scarica e separa solo materiale di cui hai i diritti, o per uso personale/studio. Rispetta il copyright e i Termini di servizio di YouTube.

## Licenza

MIT
