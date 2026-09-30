"""Expert signals: human-readable red flags of SMS scams.

Each signal is a transparent rule over the normalized text. Signals are used
both as model features and as the *reasons* given to the user.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from sikaguard.normalize import normalize
from sikaguard.pii import find_urls
from sikaguard.urls import UrlInfo, inspect_url

__all__ = ["SIGNAL_CODES", "SIGNAL_MESSAGES", "detect_signals"]

SIGNAL_MESSAGES: dict[str, str] = {
    "demande_code_secret": (
        "Le message demande un code secret (PIN, OTP, mot de passe). "
        "Aucun opérateur ni aucune banque ne le demande jamais."
    ),
    "demande_renvoi_argent": "Le message vous demande d'envoyer ou de renvoyer de l'argent.",
    "frais_a_payer": "Le message exige de payer des frais pour recevoir un gain ou un service.",
    "urgence": "Le message crée un sentiment d'urgence pour vous empêcher de réfléchir.",
    "menace_blocage": "Le message menace de bloquer ou de suspendre votre compte ou votre numéro.",
    "gain_inattendu": "Le message annonce un gain ou un cadeau inattendu.",
    "promesse_gain_financier": "Le message promet de l'argent facile ou un rendement exceptionnel.",
    "offre_emploi": "Le message propose un emploi ou un recrutement non sollicité.",
    "lien_present": "Le message contient un lien.",
    "lien_raccourci": "Le lien est raccourci : sa vraie destination est cachée.",
    "lien_suspect": (
        "Le lien est suspect (adresse IP, extension inhabituelle ou imitation d'une marque)."
    ),
    "mention_operateur": "Le message mentionne un opérateur ou un service de Mobile Money.",
    "contact_numero": "Le message vous demande de contacter un numéro.",
    "majuscules_excessives": "Le message est écrit en majuscules pour attirer l'attention.",
    "montant_present": "Le message mentionne un montant d'argent.",
}

#: Canonical order of the signals (also the order of the model's signal features).
SIGNAL_CODES: tuple[str, ...] = tuple(SIGNAL_MESSAGES)

# ----------------------------------------------------------------- vocabulary

_SEND_VERBS = (
    r"(?:envoy\w*|envoi\w*|communiqu\w*|donn\w*|transmet\w*|transmis\w*|indiqu\w*|fourni\w*"
    r"|partag\w*|renseign\w*|confirm\w*|dict\w*|lis|lisez|lire)"
)
_TYPE_VERBS = r"(?:entr\w*|saisi\w*|tap\w*|compos\w*|mets|mettez|mettre)"
_CODE_WORDS = (
    r"(?:code(?: secret| pin| confidentiel| de retrait| de validation| de confirmation| otp"
    r"| recu)?|pin|mot de passe|mdp|otp)"
)
_CODE_REQUEST_RES = (
    re.compile(rf"\b{_SEND_VERBS}\b[^.]{{0,40}}\b{_CODE_WORDS}\b"),
    re.compile(rf"\b{_TYPE_VERBS}\b[^.]{{0,15}}\b(?:votre|ton|vos|tes)\s+{_CODE_WORDS}\b"),
    re.compile(rf"\b{_CODE_WORDS}\b[^.]{{0,30}}\b(?:au|a|par sms|par whatsapp)\b[^.]{{0,15}}<tel>"),
)
_NEGATION_RE = re.compile(
    r"\bjamais\b|\ba personne\b|\bne\s+(?:le\s+|la\s+|les\s+)?(?!oubli)\w+\s+pas\b"
    r"|\bn'(?!oubli)\w+\s+pas\b"
)
_SENTENCE_SPLIT_RE = re.compile(r"[.!?\n;]+")

_MONEY_REQUEST_RE = re.compile(
    r"\b(?:renvo\w*|retourn\w*|rembours\w*)\b|\bpar erreur\b|\bpar megarde\b"
    r"|\b(?:envoie|envoies|envoyez|envoyer|transfere|transferez|depose|deposez|fais|faites)"
    r"(?:[- ](?:moi|nous))?\b[^.]{0,30}"
    r"(?:\b\d[\d .]*\s?(?:f|fcfa|cfa|francs?)\b|\bargent\b|\bcredit\b|\bunites\b|\btransfert\b)"
)
_FREE_OF_CHARGE_RE = re.compile(r"sans frais|frais\s*:\s*\d|\b0 ?f(?:cfa)? de frais|gratuit\w*")
_FEES_RE = re.compile(
    r"\b(?:pay\w*|regl\w*|envoy\w*|depos\w*|vers\w*|avanc\w*|tap\w*)\b[^.]{0,40}\bfrais\b"
    r"|\bfrais\s+(?:de\s+|d')?(?:dossier|inscription|livraison|deblocage|activation|traitement"
    r"|transport|visa|validation|enregistrement|retrait du gain|douane|liberation)"
)
_URGENCY_RE = re.compile(
    r"\b(?:urgent\w*|urgence|immediat\w*|rapidement|vite|des maintenant|sans delai"
    r"|dernier delai|derniere chance|expire\w*|aujourd'hui (?:seulement|meme|avant))\b"
    r"|\bdans les \d+ ?(?:h|heures?|minutes?|mn|min)\b|\bavant (?:ce soir|demain|minuit|\d+ ?h)\b"
)
_ACCOUNT = r"(?:compte|numero|carte|sim|puce|ligne|portefeuille|solde|gain|argent|acces)"
_BLOCK = r"(?:bloqu\w*|suspen\w*|desactiv\w*|ferm\w*|clotur\w*|supprim\w*|perdre|perdu\w*)"
_BLOCK_RE = re.compile(
    rf"\b{_BLOCK}\b[^.]{{0,40}}\b{_ACCOUNT}\b|\b{_ACCOUNT}\b[^.]{{0,30}}\b{_BLOCK}\b"
)
_PRIZE_RE = re.compile(
    r"\b(?:felicitation\w*|gagnant\w*|tombola|tirage au sort|loterie|jackpot|heureux elu\w*"
    r"|cadeau\w*|recompense\w*|prime exceptionnelle|bonus exceptionnel|lot de)\b"
    r"|\b(?:avez|as|etes|es) (?:ete )?(?:gagne|remporte|selectionne\w*|tire\w* au sort)\b"
)
_EASY_MONEY_RE = re.compile(
    r"\b(?:doubl\w*|tripl\w*|multipli\w*|investi\w*|rendement\w*|benefice\w*|interets?"
    r"|placement\w*|crypto\w*|bitcoin|trading|forex|argent facile|riche\w*)\b"
    r"|\brevenus? (?:passif|garanti)\w*\b"
    r"|\bgagne[rz]? \d[\d ]*\s?(?:f|fcfa)? ?par (?:jour|semaine|mois)\b"
)
_JOB_RE = re.compile(
    r"\b(?:recrut\w*|embauch\w*|emplois?|offre d'emploi|stage remunere|travail a domicile"
    r"|travail en ligne|salaire\w*|job\w*|candidat\w*)\b|\bposte (?:de|a pourvoir|disponible)\b"
)
_OPERATOR_RE = re.compile(
    r"\b(?:orange|mtn|momo|moov|flooz|wave|free ?money|t-?money|airtel|wizall"
    r"|mobile money|ecobank)\b"
)
_CONTACT_RE = re.compile(
    r"\b(?:appel\w*|contact\w*|joign\w*|joindre|whatsapp|ecri\w*|compos\w*|rappel\w*|texto"
    r"|sms au|message au)\b[^.]{0,40}<tel>|<tel>[^.]{0,15}\b(?:whatsapp|appel\w*)\b"
)
_AMOUNT_RE = re.compile(
    r"\b\d[\d .,]*\s?(?:fcfa|cfa|xof|francs?|frs?|f|euros?)\b|\d\s?€|\b\d{1,3}(?:[ .]\d{3})+\b"
)


def _asks_for_code(norm: str) -> bool:
    for sentence in _SENTENCE_SPLIT_RE.split(norm):
        if _NEGATION_RE.search(sentence):
            continue
        if any(rx.search(sentence) for rx in _CODE_REQUEST_RES):
            return True
    return False


def _uppercase_ratio(raw: str) -> bool:
    letters = [ch for ch in raw if ch.isalpha()]
    if len(letters) < 10:
        return False
    return sum(ch.isupper() for ch in letters) / len(letters) > 0.6


_Check = Callable[[str, str, list[UrlInfo]], bool]

_CHECKS: dict[str, _Check] = {
    "demande_code_secret": lambda raw, norm, urls: _asks_for_code(norm),
    "demande_renvoi_argent": lambda raw, norm, urls: bool(_MONEY_REQUEST_RE.search(norm)),
    "frais_a_payer": lambda raw, norm, urls: bool(
        _FEES_RE.search(_FREE_OF_CHARGE_RE.sub(" ", norm))
    ),
    "urgence": lambda raw, norm, urls: bool(_URGENCY_RE.search(norm)),
    "menace_blocage": lambda raw, norm, urls: bool(_BLOCK_RE.search(norm)),
    "gain_inattendu": lambda raw, norm, urls: bool(_PRIZE_RE.search(norm)),
    "promesse_gain_financier": lambda raw, norm, urls: bool(_EASY_MONEY_RE.search(norm)),
    "offre_emploi": lambda raw, norm, urls: bool(_JOB_RE.search(norm)),
    "lien_present": lambda raw, norm, urls: bool(urls),
    "lien_raccourci": lambda raw, norm, urls: any(u.is_shortener for u in urls),
    "lien_suspect": lambda raw, norm, urls: any(u.is_suspect for u in urls),
    "mention_operateur": lambda raw, norm, urls: bool(_OPERATOR_RE.search(norm)),
    "contact_numero": lambda raw, norm, urls: bool(_CONTACT_RE.search(norm)),
    "majuscules_excessives": lambda raw, norm, urls: _uppercase_ratio(raw),
    "montant_present": lambda raw, norm, urls: bool(_AMOUNT_RE.search(norm)),
}
if tuple(_CHECKS) != SIGNAL_CODES:  # pragma: no cover - import-time consistency guard
    raise RuntimeError("signal checks and SIGNAL_CODES are out of sync")


def detect_signals(text: str, *, use_normalization: bool = True) -> list[str]:
    """Return the codes of the signals present in ``text``, in :data:`SIGNAL_CODES` order.

    ``use_normalization=False`` only lower-cases the text (ablation study).
    """
    norm = normalize(text, enabled=use_normalization)
    urls = [inspect_url(u) for u in find_urls(text)]
    return [code for code, check in _CHECKS.items() if check(text, norm, urls)]
