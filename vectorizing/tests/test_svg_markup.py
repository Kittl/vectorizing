"""Freeze externally visible SVG formatting, including whitespace and alpha."""

from collections.abc import Sequence

import numpy as np
import pytest
from pathops import Path

from vectorizing.svg.markup import generate_SVG_markup, to_SVG_color_string, truncate


@pytest.mark.parametrize(
    "number, expected",
    [
        (0.0, "0.00"),
        (-0.0, "-0.00"),
        (1.234, "1.23"),
        (1.236, "1.24"),
        (2.675, "2.67"),
        (float("inf"), "inf"),
        (float("-inf"), "-inf"),
        (float("nan"), "nan"),
    ],
)
def test_coordinate_formatting(number: float, expected: str) -> None:
    """Retain Python's two-decimal formatting rather than truncating coordinates."""
    assert truncate(number) == expected


@pytest.mark.parametrize(
    "color, expected",
    [
        ([20, 30, 40], "rgb(20,30,40)"),
        ([20, 30, 40, 0.5], "rgba(20,30,40,0.5)"),
        ([20, 30, 40, 0], "rgba(20,30,40,0)"),
        (np.array([20, 30, 40, 0.5]), "rgba(20.0,30.0,40.0,0.5)"),
    ],
)
def test_color_formatting(color: Sequence[float] | np.ndarray, expected: str) -> None:
    """Preserve component representations without scaling alpha or adding spaces."""
    assert to_SVG_color_string(color) == expected


def test_svg_serialization_preserves_exact_markup() -> None:
    """Keep paint order, empty-path filtering, cubic syntax and document whitespace."""
    curve = Path()
    curve.moveTo(0, 0)
    curve.lineTo(10, 0)
    curve.cubicTo(10, 1, 9, 2, 0, 0)
    curve.close()
    overlay = Path()
    overlay.moveTo(1, 1)
    overlay.lineTo(2, 2)
    overlay.close()
    actual = generate_SVG_markup(
        [Path(), curve, overlay],
        [[255, 255, 255], [20, 30, 40], [50, 60, 70, 0.5]],
        40,
        20,
    )
    assert actual == (
        '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20" '
        'viewBox="0 0 40 20">\n'
        '<g>\n<path d="M 0.00 0.00 L 10.00 0.00 '
        'C10.00,1.00 9.00,2.00 0.00,0.00 Z" fill="rgb(20,30,40)" />\n'
        '<path d="M 1.00 1.00 L 2.00 2.00 Z" fill="rgba(50,60,70,0.5)" />\n'
        "</g>\n</svg>"
    )


def test_empty_svg_serialization() -> None:
    """Keep the empty document's dimensions and blank group unchanged."""
    assert generate_SVG_markup([], [], 8, 9) == (
        '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="9" '
        'viewBox="0 0 8 9">\n<g>\n\n</g>\n</svg>'
    )
