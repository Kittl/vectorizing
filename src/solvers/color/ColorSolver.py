import potrace
import numpy as np

from util.limit_size import limit_size
from solvers.color.quantize import quantize
from solvers.color.clip import remove_layering
from solvers.color.bitmaps import create_bitmaps

class ColorSolver:
    def __init__(self, img, color_count):
        color_count = color_count or ColorSolver.DEFAULT_COLOR_COUNT
        color_count = max(color_count, ColorSolver.MIN_COLOR_COUNT)
        color_count = min(color_count, ColorSolver.MAX_COLOR_COUNT)
        self.color_count = color_count

        self.img = limit_size(img)
        
        # Init image array
        self.img_arr = np.asarray(self.img).astype(np.uint8)

    def solve(self):
        labels, colors = quantize(self.img_arr, self.color_count)
        bitmaps, colors = create_bitmaps(labels, colors)
        traced_bitmaps = [potrace.Bitmap(bitmap).trace() for bitmap in bitmaps]
        compound_paths = remove_layering(traced_bitmaps)
        return [
            compound_paths,
            colors,
            self.img.size[0],
            self.img.size[1]
        ]
    
ColorSolver.MIN_COLOR_COUNT = 2
ColorSolver.DEFAULT_COLOR_COUNT = 6
ColorSolver.MAX_COLOR_COUNT = 64