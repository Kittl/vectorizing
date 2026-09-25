"""Trace editable color layers with bounded overlap at shared edges."""

import logging

import numpy as np
import potrace
from pathops import Path, PathOp, PathOpsError, op
from PIL import Image

from vectorizing.geometry.potrace import potrace_path_to_compound_path
from vectorizing.server.timer import Timer
from vectorizing.solvers.color.bitmaps import add_bitmap_rims, create_bitmaps
from vectorizing.solvers.color.quantize import quantize
from vectorizing.util.limit_size import limit_size


def _trace_mask(bitmap: np.ndarray) -> Path:
    """Trace a mask with the same detail settings on normal and recovery paths."""
    traced = potrace.Bitmap(bitmap).trace(turdsize=0, opttolerance=0.5, alphamax=1)
    return potrace_path_to_compound_path(traced)


def trace_bitmap(bitmap: np.ndarray) -> Path:
    """Trace detail without speck removal, extending then clipping canvas edges."""
    height, width = bitmap.shape
    # Potrace rounds exposed mask corners. Extending edge labels moves that
    # rounding outside the viewport instead of leaving transparent canvas corners.
    mask = bitmap.astype(np.uint8)
    padded = np.pad(mask, 2, mode="edge")
    path = _trace_mask(padded).transform(1, 0, 0, 1, -2, -2)
    left, top, right, bottom = path.bounds
    if left < 0 or top < 0 or right > width or bottom > height:
        # Keep returned geometry/bounds inside the image, not just the SVG's
        # viewport. This also makes layer exports safe without the original clip.
        canvas = Path()
        canvas.moveTo(0, 0)
        canvas.lineTo(width, 0)
        canvas.lineTo(width, height)
        canvas.lineTo(0, height)
        canvas.close()
        try:
            path = op(path, canvas, PathOp.INTERSECTION)
        except PathOpsError:
            # Recovery keeps smooth, bounded vectors and does not repeat the
            # failing boolean operation. Unpadded tracing can round canvas
            # corners inward; only this exceptional layer loses edge coverage.
            logging.getLogger(__name__).warning(
                "Canvas clipping failed; retracing without padding",
                exc_info=True,
            )
            traced = _trace_mask(mask)
            path = Path(fillType=traced.fillType)
            pen = path.getPen()
            # Even unpadded fitted curves can overshoot the canvas. Constrain
            # their control hull on recovery, without another boolean operation.
            for command, points in traced.segments:
                bounded = tuple(
                    (min(width, max(0, x)), min(height, max(0, y))) for x, y in points
                )
                getattr(pen, command)(*bounded)
    return path


class ColorSolver:
    """Resize and quantize an image, then trace its ordered color layers."""

    def __init__(self, img: Image.Image, color_count: int | None, timer: Timer) -> None:
        color_count = color_count or ColorSolver.DEFAULT_COLOR_COUNT
        color_count = max(color_count, ColorSolver.MIN_COLOR_COUNT)
        color_count = min(color_count, ColorSolver.MAX_COLOR_COUNT)
        self.color_count = color_count

        self.img = limit_size(img)

        # Init image array
        self.img_arr = np.asarray(self.img).astype(np.uint8)

        self.timer = timer

    def solve(self) -> list[list[Path] | list[np.ndarray] | int]:
        """Return paths, colors, width and height as a list."""
        self.timer.start_timer("Quantization")
        labels, colors, has_background = quantize(self.img_arr, self.color_count)
        self.timer.end_timer()

        self.timer.start_timer("Bitmap Creation")
        bitmaps, colors = create_bitmaps(labels, colors, has_background)
        add_bitmap_rims(bitmaps)
        self.timer.end_timer()

        self.timer.start_timer("Bitmap Tracing")
        compound_paths = [trace_bitmap(bitmap) for bitmap in bitmaps]
        self.timer.end_timer()

        return [compound_paths, colors, self.img.size[0], self.img.size[1]]


ColorSolver.MIN_COLOR_COUNT = 2
ColorSolver.DEFAULT_COLOR_COUNT = 6
ColorSolver.MAX_COLOR_COUNT = 64
