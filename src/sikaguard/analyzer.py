"""High-level API: turn an SMS into a :class:`~sikaguard.result.Result`."""

from __future__ import annotations

import os
import threading
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from sikaguard.explain import LinearExplainer
from sikaguard.features import fast_transform
from sikaguard.model import LoadedModel, load_model
from sikaguard.result import ADVICE, SCAM_CATEGORIES, Reason, Result, Verdict
from sikaguard.signals import CONTEXT_SIGNALS, SIGNAL_MESSAGES, detect_signals

__all__ = ["MODEL_DIR_ENV", "Analyzer", "analyze", "get_default_analyzer"]

#: Environment variable pointing to an alternative model directory.
MODEL_DIR_ENV = "SIKAGUARD_MODEL_DIR"

_MAX_SIGNAL_REASONS = 4
_MAX_TERMS = 3


def _check_threshold(name: str, value: float) -> float:
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1, got {value}")
    return value


def _quote(terms: list[str]) -> str:
    return ", ".join(f"« {t} »" for t in terms)


class Analyzer:
    """Scam detector with configurable decision thresholds.

    Args:
        threshold_high: score at or above which the verdict is ``"arnaque"``
            (default: value stored in the model manifest).
        threshold_low: score below which the verdict is ``"legitime"``;
            between the two thresholds the verdict is ``"suspect"``.
        model: an already loaded model (mainly for tests).
        model_dir: directory of the model to load (default: ``$SIKAGUARD_MODEL_DIR``
            or the bundled model).
    """

    def __init__(
        self,
        threshold_high: float | None = None,
        threshold_low: float | None = None,
        *,
        model: LoadedModel | None = None,
        model_dir: Path | str | None = None,
    ) -> None:
        if model is None:
            env_dir = os.environ.get(MODEL_DIR_ENV)
            directory = model_dir if model_dir is not None else env_dir
            loaded = load_model(Path(directory) if directory else None)
        else:
            loaded = model
        self._model = loaded
        manifest = loaded.manifest
        self.threshold_high = _check_threshold(
            "threshold_high", manifest.threshold_high if threshold_high is None else threshold_high
        )
        self.threshold_low = _check_threshold(
            "threshold_low", manifest.threshold_low if threshold_low is None else threshold_low
        )
        if self.threshold_low > self.threshold_high:
            raise ValueError("threshold_low must be lower than or equal to threshold_high")
        # Everything that does not depend on the input is computed once here.
        self._explainer = LinearExplainer(loaded.binary)
        self._binary_clf = loaded.binary.named_steps["clf"]
        self._scam_index = self._explainer.classes.index(1)
        self._weights = self._explainer.signal_weights

    @property
    def model(self) -> LoadedModel:
        return self._model

    def info(self) -> dict[str, Any]:
        """Versions and thresholds, for display or monitoring."""
        manifest = self._model.manifest
        return {
            "model_version": manifest.model_version,
            "dataset_version": manifest.dataset_version,
            "sklearn_version": manifest.sklearn_version,
            "threshold_high": self.threshold_high,
            "threshold_low": self.threshold_low,
            "categories": list(manifest.categories),
            "not_for_production": manifest.not_for_production,
            "training_data": manifest.training_data,
        }

    def analyze(self, text: str) -> Result:
        """Analyze one SMS."""
        return self.analyze_batch([text])[0]

    def analyze_batch(self, texts: Sequence[str]) -> list[Result]:
        """Analyze several SMS at once (faster than repeated :meth:`analyze` calls)."""
        if isinstance(texts, str):
            raise TypeError("analyze_batch expects a sequence of strings, not a string")
        for text in texts:
            if not isinstance(text, str):
                raise TypeError(f"SMS text must be a str, got {type(text).__name__}")
            if not text.strip():
                raise ValueError("SMS text must not be empty")
        if not texts:
            return []
        texts = list(texts)
        # One feature extraction per text, shared by the score and the explanation.
        matrix = fast_transform(self._explainer.features, texts)
        scores = self._binary_clf.predict_proba(matrix)[:, self._scam_index]
        verdicts = [self._verdict(float(s)) for s in scores]
        flagged = [i for i, v in enumerate(verdicts) if v != "legitime"]
        categories: dict[int, tuple[str, float]] = {}
        if flagged:
            category = self._model.category
            features = fast_transform(category.named_steps["features"], [texts[i] for i in flagged])
            probas = category.named_steps["clf"].predict_proba(features)
            labels = category.named_steps["clf"].classes_
            for i, row in zip(flagged, probas, strict=True):
                best = int(np.argmax(row))
                categories[i] = (str(labels[best]), round(float(row[best]), 4))
        return [
            self._build(texts[i], float(scores[i]), verdicts[i], matrix[i], categories.get(i))
            for i in range(len(texts))
        ]

    def _verdict(self, score: float) -> Verdict:
        if score >= self.threshold_high:
            return "arnaque"
        if score < self.threshold_low:
            return "legitime"
        return "suspect"

    def _build(
        self,
        text: str,
        score: float,
        verdict: Verdict,
        row: Any,
        category_info: tuple[str, float] | None,
    ) -> Result:
        category: str | None = None
        category_score: float | None = None
        reasons: list[Reason] = []
        if verdict == "legitime":
            advice = ADVICE["legitime"]
            terms = self._explainer.top_terms(row, toward=-1, k=_MAX_TERMS)
            if terms:
                reasons.append(
                    Reason(
                        "motif_legitime",
                        f"Formulation typique de messages légitimes : {_quote(terms)}.",
                    )
                )
        else:
            if category_info is not None:
                category, category_score = category_info
            fallback = "autre_arnaque" if category in SCAM_CATEGORIES else "suspect"
            advice = (
                ADVICE["suspect"]
                if verdict == "suspect"
                else ADVICE.get(category or fallback, ADVICE[fallback])
            )
            signals = [
                c
                for c in detect_signals(text)
                if c not in CONTEXT_SIGNALS and self._weights.get(c, 0.0) > 0
            ]
            signals.sort(key=lambda c: -self._weights[c])
            reasons.extend(Reason(c, SIGNAL_MESSAGES[c]) for c in signals[:_MAX_SIGNAL_REASONS])
            terms = self._explainer.top_terms(row, toward=1, k=_MAX_TERMS)
            if terms:
                reasons.append(
                    Reason(
                        "motif_appris", f"Formulation proche d'arnaques connues : {_quote(terms)}."
                    )
                )
        return Result(
            verdict=verdict,
            score=round(score, 4),
            category=category,
            category_score=category_score,
            reasons=tuple(reasons),
            advice=advice,
            model_version=self._model.manifest.model_version,
        )


_default: Analyzer | None = None
_default_lock = threading.Lock()


def get_default_analyzer() -> Analyzer:
    """The shared analyzer used by :func:`analyze`, loaded once (thread-safe)."""
    global _default
    if _default is None:
        with _default_lock:
            if _default is None:
                analyzer = Analyzer()
                if analyzer.model.manifest.not_for_production:
                    warnings.warn(
                        f"sikaguard model {analyzer.model.manifest.model_version} is flagged "
                        f"'not for production' ({analyzer.model.manifest.training_data}).",
                        UserWarning,
                        stacklevel=3,
                    )
                _default = analyzer
    return _default


def analyze(text: str) -> Result:
    """Analyze one SMS with the bundled model.

    >>> result = analyze("Envoyez votre code secret au 0701020304")  # doctest: +SKIP
    >>> result.verdict, result.category  # doctest: +SKIP
    ('arnaque', 'usurpation_operateur')
    """
    return get_default_analyzer().analyze(text)
