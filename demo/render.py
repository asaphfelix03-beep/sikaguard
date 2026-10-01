"""HTML rendering of a :class:`sikaguard.Result` for the demo (no Gradio import)."""

from __future__ import annotations

from html import escape

from sikaguard.result import Result

#: verdict -> (label, accent color, background, icon)
VERDICT_STYLE = {
    "arnaque": ("Arnaque probable", "#b42318", "#fef3f2", "⛔"),
    "suspect": ("Message suspect", "#93370d", "#fffaeb", "⚠️"),
    "legitime": ("Aucun signe d'arnaque", "#067647", "#ecfdf3", "✅"),
}

CATEGORY_LABELS = {
    "faux_transfert": "Faux transfert « par erreur »",
    "usurpation_operateur": "Faux service client / usurpation d'opérateur",
    "faux_gain": "Faux gain, tombola ou cadeau",
    "phishing_lien": "Lien piégé (phishing)",
    "investissement_emploi": "Faux investissement ou faux emploi",
    "autre_arnaque": "Autre arnaque",
}


def render_result(result: Result) -> str:
    """Self-contained HTML card. Every dynamic string is escaped."""
    label, accent, background, icon = VERDICT_STYLE[result.verdict]
    category = ""
    if result.category is not None:
        cat = result.category
        name = CATEGORY_LABELS.get(cat, cat)
        category = (
            f'<p style="margin:4px 0 0;font-size:15px;">Type : <strong>{escape(name)}</strong></p>'
        )
    reasons = "".join(
        f'<li style="margin:6px 0;">{escape(reason.message)}</li>' for reason in result.reasons
    )
    reasons_block = (
        f'<p style="margin:14px 0 4px;font-weight:600;">Pourquoi ?</p>'
        f'<ul style="margin:0;padding-left:20px;">{reasons}</ul>'
        if reasons
        else ""
    )
    score = round(100 * result.score)
    return (
        f'<div role="status" style="border-left:6px solid {accent};background:{background};'
        f'color:#101828;border-radius:10px;padding:16px 18px;font-size:15px;line-height:1.5;">'
        f'<div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;">'
        f'<span style="font-size:22px;font-weight:700;color:{accent};">{icon} {escape(label)}'
        f"</span>"
        f'<span style="color:#475467;">score de risque : {score} / 100</span></div>'
        f"{category}{reasons_block}"
        f'<p style="margin:14px 0 0;padding:10px 12px;background:#ffffff;border-radius:8px;">'
        f"<strong>Conseil :</strong> {escape(result.advice)}</p>"
        f"</div>"
    )
