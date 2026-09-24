"""Full solver regressions comparing exact SVG bytes, colors and geometry.

Replace one optimization at a time with its frozen reference while retaining the
others. This catches interactions that isolated mask/centroid/cleanup tests miss.
"""

from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
from PIL import Image

from vectorizing.geometry.bounds import compound_paths_bounds
from vectorizing.server.timer import Timer
from vectorizing.solvers.color.ColorSolver import ColorSolver
from vectorizing.svg.markup import generate_SVG_markup
from vectorizing.tests.color_reference import (
    legacy_create_bitmaps,
    legacy_enhance,
    legacy_initial_centroids,
)


@pytest.mark.parametrize("optimization", ["centroids", "bitmaps", "cleanup"])
@pytest.mark.parametrize(
    "image_name, color_count",
    [
        ("bubbles.png", 5),
        ("shapes_2.png", 7),
        ("aftermath.png", 2),
        ("aftermath.png", 6),
        ("aftermath.png", 16),
        ("aftermath.png", 64),
        ("empty.png", 6),
        ("1px.jpg", 9),
    ],
)
def test_color_optimizations_preserve_vectorization(
    image_name: str,
    color_count: int,
    optimization: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compare final SVG, colors, dimensions and bounds against the old algorithm."""
    with Image.open(Path(__file__).parent / "images" / image_name) as image:
        actual = ColorSolver(image, color_count, Timer()).solve()
        target, legacy = {
            "centroids": (
                "vectorizing.solvers.color.quantize.get_initial_centroids",
                legacy_initial_centroids,
            ),
            "bitmaps": (
                "vectorizing.solvers.color.ColorSolver.create_bitmaps",
                legacy_create_bitmaps,
            ),
            "cleanup": (
                "vectorizing.solvers.color.quantize.enhance",
                legacy_enhance,
            ),
        }[optimization]
        # Patch each lookup site and verify the legacy implementation was used.
        reference = Mock(wraps=legacy)
        monkeypatch.setattr(target, reference)
        expected = ColorSolver(image, color_count, Timer()).solve()
        reference.assert_called_once()

    actual_paths, actual_colors, actual_width, actual_height = actual
    expected_paths, expected_colors, expected_width, expected_height = expected
    np.testing.assert_array_equal(actual_colors, expected_colors)
    np.testing.assert_equal(
        (actual_width, actual_height),
        (expected_width, expected_height),
    )
    np.testing.assert_equal(
        compound_paths_bounds(actual_paths),
        compound_paths_bounds(expected_paths),
    )
    # Byte-identical SVG is stricter than a raster tolerance and includes transparency.
    np.testing.assert_equal(
        generate_SVG_markup(*actual),
        generate_SVG_markup(*expected),
    )
