"""Used-palette centroid regressions: exact values, dtype and ordering.

Centroid ordering changes K-means results, so set equality is not sufficient.
"""

import numpy as np
import pytest
from PIL import Image

from vectorizing.solvers.color import quantize as color_quantize
from vectorizing.tests.color_reference import legacy_initial_centroids


@pytest.mark.parametrize(
    "variant",
    ["noise", "strided", "one-pixel", "solid", "sparse"],
)
@pytest.mark.parametrize("color_count", [2, 6, 16, 64])
@pytest.mark.parametrize("seed", range(5))
def test_initial_centroids_match_original(
    color_count: int,
    seed: int,
    variant: str,
) -> None:
    """Preserve exact dtype, values and ordering on random and sparse RGB inputs."""
    rng = np.random.default_rng(seed)
    noise = rng.integers(0, 256, size=(63, 67, 3), dtype=np.uint8)
    pixels = {
        "noise": noise,
        "strided": noise[::2, ::2],
        "one-pixel": noise[:1, :1],
        "solid": np.full_like(noise, (175, 80, 230)),  # Ignore unused black entries.
        "sparse": (noise // 128) * 128,
    }[variant]
    expected = legacy_initial_centroids(pixels, color_count)
    actual = color_quantize.get_initial_centroids(pixels, color_count)
    np.testing.assert_equal(actual.dtype, expected.dtype)
    np.testing.assert_equal(actual.dtype, np.dtype(np.uint8))
    np.testing.assert_array_equal(actual, expected)


def test_initial_centroids_ignore_unused_and_duplicate_palette_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep only used RGB colors, deduplicated and sorted rather than palette order."""
    indexed = Image.new("P", (3, 1))
    indexed.putdata([7, 3, 5])
    palette = np.zeros((256, 3), dtype=np.uint8)
    palette[1] = (255, 0, 0)  # Unused nonblack entry.
    palette[3] = palette[7] = (90, 10, 20)  # Duplicate used RGB entries.
    palette[5] = (10, 20, 30)
    indexed.putpalette(palette.ravel().tolist())
    with monkeypatch.context() as patch:
        patch.setattr(Image.Image, "quantize", lambda *args, **kwargs: indexed)
        pixels = np.zeros((1, 3, 3), dtype=np.uint8)
        actual = color_quantize.get_initial_centroids(pixels, 64)
        expected = legacy_initial_centroids(pixels, 64)
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(actual, [[10, 20, 30], [90, 10, 20]])
