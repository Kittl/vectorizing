"""Bound image area while preserving the source aspect ratio."""

import math

from PIL import Image

# Size restrictions for image
MIN_PIXEL_COUNT = 64
MAX_PIXEL_COUNT = 1024**2


def resize_to_target(img: Image.Image, target_pixel_count: int) -> Image.Image:
    """Resize with Lanczos to rounded dimensions near the requested pixel count."""
    width = img.size[0]
    height = img.size[1]

    # We want to solve
    # width * height * k ** 2 = target_pixel_count ->
    k = math.sqrt(target_pixel_count / (width * height))
    target_width = round(k * width)
    target_height = round(k * height)
    return img.resize((target_width, target_height), resample=Image.Resampling.LANCZOS)


def limit_size(img: Image.Image) -> Image.Image:
    """Resize images outside the area limits; otherwise return the original image."""
    pixel_count = img.size[0] * img.size[1]

    if pixel_count < MIN_PIXEL_COUNT:
        return resize_to_target(img, MIN_PIXEL_COUNT)

    if pixel_count > MAX_PIXEL_COUNT:
        return resize_to_target(img, MAX_PIXEL_COUNT)

    return img
