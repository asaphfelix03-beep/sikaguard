import threading
import time
from pathlib import Path

import pytest

from sikaguard import analyzer as analyzer_module
from sikaguard.analyzer import MODEL_DIR_ENV, Analyzer, analyze
from sikaguard.model import LoadedModel, load_model
from sikaguard.result import ADVICE


@pytest.fixture
def az(tiny_model: LoadedModel) -> Analyzer:
    return Analyzer(model=tiny_model)


SCAM = "Envoyez votre code secret au <TEL> sinon votre compte Orange Money sera bloqué"
LEGIT = "Je suis arrivé à la maison, on se voit demain"


def test_scam_verdict_with_reasons(az: Analyzer) -> None:
    result = az.analyze(SCAM)
    assert result.verdict == "arnaque"
    assert result.category == "usurpation_operateur"
    assert result.category_score is not None
    codes = [r.code for r in result.reasons]
    assert "demande_code_secret" in codes
    assert codes[-1] == "motif_appris"
    assert result.advice == ADVICE["usurpation_operateur"]
    assert result.model_version == "test"


def test_legit_verdict(az: Analyzer) -> None:
    result = az.analyze(LEGIT)
    assert result.verdict == "legitime"
    assert result.category is None
    assert result.category_score is None
    assert result.advice == ADVICE["legitime"]
    assert [r.code for r in result.reasons] == ["motif_legitime"]


def test_thresholds_define_verdicts(tiny_model: LoadedModel) -> None:
    always_suspect = Analyzer(threshold_high=1.0, threshold_low=0.0, model=tiny_model)
    result = always_suspect.analyze(SCAM)
    assert result.verdict == "suspect"
    assert result.advice == ADVICE["suspect"]
    assert result.category is not None
    always_scam = Analyzer(threshold_high=0.0, threshold_low=0.0, model=tiny_model)
    assert always_scam.analyze(LEGIT).verdict == "arnaque"


@pytest.mark.parametrize(("high", "low"), [(0.3, 0.7), (1.5, 0.2), (0.5, -0.1)])
def test_invalid_thresholds(tiny_model: LoadedModel, high: float, low: float) -> None:
    with pytest.raises(ValueError, match="threshold"):
        Analyzer(threshold_high=high, threshold_low=low, model=tiny_model)


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_empty_text_rejected(az: Analyzer, text: str) -> None:
    with pytest.raises(ValueError, match="empty"):
        az.analyze(text)


def test_non_string_rejected(az: Analyzer) -> None:
    with pytest.raises(TypeError):
        az.analyze(42)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="sequence of strings"):
        az.analyze_batch("pas une liste")


@pytest.mark.parametrize("text", ["🎉🎉🎉", "!!!???", "1234", "a" * 5000, "Hello, how are you?"])
def test_unusual_inputs_do_not_crash(az: Analyzer, text: str) -> None:
    result = az.analyze(text)
    assert result.verdict in {"arnaque", "suspect", "legitime"}
    assert 0.0 <= result.score <= 1.0


def test_batch_matches_single(az: Analyzer) -> None:
    batch = az.analyze_batch([SCAM, LEGIT])
    assert batch == [az.analyze(SCAM), az.analyze(LEGIT)]
    assert az.analyze_batch([]) == []


def test_info(az: Analyzer) -> None:
    info = az.info()
    assert info["model_version"] == "test"
    assert info["not_for_production"] is True
    assert info["threshold_high"] == 0.7


def test_model_dir_env(tiny_model_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MODEL_DIR_ENV, str(tiny_model_dir))
    assert Analyzer().info()["model_version"] == "test"
    monkeypatch.delenv(MODEL_DIR_ENV)
    assert Analyzer(model_dir=tiny_model_dir).info()["model_version"] == "test"


def test_default_analyzer_loads_once_across_threads(
    tiny_model_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def slow_load(directory: Path | None = None) -> LoadedModel:
        calls.append(directory)
        time.sleep(0.2)
        return load_model(tiny_model_dir)

    monkeypatch.setattr(analyzer_module, "load_model", slow_load)
    monkeypatch.setattr(analyzer_module, "_default", None)
    results = []

    def worker() -> None:
        results.append(analyze(SCAM).verdict)

    with pytest.warns(UserWarning, match="not for production"):
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    assert len(calls) == 1
    assert results == ["arnaque"] * 8
