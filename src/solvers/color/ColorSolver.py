import potrace
import numpy as np

from util.limit_size import limit_size
from solvers.color.quantize import quantize
from solvers.color.clip import remove_layering
from solvers.color.bitmaps import create_bitmaps

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
        self.timer.start_timer('Quantization')
        labels, colors = quantize(self.img_arr, self.color_count)
        self.timer.end_timer()

        self.timer.start_timer('Bitmap Creation')
        bitmaps, colors = create_bitmaps(labels, colors)
        self.timer.end_timer()

        self.timer.start_timer('Bitmap Tracing')
        traced_bitmaps = [potrace.Bitmap(bitmap).trace() for bitmap in bitmaps]
        self.timer.end_timer()

        self.timer.start_timer('Polygon Clipping')
        compound_paths = remove_layering(traced_bitmaps)
        self.timer.end_timer()
        
        return [
            compound_paths,
            colors,
            self.img.size[0],
            self.img.size[1]
        ]
    
ColorSolver.MIN_COLOR_COUNT = 2
ColorSolver.DEFAULT_COLOR_COUNT = 6
ColorSolver.MAX_COLOR_COUNT = 64