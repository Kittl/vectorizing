import cv2
import numpy as np
import potrace
from read import read_image, is_single_channel, is_RGBA, get_width, get_height

# Aliases for colors
BLACK = [0, 0, 0, 1]

DEFAULTS = {
    'thresholding_method': 'SIMPLE'
}

""" 

Tracing with binary (black & white output)

Steps:

-   Thresholding: Images are converted to grayscale and thresholded with different strategies.
    Thresholded images are single channel, and binary in nature, even if pixel values are not ones or zeros.

-   Conversion to Bitmap: Thresholded images are converted to bitmaps where each pixel's value
    can be represented by a single bit (0 / 1), even if the channel's bit-depth is not 1

-   Tracing: The resulting bitmap is then traced using potrace

TODO: Research thresholding in general, and see if we can improve results. For now though,
the current implementation should be enough for our use cases

"""

def threshold_adaptive (img_grayscale, line_width = 5):
    return cv2.adaptiveThreshold(
        img_grayscale,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        line_width,
        2
    ).astype(np.uint8)

def threshold_simple (img_grayscale):
    return cv2.threshold(
        img_grayscale,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )[1].astype(np.uint8)

def make_bitmap (img, method):

    # Grayscale conversion
    if not is_single_channel(img):

        # If the image is in RGBA format, composite it on top of a white background
        # by combining linearly
        if is_RGBA(img):
            r, g, b, a = cv2.split(img)
            n_alpha = a / 255

            r = (255 * (1 - n_alpha) + r * n_alpha).astype(np.uint8)
            g = (255 * (1 - n_alpha) + g * n_alpha).astype(np.uint8)
            b = (255 * (1 - n_alpha) + b * n_alpha).astype(np.uint8)

            img = cv2.merge((r, g, b))
                    
        img_grayscale = cv2.cvtColor(
            img, 
            cv2.COLOR_RGB2GRAY
        )

    # If image is single channel, no conversion is needed
    else:
        img_grayscale = img

    if method == 'SIMPLE':
        thresholded = threshold_simple(img_grayscale)

    else:
        thresholded = threshold_adaptive(img_grayscale)
    
    
    return np.where(thresholded < 128, 0, 1).astype(np.uint32)

def process (url, thresholding_method = DEFAULTS['thresholding_method']):
    img = read_image(url)
    bitmap = make_bitmap(img, thresholding_method)
    width = get_width(img)
    height = get_height(img)
    return (
        [potrace.Bitmap(bitmap).trace()],
        [BLACK],
        width,
        height
    )
