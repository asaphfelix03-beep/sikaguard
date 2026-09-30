"""Exact and near-duplicate detection.

Scam campaigns reuse the same template with small variations (amount, name,
number). If variants of one template land in both train and test, the test
score is inflated. Near-duplicates are therefore grouped (character 5-gram
shingles, Jaccard similarity >= threshold, transitive closure) and the split is
done by group.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from sklearn.feature_extraction.text import CountVectorizer

from sikaguard.normalize import normalize


def shingles(text: str, k: int = 5) -> set[str]:
    """Set of character k-grams of the normalized text."""
    norm = normalize(text)
    if len(norm) <= k:
        return {norm}
    return {norm[i : i + k] for i in range(len(norm) - k + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity of two sets (1.0 for two empty sets)."""
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def drop_exact_duplicates(
    rows: Sequence[Mapping[str, str]],
) -> tuple[list[Mapping[str, str]], int]:
    """Keep the first occurrence of each normalized text. Returns (rows, n_removed)."""
    seen: set[str] = set()
    kept: list[Mapping[str, str]] = []
    for row in rows:
        key = normalize(row["text"])
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept, len(rows) - len(kept)


def assign_groups(texts: Sequence[str], threshold: float = 0.8, k: int = 5) -> list[int]:
    """Group ids such that texts with Jaccard(shingles) >= threshold share a group.

    Groups are numbered 0..G-1 in order of first appearance.
    """
    if not texts:
        return []
    vectorizer = CountVectorizer(
        analyzer=lambda t: sorted(shingles(t, k)), binary=True, lowercase=False
    )
    x = vectorizer.fit_transform(texts).astype(np.int32)
    inter = (x @ x.T).tocoo()
    sizes = np.asarray(x.sum(axis=1)).ravel()
    union = sizes[inter.row] + sizes[inter.col] - inter.data
    keep = (inter.data / np.maximum(union, 1)) >= threshold
    adjacency = coo_matrix(
        (np.ones(int(keep.sum()), dtype=np.int8), (inter.row[keep], inter.col[keep])),
        shape=inter.shape,
    )
    _, labels = connected_components(adjacency, directed=False)
    remap: dict[int, int] = {}
    return [remap.setdefault(int(label), len(remap)) for label in labels]
