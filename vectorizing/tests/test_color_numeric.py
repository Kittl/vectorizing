"""Keep numeric palette slots available for visible colors on transparent images."""

from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
from cairosvg import svg2png
from PIL import Image

from vectorizing.server.timer import Timer
from vectorizing.solvers.color import legacy
from vectorizing.solvers.color.ColorSolver import ColorSolver
from vectorizing.solvers.color.quantize import (
    _recover_background_slots,
    _remove_background_color_bias,
    quantize,
)
from vectorizing.svg.markup import generate_original_SVG_markup, generate_SVG_markup


@pytest.mark.parametrize("configuration", ["current", "experimental"])
@pytest.mark.parametrize("hidden_rgb", [(0, 0, 0), (255, 255, 0)])
def test_numeric_transparent_canvas_does_not_take_a_color_slot(
    configuration: str,
    hidden_rgb: tuple[int, int, int],
) -> None:
    """Retain three visible colors regardless of RGB hidden beneath zero alpha."""
    pixels = np.zeros((128, 128, 4), dtype=np.uint8)
    pixels[:, :, :3] = hidden_rgb
    pixels[8:56, 8:56] = (255, 128, 128, 255)
    pixels[8:56, 72:120] = (128, 255, 128, 255)
    pixels[72:120, 8:56] = (128, 128, 255, 255)
    image = Image.fromarray(pixels)
    solver = ColorSolver(image, 3, Timer(), configuration)
    paths, colors, width, height = solver.solve()

    assert solver.color_count == len(paths) == len(colors) == 3
    actual = np.array(sorted(tuple(color[:3]) for color in colors))
    expected = np.array([(128, 128, 255), (128, 255, 128), (255, 128, 128)])
    np.testing.assert_allclose(actual, expected, atol=1)
    np.testing.assert_array_equal(np.asarray(image), pixels)

    serialize = (
        generate_original_SVG_markup
        if configuration == "current"
        else generate_SVG_markup
    )
    raster = Image.open(
        BytesIO(svg2png(bytestring=serialize(paths, colors, width, height).encode())),
    ).convert("RGBA")
    assert raster.getpixel((0, 0))[3] == 0
    assert raster.getpixel((32, 32))[3] == 255
    assert serialize(*solver.solve()) == serialize(paths, colors, width, height)
    np.testing.assert_array_equal(solver.img_arr, pixels)


@pytest.mark.parametrize("configuration", ["current", "experimental"])
def test_snail_numeric_three_preserves_navy(configuration: str) -> None:
    """Hidden black must not darken navy when all three palette slots survive."""
    with Image.open(Path(__file__).parent / "images" / "snail.png") as source:
        image = source.copy()
    pixels = np.asarray(image)
    assert np.count_nonzero(pixels[:, :, 3] == 0) == 43_742
    np.testing.assert_array_equal(pixels[pixels[:, :, 3] == 0, :3], 0)
    paths, colors, width, height = ColorSolver(image, 3, Timer(), configuration).solve()
    assert len(paths) == len(colors) == 3
    navy = min(colors, key=lambda color: int(np.sum(color[:3])))
    # This opaque pixel is well inside the snail, away from blended edges.
    expected = pixels[390, 180, :3]
    np.testing.assert_allclose(navy[:3], expected, atol=4)
    serialize = (
        generate_original_SVG_markup
        if configuration == "current"
        else generate_SVG_markup
    )
    raster = Image.open(
        BytesIO(svg2png(bytestring=serialize(paths, colors, width, height).encode())),
    ).convert("RGBA")
    np.testing.assert_allclose(raster.getpixel((180, 390))[:3], expected, atol=4)
    assert raster.getpixel((180, 390))[3] == 255
    assert raster.getpixel((0, 0))[3] == 0
    np.testing.assert_array_equal(np.asarray(image), pixels)


@pytest.mark.parametrize("configuration", ["current", "experimental"])
def test_numeric_color_count_does_not_become_automatic(configuration: str) -> None:
    """A two-color request stays at two even when three visible colors exist."""
    pixels = np.zeros((128, 128, 4), dtype=np.uint8)
    pixels[8:56, 8:56] = (255, 128, 128, 255)
    pixels[8:56, 72:120] = (128, 255, 128, 255)
    pixels[72:120, 8:56] = (128, 128, 255, 255)
    solver = ColorSolver(Image.fromarray(pixels), 2, Timer(), configuration)
    paths, colors, _, _ = solver.solve()
    assert solver.color_count == len(paths) == len(colors) == 2


@pytest.mark.parametrize("configuration", ["current", "experimental"])
def test_fully_transparent_numeric_image_stays_empty(configuration: str) -> None:
    """No visible representative means no artwork, rather than a binary fallback."""
    solver = ColorSolver(Image.new("RGBA", (8, 8)), 3, Timer(), configuration)
    paths, colors, _, _ = solver.solve()
    assert solver.color_count == 3
    assert paths == colors == []


@pytest.mark.parametrize("configuration", ["current", "experimental"])
def test_numeric_palette_keeps_clusters_shared_with_background(
    configuration: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not retry when all palette colors already have visible pixels."""
    pixels = np.zeros((128, 128, 4), dtype=np.uint8)
    pixels[8:56, 8:56] = (0, 0, 0, 255)
    pixels[8:56, 72:120] = (128, 255, 128, 255)
    pixels[72:120, 8:56] = (255, 128, 128, 255)
    estimator = Mock(side_effect=AssertionError("Full numeric palettes must not retry"))
    monkeypatch.setattr(
        "vectorizing.solvers.color.quantize.auto_color_count",
        estimator,
    )
    solver = ColorSolver(Image.fromarray(pixels), 3, Timer(), configuration)
    paths, colors, _, _ = solver.solve()
    assert len(paths) == len(colors) == 3
    estimator.assert_not_called()


@pytest.mark.parametrize("configuration", ["current", "experimental"])
@pytest.mark.parametrize("alpha", [0, 60, 127, 128, 255])
def test_numeric_color_correction_keeps_alpha_classification(
    configuration: str,
    alpha: int,
) -> None:
    """Color correction cannot move masks or reinterpret half-opacity visibility."""
    pixels = np.zeros((16, 16, 4), dtype=np.uint8)
    pixels[:8, :, 3] = alpha
    pixels[0, 0, 3] = 0
    pixels[8:12] = (32, 64, 96, 255)
    pixels[12:] = (240, 240, 240, 255)
    quantizer = legacy.quantize if configuration == "current" else quantize
    before_labels, before_colors, before_background = quantizer(pixels, 2)
    labels, colors, background = quantizer(pixels, 2, recover_background_slots=True)
    assert background is before_background is True
    np.testing.assert_array_equal(labels, before_labels)
    assert colors.shape == before_colors.shape
    assert colors.dtype == before_colors.dtype == np.uint8
    if alpha >= 128:
        # Non-masked black must still contribute to the shared visible color.
        assert np.sum(colors[1, :3]) < 120
    else:
        np.testing.assert_allclose(colors[1, :3], (32, 64, 96), atol=4)


@pytest.mark.parametrize("configuration", ["current", "experimental"])
def test_numeric_component_cleanup_does_not_trigger_recovery(
    configuration: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep original colors when cleanup, not transparency, removes a cluster."""
    pixels = np.zeros((128, 128, 4), dtype=np.uint8)
    pixels[:, :, :3] = (20, 40, 60)
    pixels[8:56, 8:56] = (20, 40, 60, 255)
    pixels[8:120, 72:120] = (250, 250, 250, 255)
    pixels[80, 20] = (255, 0, 0, 255)
    quantizer = legacy.quantize if configuration == "current" else quantize
    module = quantizer.__module__
    clustering = []
    original_kmeans = quantizer.__globals__["kmeans"]

    def capture_clusters(
        rgb: np.ndarray,
        centroids: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        labels, colors = original_kmeans(rgb, centroids)
        visible = labels.reshape(pixels.shape[:2])[pixels[:, :, 3] > 0]
        clustering.append(np.bincount(visible, minlength=len(colors)))
        return labels, colors

    monkeypatch.setattr(f"{module}.kmeans", capture_clusters)
    labels, palette, _ = quantizer(pixels, 3)
    assert (clustering[0] > 0).all()
    surviving = np.unique(labels[labels != 0])
    assert len(surviving) == 2
    clustering.clear()

    _, colors, _, _ = ColorSolver(
        Image.fromarray(pixels),
        3,
        Timer(),
        configuration,
    ).solve()
    assert len(clustering) == 1
    np.testing.assert_array_equal(colors, palette[surviving])


@pytest.mark.parametrize("visible_alpha", [0, 255])
def test_unused_palette_entry_does_not_trigger_recovery(
    visible_alpha: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unused centroid or an empty image is not a background-only color loss."""
    pixels = np.zeros((8, 8, 4), dtype=np.uint8)
    pixels[2:6, 2:6, 3] = visible_alpha
    background = (pixels[:, :, 3] == 0).astype(np.uint8)
    labels = np.zeros((8, 8), dtype=np.uint8)
    estimator = Mock(side_effect=AssertionError("No occupied slot was lost"))
    monkeypatch.setattr(
        "vectorizing.solvers.color.quantize.auto_color_count",
        estimator,
    )
    assert _recover_background_slots(pixels, labels, 2, background) is None
    estimator.assert_not_called()


@pytest.mark.parametrize("count", [2, 8, 64])
@pytest.mark.parametrize("seed", range(4))
def test_background_color_bias_matches_independent_reference(
    count: int,
    seed: int,
) -> None:
    """Match per-cluster means, including shared, unused and background-only slots."""
    rng = np.random.default_rng(seed)
    rgb = rng.integers(0, 256, (7, 9, 3), dtype=np.uint8)
    labels = rng.integers(0, count, (7, 9), dtype=np.uint16)
    colors = rng.integers(0, 256, (count, 3), dtype=np.uint8)
    background = (rng.random((7, 9)) < 0.4).astype(np.uint8)
    before_rgb, before_labels, before_colors = rgb.copy(), labels.copy(), colors.copy()
    expected = colors.copy()
    for index, color in enumerate(colors):
        cluster = labels == index
        all_pixels = rgb[cluster]
        visible = rgb[cluster & (background == 0)]
        if len(visible) and len(visible) < len(all_pixels):
            bias = visible.mean(axis=0) - all_pixels.mean(axis=0)
            expected[index] = np.clip(
                np.rint(color.astype(np.float64) + bias),
                0,
                255,
            ).astype(np.uint8)
    actual = _remove_background_color_bias(rgb, labels, colors, background)
    np.testing.assert_array_equal(actual, expected)
    assert actual.dtype == colors.dtype
    np.testing.assert_array_equal(rgb, before_rgb)
    np.testing.assert_array_equal(labels, before_labels)
    np.testing.assert_array_equal(colors, before_colors)


@pytest.mark.parametrize("background_value", [None, 0, 1])
def test_background_color_correction_without_shared_pixels_is_noop(
    background_value: int | None,
) -> None:
    """Do not alter palettes for opaque images, empty images or unused slots."""
    rgb = np.full((8, 8, 3), 80, dtype=np.uint8)
    labels = np.zeros((8, 8), dtype=np.uint8)
    colors = np.array([[79, 80, 79], [255, 255, 255]], dtype=np.uint8)
    background = (
        None
        if background_value is None
        else np.full((8, 8), background_value, dtype=np.uint8)
    )
    assert _remove_background_color_bias(rgb, labels, colors, background) is colors
