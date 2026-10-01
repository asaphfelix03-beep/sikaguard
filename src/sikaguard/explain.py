"""Exact explanations for the linear models.

For a logistic regression, the log-odds are a sum of ``coefficient x feature``
terms, so the contribution of every n-gram and every signal is exact.

:class:`LinearExplainer` precomputes everything that does not depend on the
input (feature names, informative terms, signal weights), so that explaining a
prediction only reads the already-computed feature row.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import sparse
from sklearn.pipeline import Pipeline

__all__ = ["STOPWORDS", "LinearExplainer", "is_informative", "signal_weights", "top_terms"]

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


class LinearExplainer:
    """Explains a ``Pipeline([("features", FeatureUnion), ("clf", LogisticRegression)])``."""

    def __init__(self, pipeline: Pipeline) -> None:
        self.features: Any = pipeline.named_steps["features"]
        clf = pipeline.named_steps["clf"]
        self.classes: list[Any] = list(clf.classes_)
        self._coef = np.asarray(clf.coef_)[0]
        names = [str(n) for n in self.features.get_feature_names_out()]
        #: column index -> human-readable word n-gram (informative ones only)
        self._terms: dict[int, str] = {}
        for idx, name in enumerate(names):
            if name.startswith(_WORDS_PREFIX):
                term = name.removeprefix(_WORDS_PREFIX)
                if "<" not in term and is_informative(term):
                    self._terms[idx] = term
        #: learned coefficient of every expert signal
        self.signal_weights: dict[str, float] = {
            name.removeprefix(_SIGNALS_PREFIX): float(self._coef[idx])
            for idx, name in enumerate(names)
            if name.startswith(_SIGNALS_PREFIX)
        }

    def top_terms(self, row: sparse.csr_matrix, *, toward: int, k: int = 3) -> list[str]:
        """Terms of a transformed row that push the model the most toward a class.

        ``toward=1`` explains a scam score, ``toward=-1`` a legitimate one. Terms
        contained in an already chosen term are skipped ("secret" after "code secret").
        """
        sign = 1.0 if toward >= 0 else -1.0
        scored: list[tuple[float, str]] = []
        for idx, value in zip(row.indices, row.data, strict=True):
            term = self._terms.get(int(idx))
            if term is None:
                continue
            contribution = float(value * self._coef[idx] * sign)
            if contribution > 0:
                scored.append((contribution, term))
        scored.sort(key=lambda item: (-item[0], item[1]))
        chosen: list[str] = []
        for _, term in scored:
            words = set(term.split())
            if any(words <= set(c.split()) or set(c.split()) <= words for c in chosen):
                continue
            chosen.append(term)
            if len(chosen) == k:
                break
        return chosen


def top_terms(pipeline: Pipeline, text: str, *, toward: int, k: int = 3) -> list[str]:
    """Convenience wrapper: explain one text with a fresh :class:`LinearExplainer`.

    Building the explainer is the expensive part; reuse one when explaining many texts.
    """
    explainer = LinearExplainer(pipeline)
    row = explainer.features.transform([text]).tocsr()
    return explainer.top_terms(row, toward=toward, k=k)


def signal_weights(pipeline: Pipeline) -> dict[str, float]:
    """Learned coefficient of every expert signal in the binary model."""
    return LinearExplainer(pipeline).signal_weights
