"""Overlapping bitmap regressions, including transparent and unused colors.

Masks must be cumulative in palette order without sharing writable storage.
"""

import numpy as np
import pytest

from vectorizing.solvers.color.bitmaps import create_bitmaps
from vectorizing.tests.color_reference import legacy_create_bitmaps


@pytest.mark.parametrize(
    "variant",
    ["noise", "strided", "one-row", "one-column", "solid", "background", "sparse"],
)
@pytest.mark.parametrize("color_count", [1, 2, 6, 16, 64, 65])
@pytest.mark.parametrize("has_background", [False, True])
@pytest.mark.parametrize("seed", range(3))
def test_bitmap_layering_matches_original(
    color_count: int,
    has_background: bool,
    seed: int,
    variant: str,
) -> None:
    """Preserve masks, dtype, color order and read-only inputs across label patterns."""
    rng = np.random.default_rng(seed)
    noise = rng.integers(0, color_count, size=(19, 23), dtype=np.uint16)
    colors = rng.integers(0, 256, size=(color_count, 4), dtype=np.uint8)
    colors.setflags(write=False)
    labels = {
        "noise": noise,
        "strided": noise[::2, ::2],
        "one-row": noise[:1, :],
        "one-column": noise[:, :1],
        "solid": np.full_like(noise, color_count - 1),
        "background": np.zeros_like(noise),
        "sparse": noise % 2,
    }[variant]
    labels.setflags(write=False)
    expected_bitmaps, expected_colors = legacy_create_bitmaps(
        labels,
        colors,
        has_background,
    )
    actual_bitmaps, actual_colors = create_bitmaps(labels, colors, has_background)
    np.testing.assert_array_equal(actual_colors, expected_colors)
    np.testing.assert_equal(len(actual_bitmaps), len(expected_bitmaps))
    for actual, expected in zip(actual_bitmaps, expected_bitmaps):
        np.testing.assert_equal(actual.dtype, np.dtype(np.uint32))
        np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize("has_background", [False, True])
@pytest.mark.parametrize("color_count", [0, 1, 6])
def test_bitmap_layering_handles_empty_inputs(
    has_background: bool,
    color_count: int,
) -> None:
    """Return no layers for empty labels or an empty palette."""
    colors = np.zeros((color_count, 3), dtype=np.uint8)
    labels = np.empty((0, 3), dtype=np.uint8)
    np.testing.assert_equal(create_bitmaps(labels, colors, has_background), ([], []))
    np.testing.assert_equal(
        create_bitmaps(np.zeros((2, 2), dtype=np.uint8), colors[:0], has_background),
        ([], []),
    )


def test_bitmap_layering_preserves_overlap_and_transparency() -> None:
    """Keep suffix unions in palette order without including transparent pixels."""
    labels = np.array([[0, 1, 3, 4]], dtype=np.uint8)
    colors = np.arange(20, dtype=np.uint8).reshape(5, 4)
    # Label zero is transparent; label two is unused between visible layers.
    bitmaps, visible_colors = create_bitmaps(labels, colors, True)
    expected = np.array(
        [[[0, 1, 1, 1]], [[0, 0, 1, 1]], [[0, 0, 0, 1]]],
        dtype=np.uint32,
    )
    np.testing.assert_array_equal(bitmaps, expected)
    np.testing.assert_array_equal(visible_colors, colors[[1, 3, 4]])
    # The in-place accumulation must not make different layers share storage.
    bitmaps[0][0, 0] = 1
    np.testing.assert_array_equal(bitmaps[1:], expected[1:])
    np.testing.assert_array_equal(labels, [[0, 1, 3, 4]])
