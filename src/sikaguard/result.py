"""Result objects returned by :func:`sikaguard.analyze`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

__all__ = ["ADVICE", "CATEGORIES", "LEGIT_CATEGORIES", "SCAM_CATEGORIES", "Reason", "Result"]

Verdict = Literal["arnaque", "suspect", "legitime"]

SCAM_CATEGORIES: tuple[str, ...] = (
    "faux_transfert",
    "usurpation_operateur",
    "faux_gain",
    "phishing_lien",
    "investissement_emploi",
    "autre_arnaque",
)
LEGIT_CATEGORIES: tuple[str, ...] = (
    "notification_transaction",
    "otp",
    "promo_operateur",
    "personnel",
)
CATEGORIES: tuple[str, ...] = SCAM_CATEGORIES + LEGIT_CATEGORIES

#: Practical advice shown to the end user, keyed by scam category or by verdict.
ADVICE: dict[str, str] = {
    "faux_transfert": (
        "Ne renvoyez jamais un argent reçu « par erreur ». Vérifiez votre solde réel dans "
        "l'application ou le menu officiel de votre opérateur : un vrai transfert apparaît "
        "dans votre historique."
    ),
    "usurpation_operateur": (
        "Votre opérateur ne vous demandera jamais votre code secret. Ne répondez pas et "
        "contactez le service client par son numéro officiel."
    ),
    "faux_gain": (
        "On ne gagne pas à un jeu auquel on n'a pas participé. Ne payez jamais de frais "
        "pour recevoir un gain."
    ),
    "phishing_lien": (
        "N'ouvrez pas le lien. Connectez-vous uniquement via l'application ou le site "
        "officiel que vous tapez vous-même."
    ),
    "investissement_emploi": (
        "Aucun placement sérieux ne double votre argent. Un vrai employeur ne demande pas "
        "de frais pour vous embaucher."
    ),
    "autre_arnaque": (
        "Ne donnez ni argent, ni code, ni information personnelle. En cas de doute, "
        "contactez la personne ou l'organisme par un canal officiel."
    ),
    "suspect": (
        "Ce message présente des signes inquiétants. Ne répondez pas, ne cliquez sur aucun "
        "lien et vérifiez auprès de la source officielle."
    ),
    "legitime": (
        "Aucun signe d'arnaque détecté. Restez vigilant : ne communiquez jamais votre code secret."
    ),
}


@dataclass(frozen=True)
class Reason:
    """One human-readable reason behind a verdict."""

    code: str
    message: str


@dataclass(frozen=True)
class Result:
    """Outcome of the analysis of one SMS."""

    verdict: Verdict
    score: float
    category: str | None
    category_score: float | None
    reasons: tuple[Reason, ...]
    advice: str
    model_version: str

    @property
    def is_scam(self) -> bool:
        """True when the verdict is ``"arnaque"``."""
        return self.verdict == "arnaque"

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable representation."""
        return {
            "verdict": self.verdict,
            "score": self.score,
            "category": self.category,
            "category_score": self.category_score,
            "reasons": [{"code": r.code, "message": r.message} for r in self.reasons],
            "advice": self.advice,
            "model_version": self.model_version,
        }
