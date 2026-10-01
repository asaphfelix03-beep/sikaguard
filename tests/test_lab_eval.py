import random

import numpy as np
import pytest
from sklearn.metrics import average_precision_score

from sikaguard.normalize import normalize
from sikaguard_lab.evaluate import bootstrap_ci, recall_at_precision
from sikaguard_lab.perturb import PERTURBATIONS

TEXT = "Félicitations! Envoyez votre code secret au service client Orange Money"


@pytest.mark.parametrize("name", sorted(PERTURBATIONS))
def test_perturbation_changes_text_deterministically(name: str) -> None:
    fn = PERTURBATIONS[name]
    a = fn(TEXT, random.Random(7))
    b = fn(TEXT, random.Random(7))
    assert a == b
    assert a != TEXT
    assert a.strip()


@pytest.mark.parametrize("name", ["leetspeak", "homoglyphs", "zero_width", "emojis", "upper"])
def test_normalization_undoes_most_perturbations(name: str) -> None:
    disguised = PERTURBATIONS[name](TEXT, random.Random(3))
    assert "code secret" in normalize(disguised)


def test_perturbation_on_text_without_long_words() -> None:
    assert PERTURBATIONS["leetspeak"]("ok ça va", random.Random(0)) == "ok ça va"


def test_bootstrap_ci_brackets_point_estimate() -> None:
    rng = np.random.default_rng(0)
    y = np.array([0] * 60 + [1] * 40)
    s = np.concatenate([rng.uniform(0, 0.6, 60), rng.uniform(0.4, 1, 40)])
    low, point, high = bootstrap_ci(average_precision_score, y, s, n=200, seed=1)
    assert low <= point <= high
    assert point == pytest.approx(average_precision_score(y, s))


def test_recall_at_precision() -> None:
    y = np.array([0, 0, 1, 1, 1])
    s = np.array([0.1, 0.6, 0.5, 0.8, 0.9])
    assert recall_at_precision(y, s, 1.0) == pytest.approx(2 / 3)
    assert recall_at_precision(y, s, 0.5) == 1.0
