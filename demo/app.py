"""sikaguard demo (Gradio). Run locally: ``python demo/app.py``.

Deployable as a Hugging Face Space (see ``demo/README.md``).
Privacy: nothing is stored, Gradio analytics and flagging are disabled.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import gradio as gr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import render_result

from sikaguard import Analyzer, __version__

MAX_LENGTH = 1000
REPO_URL = "https://github.com/asaphfelix03-beep/sikaguard"
REPORT_URL = f"{REPO_URL}/issues/new?template=nouvelle-arnaque.yml"

EXAMPLES = [
    "Service client Orange Money: votre compte sera suspendu ce soir. "
    "Envoyez votre code secret au 0701020304 pour le garder actif.",
    "Je t'ai envoyé 20000 par erreur sur ton wave, renvoie stp c'est urgent",
    "Félicitations! Vous avez gagné 1 000 000 F. Payez 5000 F de frais pour recevoir.",
    "Cliquez ici pour débloquer votre compte: http://mtn-momo-secure.xyz/login",
    "Env0yez v0tre c0de s3cret au service client 0range M0ney",
    "Vous avez reçu 15 000 FCFA de KOUASSI. Nouveau solde: 17 500 FCFA.",
    "Votre code de vérification est 482913. Ne le partagez avec personne.",
    "Maman envoie moi 5000 pour le transport stp",
]

analyzer = Analyzer()
manifest = analyzer.model.manifest

HEADER = """
# 🛡️ sikaguard — détecteur d'arnaques SMS

Collez un SMS reçu : **sikaguard** dit s'il s'agit d'une arnaque (faux transfert,
faux service client, faux gain, lien piégé, faux investissement…), **de quel type**,
et **pourquoi**. Conçu pour les SMS en français d'Afrique de l'Ouest et le Mobile Money.

> 🔒 **Rien n'est enregistré.** Retirez quand même vos informations personnelles avant
> de coller un message.
"""

SEED_WARNING = """
> ⚠️ **Version de démonstration** : le modèle `{version}` a appris sur de vrais SMS
> légitimes et sur des reconstitutions de campagnes d'arnaque réelles (Côte d'Ivoire,
> Sénégal), mais pas encore sur de vrais SMS d'arnaque collectés.
> Ne l'utilisez pas pour prendre une décision importante.
"""

FOOTER = f"""
---
Vous avez reçu une arnaque qui n'est pas détectée ?
[**Signalez-la**]({REPORT_URL}) (anonymisée) pour améliorer le jeu de données ouvert.

Projet open source indépendant, **non affilié** à Orange, MTN, Moov, Wave ni à aucune banque.
Code, données et méthodologie : [{REPO_URL.removeprefix("https://")}]({REPO_URL}) ·
sikaguard {__version__}
"""


def analyze(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "<p>Collez un SMS ci-dessus puis cliquez sur « Analyser ».</p>"
    return render_result(analyzer.analyze(text[:MAX_LENGTH]))


with gr.Blocks(title="sikaguard — détecteur d'arnaques SMS") as demo:
    gr.Markdown(HEADER)
    if manifest.not_for_production:
        gr.Markdown(SEED_WARNING.format(version=manifest.model_version))
    sms = gr.Textbox(
        label="SMS à analyser",
        placeholder="Collez ici le SMS reçu…",
        lines=5,
        max_length=MAX_LENGTH,
    )
    button = gr.Button("Analyser", variant="primary")
    output = gr.HTML()
    gr.Examples(examples=EXAMPLES, inputs=sms, label="Exemples (cliquez pour essayer)")
    gr.Markdown(FOOTER)
    button.click(analyze, inputs=sms, outputs=output)
    sms.submit(analyze, inputs=sms, outputs=output)


if __name__ == "__main__":
    demo.launch(
        server_name=os.environ.get("HOST", "127.0.0.1"),
        server_port=int(os.environ.get("PORT", "7860")),
        footer_links=["gradio"],
    )
