"""Independent, intentionally slow oracles for optimized color operations."""

from collections import Counter

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
from skimage.measure import label


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


def original_area_cleanup(labels: np.ndarray, color_count: int) -> np.ndarray:
    """Run the original pairwise-dilation component cleanup on a small label grid."""
    shifted = labels + 1
    clusters = [
        np.where(shifted == index + 1, index + 1, 0).astype(np.uint16)
        for index in range(color_count)
    ]
    original = [label(cluster) + 1 for cluster in clusters]
    counts = [np.bincount(components.ravel()) for components in original]
    remaining = [components.copy() for components in original]
    for x, cluster_x in enumerate(clusters):
        dilated = cv2.dilate(cluster_x, np.ones((2, 2)))
        for y, cluster_y in enumerate(clusters):
            if x != y:
                remaining[y] = np.where(
                    np.logical_and(dilated, cluster_y),
                    0,
                    remaining[y],
                )
    for x, components in enumerate(remaining):
        current = np.bincount(components.ravel(), minlength=len(counts[x]))
        ratio = np.divide(
            current.astype(np.float32),
            counts[x].astype(np.float32),
            out=np.ones(len(counts[x]), dtype=np.float32),
            where=counts[x] != 0,
        )
        clusters[x] = np.where(ratio[original[x]] <= 0.1, 0, clusters[x])
    enhanced = np.zeros(labels.shape, dtype=np.uint8)
    for cluster in clusters:
        enhanced = np.where(enhanced == 0, cluster, enhanced)
    nearest = distance_transform_edt(
        enhanced == 0,
        return_distances=False,
        return_indices=True,
    )
    enhanced = np.where(enhanced != 0, enhanced, enhanced[tuple(nearest)])
    return enhanced - 1


def reference_clean_components(
    labels: np.ndarray,
    background: np.ndarray | None,
) -> np.ndarray:
    """Find small regions one color at a time, then use labeled chamfer refill."""
    remove = np.zeros(labels.shape, dtype=bool)
    for color in np.unique(labels):
        mask = labels == color
        _, components = cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)
        sizes = np.bincount(components.ravel())
        remove |= mask & (sizes[components] < 8)
    if background is not None:
        remove &= background == 0
    else:
        height, width = labels.shape
        edge = {(y, x) for y in (0, height - 1) for x in range(width)}
        edge |= {(y, x) for x in (0, width - 1) for y in range(height)}
        counts = Counter(int(labels[y, x]) for y, x in edge if not remove[y, x])
        if counts:
            color = min(counts, key=lambda value: (-counts[value], value))
            remove &= labels != color
    result = labels.copy()
    if remove.any() and not remove.all():
        _, nearest = cv2.distanceTransformWithLabels(
            remove.astype(np.uint8),
            cv2.DIST_L2,
            5,
            labelType=cv2.DIST_LABEL_PIXEL,
        )
        # OpenCV numbers each zero pixel in scan order, starting from one.
        survivors = labels[~remove]
        result[remove] = survivors[nearest[remove] - 1]
    return result
