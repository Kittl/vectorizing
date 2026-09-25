"""Acceptance checks for the approved detail-preserving color pipeline."""

import hashlib
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import cv2
import numpy as np
import pytest
from cairosvg import svg2png
from flask.testing import FlaskClient
from pathops import PathOpsError
from PIL import Image

from vectorizing.geometry.bounds import compound_paths_bounds
from vectorizing.server.timer import Timer
from vectorizing.solvers.color.bitmaps import add_bitmap_rims
from vectorizing.solvers.color.ColorSolver import ColorSolver, trace_bitmap
from vectorizing.solvers.color.quantize import quantize
from vectorizing.svg.markup import generate_SVG_markup
from vectorizing.tests.test_svg_geometry import expected_commands

IMAGES = Path(__file__).parent / "images"


def test_aftermath_matches_approved_p3_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep approved masks, validated native geometry variants, palette and size."""
    masks = []

    def capture_rims(bitmaps: list[np.ndarray]) -> None:
        add_bitmap_rims(bitmaps)
        masks.extend(bitmap.astype(np.uint8).tobytes() for bitmap in bitmaps)

    monkeypatch.setattr(
        "vectorizing.solvers.color.ColorSolver.add_bitmap_rims",
        capture_rims,
    )
    with Image.open(IMAGES / "aftermath.png") as image:
        paths, colors, width, height = ColorSolver(image, 8, Timer()).solve()
    # Ordered masks are identical across ARM64 and x86_64. Native Potrace makes
    # different curve-optimization decisions on those identical inputs. Both
    # geometry captures were checked for coverage and composited render error;
    # accept only those validated variants, not an arbitrary CI replacement.
    assert hashlib.sha256(b"".join(masks)).hexdigest() == (
        "e70cbf1c9d62e8ba853f6fa547975aac8311d9c44ac71decf14e9a6b2bf502bf"
    )
    commands = [expected_commands(path) for path in paths]
    digest = hashlib.sha256(
        json.dumps(commands, separators=(",", ":")).encode(),
    ).hexdigest()
    assert digest in {
        "23d8c97dee23ea3f0b22d164d39f726f36ead7f2ce47048ca73326bf2731c7e8",  # ARM64
        "1f52fe3d8589574cc561bf5ab0dff6a9ce410292d79b9e05dcf0a781f2d919f3",  # x86_64
    }
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


@pytest.mark.parametrize("raw", [False, True])
def test_clip_failure_retraces_bounded_vectors(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    raw: bool,
) -> None:
    """An exceptional clip failure still yields smooth vectors, holes and bounds."""
    pixels = np.full((20, 32, 4), 255, dtype=np.uint8)
    pixels[8:12, 14:18, 3] = 0
    monkeypatch.setattr(
        "vectorizing.try_read_image_from_url",
        lambda url: Image.fromarray(pixels),
    )
    clip = Mock(side_effect=PathOpsError("injected failure"))
    monkeypatch.setattr("vectorizing.solvers.color.ColorSolver.op", clip)
    upload = Mock(return_value="fallback-svg")
    monkeypatch.setattr("vectorizing.upload_markup", upload)
    response = client.post("/", json={"url": "unused", "solver": 1, "raw": raw})
    assert response.status_code == 200
    clip.assert_called_once()
    assert "retracing without padding" in caplog.text
    if raw:
        markup = response.data
        upload.assert_not_called()
    else:
        upload.assert_called_once()
        markup = upload.call_args.args[0]
        bounds = response.get_json()["info"]["bounds"]
        assert 0 <= bounds["left"] <= bounds["right"] <= 32
        assert 0 <= bounds["top"] <= bounds["bottom"] <= 20
    rendered = np.asarray(
        Image.open(BytesIO(svg2png(bytestring=markup))).convert("RGBA"),
    )
    assert rendered[10, 16, 3] == 0
    assert rendered[5, 5, 3] == 255


def test_clip_recovery_constrains_curve_overshoot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unpadded curve fitting can still extend beyond the bitmap's control hull."""
    rng = np.random.default_rng(6)
    height, width = rng.integers(1, 45, 2)
    mask = (rng.random((height, width)) < rng.uniform(0.03, 0.98)).astype(np.uint8)
    clip = Mock(side_effect=PathOpsError("injected failure"))
    monkeypatch.setattr("vectorizing.solvers.color.ColorSolver.op", clip)
    path = trace_bitmap(mask)
    clip.assert_called_once()
    for _, points in path:
        for x, y in points:
            assert 0 <= x <= width
            assert 0 <= y <= height


def test_clipped_logo_preserves_opaque_canvas() -> None:
    """Keep coverage on a real clipped logo, including the canvas boundary."""
    with Image.open(IMAGES / "geo_logo.png") as image:
        result = ColorSolver(image, 8, Timer()).solve()
    markup = generate_SVG_markup(*result)
    png = svg2png(bytestring=markup)
    pixels = np.asarray(Image.open(BytesIO(png)).convert("RGBA"))
    np.testing.assert_array_equal(pixels[:, :, 3], 255)


def test_clipped_consecutive_quadratics_keep_opaque_coverage() -> None:
    """Real clipping must not emit malformed Q commands that expose transparent gaps."""
    rng = np.random.default_rng(513)
    height, width = rng.integers(1, 45, 2)
    mask = rng.random((height, width)) < rng.uniform(0.03, 0.98)
    pixels = np.full((height, width, 3), 255, dtype=np.uint8)
    pixels[mask] = [255, 0, 0]
    result = ColorSolver(Image.fromarray(pixels), 2, Timer()).solve()
    rendered = np.asarray(
        Image.open(
            BytesIO(svg2png(bytestring=generate_SVG_markup(*result))),
        ).convert("RGBA"),
    )
    assert rendered[:, :, 3].min() >= 240


def test_fully_transparent_image_has_no_foreground() -> None:
    """Area cleanup must not invent opaque pixels in an entirely transparent input."""
    pixels = np.zeros((8, 8, 4), dtype=np.uint8)
    labels, palette, background = quantize(pixels, 16)
    assert background
    np.testing.assert_array_equal(labels, 0)
    assert palette.dtype == np.uint8
    result = ColorSolver(Image.fromarray(pixels), 16, Timer()).solve()
    assert result[0] == []
