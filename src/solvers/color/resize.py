import math
import numpy as np
from PIL import Image

MIN_PIXEL_COUNT = 64
MAX_PIXEL_COUNT = 1024 ** 2
MAX_COLOR_COUNT = 24

class ImageTooSmallError (Exception):
    def __init__ (self):
        super().__init__(self, 'Image is too small. It can\'t be vectorized.')

def resize_to_target(img, target_pixel_count):
    width = img.size[0]
    height = img.size[1]

    # We want to solve
    # width * height * k ** 2 = target_pixel_count ->
    k = math.sqrt(target_pixel_count / (width * height))
    target_width = round(k * width)
    target_height = round(k * height)
    return img.resize((target_width, target_height), resample = Image.Resampling.LANCZOS)

def resize(img):
    pixel_count = img.size[0] * img.size[1]

    if pixel_count < MIN_PIXEL_COUNT:
        raise ImageTooSmallError()
    
    if pixel_count > MAX_PIXEL_COUNT:
        return resize_to_target(img, MAX_PIXEL_COUNT)
    
    return img