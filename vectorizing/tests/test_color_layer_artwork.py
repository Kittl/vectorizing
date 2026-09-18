"""Check rim rendering and edited holes on the real artwork fixtures."""

from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import potrace
import pytest
from cairosvg import svg2png
from PIL import Image
from scipy.ndimage import distance_transform_edt

from vectorizing.geometry.potrace import potrace_path_to_compound_path
from vectorizing.server.timer import Timer
from vectorizing.solvers.color.bitmaps import add_bitmap_rims
from vectorizing.solvers.color.ColorSolver import ColorSolver
from vectorizing.svg.markup import generate_SVG_markup


@pytest.mark.parametrize("filename, count", [("bubbles.png", 5), ("shapes_2.png", 7)])
def test_opaque_artwork_has_no_alpha_seams(filename: str, count: int) -> None:
    """Keep opaque artwork opaque through every shared boundary."""
    with Image.open(Path(__file__).parent / "images" / filename) as image:
        result = ColorSolver(image, count, Timer()).solve()
    markup = generate_SVG_markup(*result)
    pixels = np.asarray(Image.open(BytesIO(svg2png(bytestring=markup))).convert("RGBA"))
    np.testing.assert_array_equal(pixels[:, :, 3], 255)
    np.testing.assert_equal("stroke=" in markup, False)


def test_aftermath_retains_holes_when_layers_are_edited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the exterior transparent and reveal holes, not underpainting, on edits."""
    foreground = []

    def capture_foreground(masks: list[np.ndarray]) -> None:
        foreground.append(masks[0].copy())
        add_bitmap_rims(masks)

    rim_builder = Mock(side_effect=capture_foreground)
    monkeypatch.setattr(
        "vectorizing.solvers.color.ColorSolver.add_bitmap_rims", rim_builder,
    )
    with Image.open(Path(__file__).parent / "images" / "aftermath.png") as image:
        paths, colors, width, height = ColorSolver(image, 16, Timer()).solve()
    rim_builder.assert_called_once()
    silhouette = potrace_path_to_compound_path(potrace.Bitmap(foreground[0]).trace())
    silhouette_svg = generate_SVG_markup([silhouette], [[0, 0, 0]], width, height)
    silhouette_alpha = np.asarray(
        Image.open(BytesIO(svg2png(bytestring=silhouette_svg))).convert("RGBA"),
    )[:, :, 3]
    markup = generate_SVG_markup(paths, colors, width, height)
    full = np.asarray(Image.open(BytesIO(svg2png(bytestring=markup))).convert("RGBA"))
    np.testing.assert_equal(full[:, :, 3].min(), 0)
    np.testing.assert_equal(full[:, :, 3].max(), 255)
    # Allow smooth exterior edges, but catch broad interior seam regressions.
    alpha = full[:, :, 3]
    # Unlike a total partial-alpha budget, this checks where gaps occur. Allow
    # a 3-pixel band by the exterior: separately fitted curves can differ there.
    interior = distance_transform_edt(silhouette_alpha == 255) > 3
    np.testing.assert_equal(interior.any(), True)
    np.testing.assert_array_equal(alpha[interior], 255)
    exterior = distance_transform_edt(silhouette_alpha == 0) > 3
    np.testing.assert_array_equal(alpha[exterior], 0)
    np.testing.assert_equal(
        np.count_nonzero((alpha > 0) & (alpha < 255)) < 10_000,
        True,
    )
    for index in [0, len(paths) // 2, len(paths) - 1]:
        solo = generate_SVG_markup([paths[index]], [colors[index]], width, height)
        solo_alpha = np.asarray(
            Image.open(BytesIO(svg2png(bytestring=solo))).convert("RGBA"),
        )[:, :, 3]
        # Select a point far inside the color, excluding its intentionally narrow rim.
        distances = distance_transform_edt(solo_alpha == 255)
        np.testing.assert_equal(distances.max() > 2, True)
        point = np.unravel_index(distances.argmax(), distances.shape)
        for opacity in [None, 0, 0.5]:
            edited_paths, edited_colors = list(paths), list(colors)
            if opacity is None:
                del edited_paths[index]
                del edited_colors[index]
            else:
                edited_colors[index] = np.array([*colors[index][:3], opacity])
            edited = generate_SVG_markup(edited_paths, edited_colors, width, height)
            pixels = np.asarray(
                Image.open(BytesIO(svg2png(bytestring=edited))).convert("RGBA"),
            )
            np.testing.assert_equal(pixels[point][3], 128 if opacity == 0.5 else 0)
            np.testing.assert_equal(pixels[0, 0, 3], 0)
