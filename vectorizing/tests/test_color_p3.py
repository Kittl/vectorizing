"""Acceptance checks for the approved detail-preserving color pipeline."""

import hashlib
import json
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
import pytest
from cairosvg import svg2png
from PIL import Image

from vectorizing.geometry.bounds import compound_paths_bounds
from vectorizing.server.timer import Timer
from vectorizing.solvers.color.ColorSolver import ColorSolver, trace_bitmap
from vectorizing.solvers.color.quantize import quantize
from vectorizing.svg.markup import generate_SVG_markup
from vectorizing.tests.test_svg_geometry import expected_commands

IMAGES = Path(__file__).parent / "images"


def test_aftermath_matches_approved_p3_geometry() -> None:
    """Match the independently captured approved P3 geometry, palette and size."""
    with Image.open(IMAGES / "aftermath.png") as image:
        paths, colors, width, height = ColorSolver(image, 8, Timer()).solve()
    # This digest was captured from the approved experimental SVG, before the
    # production port, with absolute commands in integer hundredths of a pixel.
    commands = [expected_commands(path) for path in paths]
    digest = hashlib.sha256(
        json.dumps(commands, separators=(",", ":")).encode(),
    ).hexdigest()
    assert digest == "23d8c97dee23ea3f0b22d164d39f726f36ead7f2ce47048ca73326bf2731c7e8"
    np.testing.assert_array_equal(
        np.asarray(colors)[:, :3],
        [
            [2, 3, 8],
            [19, 60, 148],
            [28, 100, 202],
            [41, 36, 63],
            [192, 149, 160],
            [213, 54, 118],
            [235, 215, 217],
            [248, 57, 61],
        ],
    )
    assert (width, height) == (1024, 1024)
    svg = generate_SVG_markup(paths, colors, width, height)
    # Approved pre-encoding P3: 1,376,657 bytes. Do not discard geometry for size.
    assert len(svg.encode()) < 760_000


@pytest.fixture(scope="module")
def bubbles_pixels() -> np.ndarray:
    """Render the real 16-color artwork at its original dimensions."""
    with Image.open(IMAGES / "bubbles.png") as image:
        result = ColorSolver(image, 16, Timer()).solve()
        png = svg2png(
            bytestring=generate_SVG_markup(*result),
            output_width=image.width,
            output_height=image.height,
        )
    return np.asarray(Image.open(BytesIO(png)).convert("RGBA"))


@pytest.mark.parametrize("threshold", [15, 30, 45])
@pytest.mark.parametrize(
    "box, center, minimum_area",
    [((697, 891, 736, 933), (19, 21), 15), ((752, 868, 786, 899), (17, 15), 5)],
    ids=["a", "e"],
)
def test_laundry_care_counters_remain_open(
    bubbles_pixels: np.ndarray,
    threshold: int,
    box: tuple[int, int, int, int],
    center: tuple[int, int],
    minimum_area: int,
) -> None:
    """Retain both enclosed light counters, including the smaller 'e'."""
    x0, y0, x1, y1 = box
    roi = bubbles_pixels[y0:y1, x0:x1, :3].astype(np.int16)
    pink = (roi[:, :, 0] - roi[:, :, 1] > threshold) & (
        roi[:, :, 0] - roi[:, :, 2] > threshold / 2
    )
    _, components, stats, centers = cv2.connectedComponentsWithStats(
        (~pink).astype(np.uint8),
        connectivity=8,
    )
    border = np.unique(
        np.concatenate(
            [
                components[0],
                components[-1],
                components[:, 0],
                components[:, -1],
            ],
        ),
    )
    holes = [
        index
        for index in range(1, len(stats))
        if index not in border
        and stats[index, cv2.CC_STAT_AREA] >= minimum_area
        and np.linalg.norm(centers[index] - center) <= 6
    ]
    assert holes, f"The Laundry Care counter at {box} was filled"


@pytest.mark.parametrize(
    "count, expected",
    [(None, 6), (0, 6), (1, 2), (8, 8), (100, 64)],
)
def test_public_limits_remain_unchanged(count: int | None, expected: int) -> None:
    """Keep caller color counts/defaults and the existing pixel-area cap."""
    solver = ColorSolver(Image.new("RGB", (1200, 1200)), count, Timer())
    assert solver.color_count == expected
    assert solver.img.size == (1024, 1024)


def test_canvas_padding_is_clipped_from_returned_paths() -> None:
    """Fill canvas corners without exposing padding in exported geometry or bounds."""
    path = trace_bitmap(np.ones((12, 20), dtype=np.uint8))
    assert compound_paths_bounds([path]) == {
        "left": 0,
        "top": 0,
        "right": 20,
        "bottom": 12,
        "width": 20,
        "height": 12,
    }
    png = svg2png(bytestring=generate_SVG_markup([path], [[0, 0, 0]], 20, 12))
    np.testing.assert_array_equal(
        np.asarray(Image.open(BytesIO(png)).convert("RGBA"))[:, :, 3],
        255,
    )


def test_clipped_logo_preserves_opaque_canvas() -> None:
    """Keep coverage on a real clipped logo, including the canvas boundary."""
    with Image.open(IMAGES / "geo_logo.png") as image:
        result = ColorSolver(image, 8, Timer()).solve()
    markup = generate_SVG_markup(*result)
    png = svg2png(bytestring=markup)
    pixels = np.asarray(Image.open(BytesIO(png)).convert("RGBA"))
    np.testing.assert_array_equal(pixels[:, :, 3], 255)


def test_fully_transparent_image_has_no_foreground() -> None:
    """Area cleanup must not invent opaque pixels in an entirely transparent input."""
    pixels = np.zeros((8, 8, 4), dtype=np.uint8)
    labels, palette, background = quantize(pixels, 16)
    assert background
    np.testing.assert_array_equal(labels, 0)
    assert palette.dtype == np.uint8
    result = ColorSolver(Image.fromarray(pixels), 16, Timer()).solve()
    assert result[0] == []
