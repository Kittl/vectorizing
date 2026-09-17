"""Build overlapping color masks for Potrace tracing."""

import numpy as np


def create_bitmaps(
    labels: np.ndarray,
    colors: np.ndarray,
    has_background: bool,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Return cumulative uint32 masks and their colors in the original palette order."""
    bitmaps = []
    retained_colors = []
    for index, color in enumerate(colors):
        if has_background and index == 0:
            continue
        mask = labels == index
        # Pruned colors need no uint32 allocation; keep retained colors aligned.
        if mask.any():
            bitmaps.append(mask.astype(np.uint32))
            retained_colors.append(color)

    # Work backwards: the next bitmap already contains every later layer.
    # Preserve overlap to avoid tracing seams, with O(K*N) rather than O(K^2*N) work.
    for index in range(len(bitmaps) - 2, -1, -1):
        bitmaps[index] += bitmaps[index + 1]

    return bitmaps, retained_colors
