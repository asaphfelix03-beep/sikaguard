"""Build the processed dataset from the seed and raw collections.

Usage::

    python -m sikaguard_lab.build [--seed-dir data/seed] [--raw-dir data/raw]
                                  [--out data/processed] [--version 0.1.0.dev0]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from sikaguard_lab.dedup import assign_groups, drop_exact_duplicates
from sikaguard_lab.schema import COLUMNS, read_csv, validate_rows, write_csv
from sikaguard_lab.split import group_stratified_split

DATASET_FILE = "dataset.csv"
STATS_FILE = "stats.json"


def _collect(directories: Sequence[Path]) -> tuple[list[dict[str, str]], list[str]]:
    rows: list[dict[str, str]] = []
    errors: list[str] = []
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.csv")):
            file_rows = read_csv(path)
            errors.extend(f"{path.name}: {e}" for e in validate_rows(file_rows))
            rows.extend(file_rows)
    return rows, errors


def build(
    directories: Sequence[Path], out_dir: Path, *, version: str, seed: int = 42
) -> dict[str, object]:
    """Validate, deduplicate, group and split. Returns the statistics written to disk."""
    rows, errors = _collect(directories)
    if errors:
        raise ValueError("\n".join(errors))
    if not rows:
        raise ValueError("aucune donnée trouvée")
    unique, n_duplicates = drop_exact_duplicates(rows)
    texts = [row["text"] for row in unique]
    groups = assign_groups(texts)
    split = group_stratified_split([row["category"] for row in unique], groups, seed=seed)
    processed = [
        {**row, "id": f"sg-{i:05d}", "group_id": str(g), "split": s}
        for i, (row, g, s) in enumerate(zip(unique, groups, split, strict=True), start=1)
    ]
    processed_errors = validate_rows(processed, processed=True)
    if processed_errors:  # pragma: no cover - defensive, raw validation already passed
        raise ValueError("\n".join(processed_errors))
    leaked = {r["group_id"] for r in processed if r["split"] == "train"} & {
        r["group_id"] for r in processed if r["split"] == "test"
    }
    if leaked:  # pragma: no cover - guaranteed by the group split
        raise RuntimeError(f"groups present in both splits: {sorted(leaked)}")

    write_csv(out_dir / DATASET_FILE, processed, COLUMNS)
    stats: dict[str, object] = {
        "version": version,
        "n_rows": len(processed),
        "n_exact_duplicates_removed": n_duplicates,
        "n_groups": len(set(groups)),
        "n_multi_row_groups": sum(1 for c in Counter(groups).values() if c > 1),
        "by_label": dict(Counter(r["label"] for r in processed)),
        "by_category": dict(sorted(Counter(r["category"] for r in processed).items())),
        "by_source_type": dict(Counter(r["source_type"] for r in processed)),
        "by_country": dict(sorted(Counter(r["pays"] for r in processed).items())),
        "by_split_label": {
            s: dict(Counter(r["label"] for r in processed if r["split"] == s))
            for s in ("train", "test")
        },
    }
    (out_dir / STATS_FILE).write_text(
        json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    return stats


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-dir", type=Path, default=Path("data/seed"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--out", type=Path, default=Path("data/processed"))
    parser.add_argument("--version", default="0.1.0.dev0")
    parser.add_argument("--random-seed", type=int, default=42)
    args = parser.parse_args(argv)
    try:
        stats = build(
            [args.seed_dir, args.raw_dir], args.out, version=args.version, seed=args.random_seed
        )
    except ValueError as exc:
        print(f"Données invalides :\n{exc}", file=sys.stderr)
        return 1
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
