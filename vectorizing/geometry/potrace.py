"""Convert Potrace curves into paths suitable for SVG serialization."""

import potrace
from pathops import FillType, Path


def potrace_path_to_compound_path(potrace_path: potrace.Path) -> Path:
    """Convert Potrace curves to an even-odd path of lines and cubic Beziers."""
    compound_path = Path(fillType=FillType.EVEN_ODD)

    for potrace_curve in potrace_path:
        start_x, start_y = potrace_curve.start_point
        compound_path.moveTo(start_x, start_y)

        for segment in potrace_curve:
            end_x, end_y = segment.end_point

            if segment.is_corner:
                c_x, c_y = segment.c
                compound_path.lineTo(c_x, c_y)
                compound_path.lineTo(end_x, end_y)

            else:
                c1_x, c1_y = segment.c1
                c2_x, c2_y = segment.c2
                compound_path.cubicTo(c1_x, c1_y, c2_x, c2_y, end_x, end_y)

            start_x = end_x
            start_y = end_y

        compound_path.close()

    return compound_path
