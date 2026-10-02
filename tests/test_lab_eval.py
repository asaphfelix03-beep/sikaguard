import random
from pathlib import Path

import numpy as np
import pytest
from sklearn.metrics import average_precision_score

from sikaguard.model import LoadedModel
from sikaguard.normalize import normalize
from sikaguard_lab.evaluate import bootstrap_ci, recall_at_precision
from sikaguard_lab.perturb import PERTURBATIONS
from sikaguard_lab.schema import write_csv

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


def test_proportion_ci() -> None:
    from sikaguard_lab.evaluate import proportion_ci

    low, high = proportion_ci([True] * 10 + [False] * 90, n=300, seed=0)
    assert 0.0 <= low <= 0.10 <= high <= 0.25


def test_africa_benchmark(tmp_path: Path, tiny_model: LoadedModel) -> None:
    from sikaguard import Analyzer
    from sikaguard_lab.evaluate import _africa_benchmark

    assert _africa_benchmark(Analyzer(model=tiny_model), tmp_path / "absent.csv") is None
    path = tmp_path / "afrique.csv"
    rows = [
        {"text": TEXT, "label": "arnaque", "pays": "CI", "canal": "sms"},
        {
            "text": "Bonus offert, cliquez vite",
            "label": "arnaque",
            "pays": "CM",
            "canal": "site_web",
        },
        {
            "text": "Vous avez recu 5000 FCFA. Solde: 7000 FCFA",
            "label": "legitime",
            "pays": "BF",
            "canal": "sms",
        },
    ]
    write_csv(path, rows, ("text", "label", "pays", "canal"))
    out = _africa_benchmark(Analyzer(model=tiny_model), path)
    assert out is not None
    assert (out["n_scams"], out["n_legit"]) == (2, 1)
    assert out["countries"] == {"CI": 1, "CM": 1, "BF": 1}
    assert 0.0 <= out["scams_flagged_arnaque_or_suspect"] <= 1.0
    assert out["sms_scams_flagged"] in {"0/1", "1/1"}
    assert out["legit_flagged_arnaque"] in {"0/1", "1/1"}
    assert [r["verdict"] for r in out["rows"]] == [
        r.verdict for r in Analyzer(model=tiny_model).analyze_batch([r["text"] for r in rows])
    ]


def test_real_africa_benchmark_file_is_valid() -> None:
    from sikaguard_lab.schema import read_csv, validate_rows

    rows = read_csv(Path(__file__).parent.parent / "data" / "eval" / "afrique_reel.csv")
    assert not validate_rows(rows)
    assert all(r["derive_de_modele"] == "false" and r["source_ref"] for r in rows)
    assert {r["label"] for r in rows} == {"arnaque", "legitime"}
