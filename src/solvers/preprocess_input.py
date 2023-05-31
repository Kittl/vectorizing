import math
import numpy as np
from PIL import Image

MIN_PIXEL_COUNT = 64
MAX_PIXEL_COUNT = 1024 ** 2
MAX_COLOR_COUNT = 24

class ImageTooSmallError (Exception):
    def __init__ (self):
        super().__init__(self, 'Image is too small. It can\'t be vectorized')

class TooManyColorsError (Exception):
    def __init__ (self):
        super().__init__(self, f'Maximum number of colors exceeded ({MAX_COLOR_COUNT})')

def resize(img, target_pixel_count):
    width = img.size[0]
    height = img.size[1]

    # We want to solve
    # width * height * k ** 2 = target_pixel_count ->
    k = math.sqrt(target_pixel_count / (width * height))
    target_width = round(k * width)
    target_height = round(k * height)
    return img.resize((target_width, target_height), resample = Image.Resampling.LANCZOS)

def handle_size(img):
    pixel_count = img.size[0] * img.size[1]

    if pixel_count < MIN_PIXEL_COUNT:
        raise ImageTooSmallError()
    
    if pixel_count > MAX_PIXEL_COUNT:
        return resize(img, MAX_PIXEL_COUNT)
    
    return img

def perpare_image(img):
    resized = handle_size(img)
    return np.asarray(resized).astype(np.uint8)

def validate_options(options):
    color_count = options.get('color_count', None)
    if (color_count is None) or color_count > MAX_COLOR_COUNT:
        raise TooManyColorsError() 
    return options


def validate_input(img, options):
    return perpare_image(img), validate_options(options)