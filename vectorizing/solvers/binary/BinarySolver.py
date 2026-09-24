"""Trace an image into a single black vector layer."""

import numpy as np
import potrace
from pathops import Path
from PIL import Image

from vectorizing.geometry.potrace import potrace_path_to_compound_path
from vectorizing.solvers.binary.bitmap import compute_bitmap
from vectorizing.util.limit_size import limit_size


class BinarySolver:
    """Resize, threshold and trace an RGB or RGBA image."""

    def __init__(self, img: Image.Image) -> None:
        self.img = limit_size(img)

        # Init image array
        self.img_arr = np.asarray(self.img).astype(np.uint8)

    def solve(self) -> tuple[list[Path], list[list[int]], int, int]:
        """Return the traced path, black RGBA color and processed image size."""
        width, height = self.img.size
        bitmap = compute_bitmap(self.img_arr)
        traced_bitmap = potrace.Bitmap(bitmap).trace()
        compound_path = potrace_path_to_compound_path(traced_bitmap)
        return ([compound_path], [[0, 0, 0, 1]], width, height)  # black
