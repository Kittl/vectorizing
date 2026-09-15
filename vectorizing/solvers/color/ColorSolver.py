import numpy as np
import potrace

from vectorizing.geometry.potrace import potrace_path_to_compound_path
from vectorizing.solvers.color.bitmaps import create_bitmaps
from vectorizing.solvers.color.quantize import quantize
from vectorizing.util.limit_size import limit_size


class ColorSolver:
    def __init__(self, img, color_count, timer):
        color_count = color_count or ColorSolver.DEFAULT_COLOR_COUNT
        color_count = max(color_count, ColorSolver.MIN_COLOR_COUNT)
        color_count = min(color_count, ColorSolver.MAX_COLOR_COUNT)
        self.color_count = color_count

        self.img = limit_size(img)

        # Init image array
        self.img_arr = np.asarray(self.img).astype(np.uint8)

        self.timer = timer

    def solve(self):
        self.timer.start_timer("Quantization")
        labels, colors, has_background = quantize(self.img_arr, self.color_count)
        self.timer.end_timer()

        self.timer.start_timer("Bitmap Creation")
        bitmaps, colors = create_bitmaps(labels, colors, has_background)
        self.timer.end_timer()

        self.timer.start_timer("Bitmap Tracing")
        traced_bitmaps = [potrace.Bitmap(bitmap).trace() for bitmap in bitmaps]
        self.timer.end_timer()

        compound_paths = [
            potrace_path_to_compound_path(traced) for traced in traced_bitmaps
        ]

        return [compound_paths, colors, self.img.size[0], self.img.size[1]]


ColorSolver.MIN_COLOR_COUNT = 2
ColorSolver.DEFAULT_COLOR_COUNT = 6
ColorSolver.MAX_COLOR_COUNT = 64
