"""Decode compact paths independently to verify exact two-decimal geometry."""

import re
from decimal import Decimal
from io import BytesIO

import numpy as np
import pytest
from cairosvg import svg2png
from defusedxml import ElementTree as ET
from pathops import Path
from PIL import Image

from vectorizing.svg.markup import generate_SVG_markup

SVG = "{http://www.w3.org/2000/svg}"


def decode_path(data: str) -> list[tuple[str, tuple[int, ...]]]:
    """Expand SVG's integer path grammar to absolute M/L/Q/C/Z commands."""
    tokens = re.findall(r"[A-Za-z]|-?\d+", data)
    result = []
    cursor = np.array([0, 0], dtype=np.int64)
    origin = cursor.copy()
    control = None
    command = ""
    i = 0
    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]
            i += 1
        kind = command.upper()
        if kind == "Z":
            result.append(("Z", ()))
            cursor = origin.copy()
            control = None
            command = ""
            continue
        count = {"M": 2, "L": 2, "H": 1, "V": 1, "Q": 4, "C": 6, "S": 4}[kind]
        values = np.array(tokens[i : i + count], dtype=np.int64)
        i += count
        if kind in ("H", "V"):
            axis = int(kind == "V")
            point = cursor.copy()
            point[axis] = values[0] + (cursor[axis] if command.islower() else 0)
            points = point.reshape(1, 2)
            kind = "L"
        else:
            points = values.reshape(-1, 2)
            if command.islower():
                points = points + cursor
            if kind == "S":
                reflected = cursor if control is None else 2 * cursor - control
                points = np.vstack([reflected, points])
                kind = "C"
        result.append((kind, tuple(int(n) for n in points.ravel())))
        cursor = points[-1].copy()
        control = points[-2].copy() if kind == "C" else None
        if kind == "M":
            origin = cursor.copy()
            command = "l" if command.islower() else "L"
    return result


def expected_commands(path: Path) -> list[tuple[str, tuple[int, ...]]]:
    """Use decimal arithmetic on the original segments, not encoder helpers."""
    expanded = []
    for kind, points in path.segments:
        if kind == "qCurveTo":
            # Independently expand the segment-pen's implied on-curve midpoints;
            # production uses raw PathVerb pairs instead of this interface.
            for index, control in enumerate(points[:-1]):
                endpoint = points[-1]
                if index < len(points) - 2:
                    endpoint = tuple(
                        (a + b) / 2 for a, b in zip(control, points[index + 1])
                    )
                expanded.append(("Q", (control, endpoint)))
        else:
            command = {
                "moveTo": "M",
                "lineTo": "L",
                "curveTo": "C",
                "closePath": "Z",
            }[kind]
            expanded.append((command, points))
    return [
        (
            command,
            tuple(int(Decimal(f"{n:.2f}") * 100) for point in points for n in point),
        )
        for command, points in expanded
    ]


@pytest.mark.parametrize("seed", range(30))
def test_random_compound_paths_round_trip(seed: int) -> None:
    """Preserve every point and closed subpath through mixed relative commands."""
    rng = np.random.default_rng(seed)
    path = Path()
    for _ in range(5):
        path.moveTo(*rng.uniform(-2000, 2000, 2))
        for index in range(20):
            if index % 3 == 1:
                path.cubicTo(*rng.uniform(-2000, 2000, 6))
            elif index % 3 == 2:
                path.quadTo(*rng.uniform(-2000, 2000, 4))
            else:
                path.lineTo(*rng.uniform(-2000, 2000, 2))
        path.close()
    root = ET.fromstring(generate_SVG_markup([path], [[12, 34, 56]], 1024, 900))
    assert root.attrib == {"width": "1024", "height": "900", "viewBox": "0 0 1024 900"}
    assert root.find(f"{SVG}g").get("transform") == "scale(.01)"
    assert decode_path(root.find(f".//{SVG}path").get("d")) == expected_commands(path)


def test_axes_reflections_and_close_reset() -> None:
    """Cover H/V/S, implicit repeats and relative moves after a closed subpath."""
    path = Path()
    path.moveTo(100, 100)
    path.lineTo(101, 100)
    path.lineTo(101, 102)
    path.cubicTo(101, 103, 102, 104, 103, 104)
    path.cubicTo(104, 104, 105, 103, 105, 102)
    path.cubicTo(105, 101, 104, 100, 103, 100)
    path.close()
    path.moveTo(101, 101)
    path.lineTo(101.25, 101.25)
    path.lineTo(102.25, 102.25)
    path.close()
    markup = generate_SVG_markup([path], [[0, 0, 0]], 200, 200)
    data = ET.fromstring(markup).find(f".//{SVG}path").get("d")
    assert all(command in data.lower() for command in "hvsmz")
    assert decode_path(data) == expected_commands(path)


def test_consecutive_quadratics_expand_implied_endpoints() -> None:
    """Skia's segment pen can combine two quadratics into three coordinate pairs."""
    path = Path()
    path.moveTo(1, 1)
    path.quadTo(2, 3, 4, 4)
    path.quadTo(6, 5, 7, 7)
    path.close()
    assert len(list(path.segments)[1][1]) == 3
    markup = generate_SVG_markup([path], [[0, 0, 0]], 10, 10)
    data = ET.fromstring(markup).find(f".//{SVG}path").get("d")
    assert decode_path(data) == [
        ("M", (100, 100)),
        ("Q", (200, 300, 400, 400)),
        ("Q", (600, 500, 700, 700)),
        ("Z", ()),
    ]


def test_rounding_near_half_ties_and_negative_zero() -> None:
    """Retain legacy decimal rounding instead of rounding multiplied binary floats."""
    path = Path()
    path.moveTo(-0.0, 2.675)
    path.cubicTo(-2.675, 1.005, 9.995, -0.005, 1000.125, 1.235)
    path.close()
    markup = generate_SVG_markup([path], [[255, 0, 0]], 1200, 1200)
    data = ET.fromstring(markup).find(f".//{SVG}path").get("d")
    assert decode_path(data) == expected_commands(path)
    assert 'fill="#f00"' in markup


@pytest.mark.parametrize("size", [40, 101, 160])
def test_compound_hole_rendering(size: int) -> None:
    """Keep holes, transparent exterior and half opacity after transformed encoding."""
    path = Path()
    path.moveTo(4, 4)
    path.lineTo(36, 4)
    path.lineTo(36, 36)
    path.lineTo(4, 36)
    path.close()
    # Opposite winding carves a hole in the same compound path.
    path.moveTo(12, 12)
    path.lineTo(12, 28)
    path.lineTo(28, 28)
    path.lineTo(28, 12)
    path.close()
    svg = generate_SVG_markup([path], [[20, 30, 40, 0.5]], 40, 40)
    pixels = np.asarray(
        Image.open(
            BytesIO(
                svg2png(
                    bytestring=svg,
                    output_width=size,
                    output_height=size,
                ),
            ),
        ).convert("RGBA"),
    )
    assert pixels[size // 2, size // 2, 3] == 0
    assert pixels[0, 0, 3] == 0
    assert pixels[size // 5, size // 5, 3] == 128
