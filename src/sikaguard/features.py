"""scikit-learn feature extraction: normalized text n-grams + expert signals."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np
from scipy import sparse
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline

from sikaguard.normalize import normalize as normalize_text
from sikaguard.signals import SIGNAL_CODES, detect_signals

__all__ = ["WORD_REGEX", "SignalTransformer", "TextNormalizer", "build_features", "fast_transform"]

#: Placeholders such as ``<tel>`` are kept as single tokens; one-letter words are
#: kept so that bigrams read naturally ("arrive a").
WORD_REGEX = r"<[a-z]+>|\b\w+\b"


class TextNormalizer(TransformerMixin, BaseEstimator):  # type: ignore[misc]
    """Apply :func:`sikaguard.normalize.normalize` to each document."""

    def __init__(self, normalize: bool = True) -> None:
        self.normalize = normalize

    def fit(self, X: Iterable[str], y: Any = None) -> TextNormalizer:  # noqa: N803
        return self

    def transform(self, X: Iterable[str]) -> list[str]:  # noqa: N803
        return [normalize_text(str(t), enabled=self.normalize) for t in X]

    def get_feature_names_out(self, input_features: Any = None) -> np.ndarray[Any, Any]:
        return np.asarray(["text"], dtype=object)


class SignalTransformer(TransformerMixin, BaseEstimator):  # type: ignore[misc]
    """Binary matrix of the expert signals, columns in :data:`SIGNAL_CODES` order."""

    def __init__(self, normalize: bool = True) -> None:
        self.normalize = normalize

    def fit(self, X: Iterable[str], y: Any = None) -> SignalTransformer:  # noqa: N803
        return self

    def transform(self, X: Iterable[str]) -> sparse.csr_matrix:  # noqa: N803
        index = {code: i for i, code in enumerate(SIGNAL_CODES)}
        rows = [detect_signals(str(t), use_normalization=self.normalize) for t in X]
        data = np.zeros((len(rows), len(SIGNAL_CODES)), dtype=np.float64)
        for r, codes in enumerate(rows):
            for code in codes:
                data[r, index[code]] = 1.0
        return sparse.csr_matrix(data)

    def get_feature_names_out(self, input_features: Any = None) -> np.ndarray[Any, Any]:
        return np.asarray(SIGNAL_CODES, dtype=object)


def build_features(normalize: bool = True) -> FeatureUnion:
    """Character n-grams (2-5), word n-grams (1-2) and expert signals."""
    chars = Pipeline(
        [
            ("norm", TextNormalizer(normalize=normalize)),
            (
                "tfidf",
                TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True),
            ),
        ]
    )
    words = Pipeline(
        [
            ("norm", TextNormalizer(normalize=normalize)),
            (
                "tfidf",
                TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, token_pattern=WORD_REGEX),
            ),
        ]
    )
    return FeatureUnion(
        [("chars", chars), ("words", words), ("signals", SignalTransformer(normalize=normalize))]
    )


def fast_transform(union: FeatureUnion, texts: Sequence[str]) -> sparse.csr_matrix:
    """Same matrix as ``union.transform(texts)``, without joblib's dispatch overhead.

    ``FeatureUnion.transform`` goes through ``joblib.Parallel`` even with one job,
    which costs about 1 ms per call: noticeable when analyzing one SMS at a time.
    Unions with transformer weights fall back to the standard path.
    """
    if union.transformer_weights:
        return union.transform(list(texts)).tocsr()
    blocks = [
        transformer.transform(list(texts))
        for _, transformer in union.transformer_list
        if transformer not in ("drop", "passthrough")
    ]
    return sparse.hstack(blocks, format="csr")
