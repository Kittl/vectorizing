import numpy as np
import potrace
from types import SimpleNamespace

from solvers.color.resize import resize
from solvers.color.posterize import posterize, cluster
from solvers.color.bitmaps import create_bitmaps
from solvers.color.geometry.potrace import to_geo
from solvers.color.markup import create_markup
from solvers.color.filter import bilateral_filter
from solvers.color.geometry.misc import flatten_geo
from solvers.color.dither import dither

class ColorSolver:
    def _preprocess_image(self, img):
        return img

    def __init__(self, img, color_count = 6):
        # Set color count
        self.color_count = color_count

        # Init image array
        self.img = self._preprocess_image(img)
        self.img_array = np.asarray(self.img).astype(np.uint8)

        # Store some useful image information
        width, height = self.img.size
        self.img_info = SimpleNamespace(
            width = width,
            height = height,
            dims = (height, width),
            channel_count = len(self.img.getbands())
        )

    def solve(self):
        filtered_img_array = dither(self.img_array)
        filtered_img_array = bilateral_filter(filtered_img_array, self.img_info)
        labels, colors = cluster(filtered_img_array, self.img_info, self.color_count)
        posterized_before = colors[labels]
        labels, colors = posterize(filtered_img_array, self.img_info, self.color_count)
        posterized = colors[labels]
        bitmaps, colors = create_bitmaps(labels, colors)
        traced_bitmaps = [potrace.Bitmap(bitmap).trace() for bitmap in bitmaps]
        geo = [to_geo(traced) for traced in traced_bitmaps]
        flatten_geo(geo)
        markup = create_markup(geo, colors, self.img_info)
        return [markup, posterized, posterized_before]