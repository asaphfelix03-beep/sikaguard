"""Exact explanations for the linear models.

For a logistic regression, the log-odds are a sum of ``coefficient x feature``
terms, so the contribution of every n-gram and every signal is exact.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.pipeline import Pipeline

__all__ = ["signal_weights", "top_terms"]

_WORDS_PREFIX = "words__"
_SIGNALS_PREFIX = "signals__"


def _parts(pipeline: Pipeline) -> tuple[Any, np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    features = pipeline.named_steps["features"]
    coef = np.asarray(pipeline.named_steps["clf"].coef_)[0]
    names = np.asarray(features.get_feature_names_out())
    return features, coef, names


def top_terms(pipeline: Pipeline, text: str, *, toward: int, k: int = 3) -> list[str]:
    """Words or bigrams of ``text`` that push the binary model the most toward a class.

    ``toward=1`` explains a scam score, ``toward=-1`` a legitimate one.
    Placeholders (``<tel>``...) and character n-grams are excluded: they are not
    meaningful to a human reader.
    """
    features, coef, names = _parts(pipeline)
    row = features.transform([text]).tocsr()
    sign = 1.0 if toward >= 0 else -1.0
    scored: list[tuple[float, str]] = []
    for idx, value in zip(row.indices, row.data, strict=True):
        name = str(names[idx])
        if not name.startswith(_WORDS_PREFIX) or "<" in name:
            continue
        contribution = float(value * coef[idx] * sign)
        if contribution > 0:
            scored.append((contribution, name.removeprefix(_WORDS_PREFIX)))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [term for _, term in scored[:k]]


def signal_weights(pipeline: Pipeline) -> dict[str, float]:
    """Learned coefficient of every expert signal in the binary model."""
    _, coef, names = _parts(pipeline)
    return {
        str(name).removeprefix(_SIGNALS_PREFIX): float(c)
        for name, c in zip(names, coef, strict=True)
        if str(name).startswith(_SIGNALS_PREFIX)
    }
