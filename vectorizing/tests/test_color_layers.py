"""Check editable layer geometry, not only the fully assembled picture."""

from io import BytesIO
from unittest.mock import Mock

import numpy as np
import pytest
from cairosvg import svg2png
from pathops import Path
from PIL import Image

from vectorizing.server.timer import Timer
from vectorizing.solvers.color.ColorSolver import ColorSolver
from vectorizing.svg.markup import generate_SVG_markup


def trace_layers(
    monkeypatch: pytest.MonkeyPatch,
    labels: np.ndarray,
    palette: np.ndarray,
    transparent: bool,
) -> tuple[list[Path], list[np.ndarray]]:
    """Exercise bitmap creation and tracing with known labels, bypassing clustering."""
    quantize = Mock(return_value=(labels, palette, transparent))
    monkeypatch.setattr("vectorizing.solvers.color.ColorSolver.quantize", quantize)
    paths, retained, _, _ = ColorSolver(
        Image.fromarray(palette[labels]),
        3,
        Timer(),
    ).solve()
    quantize.assert_called_once()
    return paths, retained


def nested_layers(
    monkeypatch: pytest.MonkeyPatch,
    transparent: bool,
) -> tuple[list[Path], list[np.ndarray]]:
    """Trace three known nested colors, optionally inside a transparent border."""
    labels = np.zeros((40, 40), dtype=np.uint8)
    colors = [[220, 40, 40, 255], [40, 180, 40, 255], [40, 40, 220, 255]]
    offset = int(transparent)
    if transparent:
        colors.insert(0, [0, 0, 0, 0])
        labels[4:36, 4:36] = 1
    labels[10:30, 10:30] = 1 + offset
    labels[16:24, 16:24] = 2 + offset
    return trace_layers(
        monkeypatch,
        labels,
        np.asarray(colors, dtype=np.uint8),
        transparent,
    )


def render_layers(
    paths: list[Path],
    colors: list[np.ndarray],
    size: int = 40,
) -> np.ndarray:
    """Render transparent RGBA pixels without a background hiding alpha defects."""
    markup = generate_SVG_markup(paths, colors, 40, 40)
    np.testing.assert_equal("stroke=" in markup, False)
    np.testing.assert_equal("crispEdges" in markup, False)
    png = svg2png(bytestring=markup, output_width=size, output_height=size)
    return np.asarray(Image.open(BytesIO(png)).convert("RGBA"))


@pytest.mark.parametrize("transparent", [False, True])
@pytest.mark.parametrize("layer", [0, 1, 2])
@pytest.mark.parametrize("operation", ["remove", "transparent", "half-opacity"])
def test_editing_a_layer_leaves_a_hole(
    monkeypatch: pytest.MonkeyPatch,
    transparent: bool,
    layer: int,
    operation: str,
) -> None:
    """Deleting or fading any color must not reveal a solid lower-color layer."""
    paths, colors = nested_layers(monkeypatch, transparent)
    samples = [(20, 7), (20, 12), (20, 20)]
    original = render_layers(paths, colors)
    for point in samples:
        np.testing.assert_equal(original[point][3], 255)
    if operation == "remove":
        del paths[layer]
        del colors[layer]
    else:
        colors[layer] = colors[layer].astype(float)
        # SVG rgba() uses alpha in [0, 1], unlike the quantizer's uint8 palette.
        colors[layer][3] = 0.5 if operation == "half-opacity" else 0
    edited = render_layers(paths, colors)
    np.testing.assert_equal(
        edited[samples[layer]][3],
        128 if operation == "half-opacity" else 0,
    )
    for index, point in enumerate(samples):
        if index != layer:
            np.testing.assert_array_equal(edited[point], original[point])
    if transparent:
        np.testing.assert_array_equal(edited[0, 0], [0, 0, 0, 0])


@pytest.mark.parametrize("transparent", [False, True])
@pytest.mark.parametrize("size", [40, 101, 160])
def test_rims_cover_shared_edges(
    monkeypatch: pytest.MonkeyPatch,
    transparent: bool,
    size: int,
) -> None:
    """Hide interior alpha seams at native, fractional and enlarged render scales."""
    paths, colors = nested_layers(monkeypatch, transparent)
    pixels = render_layers(paths, colors, size)
    inset = size // 5
    np.testing.assert_array_equal(pixels[inset:-inset, inset:-inset, 3], 255)


@pytest.mark.parametrize("transparent", [False, True])
@pytest.mark.parametrize("layer, edge", [(0, 10), (1, 16)])
def test_rims_are_narrow_and_only_under_later_colors(
    monkeypatch: pytest.MonkeyPatch,
    transparent: bool,
    layer: int,
    edge: int,
) -> None:
    """Allow a small lip, not full underpainting or a shifted visible edge."""
    paths, _ = nested_layers(monkeypatch, transparent)
    np.testing.assert_equal(paths[layer].contains((edge + 0.25, 20)), True)
    np.testing.assert_equal(paths[layer].contains((edge + 2.25, 20)), False)
    if layer == 1:
        np.testing.assert_equal(paths[layer].contains((9.75, 20)), False)
    for path in paths:
        np.testing.assert_equal(path.contains((-0.25, 20)), False)
        if transparent:
            np.testing.assert_equal(path.contains((3.75, 20)), False)


@pytest.mark.parametrize("size", [40, 101, 160])
def test_rims_cover_three_color_junctions(
    monkeypatch: pytest.MonkeyPatch,
    size: int,
) -> None:
    """Check a T junction, where more than two independently traced colors meet."""
    labels = np.zeros((40, 40), dtype=np.uint8)
    labels[:, 20:] = 1
    labels[20:, 20:] = 2
    palette = np.array([[220, 0, 0], [0, 180, 0], [0, 0, 220]], dtype=np.uint8)
    paths, colors = trace_layers(monkeypatch, labels, palette, False)
    np.testing.assert_array_equal(
        render_layers(paths, colors, size)[2:-2, 2:-2, 3],
        255,
    )


def test_rims_leave_transparent_holes_and_islands_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep background holes and gaps empty; do not leave ghosts of distant colors."""
    labels = np.zeros((40, 40), dtype=np.uint8)
    labels[2:18, 2:18] = 1
    labels[6:14, 6:14] = 0
    labels[24:36, 24:36] = 2
    palette = np.array(
        [[0, 0, 0, 0], [220, 0, 0, 255], [0, 0, 220, 255]],
        dtype=np.uint8,
    )
    paths, colors = trace_layers(monkeypatch, labels, palette, True)
    pixels = render_layers(paths, colors)
    np.testing.assert_array_equal(pixels[8:12, 8:12, 3], 0)
    np.testing.assert_array_equal(pixels[19:22, 19:22, 3], 0)
    # Removing the distant blue island must not leave even a red outline behind.
    removed = render_layers(paths[:1], colors[:1])
    np.testing.assert_array_equal(removed[22:38, 22:38, 3], 0)
