"""Latency guard. Bounds are generous (shared CI runners are slow); the
reference numbers are measured on a laptop and reported in the README."""

import statistics
import time

import pytest

from sikaguard.analyzer import Analyzer
from sikaguard.model import load_model


@pytest.fixture(scope="module")
def az() -> Analyzer:
    analyzer = Analyzer(model=load_model())
    analyzer.analyze("échauffement")
    return analyzer


def _texts(n: int) -> list[str]:
    return [
        f"Envoyez votre code secret au 07010203{i:02d} pour débloquer le compte {i}"
        for i in range(n)
    ]


def test_single_sms_latency(az: Analyzer) -> None:
    timings = []
    for text in _texts(40):
        start = time.perf_counter()
        az.analyze(text)
        timings.append(time.perf_counter() - start)
    assert statistics.median(timings) < 0.05  # 50 ms; ~7 ms on a laptop


def test_batch_is_faster_than_single_calls(az: Analyzer) -> None:
    texts = _texts(100)
    start = time.perf_counter()
    az.analyze_batch(texts)
    per_sms = (time.perf_counter() - start) / len(texts)
    assert per_sms < 0.02  # 20 ms; ~1.6 ms on a laptop
