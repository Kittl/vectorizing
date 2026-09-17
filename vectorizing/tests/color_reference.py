"""Frozen pre-optimization algorithms used as independent regression oracles.

Keep these intentionally slow implementations separate from production helpers:
sharing optimized code would let a regression affect both sides of a comparison.
Cleanup shares only the unchanged fill_holes step so tests can bypass it in both
paths to inspect component removal before nearest-neighbor filling hides holes.
"""

import cv2
import numpy as np
from PIL import Image
from skimage.measure import label

from vectorizing.solvers.color import quantize as color_quantize


def legacy_initial_centroids(img_arr: np.ndarray, color_count: int) -> np.ndarray:
    """Preserve the RGB-pixel centroid algorithm from before PR 71."""
    img = (
        Image.fromarray(img_arr)
        .quantize(color_count, method=Image.Quantize.FASTOCTREE)
        .convert("RGB")
    )
    pixels = np.asarray(img)
    return np.unique(pixels.reshape(-1, pixels.shape[-1]), axis=0).astype(np.uint8)


def legacy_create_bitmaps(
    labels: np.ndarray,
    colors: np.ndarray,
    has_background: bool,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Preserve the pairwise bitmap accumulation from before PR 73."""
    bitmaps = [
        np.where(labels == index, 1, 0).astype(np.uint32)
        for index in range(len(colors))
    ]
    if has_background:
        bitmaps = bitmaps[1:]
        colors = colors[1:]
    zipped = list(zip(bitmaps, colors))
    zipped = [[bitmap, color] for bitmap, color in zipped if np.sum(bitmap) > 0]
    bitmaps = [bitmap for bitmap, _ in zipped]
    colors = [color for _, color in zipped]
    for x in range(len(bitmaps)):
        bitmap_x = bitmaps[x]
        for y in range(x + 1, len(bitmaps)):
            bitmap_x += bitmaps[y]
        bitmaps[x] = bitmap_x
    return bitmaps, colors


def legacy_enhance(
    img_arr: np.ndarray,
    labels: np.ndarray,
    colors: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Preserve the pairwise cleanup from main at f69c69b, before PR 74."""
    dims = img_arr.shape[:2]
    labels = labels + 1
    clusters = [
        np.where(labels == idx + 1, idx + 1, 0).astype(np.uint16)
        for idx, _ in enumerate(colors)
    ]
    # Preserve integer labeling, full connectivity and shifted component IDs.
    # The optimized path must match this, not redefine the expected behavior.
    original_connected_components_list = [label(cluster) + 1 for cluster in clusters]
    connected_components_bincounts = [
        np.bincount(connected_components.flatten())
        for connected_components in original_connected_components_list
    ]
    connected_components_list = [
        np.array(item, copy=True) for item in original_connected_components_list
    ]
    # Keep the expensive pairwise dilation scans: independence is the point.
    for x, cluster_x in enumerate(clusters):
        dilated_cluster_x = cv2.dilate(cluster_x, np.ones((2, 2)))
        for y, cluster_y in enumerate(clusters):
            if x == y:
                continue
            overlap = np.logical_and(dilated_cluster_x, cluster_y)
            connected_components_list[y] = np.where(
                overlap,
                0,
                connected_components_list[y],
            )
    for x, connected_components in enumerate(connected_components_list):
        original_bincount = connected_components_bincounts[x]
        count = original_bincount.shape[0]
        new_bincount = np.bincount(connected_components.flatten(), minlength=count)
        areas_ratio = np.divide(
            new_bincount.astype(np.float32),
            original_bincount.astype(np.float32),
            out=np.ones((count,), dtype=np.float32),
            where=original_bincount != 0,
        )
        clusters[x] = np.where(
            areas_ratio[original_connected_components_list[x]] <= 0.1,
            0,
            clusters[x],
        )
    labels = np.zeros(dims).astype(np.uint8)
    for cluster in clusters:
        labels = np.where(labels == 0, cluster, labels)
    return color_quantize.fill_holes(labels) - 1, colors
