"""Cluster cleanup parity, morphology edge cases and component-map lifetime.

Unfilled comparisons expose the actual keep/remove decisions: hole filling can
otherwise repaint a wrongly removed component and hide the regression.
"""

import weakref

import numpy as np
import pytest

from vectorizing.solvers.color import quantize as color_quantize
from vectorizing.tests.color_reference import legacy_enhance

# After the final label shift, an unfilled zero wraps to uint16's maximum.
# This sentinel is used only by tests bypassing fill_holes with a nonempty palette.
UNFILLED_LABEL = np.iinfo(np.uint16).max


@pytest.mark.parametrize("before_fill", [False, True], ids=["filled", "unfilled"])
@pytest.mark.parametrize(
    "variant",
    [
        "noise",
        "strided",
        "one-pixel",
        "one-row",
        "one-column",
        "solid",
        "sparse",
        "checkerboard",
    ],
)
# Transparent artwork can add a background entry to the 64 requested colors.
@pytest.mark.parametrize("color_count", [1, 2, 6, 16, 64, 65])
@pytest.mark.parametrize("seed", range(3))
def test_cluster_cleanup_matches_original(
    before_fill: bool,
    variant: str,
    color_count: int,
    seed: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preserve component decisions and filled labels without mutating inputs."""
    rng = np.random.default_rng(seed)
    noise = rng.integers(0, color_count, (19, 23), dtype=np.uint8)
    labels = {
        "noise": noise,
        "strided": noise[::2, ::2],
        "one-pixel": noise[:1, :1],
        "one-row": noise[:1, :],
        "one-column": noise[:, :1],
        "solid": np.full_like(noise, color_count - 1),
        "sparse": noise % 2,
        "checkerboard": (
            np.indices(noise.shape).sum(axis=0) % min(color_count, 2)
        ).astype(np.uint8),
    }[variant]
    colors = rng.integers(0, 256, (color_count, 4), dtype=np.uint8)
    pixels = np.zeros((*labels.shape, 3), dtype=np.uint8)
    labels.setflags(write=False)
    colors.setflags(write=False)
    pixels.setflags(write=False)
    original_labels = labels.copy()
    if before_fill:
        # Compare removal decisions, not just the colors painted over their holes.
        monkeypatch.setattr(color_quantize, "fill_holes", lambda matrix: matrix)
    expected, expected_colors = legacy_enhance(pixels, labels, colors)
    actual, actual_colors = color_quantize.enhance(pixels, labels, colors)
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_equal(actual.dtype, expected.dtype)
    np.testing.assert_array_equal(actual_colors, expected_colors)
    np.testing.assert_equal(actual_colors is colors, True)
    np.testing.assert_array_equal(labels, original_labels)


@pytest.mark.parametrize("area", [9, 10, 11])
def test_cluster_cleanup_preserves_inclusive_area_threshold(
    area: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep a component with 1/9 interior area, but remove 1/10 and 1/11."""
    labels = np.zeros((8, 16), dtype=np.uint8)
    # A 2x2 core has one interior pixel at (3, 3). Extending only its top row
    # changes the component's total area without adding any interior pixels.
    labels[2, 2:area] = 1
    labels[3, 2:4] = 1
    colors = np.zeros((2, 3), dtype=np.uint8)
    pixels = np.zeros((*labels.shape, 3), dtype=np.uint8)
    monkeypatch.setattr(color_quantize, "fill_holes", lambda matrix: matrix)
    expected = labels.astype(np.uint16)
    if area >= 10:
        expected[labels == 1] = UNFILLED_LABEL
    for cleaner in (legacy_enhance, color_quantize.enhance):
        actual, _ = cleaner(pixels, labels, colors)
        np.testing.assert_array_equal(actual, expected)


def test_cluster_cleanup_preserves_diagonal_connectivity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Treat a 2x2 core and its diagonal thin tail as one removable component."""
    labels = np.zeros((8, 16), dtype=np.uint8)
    # Seven tail pixels touch the 4-pixel core only at a corner. With full
    # connectivity the combined 11-pixel component has 1/11 interior area;
    # with 4-neighbor connectivity the core would incorrectly survive at 1/4.
    labels[2:4, 2:4] = 1
    labels[4, 4:11] = 1
    colors = np.zeros((2, 3), dtype=np.uint8)
    pixels = np.zeros((*labels.shape, 3), dtype=np.uint8)
    monkeypatch.setattr(color_quantize, "fill_holes", lambda matrix: matrix)
    expected = labels.astype(np.uint16)
    expected[labels == 1] = UNFILLED_LABEL
    for cleaner in (legacy_enhance, color_quantize.enhance):
        actual, _ = cleaner(pixels, labels, colors)
        np.testing.assert_array_equal(actual, expected)


def test_cluster_cleanup_preserves_dilation_anchor_and_border(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The 2x2 default anchor spares only the isolated top-left corner pixel."""
    labels = np.zeros((5, 5), dtype=np.uint8)
    labels[::4, ::4] = 1
    colors = np.zeros((2, 3), dtype=np.uint8)
    pixels = np.zeros((*labels.shape, 3), dtype=np.uint8)
    monkeypatch.setattr(color_quantize, "fill_holes", lambda matrix: matrix)
    expected = labels.astype(np.uint16)
    expected[labels == 1] = UNFILLED_LABEL
    # No upper/left source exists at (0, 0); outside the image is not a color.
    expected[0, 0] = 1
    for cleaner in (legacy_enhance, color_quantize.enhance):
        actual, _ = cleaner(pixels, labels, colors)
        np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize("before_fill", [False, True], ids=["filled", "unfilled"])
@pytest.mark.parametrize("color_count", [0, 1, 3, 256])
@pytest.mark.parametrize("dtype", [np.uint8, np.uint16, np.int16])
def test_cluster_cleanup_preserves_unassigned_labels_and_dtype(
    color_count: int,
    dtype: type[np.generic],
    before_fill: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ignore unassigned neighbors and retain existing label-shift overflow behavior."""
    rng = np.random.default_rng(42)
    # 255 + 1 wraps only for uint8; do not silently fix that old behavior here.
    # Small palettes also leave labels whose pixels must not dilate into others.
    labels = rng.choice([0, 1, 2, 3, 254, 255], size=(7, 9)).astype(dtype)
    if dtype == np.int16:
        labels[1, 1:3] = [-1, -2]
    if before_fill:
        monkeypatch.setattr(color_quantize, "fill_holes", lambda matrix: matrix)
    colors = np.zeros((color_count, 3), dtype=np.uint8)
    pixels = np.zeros((*labels.shape, 3), dtype=np.uint8)
    expected, _ = legacy_enhance(pixels, labels, colors)
    actual, actual_colors = color_quantize.enhance(pixels, labels, colors)
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_equal(actual.dtype, expected.dtype)
    np.testing.assert_equal(actual_colors is colors, True)


@pytest.mark.parametrize("before_fill", [False, True], ids=["filled", "unfilled"])
@pytest.mark.parametrize("transpose", [False, True])
def test_cluster_cleanup_crops_labeling_without_losing_neighbor_influence(
    before_fill: bool,
    transpose: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Crop sparse colors while preserving disjoint islands and outside influences."""
    labels = np.zeros((13, 17), dtype=np.uint8)
    labels[2:4, 3:5] = 1
    labels[8, 11] = 1  # A disconnected pixel of the same color must be removed.
    labels[0, 14:17] = 2  # A single-row crop touching the image border.
    labels[9, 2] = labels[10, 3] = 3  # Diagonal contact within a tight crop.
    if transpose:
        labels = labels.T
    colors = np.zeros((6, 3), dtype=np.uint8)  # Two palette entries are unused.
    pixels = np.zeros((*labels.shape, 3), dtype=np.uint8)
    if before_fill:
        monkeypatch.setattr(color_quantize, "fill_holes", lambda matrix: matrix)
    expected, _ = legacy_enhance(pixels, labels, colors)
    original_label = color_quantize.label
    shapes = []

    def record_label(cluster: np.ndarray, connectivity: int) -> np.ndarray:
        shapes.append(cluster.shape)
        return original_label(cluster, connectivity=connectivity)

    monkeypatch.setattr(color_quantize, "label", record_label)
    actual, _ = color_quantize.enhance(pixels, labels, colors)
    np.testing.assert_array_equal(actual, expected)
    # The background spans the image; each other color gets one minimal box,
    # including all of its disconnected pieces, and unused entries get no pass.
    expected_shapes = [(13, 17), (7, 9), (1, 3), (2, 2)]
    if transpose:
        expected_shapes = [(width, height) for height, width in expected_shapes]
    np.testing.assert_array_equal(shapes, expected_shapes)


def test_cluster_cleanup_releases_each_component_map(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Release the old map before labeling the next color, not only on return."""
    original_label = color_quantize.label
    maps: list[weakref.ReferenceType[np.ndarray]] = []

    def record_label(cluster: np.ndarray, connectivity: int) -> np.ndarray:
        # Weak references observe lifetime without keeping the maps alive.
        # Checking before allocation catches even a temporary two-map overlap.
        np.testing.assert_equal(all(ref() is None for ref in maps), True)
        components = original_label(cluster, connectivity=connectivity)
        maps.append(weakref.ref(components))
        return components

    monkeypatch.setattr(color_quantize, "label", record_label)
    labels = (np.indices((8, 9)).sum(axis=0) % 4).astype(np.uint8)
    pixels = np.zeros((*labels.shape, 3), dtype=np.uint8)
    colors = np.zeros((4, 3), dtype=np.uint8)
    color_quantize.enhance(pixels, labels, colors)
    # All colors are present: a skipped labeler must not make this pass vacuously.
    np.testing.assert_equal(len(maps), 4)
    np.testing.assert_equal(all(ref() is None for ref in maps), True)
