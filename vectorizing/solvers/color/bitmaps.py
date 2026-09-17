"""Build overlapping color masks for Potrace tracing."""

import numpy as np


def create_bitmaps(
    labels: np.ndarray,
    colors: np.ndarray,
    has_background: bool,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Return cumulative uint32 masks and their colors in the original palette order."""
    bitmaps = [(labels == index).astype(np.uint32) for index in range(len(colors))]

    if has_background:
        bitmaps = bitmaps[1:]
        colors = colors[1:]

    # Filter empty masks before layering to keep each retained color aligned.
    zipped = [(bitmap, color) for bitmap, color in zip(bitmaps, colors) if bitmap.any()]
    bitmaps = [bitmap for bitmap, _ in zipped]
    colors = [color for _, color in zipped]

    # Work backwards: the next bitmap already contains every later layer.
    # Preserve overlap to avoid tracing seams, with O(K*N) rather than O(K^2*N) work.
    for index in range(len(bitmaps) - 2, -1, -1):
        bitmaps[index] += bitmaps[index + 1]

    return bitmaps, colors
