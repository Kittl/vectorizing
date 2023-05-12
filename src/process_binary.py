import cv2
import numpy as np
import potrace
from read import read_image, is_single_channel, is_RGBA, get_width, get_height, get_pixel_count
from PIL import Image

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
        cv2.THRESH_BINARY,
        line_width,
        2
    ).astype(np.uint8)

def threshold_simple (img_grayscale):
    return cv2.threshold(
        img_grayscale,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )[1].astype(np.uint8)

def threshold (img_grayscale, method):
    if method == 'SIMPLE':
        return threshold_simple(img_grayscale)
    
    return threshold_adaptive(img_grayscale)

def rgba_on_white (img):
    r, g, b, a = cv2.split(img)
    n_alpha = a / 255

    r = (255 * (1 - n_alpha) + r * n_alpha).astype(np.uint8)
    g = (255 * (1 - n_alpha) + g * n_alpha).astype(np.uint8)
    b = (255 * (1 - n_alpha) + b * n_alpha).astype(np.uint8)

    return cv2.merge((r, g, b))

def invert (img):
    if is_RGBA(img):
        r, g, b, a = cv2.split(img)
        r = 255 - r
        g = 255 - g
        b = 255 - b
        return cv2.merge((r, g, b, a))
    
    return 255 - img

def make_bitmap (img, method):
    inverted = invert(img)

    if not is_single_channel(img):
        
        if is_RGBA(img):
            img = rgba_on_white(img)
            inverted = rgba_on_white(inverted)
                    
        # Grayscale conversion
        grayscale = cv2.cvtColor(
            img, 
            cv2.COLOR_RGB2GRAY
        )

        inverted_grayscale = cv2.cvtColor(
            inverted,
            cv2.COLOR_RGB2GRAY
        )

        candidates = [grayscale, inverted_grayscale]
    
    else:
        candidates = [img, inverted]

    candidates = [threshold(img, method) for img in candidates]

    bitmap, inverted_bitmap = [
        np.where(candidate == 255, 0, 1).astype(np.uint32) 
        for candidate in candidates
    ]

    pixel_count = get_pixel_count(img)
    foreground_area = np.sum(bitmap)
    inverted_foreground_area = np.sum(inverted_bitmap)

    if (foreground_area / pixel_count) < 0.01:
        # If total area of the foreground is less than 1 percent of the image's

        # It's possible that the inverted image produced a better bitmap.
        # The main relevant case is an all-or-mostly white foreground with a transparent background.

        #NOTE: The inverted bitmap CAN be worse than the non-inverted one.
        # e.g A very small amount of black pixels on a transparent background

        if inverted_foreground_area > foreground_area:
            # Then we say the inverted bitmap is better. And its area is at least 1.
            return inverted_bitmap

    if foreground_area != 0:
        # If the non-inverted foreground has an area greater than zero
        # there are two possibilities:
        # 1. It's less than 1% of the image's, but no alternative was found
        # 2. It's more than 1% of the image's

        # In both cases we are happy returning bitmap
        return bitmap
    
    # If the non-inverted foreground has an area of zero
    # And no alternative was found, just return a black rectangle
    # e.g Fully transparent image
    return np.ones(bitmap.shape)

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
