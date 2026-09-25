"""Background deletion must preserve the visible artwork, not every color's rim."""

from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from cairosvg import svg2png
from defusedxml import ElementTree
from PIL import Image

from vectorizing.server.timer import Timer
from vectorizing.solvers.color.ColorSolver import ColorSolver
from vectorizing.svg.markup import generate_SVG_markup
from vectorizing.tests.test_color_layers import trace_layers


def edit_background(markup: str, opacity: float | None = None) -> bytes:
    """Delete or change the first color node in the emitted SVG itself."""
    document = ElementTree.fromstring(markup)
    container = document.find("{http://www.w3.org/2000/svg}g")
    assert container is not None
    background = list(container)[0]
    if opacity is None:
        container.remove(background)
    else:
        background.set("opacity", str(opacity))
    return ElementTree.tostring(document)


def raster(markup: str | bytes, scale: float = 1) -> Image.Image:
    """Render the SVG on a transparent surface at the requested scale."""
    return Image.open(BytesIO(svg2png(bytestring=markup, scale=scale))).convert("RGBA")


@pytest.fixture(scope="module", params=[3, 4, 6, 8, 16])
def customer_svg(request: pytest.FixtureRequest) -> tuple[str, tuple[int, ...]]:
    """Solve the customer image once per palette with real quantization and tracing."""
    filename = Path(__file__).parent / "images" / "midnight_strike.png"
    with Image.open(filename) as image:
        paths, colors, width, height = ColorSolver(
            image,
            request.param,
            Timer(),
        ).solve()
    # On this fixture the cream background is the last RGB-ordered color, not
    # the first foreground color. It must become the first emitted layer.
    background = tuple(int(value) for value in colors[0])
    assert background == max(tuple(int(value) for value in color) for color in colors)
    assert len(colors) <= request.param
    assert (width, height) == (1024, 1024)
    return generate_SVG_markup(paths, colors, width, height), (*background, 255)


@pytest.mark.parametrize("scale", [1, 2])
def test_customer_background_deletion_preserves_artwork(
    customer_svg: tuple[str, tuple[int, ...]],
    scale: int,
) -> None:
    """Preserve appearance on the same matte, with opaque assembly and no new seams."""
    markup, color = customer_svg
    full = raster(markup, scale)
    removed = raster(edit_background(markup), scale)
    zero = raster(edit_background(markup, 0), scale)
    assert np.asarray(full)[:, :, 3].min() >= 240
    np.testing.assert_array_equal(np.asarray(removed), np.asarray(zero))
    before = Image.new("RGBA", full.size, color)
    before.alpha_composite(full)
    after = Image.new("RGBA", full.size, color)
    after.alpha_composite(removed)
    # Source-over rounding is not pixel-exact. A large hidden foreground lip
    # produces differences of hundreds, not these few channel levels.
    difference = np.abs(np.asarray(before).astype(np.int16) - np.asarray(after))
    assert difference.max() <= 4
    assert "stroke=" not in markup
    assert 'shape-rendering="crispEdges"' not in markup


@pytest.mark.parametrize("scale", [1, 1.25, 2])
def test_thin_line_keeps_its_width_after_background_deletion(
    monkeypatch: pytest.MonkeyPatch,
    scale: float,
) -> None:
    """A six-pixel line stays six pixels wide rather than exposing a four-pixel lip."""
    labels = np.full((40, 40), 2, dtype=np.uint16)
    labels[5:35, 8:14] = 0
    labels[8:32, 22:36] = 1
    palette = np.array([[20, 80, 200], [230, 130, 20], [255, 255, 255]], np.uint8)
    paths, colors = trace_layers(monkeypatch, labels, palette, False)
    np.testing.assert_array_equal(colors, palette[[2, 0, 1]])
    markup = generate_SVG_markup(paths, colors, 40, 40)
    full = raster(markup, scale)
    removed = raster(edit_background(markup), scale)
    assert np.asarray(full)[:, :, 3].min() >= 240
    row = np.asarray(removed)[int(20 * scale), : int(20 * scale), 3]
    if scale == 1:
        assert np.flatnonzero(row > 128).tolist() == list(range(8, 14))
    expected = Image.new("RGBA", full.size, (255, 255, 255, 255))
    expected.alpha_composite(removed)
    difference = np.abs(np.asarray(full).astype(np.int16) - np.asarray(expected))
    assert difference.max() <= 4


def test_background_half_opacity_does_not_fade_foreground(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep a single editable background color and normal path-opacity behavior."""
    labels = np.full((40, 40), 2, dtype=np.uint16)
    labels[10:30, 10:30] = 0
    labels[15:25, 25:35] = 1
    palette = np.array([[20, 80, 200], [230, 130, 20], [255, 255, 255]], np.uint8)
    paths, colors = trace_layers(monkeypatch, labels, palette, False)
    markup = generate_SVG_markup(paths, colors, 40, 40)
    pixels = np.asarray(raster(edit_background(markup, 0.5)))
    assert pixels[2, 2, 3] == 128
    np.testing.assert_array_equal(pixels[20, 15], [20, 80, 200, 255])
    np.testing.assert_array_equal(pixels[20, 30], [230, 130, 20, 255])
