"""Anti-leak train/test split: stratified, by near-duplicate group."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold


def group_stratified_split(
    strata: Sequence[str],
    groups: Sequence[int],
    *,
    test_size: float = 0.2,
    seed: int = 42,
) -> list[str]:
    """Return ``"train"``/``"test"`` for each row.

    All rows of a group land in the same split; the distribution of ``strata``
    (e.g. the category) is kept as close as possible in both splits.
    """
    if not 0 < test_size < 1:
        raise ValueError("test_size must be in (0, 1)")
    n_splits = max(2, round(1 / test_size))
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    _, test_idx = next(splitter.split(np.zeros(len(strata)), list(strata), list(groups)))
    split = ["train"] * len(strata)
    for i in test_idx:
        split[int(i)] = "test"
    return split
