"""
Stem Splitter - interfaccia web (Gradio).

Carica un file audio oppure incolla un link YouTube, scegli il modello,
ottieni gli stem separati e scaricabili.
"""
import tempfile
from pathlib import Path

import gradio as gr

from separate import MODELS, DEFAULT_MODEL, download_youtube, separate

# Etichette fisse degli output (il superset a 6 stem).
ALL_STEMS = MODELS["htdemucs_6s"]


def run(audio_file, youtube_url, model):
    if not audio_file and not (youtube_url and youtube_url.strip()):
        raise gr.Error("Carica un file oppure inserisci un link YouTube.")

    work = Path(tempfile.mkdtemp(prefix="ui_"))
    if youtube_url and youtube_url.strip():
        audio = download_youtube(youtube_url.strip(), work)
    else:
        audio = Path(audio_file)

    stems = separate(audio, model=model, out_dir=work / "out")

    # Ritorna 6 output nello stesso ordine delle etichette; gli stem assenti -> None.
    return [str(stems[name]) if name in stems else None for name in ALL_STEMS]


with gr.Blocks(title="Stem Splitter") as demo:
    gr.Markdown(
        "# Stem Splitter\n"
        "Isola voce e singoli strumenti di una canzone.\n\n"
        "Con il modello a **4 stem** si riempiono solo voce/batteria/basso/altro; "
        "le caselle chitarra e piano restano vuote (servono il modello `htdemucs_6s`)."
    )

    with gr.Row():
        with gr.Column():
            f = gr.Audio(label="File audio", type="filepath")
            url = gr.Textbox(label="oppure link YouTube", placeholder="https://youtu.be/...")
            model = gr.Dropdown(
                choices=list(MODELS), value=DEFAULT_MODEL, label="Modello",
                info="htdemucs_6s isola anche chitarra e piano (sperimentale)",
            )
            btn = gr.Button("Separa", variant="primary")
        with gr.Column():
            outs = [gr.Audio(label=name, type="filepath") for name in ALL_STEMS]

    btn.click(run, inputs=[f, url, model], outputs=outs)


if __name__ == "__main__":
    demo.launch()
