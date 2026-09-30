import numpy as np
import pytest

from sikaguard_lab.train import choose_thresholds


def test_thresholds_on_separable_scores() -> None:
    y = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    s = np.array([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9])
    high, low = choose_thresholds(y, s)
    assert high == 0.6
    assert low == 0.6


def test_thresholds_guarantee_precision_and_recall() -> None:
    rng = np.random.default_rng(0)
    y = np.array([0] * 200 + [1] * 100)
    s = np.clip(np.concatenate([rng.normal(0.3, 0.15, 200), rng.normal(0.75, 0.15, 100)]), 0, 1)
    high, low = choose_thresholds(y, s, min_precision=0.95, min_recall=0.95)
    assert low <= high
    assert y[s >= high].mean() >= 0.95
    assert (s[y == 1] >= low).mean() >= 0.95


def test_thresholds_need_both_classes() -> None:
    with pytest.raises(ValueError, match="both classes"):
        choose_thresholds(np.array([1, 1]), np.array([0.2, 0.8]))
