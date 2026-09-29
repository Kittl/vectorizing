"""Color-processing operations retained for the pre-layer-seam configuration."""

import cv2
import numpy as np
import potrace
import scipy.ndimage as ndi
from pathops import Path, PathOp, op
from PIL import Image
from skimage.measure import label

from vectorizing.geometry.potrace import potrace_path_to_compound_path
from vectorizing.solvers.color.quantize import (
    get_background_cluster,
    get_initial_centroids,
    kmeans,
)


def quantize(
    img_arr: np.ndarray,
    color_count: int,
    *,
    auto_method: Image.Quantize | None = None,
) -> tuple[np.ndarray, np.ndarray, bool]:
    """Run the original strong-filter and overlap-based component cleanup."""
    background = get_background_cluster(img_arr) if img_arr.shape[-1] == 4 else None
    rgb = (
        cv2.cvtColor(img_arr, cv2.COLOR_RGBA2RGB) if img_arr.shape[-1] == 4 else img_arr
    )
    rgb = cv2.bilateralFilter(rgb.copy(), 7, 50, 50)
    centroids = (
        get_initial_centroids(rgb, color_count, auto_method)
        if auto_method is not None
        else get_initial_centroids(rgb, color_count)
    )
    labels, colors = kmeans(rgb, centroids)
    labels = labels.reshape(rgb.shape[:2])
    if background is not None:
        labels = np.where(background > 0, 0, labels + 1)
        colors = np.vstack(
            (
                np.zeros((1, 4), dtype=np.uint8),
                np.column_stack((colors, np.ones(len(colors), dtype=np.uint8))),
            ),
        )
    labels = labels + 1
    enhanced = np.zeros(labels.shape, dtype=np.uint16)
    kernel = np.ones((2, 2))
    for index in range(len(colors)):
        mask = labels == index + 1
        if not mask.any():
            continue
        components = label(mask) + 1
        counts = np.bincount(components.ravel())
        # A pixel is erased from this component when any other color's
        # two-pixel dilation covers it. The union replaces pairwise overlaps.
        covered = cv2.dilate((~mask).astype(np.uint8), kernel) > 0
        remaining = np.bincount(components[mask & ~covered], minlength=len(counts))
        ratio = np.divide(
            remaining.astype(np.float32),
            counts.astype(np.float32),
            out=np.ones(len(counts), dtype=np.float32),
            where=counts != 0,
        )
        enhanced[mask & (ratio[components] > 0.1)] = index + 1
    nearest = ndi.distance_transform_edt(
        enhanced == 0,
        return_distances=False,
        return_indices=True,
    )
    enhanced = np.where(enhanced != 0, enhanced, enhanced[tuple(nearest)])
    return enhanced - 1, colors.astype(np.uint8), background is not None


def create_background_rect(width: int, height: int, padding: int) -> Path:
    """Build the padded clipping rectangle used by the original layer solver."""
    rect = Path()
    rect.moveTo(-padding, -padding)
    rect.lineTo(width + padding, -padding)
    rect.lineTo(width + padding, height + padding)
    rect.lineTo(-padding, height + padding)
    rect.close()
    return rect


def remove_layering(
    traced_bitmaps: list[potrace.Path],
    width: int,
    height: int,
    has_background: bool,
) -> list[Path]:
    """Apply the original boolean clipping strategy to traced palette layers."""
    paths = [potrace_path_to_compound_path(path) for path in traced_bitmaps]
    if has_background:
        for i in range(len(paths) - 1):
            try:
                paths[i] = op(paths[i], paths[i + 1], PathOp.DIFFERENCE)
            except Exception:
                break
        return paths

    disjoint = []
    for i in range(len(paths) - 1):
        subtract = Path()
        for path in disjoint:
            subtract.addPath(path)
        subtract.addPath(paths[i + 1])
        try:
            disjoint.append(
                op(
                    create_background_rect(width, height, (i + 1) * 10),
                    subtract,
                    PathOp.DIFFERENCE,
                ),
            )
        except Exception:
            break
    try:
        disjoint = [
            op(path, create_background_rect(width, height, 0), PathOp.INTERSECTION)
            for path in disjoint
        ]
    except Exception:
        return paths
    return disjoint + paths[len(disjoint) :]
