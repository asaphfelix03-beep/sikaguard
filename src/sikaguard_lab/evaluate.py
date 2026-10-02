"""Benchmark, honest test evaluation and adversarial robustness.

Usage::

    python -m sikaguard_lab.evaluate [--data data/processed] [--reports reports]

* Baselines and the retained model are compared by grouped 5-fold CV on the
  train split, then evaluated **once** on the test split.
* The retained model is the bundled one (``src/sikaguard/assets``), used with
  its own thresholds.
* Confidence intervals: percentile bootstrap (1 000 resamples).
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import average_precision_score, f1_score, precision_recall_curve
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from sikaguard.analyzer import Analyzer
from sikaguard.features import WORD_REGEX, TextNormalizer, build_features
from sikaguard.model import load_model
from sikaguard.signals import CONTEXT_SIGNALS, detect_signals
from sikaguard_lab.build import DATASET_FILE, STATS_FILE
from sikaguard_lab.perturb import PERTURBATIONS
from sikaguard_lab.schema import read_csv
from sikaguard_lab.train import N_FOLDS, SEED, build_binary_pipeline, choose_thresholds

Metric = Callable[[np.ndarray[Any, Any], np.ndarray[Any, Any]], float]
HARD_LEGIT = ("notification_transaction", "otp")
EXTERNAL_FILE = "88milsms_eval.csv"
OBJECTIVES = {
    "test_average_precision": 0.95,
    "recall_at_precision_95": 0.90,
    "hard_legit_false_positive_rate": 0.05,
    "min_detection_under_perturbation": 0.85,
    # Pre-registered on 2026-10-01, before any evaluation on real SMS.
    "real_sms_false_positive_rate": 0.05,
    # Pre-registered on 2026-10-02, before the first evaluation on real scam SMS.
    "real_test_average_precision": 0.95,
    "real_scam_detection_rate": 0.90,
    "real_scam_arnaque_rate": 0.85,
}

LOWER_IS_BETTER = frozenset({"hard_legit_false_positive_rate", "real_sms_false_positive_rate"})

REAL_SCAM_SOURCE = "reportsmishing"  # IMC'25: real scam SMS reported by users
REAL_LEGIT_SOURCE = "88milsms"  # 88milSMS: real personal SMS


def source_name(row: dict[str, str]) -> str:
    """Human-readable origin of a dataset row."""
    if REAL_SCAM_SOURCE in row.get("source_ref", ""):
        return "IMC'25 (real scam SMS)"
    if REAL_LEGIT_SOURCE in row.get("source_ref", ""):
        return "88milSMS (real legitimate SMS)"
    if row.get("campagne"):
        return "documented campaigns (CI/SN)"
    return "seed (hand-written)"


def _is_real(row: dict[str, str]) -> bool:
    ref = row.get("source_ref", "")
    return REAL_SCAM_SOURCE in ref or REAL_LEGIT_SOURCE in ref


# ----------------------------------------------------------------- statistics


def bootstrap_ci(
    metric: Metric,
    y: np.ndarray[Any, Any],
    s: np.ndarray[Any, Any],
    *,
    n: int = 1000,
    seed: int = 0,
) -> tuple[float, float, float]:
    """``(low, point, high)``: 95 % percentile bootstrap interval of ``metric(y, s)``."""
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(n):
        idx = rng.integers(0, len(y), len(y))
        if len(np.unique(y[idx])) < 2:
            continue
        values.append(metric(y[idx], s[idx]))
    point = float(metric(y, s))
    return float(np.percentile(values, 2.5)), point, float(np.percentile(values, 97.5))


def recall_at_precision(y: np.ndarray[Any, Any], s: np.ndarray[Any, Any], target: float) -> float:
    """Best recall reachable with a precision of at least ``target``."""
    precision, recall, _ = precision_recall_curve(y, s)
    ok = precision >= target
    return float(recall[ok].max()) if ok.any() else 0.0


def proportion_ci(flags: Sequence[bool], *, n: int = 1000, seed: int = 0) -> tuple[float, float]:
    """95 % percentile bootstrap interval of a proportion."""
    arr = np.asarray(flags, dtype=float)
    rng = np.random.default_rng(seed)
    means = [arr[rng.integers(0, len(arr), len(arr))].mean() for _ in range(n)]
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def _real_only(
    test: list[dict[str, str]],
    y: np.ndarray[Any, Any],
    scores: np.ndarray[Any, Any],
    verdicts: list[str],
) -> dict[str, Any] | None:
    """Metrics on the real rows of the test split (real scams vs real legitimate SMS)."""
    idx = np.array([i for i, r in enumerate(test) if _is_real(r)], dtype=int)
    if len(idx) == 0 or len(np.unique(y[idx])) < 2:
        return None
    ry, rs = y[idx], scores[idx]
    scam = [i for i in idx if y[i] == 1]
    legit = [i for i in idx if y[i] == 0]
    alert = [verdicts[i] != "legitime" for i in scam]
    as_scam = [verdicts[i] == "arnaque" for i in scam]
    false_alarm = [verdicts[i] == "arnaque" for i in legit]
    ap_lo, ap, ap_hi = bootstrap_ci(_ap, ry, rs)
    rec_lo, rec, rec_hi = bootstrap_ci(lambda a, b: recall_at_precision(a, b, 0.95), ry, rs)
    missed = [test[i]["text"] for i in scam if verdicts[i] == "legitime"]
    return {
        "n_scams": len(scam),
        "n_legit": len(legit),
        "average_precision": _r(ap),
        "average_precision_ci95": [_r(ap_lo), _r(ap_hi)],
        "recall_at_precision_95": _r(rec),
        "recall_at_precision_95_ci95": [_r(rec_lo), _r(rec_hi)],
        "scams_flagged_arnaque_or_suspect": _r(np.mean(alert)),
        "scams_flagged_arnaque_or_suspect_ci95": [_r(v) for v in proportion_ci(alert)],
        "scams_flagged_arnaque": _r(np.mean(as_scam)),
        "scams_flagged_arnaque_ci95": [_r(v) for v in proportion_ci(as_scam)],
        "legit_flagged_arnaque": _r(np.mean(false_alarm)),
        "missed_scams": missed[:15],
    }


def _external_benchmark(analyzer: Analyzer, path: Path) -> dict[str, Any] | None:
    """False-positive rate on real legitimate SMS that were never used for training."""
    if not path.is_file():
        return None
    rows = read_csv(path)
    verdicts = [r.verdict for r in analyzer.analyze_batch([row["text"] for row in rows])]
    scam = [v == "arnaque" for v in verdicts]
    alert = [v != "legitime" for v in verdicts]
    lo, hi = proportion_ci(scam)
    lo2, hi2 = proportion_ci(alert)
    flagged = [row["text"] for row, v in zip(rows, verdicts, strict=True) if v == "arnaque"]
    return {
        "file": path.name,
        "n": len(rows),
        "false_positive_rate": _r(np.mean(scam)),
        "false_positive_rate_ci95": [_r(lo), _r(hi)],
        "flagged_suspect_or_arnaque": _r(np.mean(alert)),
        "flagged_suspect_or_arnaque_ci95": [_r(lo2), _r(hi2)],
        "examples_flagged_arnaque": flagged[:10],
    }


def _ap(y: np.ndarray[Any, Any], s: np.ndarray[Any, Any]) -> float:
    return float(average_precision_score(y, s))


def _r(x: Any) -> float:
    return round(float(x), 4)


# -------------------------------------------------------------------- models


class RulesOnly:
    """Unlearned baseline: score = number of red-flag signals / 3 (capped at 1)."""

    def fit(self, texts: Sequence[str], y: Any) -> RulesOnly:
        return self

    def scores(self, texts: Sequence[str]) -> np.ndarray[Any, Any]:
        counts = [sum(1 for c in detect_signals(t) if c not in CONTEXT_SIGNALS) for t in texts]
        return np.minimum(np.asarray(counts, dtype=float) / 3.0, 1.0)


def _scores(model: Any, texts: Sequence[str]) -> np.ndarray[Any, Any]:
    if isinstance(model, RulesOnly):
        return model.scores(texts)
    if hasattr(model, "predict_proba"):
        classes = list(model.classes_)
        return np.asarray(model.predict_proba(list(texts))[:, classes.index(1)])
    return np.asarray(model.decision_function(list(texts)))


def baselines(best_c: float) -> dict[str, tuple[Callable[[], Any], float]]:
    """name -> (factory, default decision threshold on the score)."""
    return {
        "B0 majority class": (lambda: DummyClassifier(strategy="prior"), 0.5),
        "B1 rules only": (RulesOnly, 1 / 3),
        "B2 naive Bayes (words)": (
            lambda: Pipeline(
                [
                    ("norm", TextNormalizer()),
                    ("vec", CountVectorizer(ngram_range=(1, 2), token_pattern=WORD_REGEX)),
                    ("clf", MultinomialNB()),
                ]
            ),
            0.5,
        ),
        "B3 linear SVM": (
            lambda: Pipeline(
                [
                    ("features", build_features()),
                    ("clf", LinearSVC(class_weight="balanced", max_iter=10000)),
                ]
            ),
            0.0,
        ),
        "B4 sikaguard (retained)": (lambda: build_binary_pipeline(C=best_c), 0.5),
    }


def _oof(
    factory: Callable[[], Any],
    texts: list[str],
    y: np.ndarray[Any, Any],
    strata: list[str],
    groups: list[str],
) -> np.ndarray[Any, Any]:
    out = np.zeros(len(texts))
    splitter = StratifiedGroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
    arr = np.asarray(texts, dtype=object)
    for fit_idx, pred_idx in splitter.split(arr, strata, groups):
        model = factory().fit(list(arr[fit_idx]), y[fit_idx])
        out[pred_idx] = _scores(model, list(arr[pred_idx]))
    return out


# ---------------------------------------------------------------- evaluation


def evaluate(data_dir: Path, reports_dir: Path, notes: Sequence[str] = ()) -> dict[str, Any]:
    rows = read_csv(data_dir / DATASET_FILE)
    stats = json.loads((data_dir / STATS_FILE).read_text(encoding="utf-8"))
    training = json.loads((reports_dir / "training.json").read_text(encoding="utf-8"))
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    tr_texts = [r["text"] for r in train]
    te_texts = [r["text"] for r in test]
    tr_y = np.array([int(r["label"] == "arnaque") for r in train])
    te_y = np.array([int(r["label"] == "arnaque") for r in test])
    strata = [r["category"] for r in train]
    groups = [r["group_id"] for r in train]
    best_c = float(training["best_C"])

    model = load_model()
    analyzer = Analyzer(model=model)
    if model.manifest.dataset_version != stats["version"]:
        raise RuntimeError("bundled model was not trained on this dataset version")

    # Benchmark ---------------------------------------------------------------
    benchmark: dict[str, dict[str, Any]] = {}
    for name, (factory, decision) in baselines(best_c).items():
        print(f"benchmark: {name}")
        cv_scores = _oof(factory, tr_texts, tr_y, strata, groups)
        if name.startswith("B4"):
            te_scores = _scores(model.binary, te_texts)
        else:
            te_scores = _scores(factory().fit(tr_texts, tr_y), te_texts)
        low, ap, high = bootstrap_ci(_ap, te_y, te_scores)
        benchmark[name] = {
            "cv_average_precision": _r(_ap(tr_y, cv_scores)),
            "test_average_precision": _r(ap),
            "test_average_precision_ci95": [_r(low), _r(high)],
            "test_f1_default_decision": _r(f1_score(te_y, te_scores >= decision)),
            "test_recall_at_precision_95": _r(recall_at_precision(te_y, te_scores, 0.95)),
        }

    # Retained model at its operating thresholds --------------------------------
    results = analyzer.analyze_batch(te_texts)
    verdicts = [r.verdict for r in results]
    scores = np.array([r.score for r in results])
    confusion = {
        label: dict(Counter(v for v, r in zip(verdicts, test, strict=True) if r["label"] == label))
        for label in ("arnaque", "legitime")
    }
    is_alert = np.array([v != "legitime" for v in verdicts])
    is_scam_verdict = np.array([v == "arnaque" for v in verdicts])
    operating = {
        "threshold_high": _r(analyzer.threshold_high),
        "threshold_low": _r(analyzer.threshold_low),
        "precision_of_arnaque_verdict": _r(te_y[is_scam_verdict].mean()),
        "recall_arnaque_verdict": _r(is_scam_verdict[te_y == 1].mean()),
        "recall_arnaque_or_suspect": _r(is_alert[te_y == 1].mean()),
        "legit_flagged_arnaque": _r(is_scam_verdict[te_y == 0].mean()),
        "legit_flagged_suspect_or_arnaque": _r(is_alert[te_y == 0].mean()),
        "confusion": confusion,
    }
    rec_ci = bootstrap_ci(lambda y, s: recall_at_precision(y, s, 0.95), te_y, scores)

    # Hard legitimate messages, per category, per source ----------------------------
    hard = [i for i, r in enumerate(test) if r["category"] in HARD_LEGIT]
    hard_legit = {
        "n": len(hard),
        "false_positive_rate": _r(np.mean([verdicts[i] == "arnaque" for i in hard])),
        "flagged_suspect_or_arnaque": _r(np.mean([verdicts[i] != "legitime" for i in hard])),
    }
    per_category: dict[str, dict[str, Any]] = {}
    for cat in sorted({r["category"] for r in test}):
        idx = [i for i, r in enumerate(test) if r["category"] == cat]
        label = test[idx[0]]["label"]
        key = "detected" if label == "arnaque" else "flagged"
        per_category[cat] = {
            "label": label,
            "n": len(idx),
            key: _r(np.mean([verdicts[i] != "legitime" for i in idx])),
        }
    per_source: dict[str, dict[str, Any]] = {}
    keys = {
        "source": [source_name(r) for r in test],
        "pays": [r["pays"] for r in test],
    }
    for column, values in keys.items():
        for value in sorted(set(values)):
            idx = np.array([i for i, v in enumerate(values) if v == value])
            entry: dict[str, Any] = {"n": len(idx)}
            if len(np.unique(te_y[idx])) == 2:
                entry["average_precision"] = _r(_ap(te_y[idx], scores[idx]))
            scam_part = [i for i in idx if te_y[i] == 1]
            legit_part = [i for i in idx if te_y[i] == 0]
            if scam_part:
                entry["scams_flagged"] = _r(np.mean([verdicts[i] != "legitime" for i in scam_part]))
            if legit_part:
                entry["legit_flagged_arnaque"] = _r(
                    np.mean([verdicts[i] == "arnaque" for i in legit_part])
                )
            per_source[f"{column}={value}"] = entry

    # Real SMS only: real scams vs real legitimate messages of the test split -------------
    real = _real_only(test, te_y, scores, verdicts)

    # External benchmark: real SMS never used for training ---------------------------
    external = _external_benchmark(analyzer, data_dir.parent / "eval" / EXTERNAL_FILE)

    # Category model --------------------------------------------------------------
    scam_idx = [i for i, r in enumerate(test) if r["label"] == "arnaque"]
    predicted_cat = model.category.predict([te_texts[i] for i in scam_idx])
    true_cat = [test[i]["category"] for i in scam_idx]
    category_model = {
        "n": len(scam_idx),
        "accuracy": _r(np.mean(predicted_cat == np.array(true_cat))),
        "macro_f1": _r(f1_score(true_cat, predicted_cat, average="macro")),
    }

    # Errors ------------------------------------------------------------------------
    errors = [
        {
            "id": r["id"],
            "label": r["label"],
            "category": r["category"],
            "verdict": v,
            "score": _r(res.score),
            "text": r["text"],
        }
        for r, v, res in zip(test, verdicts, results, strict=True)
        if (r["label"] == "arnaque" and v != "arnaque")
        or (r["label"] == "legitime" and v != "legitime")
    ]

    # Robustness ----------------------------------------------------------------------
    print("robustness: ablation model without normalization")
    ablation_oof = _oof(
        lambda: build_binary_pipeline(normalize=False, C=best_c), tr_texts, tr_y, strata, groups
    )
    _, ablation_low = choose_thresholds(tr_y, ablation_oof)
    ablation = build_binary_pipeline(normalize=False, C=best_c).fit(tr_texts, tr_y)
    scam_texts = [te_texts[i] for i in scam_idx]
    robustness: dict[str, dict[str, float]] = {}
    variants: dict[str, list[str]] = {"original": scam_texts}
    for k, (name, fn) in enumerate(PERTURBATIONS.items()):
        variants[name] = [fn(t, random.Random(1000 * k + i)) for i, t in enumerate(scam_texts)]
    for name, texts in variants.items():
        with_norm = np.mean([r.verdict != "legitime" for r in analyzer.analyze_batch(texts)])
        without = np.mean(_scores(ablation, texts) >= ablation_low)
        robustness[name] = {
            "with_normalization": _r(with_norm),
            "without_normalization": _r(without),
        }
    perturbed = [v["with_normalization"] for k, v in robustness.items() if k != "original"]

    achieved = {
        "test_average_precision": benchmark["B4 sikaguard (retained)"]["test_average_precision"],
        "recall_at_precision_95": benchmark["B4 sikaguard (retained)"][
            "test_recall_at_precision_95"
        ],
        "hard_legit_false_positive_rate": hard_legit["false_positive_rate"],
        "min_detection_under_perturbation": _r(min(perturbed)),
    }
    if external is not None:
        achieved["real_sms_false_positive_rate"] = external["false_positive_rate"]
    if real is not None:
        achieved["real_test_average_precision"] = real["average_precision"]
        achieved["real_scam_detection_rate"] = real["scams_flagged_arnaque_or_suspect"]
        achieved["real_scam_arnaque_rate"] = real["scams_flagged_arnaque"]
    objectives = {
        key: {
            "target": target,
            "achieved": achieved[key],
            "lower_is_better": key in LOWER_IS_BETTER,
            "met": achieved[key] <= target if key in LOWER_IS_BETTER else achieved[key] >= target,
        }
        for key, target in OBJECTIVES.items()
        if key in achieved
    }

    metrics: dict[str, Any] = {
        "model_version": model.manifest.model_version,
        "dataset_version": stats["version"],
        "not_for_production": model.manifest.not_for_production,
        "n_train": len(train),
        "n_test": len(test),
        "benchmark": benchmark,
        "operating_point": operating,
        "recall_at_precision_95_ci95": [_r(rec_ci[0]), _r(rec_ci[2])],
        "hard_legit": hard_legit,
        "per_category": per_category,
        "per_source": per_source,
        "category_model": category_model,
        "real_test": real,
        "external_real_sms": external,
        "robustness": robustness,
        "objectives": objectives,
        "errors": errors,
        "notes": list(notes),
    }
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    (reports_dir / "evaluation.md").write_text(
        render_markdown(metrics, stats, training), encoding="utf-8", newline="\n"
    )
    _plot_pr(te_y, {"sikaguard": scores}, reports_dir / "pr_curve.png")
    return metrics


# -------------------------------------------------------------------- report


def _pct(x: float) -> str:
    return f"{100 * x:.1f} %"


def render_markdown(m: dict[str, Any], stats: dict[str, Any], training: dict[str, Any]) -> str:
    lines: list[str] = ["# sikaguard — evaluation report", ""]
    if m["not_for_production"]:
        lines += [
            "> **Seed data warning.** This model was trained and tested on the *seed dataset*:",
            "> SMS written by hand from publicly documented scam patterns, not real collected",
            "> messages. These numbers validate the pipeline; they are **not** an estimate of",
            "> real-world performance. Real-data results will replace them in v0.1.0.",
            "",
        ]
    lines += [
        f"Model `{m['model_version']}` · dataset `{m['dataset_version']}` · "
        f"{m['n_train']} train / {m['n_test']} test SMS · split by near-duplicate group, "
        "stratified by category · test split opened once.",
        "",
        "## Benchmark",
        "",
        "Average precision (area under the precision-recall curve) with 95 % bootstrap CI.",
        "",
        "| Model | CV AP (train) | Test AP [95 % CI] | Test F1 | Recall @ precision 95 % |",
        "|---|---|---|---|---|",
    ]
    for name, b in m["benchmark"].items():
        lo, hi = b["test_average_precision_ci95"]
        lines.append(
            f"| {name} | {b['cv_average_precision']:.3f} | {b['test_average_precision']:.3f} "
            f"[{lo:.3f}, {hi:.3f}] | {b['test_f1_default_decision']:.3f} | "
            f"{_pct(b['test_recall_at_precision_95'])} |"
        )
    op = m["operating_point"]
    conf = op["confusion"]
    lines += [
        "",
        f"Regularization chosen by grouped CV: C = {training['best_C']} "
        "(strongest regularization within 0.001 AP of the best).",
        "",
        "## Operating point (three verdicts)",
        "",
        f"Thresholds chosen on out-of-fold train predictions: `arnaque` if score ≥ "
        f"{op['threshold_high']:.3f} (precision ≥ 95 %), `legitime` if score < "
        f"{op['threshold_low']:.3f} (recall ≥ 99 %), `suspect` in between.",
        "",
        "| True label \\ verdict | arnaque | suspect | legitime |",
        "|---|---|---|---|",
    ]
    for label in ("arnaque", "legitime"):
        c = conf.get(label, {})
        lines.append(
            f"| {label} | {c.get('arnaque', 0)} | {c.get('suspect', 0)} | {c.get('legitime', 0)} |"
        )
    hl = m["hard_legit"]
    cm = m["category_model"]
    lines += [
        "",
        f"- Precision of the `arnaque` verdict: {_pct(op['precision_of_arnaque_verdict'])}",
        f"- Scams flagged `arnaque`: {_pct(op['recall_arnaque_verdict'])}; "
        f"flagged `arnaque` or `suspect`: {_pct(op['recall_arnaque_or_suspect'])}",
        f"- Legitimate SMS flagged `arnaque`: {_pct(op['legit_flagged_arnaque'])}; "
        f"`arnaque` or `suspect`: {_pct(op['legit_flagged_suspect_or_arnaque'])}",
        f"- **Hard legitimate SMS** (transaction notifications and OTP codes, n = {hl['n']}): "
        f"false-positive rate {_pct(hl['false_positive_rate'])}, "
        f"flagged suspect or worse {_pct(hl['flagged_suspect_or_arnaque'])}",
        f"- Category model on test scams (n = {cm['n']}): accuracy {_pct(cm['accuracy'])}, "
        f"macro-F1 {cm['macro_f1']:.3f}",
        "",
        "![Precision-recall curve](pr_curve.png)",
        "",
        "## Per category (test)",
        "",
        "| Category | Label | n | Detected / flagged |",
        "|---|---|---|---|",
    ]
    for cat, c in m["per_category"].items():
        rate = c.get("detected", c.get("flagged", 0.0))
        lines.append(f"| {cat} | {c['label']} | {c['n']} | {_pct(rate)} |")
    lines += [
        "",
        "## Adversarial robustness",
        "",
        "Share of test scams still flagged (`arnaque` or `suspect`) after each disguise. "
        "*Without normalization* is the same model trained on raw lower-cased text.",
        "",
        "| Disguise | With normalization | Without normalization |",
        "|---|---|---|",
    ]
    for name, r in m["robustness"].items():
        lines.append(
            f"| {name} | {_pct(r['with_normalization'])} | {_pct(r['without_normalization'])} |"
        )
    lines += [
        "",
        "## Per source (test)",
        "",
        "| Source | n | AP | Scams flagged | Legit flagged `arnaque` |",
        "|---|---|---|---|---|",
    ]
    for key, e in m["per_source"].items():
        if not key.startswith("source="):
            continue
        ap = f"{e['average_precision']:.3f}" if "average_precision" in e else "—"
        sf = _pct(e["scams_flagged"]) if "scams_flagged" in e else "—"
        lf = _pct(e["legit_flagged_arnaque"]) if "legit_flagged_arnaque" in e else "—"
        lines.append(f"| {key.removeprefix('source=')} | {e['n']} | {ap} | {sf} | {lf} |")
    real = m.get("real_test")
    if real:
        lo, hi = real["average_precision_ci95"]
        r_lo, r_hi = real["recall_at_precision_95_ci95"]
        a_lo, a_hi = real["scams_flagged_arnaque_or_suspect_ci95"]
        s_lo, s_hi = real["scams_flagged_arnaque_ci95"]
        lines += [
            "",
            "## Real SMS only (test split)",
            "",
            f"Real scam SMS reported by victims (IMC'25, n = {real['n_scams']}) against real "
            f"legitimate SMS (88milSMS, n = {real['n_legit']}), all never seen in training.",
            "",
            f"- Average precision: **{real['average_precision']:.3f}** [{lo:.3f}, {hi:.3f}]",
            f"- Recall at 95 % precision: {_pct(real['recall_at_precision_95'])} "
            f"[{_pct(r_lo)}, {_pct(r_hi)}]",
            f"- Real scams flagged `arnaque` or `suspect`: "
            f"**{_pct(real['scams_flagged_arnaque_or_suspect'])}** [{_pct(a_lo)}, {_pct(a_hi)}]",
            f"- Real scams flagged `arnaque`: {_pct(real['scams_flagged_arnaque'])} "
            f"[{_pct(s_lo)}, {_pct(s_hi)}]",
            f"- Real legitimate SMS flagged `arnaque`: {_pct(real['legit_flagged_arnaque'])}",
        ]
        if real["missed_scams"]:
            lines += ["", "Real scams judged legitimate (first 15):", ""]
            lines += [f"- {t}" for t in real["missed_scams"]]
    ext = m.get("external_real_sms")
    if ext:
        lo, hi = ext["false_positive_rate_ci95"]
        lo2, hi2 = ext["flagged_suspect_or_arnaque_ci95"]
        lines += [
            "",
            "## Real SMS benchmark (never used for training)",
            "",
            f"{ext['n']} authentic French SMS from the 88milSMS corpus (CC BY 4.0), disjoint "
            "from the training sample. Every one is legitimate, so every alert is a false alarm.",
            "",
            f"- Flagged `arnaque`: **{_pct(ext['false_positive_rate'])}** "
            f"[95 % CI {_pct(lo)}, {_pct(hi)}]",
            f"- Flagged `arnaque` or `suspect`: {_pct(ext['flagged_suspect_or_arnaque'])} "
            f"[95 % CI {_pct(lo2)}, {_pct(hi2)}]",
        ]
        if ext["examples_flagged_arnaque"]:
            lines += ["", "False alarms (first 10):", ""]
            lines += [f"- {t}" for t in ext["examples_flagged_arnaque"]]
    lines += [
        "",
        "## Pre-registered objectives",
        "",
        "| Objective | Target | Achieved | Met |",
        "|---|---|---|---|",
    ]
    for key, o in m["objectives"].items():
        sign = "≤" if o.get("lower_is_better") else "≥"
        lines.append(
            f"| {key} | {sign} {o['target']} | {o['achieved']} | {'yes' if o['met'] else 'no'} |"
        )
    if m.get("notes"):
        lines += ["", "## Notes", ""] + [f"- {note}" for note in m["notes"]]
    lines += ["", f"## All test errors ({len(m['errors'])})", ""]
    if m["errors"]:
        lines += ["| Label | Category | Verdict | Score | SMS |", "|---|---|---|---|---|"]
        for e in m["errors"]:
            text = e["text"].replace("|", "\\|")
            lines.append(
                f"| {e['label']} | {e['category']} | {e['verdict']} | {e['score']:.2f} | {text} |"
            )
    else:
        lines.append("No error on the test split.")
    lines += [
        "",
        "## Reproduce",
        "",
        "```bash",
        "python -m sikaguard_lab.build",
        "python -m sikaguard_lab.train",
        "python -m sikaguard_lab.evaluate",
        "```",
        "",
    ]
    return "\n".join(lines)


def _plot_pr(y: np.ndarray[Any, Any], curves: dict[str, np.ndarray[Any, Any]], path: Path) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:  # pragma: no cover - optional dependency
        return
    fig, ax = plt.subplots(figsize=(5, 4), dpi=120)
    for name, s in curves.items():
        precision, recall, _ = precision_recall_curve(y, s)
        ax.plot(recall, precision, label=f"{name} (AP {average_precision_score(y, s):.3f})")
    ax.axhline(0.95, color="grey", linestyle="--", linewidth=0.8, label="precision 95 %")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_ylim(0, 1.02)
    ax.set_title("Precision-recall on the test split")
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/processed"))
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    parser.add_argument("--note", action="append", default=[], help="note added to the report")
    args = parser.parse_args(argv)
    metrics = evaluate(args.data, args.reports, args.note)
    print(json.dumps({k: metrics[k] for k in ("benchmark", "objectives")}, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
