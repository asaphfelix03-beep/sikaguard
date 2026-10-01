"""Train the two-stage model and write it into ``src/sikaguard/assets``.

Usage::

    python -m sikaguard_lab.train [--data data/processed] [--out src/sikaguard/assets]

Model selection and threshold choice use out-of-fold predictions of a
grouped, stratified 5-fold cross-validation on the **train split only**. The
test split is never read here.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline

from sikaguard import __version__
from sikaguard.features import build_features
from sikaguard.model import DEFAULT_MODEL_DIR, save_model
from sikaguard_lab.build import DATASET_FILE, STATS_FILE
from sikaguard_lab.schema import read_csv

C_GRID = (1.0, 4.0, 10.0, 30.0, 100.0)
C_TOLERANCE = 0.001
N_FOLDS = 5
SEED = 42


def build_binary_pipeline(*, normalize: bool = True, C: float = 4.0) -> Pipeline:  # noqa: N803
    return Pipeline(
        [
            ("features", build_features(normalize=normalize)),
            ("clf", LogisticRegression(C=C, class_weight="balanced", max_iter=5000)),
        ]
    )


def build_category_pipeline(*, normalize: bool = True, C: float = 4.0) -> Pipeline:  # noqa: N803
    return build_binary_pipeline(normalize=normalize, C=C)


def out_of_fold_scores(
    factory: Callable[[], Any],
    texts: Sequence[str],
    y: np.ndarray[Any, Any],
    strata: Sequence[str],
    groups: Sequence[str],
    *,
    n_folds: int = N_FOLDS,
    seed: int = SEED,
) -> np.ndarray[Any, Any]:
    """Out-of-fold P(scam) for every training row (grouped, stratified CV)."""
    scores = np.zeros(len(texts), dtype=np.float64)
    splitter = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    texts_arr = np.asarray(texts, dtype=object)
    for fit_idx, pred_idx in splitter.split(texts_arr, list(strata), list(groups)):
        model = factory()
        model.fit(list(texts_arr[fit_idx]), y[fit_idx])
        classes = list(model.named_steps["clf"].classes_)
        scores[pred_idx] = model.predict_proba(list(texts_arr[pred_idx]))[:, classes.index(1)]
    return scores


def choose_thresholds(
    y_true: np.ndarray[Any, Any],
    scores: np.ndarray[Any, Any],
    *,
    min_precision: float = 0.95,
    min_recall: float = 0.98,
) -> tuple[float, float]:
    """Return ``(threshold_high, threshold_low)``.

    * ``threshold_high``: the lowest threshold whose precision (score >= t)
      reaches ``min_precision`` on the given data.
    * ``threshold_low``: the highest threshold that keeps a recall (score >= t)
      of at least ``min_recall``.

    ``threshold_low`` is capped at ``threshold_high``.
    """
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores, dtype=np.float64)
    positives = int(y_true.sum())
    if positives == 0 or positives == len(y_true):
        raise ValueError("both classes are required to choose thresholds")
    candidates = np.unique(scores)
    high = float(candidates[-1])
    for t in candidates:
        predicted = scores >= t
        precision = y_true[predicted].mean() if predicted.any() else 0.0
        if precision >= min_precision:
            high = float(t)
            break
    pos_scores = np.sort(scores[y_true == 1])
    k = int(np.floor((1 - min_recall) * positives))
    low = float(pos_scores[k])
    low = min(low, high)
    # No rounding: rounding could move a threshold past a score and break the guarantee.
    return high, low


def _report_metrics(
    y: np.ndarray[Any, Any], scores: np.ndarray[Any, Any], high: float, low: float
) -> dict[str, float]:
    return {
        "average_precision": round(float(average_precision_score(y, scores)), 4),
        "f1_at_0.5": round(float(f1_score(y, scores >= 0.5)), 4),
        "precision_at_high": round(float(y[scores >= high].mean()), 4),
        "recall_at_high": round(float((scores[y == 1] >= high).mean()), 4),
        "recall_at_low": round(float((scores[y == 1] >= low).mean()), 4),
        "share_suspect": round(float(((scores >= low) & (scores < high)).mean()), 4),
    }


def train(data_dir: Path, out_dir: Path, reports_dir: Path) -> dict[str, Any]:
    rows = [r for r in read_csv(data_dir / DATASET_FILE) if r["split"] == "train"]
    stats = json.loads((data_dir / STATS_FILE).read_text(encoding="utf-8"))
    texts = [r["text"] for r in rows]
    y = np.array([1 if r["label"] == "arnaque" else 0 for r in rows])
    strata = [r["category"] for r in rows]
    groups = [r["group_id"] for r in rows]

    grid: dict[str, float] = {}
    for c in C_GRID:
        oof = out_of_fold_scores(lambda c=c: build_binary_pipeline(C=c), texts, y, strata, groups)
        grid[str(c)] = round(float(average_precision_score(y, oof)), 4)
        print(f"C={c}: CV average precision = {grid[str(c)]}")
    # Parsimony: the strongest regularization within C_TOLERANCE of the best score.
    best_score = max(grid.values())
    best_c = min(c for c in C_GRID if grid[str(c)] >= best_score - C_TOLERANCE)
    oof = out_of_fold_scores(lambda: build_binary_pipeline(C=best_c), texts, y, strata, groups)
    high, low = choose_thresholds(y, oof)

    binary = build_binary_pipeline(C=best_c).fit(texts, y)
    scam_rows = [r for r in rows if r["label"] == "arnaque"]
    category = build_category_pipeline(C=best_c).fit(
        [r["text"] for r in scam_rows], [r["category"] for r in scam_rows]
    )
    # Production use requires real collected scams, not only reconstructions.
    real_scams = sum(
        1 for r in rows if r["label"] == "arnaque" and r["derive_de_modele"] == "false"
    )
    sources = Counter(r["source_type"] for r in rows)
    manifest = save_model(
        binary,
        category,
        out_dir,
        model_version=__version__,
        dataset_version=str(stats["version"]),
        threshold_high=high,
        threshold_low=low,
        not_for_production=real_scams == 0,
        training_data=(
            f"{len(rows)} SMS: "
            + ", ".join(f"{n} {source}" for source, n in sorted(sources.items()))
            + f"; real collected scams: {real_scams}"
        ),
    )
    report = {
        "model_version": manifest.model_version,
        "dataset_version": manifest.dataset_version,
        "n_train": len(rows),
        "c_grid_average_precision": grid,
        "best_C": best_c,
        "threshold_high": high,
        "threshold_low": low,
        "cv_metrics": _report_metrics(y, oof, high, low),
        "sha256": manifest.sha256,
    }
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "training.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/processed"))
    parser.add_argument("--out", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    args = parser.parse_args(argv)
    report = train(args.data, args.out, args.reports)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
