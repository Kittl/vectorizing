"""Compute document bounds from traced vector paths."""

from collections.abc import Iterable

import numpy as np
from pathops import Path


def compound_paths_bounds(compound_paths: Iterable[Path]) -> dict[str, float]:
    """Return combined bounds, retaining infinite extents for an empty iterable."""
    min_x = np.inf
    min_y = np.inf
    max_x = -np.inf
    max_y = -np.inf

    for compound_path in compound_paths:
        l, t, r, b = compound_path.bounds
        min_x = min(min_x, l)
        min_y = min(min_y, t)
        max_x = max(max_x, r)
        max_y = max(max_y, b)

    return {
        "top": min_y,
        "left": min_x,
        "bottom": max_y,
        "right": max_x,
        "width": max_x - min_x,
        "height": max_y - min_y,
    }
