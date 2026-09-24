"""Serialize traced paths without strokes or changes to their paint order."""

from collections.abc import Iterable, Sequence

import numpy as np
from pathops import Path


def truncate(number: float) -> str:
    """Format a coordinate with two decimal places to limit SVG size."""
    return f"{number:.2f}"


def to_SVG_color_string(color: Sequence[float] | np.ndarray) -> str:
    """Format RGB or RGBA components without scaling or rounding their values."""
    func = "rgb" if len(color) == 3 else "rgba"
    tuple = "".join(
        [
            f"{item}," if i != len(color) - 1 else f"{item}"
            for i, item in enumerate(color)
        ],
    )
    return f"{func}({tuple})"


def generate_SVG_markup(
    compound_paths: Iterable[Path],
    colors: Iterable[Sequence[float] | np.ndarray],
    width: int,
    height: int,
) -> str:
    """Serialize line/cubic paths in paint order, skipping empty geometry."""
    paths_markup = []

    for compound_path, color in zip(compound_paths, colors):
        segments = list(compound_path.segments)
        if not len(segments):
            continue

        d = ""
        for segment in segments:
            command = segment[0]
            if command == "moveTo":
                x = segment[1][0][0]
                y = segment[1][0][1]
                d += f"M {truncate(x)} {truncate(y)} "
            if command == "lineTo":
                x = segment[1][0][0]
                y = segment[1][0][1]
                d += f"L {truncate(x)} {truncate(y)} "
            if command == "curveTo":
                d += (
                    "C" + f"{truncate(segment[1][0][0])},{truncate(segment[1][0][1])} "
                    f"{truncate(segment[1][1][0])},{truncate(segment[1][1][1])} "
                    f"{truncate(segment[1][2][0])},{truncate(segment[1][2][1])} "
                )
            if command == "closePath":
                d += "Z"

        path_markup = f'<path d="{d}" fill="{to_SVG_color_string(color)}" />'
        paths_markup.append(path_markup)

    paths_markup = "\n".join(paths_markup)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        f"<g>\n{paths_markup}\n</g>\n"
        f"</svg>"
    )
