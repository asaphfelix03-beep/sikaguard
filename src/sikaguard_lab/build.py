"""Build the processed dataset from the seed, sources and raw collections.

Usage::

    python -m sikaguard_lab.build [--inputs data/seed data/sources data/raw]
                                  [--out data/processed] [--version 0.1.0.dev1]
                                  [--consumed data/history/test_0.1.0.dev0.csv]

Grouping rules (a group never straddles train and test):

* near-duplicates (character 5-gram Jaccard >= 0.8) share a group;
* rows of the same documented campaign (``campagne`` column) share a group;
* rows of a *consumed* test split (a previous test set whose errors have been
  looked at) are forced into train: a test set can only be used once.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from sikaguard.normalize import normalize
from sikaguard_lab.dedup import assign_groups, drop_exact_duplicates
from sikaguard_lab.schema import COLUMNS, OPTIONAL_COLUMNS, read_csv, validate_rows, write_csv
from sikaguard_lab.split import group_stratified_split

DATASET_FILE = "dataset.csv"
STATS_FILE = "stats.json"
DEFAULT_INPUTS = (Path("data/seed"), Path("data/sources"), Path("data/raw"))


def _collect(directories: Sequence[Path]) -> tuple[list[dict[str, str]], list[str]]:
    rows: list[dict[str, str]] = []
    errors: list[str] = []
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.csv")):
            file_rows = read_csv(path)
            for row in file_rows:
                for column in OPTIONAL_COLUMNS:
                    row[column] = row.get(column) or ""
            errors.extend(f"{path.name}: {e}" for e in validate_rows(file_rows))
            rows.extend(file_rows)
    return rows, errors


def _merge_campaigns(groups: list[int], campaigns: list[str]) -> list[int]:
    """Give every row of a campaign the group of the campaign's first row (transitively)."""
    parent = list(range(max(groups, default=-1) + 1))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    first: dict[str, int] = {}
    for group, campaign in zip(groups, campaigns, strict=True):
        if campaign:
            if campaign in first:
                parent[find(group)] = find(first[campaign])
            else:
                first[campaign] = group
    remap: dict[int, int] = {}
    return [remap.setdefault(find(g), len(remap)) for g in groups]


def build(
    directories: Sequence[Path],
    out_dir: Path,
    *,
    version: str,
    seed: int = 42,
    consumed: set[str] | None = None,
) -> dict[str, object]:
    """Validate, deduplicate, group and split. Returns the statistics written to disk.

    ``consumed`` holds the normalized texts of a previous, already-used test split.
    """
    rows, errors = _collect(directories)
    if errors:
        raise ValueError("\n".join(errors))
    if not rows:
        raise ValueError("aucune donnée trouvée")
    unique, n_duplicates = drop_exact_duplicates(rows)
    texts = [row["text"] for row in unique]
    groups = _merge_campaigns(assign_groups(texts), [row["campagne"] for row in unique])

    consumed = consumed or set()
    consumed_groups = {g for g, t in zip(groups, texts, strict=True) if normalize(t) in consumed}
    open_idx = [i for i, g in enumerate(groups) if g not in consumed_groups]
    split = ["train"] * len(unique)
    open_split = group_stratified_split(
        [unique[i]["category"] for i in open_idx], [groups[i] for i in open_idx], seed=seed
    )
    for i, s in zip(open_idx, open_split, strict=True):
        split[i] = s

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
        "n_campaigns": len({r["campagne"] for r in processed if r["campagne"]}),
        "n_consumed_rows_forced_to_train": sum(1 for g in groups if g in consumed_groups),
        "by_label": dict(Counter(r["label"] for r in processed)),
        "by_category": dict(sorted(Counter(r["category"] for r in processed).items())),
        "by_source_type": dict(sorted(Counter(r["source_type"] for r in processed).items())),
        "by_country": dict(sorted(Counter(r["pays"] for r in processed).items())),
        "by_split_label": {
            s: dict(Counter(r["label"] for r in processed if r["split"] == s))
            for s in ("train", "test")
        },
        "by_split_source_type": {
            s: dict(sorted(Counter(r["source_type"] for r in processed if r["split"] == s).items()))
            for s in ("train", "test")
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / STATS_FILE).write_text(
        json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    return stats


def read_consumed(path: Path) -> set[str]:
    """Normalized texts of a consumed test split (CSV with a ``text`` column)."""
    return {normalize(row["text"]) for row in read_csv(path)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, nargs="+", default=list(DEFAULT_INPUTS))
    parser.add_argument("--out", type=Path, default=Path("data/processed"))
    parser.add_argument("--version", default="0.1.0.dev1")
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument(
        "--consumed",
        type=Path,
        action="append",
        default=[],
        help="CSV of a previous test split whose rows must stay in train (repeatable)",
    )
    args = parser.parse_args(argv)
    consumed: set[str] = set()
    for path in args.consumed:
        consumed |= read_consumed(path)
    try:
        stats = build(
            args.inputs, args.out, version=args.version, seed=args.random_seed, consumed=consumed
        )
    except ValueError as exc:
        print(f"Données invalides :\n{exc}", file=sys.stderr)
        return 1
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
