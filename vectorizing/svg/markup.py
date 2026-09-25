"""Serialize editable filled paths on an exact hundredth-pixel coordinate grid."""

from collections.abc import Iterable, Sequence

import numpy as np
from pathops import Path, PathVerb

Point = tuple[int, int]
Command = tuple[str, tuple[int, ...]]


def truncate(number: float) -> str:
    """Format a coordinate with two decimal places to limit SVG size."""
    return f"{number:.2f}"


def to_SVG_color_string(color: Sequence[float] | np.ndarray) -> str:
    """Format RGB or RGBA components without scaling or rounding their values."""
    func = "rgb" if len(color) == 3 else "rgba"
    return f"{func}({','.join(str(item) for item in color)})"


def _color_string(color: Sequence[float] | np.ndarray) -> str:
    """Use short hex for opaque integral RGB, preserving other color/alpha values."""
    opaque = len(color) == 3 or color[3] == 1
    integral = all(0 <= value <= 255 and value == int(value) for value in color[:3])
    if opaque and integral:
        rgb = "".join(f"{int(value):02x}" for value in color[:3])
        return "#" + (rgb[::2] if rgb[::2] == rgb[1::2] else rgb)
    return to_SVG_color_string(color)


def _point(point: tuple[float, float]) -> Point:
    """Keep decimal-format rounding, including half ties, before changing units."""
    # Multiplying a float by 100 and rounding can disagree with formatting it
    # first (e.g. 2.675). No additional precision is lost by the integer encoding.
    return tuple(int(truncate(value).replace(".", "")) for value in point)


def _variants(
    command: str,
    points: tuple[Point, ...],
    current: Point,
    control: Point | None,
) -> list[Command]:
    """Offer equivalent absolute, relative, axial and reflected cubic commands."""
    absolute = tuple(value for point in points for value in point)
    relative = tuple(value - current[i % 2] for i, value in enumerate(absolute))
    variants = [(command, absolute), (command.lower(), relative)]
    if command == "L":
        if points[0][1] == current[1]:
            variants.extend([("H", (absolute[0],)), ("h", (relative[0],))])
        if points[0][0] == current[0]:
            variants.extend([("V", (absolute[1],)), ("v", (relative[1],))])
    if command == "C" and control is not None:
        reflected = (2 * current[0] - control[0], 2 * current[1] - control[1])
        if points[0] == reflected:
            variants.extend([("S", absolute[2:]), ("s", relative[2:])])
    return variants


def _shortest(variants: list[Command], previous: str) -> tuple[str, str]:
    """Choose the shortest legal spelling, eliding repeated commands when allowed."""
    candidates = []
    for command, values in variants:
        numbers = " ".join(str(value) for value in values).replace(" -", "-")
        candidates.append((command + numbers, command))
        # Extra moveto pairs are lines, not new subpaths: never omit an M/m.
        implicit_line = (previous, command) in [("M", "L"), ("m", "l")]
        if command.upper() != "M" and (previous == command or implicit_line):
            separator = "" if numbers.startswith("-") else " "
            candidates.append((separator + numbers, command))
    return min(candidates, key=lambda candidate: len(candidate[0]))


def _path_data(path: Path, width: int, height: int) -> str:
    """Encode filled geometry without changing contour order or winding."""
    pieces = []
    current = start = (0, 0)
    control = None
    previous = ""
    # The segment-pen interface coalesces adjacent quadratics with implied
    # endpoints. Raw verbs expose each control/end pair required by SVG Q/q.
    for kind, coordinates in path:
        if kind == PathVerb.CLOSE:
            pieces.append("z")
            current = start
            control = None
            previous = "z"
            continue
        # Canvas clipping can reduce a cubic to a quadratic; retain those too.
        command = {
            PathVerb.MOVE: "M",
            PathVerb.LINE: "L",
            PathVerb.CUBIC: "C",
            PathVerb.QUAD: "Q",
        }[kind]
        points = tuple(_point(point) for point in coordinates)
        variants = _variants(command, points, current, control)
        x, y = points[-1]
        if x in (0, width * 100) or y in (0, height * 100):
            # Some renderers accumulate subpixel error in relative commands.
            # Anchor canvas boundaries explicitly (not H/V, which retain one
            # current coordinate) to keep opaque edge pixels fully covered.
            variants = variants[:1]
        text, previous = _shortest(variants, previous)
        pieces.append(text)
        current = points[-1]
        if command == "M":
            start = current
        control = points[1] if command == "C" else None
    return "".join(pieces)


def generate_SVG_markup(
    compound_paths: Iterable[Path],
    colors: Iterable[Sequence[float] | np.ndarray],
    width: int,
    height: int,
) -> str:
    """Emit compact vectors with unchanged viewport, paint order and alpha values.

    Integer coordinates with a 0.01 scale represent the same two-decimal geometry
    as absolute pixel coordinates. Relative commands and transforms can still
    cause small renderer-specific antialiasing differences; this is not a promise
    of pixel-identical rendering at every zoom level.

    Parameters
    ----------
    compound_paths : Iterable[Path]
        Line/quadratic/cubic compound paths in paint order.
    colors : Iterable[Sequence[float] | numpy.ndarray]
        Corresponding RGB or RGBA colors; alpha is not rescaled.
    width : int
        Viewport width in pixels.
    height : int
        Viewport height in pixels.

    Returns
    -------
    str
        SVG markup with real filled paths and no strokes.
    """
    paths_markup = []
    for path, color in zip(compound_paths, colors):
        data = _path_data(path, width, height)
        if data:
            paths_markup.append(f'<path d="{data}" fill="{_color_string(color)}"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        '<g transform="scale(.01)">' + "".join(paths_markup) + "</g></svg>"
    )
