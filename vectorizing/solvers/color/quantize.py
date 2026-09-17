"""Quantize RGB colors while keeping transparent background pixels separate."""

import cv2
import numpy as np
import scipy.ndimage as ndi
from faiss import Kmeans
from PIL import Image
from skimage.measure import label

BILATERAL_FILTER_DIAMETER = 7
BILATERAL_FILTER_SIGMA = 50


def bilateral_filter(
    img_arr: np.ndarray,
    d: int = BILATERAL_FILTER_DIAMETER,
    s: float = BILATERAL_FILTER_SIGMA,
) -> np.ndarray:
    """Smooth clip-art colors while preserving edges; photos may lose detail."""
    return cv2.bilateralFilter(img_arr, d, s, s)


def fill_holes(matrix: np.ndarray) -> np.ndarray:
    """Replace zero cells with their nearest nonzero value via a distance transform."""
    closest = ndi.distance_transform_edt(
        np.logical_not(matrix),
        return_distances=False,
        return_indices=True,
    )
    matrix = np.where(matrix != 0, matrix, matrix[closest[0], closest[1]])
    return matrix


def enhance(
    img_arr: np.ndarray,
    labels: np.ndarray,
    colors: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Remove boundary-dominated components with O(K*N) work and O(N) image storage."""
    # Reserve zero for holes, preserving the existing input-dtype shift behavior.
    labels = labels + 1
    valid = (labels > 0) & (labels <= len(colors))

    # OpenCV's 2x2 dilation (default anchor/border) reaches a pixel from above,
    # left, and upper-left. Mark overlap from any OTHER palette color once,
    # without treating missing/out-of-palette neighbors as a dilated cluster.
    boundary = np.zeros(labels.shape, dtype=bool)
    boundary[1:, :] |= valid[:-1, :] & (labels[1:, :] != labels[:-1, :])
    boundary[:, 1:] |= valid[:, :-1] & (labels[:, 1:] != labels[:, :-1])
    boundary[1:, 1:] |= valid[:-1, :-1] & (labels[1:, 1:] != labels[:-1, :-1])

    # The boundary is fixed; reuse its complement for every color's area count.
    interior = ~boundary
    cleaned = np.zeros(img_arr.shape[:2], dtype=np.uint16 if len(colors) else np.uint8)
    for index in range(len(colors)):
        cluster = labels == index + 1
        if not cluster.any():
            continue
        # Keep full (8-neighbor) connectivity, including diagonal contacts.
        components = label(cluster, connectivity=2)
        original_counts = np.bincount(components.ravel())
        interior_counts = np.bincount(
            components[interior],
            minlength=len(original_counts),
        )
        areas_ratio = np.divide(
            interior_counts.astype(np.float32),
            original_counts.astype(np.float32),
            out=np.ones(len(original_counts), dtype=np.float32),
            where=original_counts != 0,
        )
        # Retain whole components, using the same float32, inclusive <=0.1 cutoff.
        cleaned[cluster & (areas_ratio[components] > 0.1)] = index + 1
        # Release this map before allocating the next color's component map.
        del components

    return fill_holes(cleaned) - 1, colors


# Try to get the cluster of pixels that represent a transparent background
# If there is no transparent background, return None
# This is needed because RGBA quantization is very volatile, and sometimes
# opaque colors get assigned to the same clusters as highly transparent ones.
# So we focus on the solid image + transparent background case for now.
def get_background_cluster(img_arr: np.ndarray, t: float = 0.5) -> np.ndarray | None:
    """Return an alpha mask if any raw alpha is below t, otherwise return None."""
    r, g, b, a = cv2.split(img_arr)

    has_transparent_background = np.any(a < t)
    if has_transparent_background:
        a = np.where(a / 255 < t, 1, 0)
        return np.reshape(a, img_arr.shape[:2])

    return None


# Write the background cluster on top of a matrix of clusters (labels)
# The background cluster has priority
def write_background_cluster(labels: np.ndarray, bg_cluster: np.ndarray) -> np.ndarray:
    """Shift labels by one, reserving zero for the overriding background mask."""
    labels = labels + 1
    labels = np.where(bg_cluster > 0, 0, labels)
    return labels


def get_initial_centroids(img_arr: np.ndarray, color_count: int) -> np.ndarray:
    """Return sorted unique used RGB palette colors for K-means initialization."""
    img = Image.fromarray(img_arr)

    img = img.quantize(color_count, method=Image.Quantize.FASTOCTREE)

    # Ignore unused entries: palette padding must not add extra K-means clusters.
    # Keep np.unique's RGB order and deduplication, but sort only the used palette
    # rather than every pixel. Centroid order affects K-means results.
    # quantize() returns mode P: at most 256 entries, within getcolors()'s cap.
    used_indices = [index for _, index in img.getcolors()]
    palette = np.asarray(img.getpalette("RGB"), dtype=np.uint8).reshape(-1, 3)
    return np.unique(palette[used_indices], axis=0)


def kmeans(
    img_arr: np.ndarray,
    init_centroids: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Cluster RGB pixels with FAISS and return uint8 labels and centroids."""
    channel_count = img_arr.shape[-1]
    data = np.reshape(img_arr, (-1, channel_count)).astype(np.float32)
    init_centroids = init_centroids.astype(np.float32)
    km = Kmeans(channel_count, init_centroids.shape[0], niter=100)
    km.train(data, init_centroids=init_centroids)
    _, labels = km.index.search(data, 1)
    return labels.astype(np.uint8), km.centroids.astype(np.uint8)


def quantize(
    img_arr: np.ndarray,
    color_count: int,
) -> tuple[np.ndarray, np.ndarray, bool]:
    """Return cleaned labels, palette colors and whether a background was isolated."""
    channel_count = img_arr.shape[-1]

    background_cluster = None
    if channel_count == 4:
        background_cluster = get_background_cluster(img_arr)
        img = Image.fromarray(img_arr)
        img = img.convert("RGB")
        img_arr = np.asarray(img)

    img_arr = bilateral_filter(img_arr)

    labels, colors = kmeans(img_arr, get_initial_centroids(img_arr, color_count))

    labels = np.reshape(labels, img_arr.shape[:-1])

    has_background = background_cluster is not None
    if has_background:
        labels = write_background_cluster(labels, background_cluster)
        colors = [[0, 0, 0, 0]] + [[r, g, b, 1] for r, g, b in colors]
        colors = np.array(colors)

    colors = colors.astype(np.uint8)
    labels, colors = enhance(img_arr, labels, colors)
    return labels, colors, has_background
