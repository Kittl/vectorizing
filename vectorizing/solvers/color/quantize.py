"""Quantize colors without discarding connected thin features or alpha holes."""

import cv2
import numpy as np
from faiss import Kmeans
from PIL import Image
from scipy.ndimage import distance_transform_edt
from skimage.measure import label

MIN_COMPONENT_AREA = 8


def auto_color_count(
    img_arr: np.ndarray,
    background: np.ndarray | None,
) -> tuple[int, np.ndarray | None, Image.Quantize]:
    """Return color count, representative visible RGB and chosen seed method.

    Small sample palettes choose K and the K-means initialization method; the
    selected profile still quantizes the full processed image with its own filter.

    Parameters
    ----------
    img_arr : numpy.ndarray
        Processed RGB or RGBA pixels.
    background : numpy.ndarray or None
        Nonzero at pixels that the quantizer treats as transparent background.

    Returns
    -------
    tuple
        Color count, representative RGB (or None), and seed method.
    """
    pixels = (
        img_arr[background == 0, :3]
        if background is not None
        else img_arr[:, :, :3].reshape(-1, 3)
    )
    if not len(pixels):
        return 1, None, Image.Quantize.FASTOCTREE
    if len(pixels) > 65536:
        # Fixed-seed sampling avoids row-aligned strides hiding whole features.
        indices = np.random.default_rng(0).choice(len(pixels), 65536, replace=False)
        pixels = pixels[indices]
    sample = Image.fromarray(pixels.reshape(1, -1, 3))
    best_count = 0
    representative = None
    chosen_method = Image.Quantize.FASTOCTREE
    # Octree keeps small vivid accents; median cut separates large close tones.
    for method in (Image.Quantize.FASTOCTREE, Image.Quantize.MEDIANCUT):
        palette_image = sample.quantize(16, method=method)
        palette = np.asarray(palette_image.getpalette("RGB"), dtype=np.uint8).reshape(
            -1,
            3,
        )
        entries = sorted(palette_image.getcolors(), reverse=True)
        dominant: list[np.ndarray] = []
        for size, index in entries:
            share = size / len(pixels)
            if share < 0.005:
                continue
            color = palette[index].astype(np.float32)
            # Large, subtly different regions (e.g. a patterned background)
            # matter even when their RGB distance is below the edge-shade cutoff.
            separation = 8 if share >= 0.1 else 25
            if any(np.linalg.norm(color - other) < separation for other in dominant):
                continue
            # Small blended edge colors lie between two stronger colors; large
            # intermediate regions can be real artwork and must keep their slot.
            if share < 0.03 and any(
                np.linalg.norm(
                    color
                    - first
                    - np.clip(
                        np.dot(color - first, second - first)
                        / np.dot(second - first, second - first),
                        0,
                        1,
                    )
                    * (second - first),
                )
                < 25
                for i, first in enumerate(dominant)
                for second in dominant[i + 1 :]
            ):
                continue
            dominant.append(color)
        if len(dominant) > best_count:
            best_count = len(dominant)
            representative = palette[entries[0][1]]
            chosen_method = method
    return max(1, best_count), representative, chosen_method


def _recover_background_slots(
    img_arr: np.ndarray,
    labels: np.ndarray,
    cluster_count: int,
    background: np.ndarray | None,
) -> np.ndarray | None:
    """Replace hidden RGB only for occupied, background-only raw clusters."""
    # Inspect labels before masking or cleanup; losing a tiny visible component
    # to cleanup is not evidence that hidden RGB consumed a palette slot.
    if background is None:
        return None
    visible = background == 0
    if not visible.any():
        return None
    visible_counts = np.bincount(labels[visible], minlength=cluster_count)
    if (visible_counts > 0).all():
        return None
    counts = np.bincount(labels.ravel(), minlength=cluster_count)
    if not np.any((counts > 0) & (visible_counts == 0)):
        return None
    _, representative, _ = auto_color_count(img_arr, background)
    if representative is None:
        return None
    recovered = img_arr.copy()
    recovered[~visible, :3] = representative
    return recovered


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


def get_initial_centroids(
    img_arr: np.ndarray,
    color_count: int,
    method: Image.Quantize = Image.Quantize.FASTOCTREE,
) -> np.ndarray:
    """Return sorted unique used RGB palette colors for K-means initialization."""
    img = Image.fromarray(img_arr)
    img = img.quantize(color_count, method=method)
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
    *,
    auto_method: Image.Quantize | None = None,
    recover_background_slots: bool = False,
) -> tuple[np.ndarray, np.ndarray, bool]:
    """Return cleaned labels/palette, optionally recovering background-only slots."""
    background = get_background_cluster(img_arr) if img_arr.shape[-1] == 4 else None
    for attempt in range(2):
        rgb = bilateral_filter(img_arr[:, :, :3].copy())
        centroids = (
            get_initial_centroids(rgb, color_count, auto_method)
            if auto_method is not None
            else get_initial_centroids(rgb, color_count)
        )
        labels, colors = kmeans(rgb, centroids)
        labels = labels.reshape(rgb.shape[:2])
        if attempt or not recover_background_slots or auto_method is not None:
            break
        recovered = _recover_background_slots(img_arr, labels, len(colors), background)
        if recovered is None:
            break
        # Retry the same numeric count and seed method, then clean only once.
        img_arr = recovered

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
