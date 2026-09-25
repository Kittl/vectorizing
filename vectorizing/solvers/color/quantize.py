"""Quantize colors without discarding connected thin features or alpha holes."""

import cv2
import numpy as np
from faiss import Kmeans
from PIL import Image
from scipy.ndimage import distance_transform_edt
from skimage.measure import label

MIN_COMPONENT_AREA = 8


def bilateral_filter(img_arr: np.ndarray) -> np.ndarray:
    """Gently smooth local color noise without the broad blur of a large kernel."""
    return cv2.bilateralFilter(img_arr, 3, 12, 1)


def _perimeter(array: np.ndarray) -> np.ndarray:
    """Read each boundary pixel once, including single-row or single-column images."""
    if min(array.shape) == 1:
        return array.ravel()
    return np.concatenate([array[0], array[-1], array[1:-1, 0], array[1:-1, -1]])


def clean_components(
    labels: np.ndarray,
    background: np.ndarray | None,
) -> np.ndarray:
    """Refill tiny components, protecting transparency and background-color counters.

    Area, not the proportion of interior pixels, determines removal, retaining
    thin components above the cutoff. Connectivity includes diagonal contacts.
    The labeled chamfer transform assigns removed pixels to surviving neighbors;
    when nothing survives, retain the input instead of inventing a replacement.
    For opaque images, protect the most common surviving perimeter color so small
    enclosed letter counters are not filled. Ties use the lowest palette index.

    Parameters
    ----------
    labels : numpy.ndarray
        Two-dimensional palette indices, including zero for any background.
    background : numpy.ndarray or None
        Nonzero at protected transparent pixels, if present.

    Returns
    -------
    numpy.ndarray
        Cleaned labels with the input dtype; the input is never mutated.
    """
    components = label(labels.astype(np.uint16) + 1, background=0, connectivity=2)
    counts = np.bincount(components.ravel())
    holes = counts[components] < MIN_COMPONENT_AREA
    if background is not None:
        holes &= background == 0
    elif holes.any() and not holes.all():
        perimeter = _perimeter(labels)[~_perimeter(holes)]
        if perimeter.size:
            background_color = np.bincount(perimeter).argmax()
            holes &= labels != background_color
    if not holes.any() or holes.all():
        return labels

    _, nearest = cv2.distanceTransformWithLabels(
        holes.astype(np.uint8),
        cv2.DIST_L2,
        5,
        labelType=cv2.DIST_LABEL_PIXEL,
    )
    lookup = np.zeros(int(nearest.max()) + 1, dtype=labels.dtype)
    lookup[nearest[~holes]] = labels[~holes]
    cleaned = labels.copy()
    cleaned[holes] = lookup[nearest[holes]]
    unassigned = holes & (nearest == 0)
    if unassigned.any():
        # OpenCV can leave zero labels beyond its distance propagation limit
        # on very wide/tall images. Zero is not a seed: use an exact fallback
        # only there, preserving normal chamfer assignments and tie breaking.
        indices = distance_transform_edt(
            holes,
            return_distances=False,
            return_indices=True,
        )
        cleaned[unassigned] = labels[tuple(indices[:, unassigned])]
    return cleaned


# Keep transparent pixels separate from RGB clustering: otherwise opaque and
# transparent pixels with similar RGB values can be assigned to the same color.
def get_background_cluster(img_arr: np.ndarray, t: float = 0.5) -> np.ndarray | None:
    """Return an alpha mask if any raw alpha is below t, otherwise return None."""
    r, g, b, a = cv2.split(img_arr)

    has_transparent_background = np.any(a < t)
    if has_transparent_background:
        a = np.where(a / 255 < t, 1, 0)
        return np.reshape(a, img_arr.shape[:2])

    return None


def write_background_cluster(labels: np.ndarray, bg_cluster: np.ndarray) -> np.ndarray:
    """Shift labels by one, reserving zero for the overriding background mask."""
    labels = labels + 1
    labels = np.where(bg_cluster > 0, 0, labels)
    return labels


def get_initial_centroids(img_arr: np.ndarray, color_count: int) -> np.ndarray:
    """Return sorted unique used RGB palette colors for K-means initialization."""
    img = Image.fromarray(img_arr)
    img = img.quantize(color_count, method=Image.Quantize.FASTOCTREE)
    # Palette padding must not introduce additional clusters. RGB order affects
    # initialization, so sort the used entries rather than the entire pixel grid.
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
    """Return area-cleaned labels, an RGB-ordered palette and background status."""
    background = get_background_cluster(img_arr) if img_arr.shape[-1] == 4 else None
    rgb = bilateral_filter(img_arr[:, :, :3].copy())
    labels, colors = kmeans(rgb, get_initial_centroids(rgb, color_count))
    labels = labels.reshape(rgb.shape[:2])

    # Paint order determines which neighboring colors may receive a bounded rim.
    order = np.lexsort(colors.T[::-1])
    labels = np.argsort(order)[labels].astype(np.uint16)
    colors = colors[order]
    if background is not None:
        labels = write_background_cluster(labels, background)
        colors = np.vstack(
            [
                np.zeros((1, 4), dtype=np.uint8),
                np.column_stack([colors, np.ones(len(colors), dtype=np.uint8)]),
            ],
        )
    labels = clean_components(labels, background)
    if background is not None:
        labels = np.where(background > 0, 0, labels)
    return labels, colors, background is not None
