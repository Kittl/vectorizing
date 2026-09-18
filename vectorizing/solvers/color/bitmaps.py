"""Build overlapping color masks for Potrace tracing."""

import cv2
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


def add_bitmap_rims(bitmaps: list[np.ndarray]) -> None:
    """Replace cumulative masks in place with cutouts plus two-pixel inner rims."""
    # One pixel still leaves gaps after curve fitting on the artwork fixtures.
    # This is in processed-image pixels, not screen pixels: zoom enlarges the
    # lip, and features at most four pixels wide may be covered by neighboring rims.
    kernel = np.ones((5, 5), dtype=np.uint8)
    # Work forwards while the next mask is still cumulative. Dilation adds only
    # neighboring pixels; clipping to this mask excludes earlier colors and
    # transparent space. The last mask already contains just its own color.
    for bitmap, above in zip(bitmaps, bitmaps[1:]):
        visible = (bitmap > above).astype(np.uint8)
        bitmap &= cv2.dilate(
            visible,
            kernel,
            borderType=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
