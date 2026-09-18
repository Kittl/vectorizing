"""Bound overlap at the bitmap stage independently of Potrace's curve fitting."""

import numpy as np
import pytest

from vectorizing.solvers.color.bitmaps import add_bitmap_rims, create_bitmaps


@pytest.mark.parametrize("transparent", [False, True])
@pytest.mark.parametrize("shape", [(1, 1), (1, 9), (9, 1), (8, 13)])
@pytest.mark.parametrize("seed", range(5))
def test_bitmap_rims_match_a_bounded_neighbor_reference(
    transparent: bool,
    shape: tuple[int, int],
    seed: int,
) -> None:
    """Add only later-color pixels within two grid cells of this color's own pixels."""
    labels = np.random.default_rng(seed).integers(0, 5, size=shape)
    colors = np.arange(15).reshape(5, 3)
    masks, retained = create_bitmaps(labels, colors, transparent)
    ids = [id(mask) for mask in masks]
    expected = []
    # A direct pixel loop is deliberately independent of OpenCV dilation and
    # cumulative-mask mutation. Missing palette colors must not affect ordering.
    for color in retained:
        index = int(color[0] // 3)
        own = labels == index
        neighbors = np.zeros(shape, dtype=bool)
        for y, x in np.argwhere(own):
            top, bottom = max(0, y - 2), y + 3
            left, right = max(0, x - 2), x + 3
            neighbors[top:bottom, left:right] = True
        expected.append((neighbors & (labels >= index)).astype(np.uint32))
    add_bitmap_rims(masks)
    np.testing.assert_equal([id(mask) for mask in masks], ids)
    for actual, reference in zip(masks, expected):
        np.testing.assert_array_equal(actual, reference)
        np.testing.assert_equal(actual.dtype, np.dtype(np.uint32))
    # Every original foreground pixel remains covered; no transparent background
    # pixel becomes painted, even where it touches several colors.
    combined = np.any(masks, axis=0) if masks else np.zeros(shape, dtype=bool)
    np.testing.assert_array_equal(combined, labels != 0 if transparent else True)


def test_bitmap_rims_handle_empty_input() -> None:
    """Leave empty artwork empty."""
    masks = []
    add_bitmap_rims(masks)
    np.testing.assert_equal(masks, [])


def test_bitmap_rims_document_the_thin_feature_tradeoff() -> None:
    """Document that a narrow strip can be covered entirely by a neighboring rim."""
    labels = np.zeros((12, 12), dtype=int)
    labels[:, 5:7] = 1
    masks, _ = create_bitmaps(labels, np.zeros((2, 3)), False)
    add_bitmap_rims(masks)
    np.testing.assert_array_equal(masks[0][:, 5:7], 1)
