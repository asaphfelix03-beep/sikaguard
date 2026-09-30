"""Exact explanations for the linear models.

For a logistic regression, the log-odds are a sum of ``coefficient x feature``
terms, so the contribution of every n-gram and every signal is exact.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.pipeline import Pipeline

__all__ = ["STOPWORDS", "is_informative", "signal_weights", "top_terms"]

_WORDS_PREFIX = "words__"
_SIGNALS_PREFIX = "signals__"

#: Function words that carry weight in the model but explain nothing to a human.
STOPWORDS = frozenset(
    """
    a au aux avec ce ces cet cette chez d de des du dans donc elle elles en entre est et etre
    es etes ete il ils j je l la le les leur leurs lui m ma mais me mes moi mon n ne ni nos notre
    nous on ou par pas plus pour qu que qui s sa sans se ses si son sont sous suis sur t ta te tes
    toi ton tu un une vers vos votre vous y c ca cher chere svp stp ok oui non tres bien tout tous
    toute toutes comme aussi ai as avez ont avoir sera seront etait fait faire bonjour bonsoir
    salut merci ici
    """.split()  # noqa: SIM905 - a word list reads better than 120 quoted strings
)


def is_informative(term: str) -> bool:
    """True if a word n-gram contains at least one meaningful word (3+ letters, not a stopword)."""
    return any(len(word) >= 3 and word.isalpha() and word not in STOPWORDS for word in term.split())


def _parts(pipeline: Pipeline) -> tuple[Any, np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    features = pipeline.named_steps["features"]
    coef = np.asarray(pipeline.named_steps["clf"].coef_)[0]
    names = np.asarray(features.get_feature_names_out())
    return features, coef, names


def top_terms(pipeline: Pipeline, text: str, *, toward: int, k: int = 3) -> list[str]:
    """Words or bigrams of ``text`` that push the binary model the most toward a class.

    ``toward=1`` explains a scam score, ``toward=-1`` a legitimate one.
    Placeholders (``<tel>``...), character n-grams and n-grams made only of
    function words or numbers are excluded: they are not meaningful to a human.
    """
    features, coef, names = _parts(pipeline)
    row = features.transform([text]).tocsr()
    sign = 1.0 if toward >= 0 else -1.0
    scored: list[tuple[float, str]] = []
    for idx, value in zip(row.indices, row.data, strict=True):
        name = str(names[idx])
        term = name.removeprefix(_WORDS_PREFIX)
        if not name.startswith(_WORDS_PREFIX) or "<" in term or not is_informative(term):
            continue
        contribution = float(value * coef[idx] * sign)
        if contribution > 0:
            scored.append((contribution, term))
    scored.sort(key=lambda item: (-item[0], item[1]))
    chosen: list[str] = []
    for _, term in scored:
        words = set(term.split())
        # Skip "secret" when "code secret" is already shown (and vice versa).
        if any(words <= set(c.split()) or set(c.split()) <= words for c in chosen):
            continue
        chosen.append(term)
        if len(chosen) == k:
            break
    return chosen


def signal_weights(pipeline: Pipeline) -> dict[str, float]:
    """Learned coefficient of every expert signal in the binary model."""
    _, coef, names = _parts(pipeline)
    return {
        str(name).removeprefix(_SIGNALS_PREFIX): float(c)
        for name, c in zip(names, coef, strict=True)
        if str(name).startswith(_SIGNALS_PREFIX)
    }
