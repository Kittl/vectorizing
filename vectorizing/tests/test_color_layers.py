"""Tests for holes left by deleted or transparent color layers."""

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


def nested_layers(
    monkeypatch: pytest.MonkeyPatch,
    transparent: bool,
) -> tuple[list[Path], list[np.ndarray]]:
    """Trace three nested color regions with an optional transparent border."""
    labels = np.zeros((40, 40), dtype=np.uint8)
    colors = [[220, 40, 40, 255], [40, 180, 40, 255], [40, 40, 220, 255]]
    offset = int(transparent)
    if transparent:
        colors.insert(0, [0, 0, 0, 0])
        labels[4:36, 4:36] = 1
    labels[10:30, 10:30] = 1 + offset
    labels[16:24, 16:24] = 2 + offset
    palette = np.asarray(colors, dtype=np.uint8)
    quantize = Mock(return_value=(labels, palette, transparent))
    monkeypatch.setattr("vectorizing.solvers.color.ColorSolver.quantize", quantize)
    paths, retained, _, _ = ColorSolver(
        Image.fromarray(palette[labels]),
        3,
        Timer(),
    ).solve()
    quantize.assert_called_once()
    return paths, retained


def render_layers(paths: list[Path], colors: list[np.ndarray]) -> np.ndarray:
    """Render SVG paths as RGBA pixels."""
    markup = generate_SVG_markup(paths, colors, 40, 40)
    np.testing.assert_equal("stroke=" in markup, False)
    return np.asarray(Image.open(BytesIO(svg2png(bytestring=markup))).convert("RGBA"))


@pytest.mark.parametrize("transparent", [False, True])
@pytest.mark.parametrize("layer", [0, 1, 2])
@pytest.mark.parametrize("operation", ["remove", "transparent", "half-opacity"])
def test_editing_a_layer_leaves_a_hole(
    monkeypatch: pytest.MonkeyPatch,
    transparent: bool,
    layer: int,
    operation: str,
) -> None:
    """Verify layer edits expose transparency without changing other regions."""
    paths, colors = nested_layers(monkeypatch, transparent)
    # Sample region interiors, away from anti-aliased boundaries.
    samples = [(20, 7), (20, 12), (20, 20)]
    original = render_layers(paths, colors)
    for point in samples:
        np.testing.assert_equal(original[point][3], 255)

    if operation == "remove":
        del paths[layer]
        del colors[layer]
    else:
        colors[layer] = colors[layer].copy()
        # SVG rgba() uses alpha in [0, 1], unlike the quantizer's uint8 palette.
        colors[layer] = colors[layer].astype(float)
        colors[layer][3] = 0.5 if operation == "half-opacity" else 0
    edited = render_layers(paths, colors)
    expected_alpha = 128 if operation == "half-opacity" else 0
    np.testing.assert_equal(edited[samples[layer]][3], expected_alpha)
    for index, point in enumerate(samples):
        if index != layer:
            np.testing.assert_array_equal(edited[point], original[point])
    if transparent:
        np.testing.assert_array_equal(edited[0, 0], [0, 0, 0, 0])
