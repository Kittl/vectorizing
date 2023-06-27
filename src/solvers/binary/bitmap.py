import cv2
import numpy as np

from solvers.binary.threshold import threshold

# Inverts an image
def invert(img_arr):
    channel_count = img_arr.shape[-1]

    if channel_count == 4:
        r, g, b, a = cv2.split(img_arr)
        r = 255 - r
        g = 255 - g
        b = 255 - b
        return cv2.merge((r, g, b, a))
    
    return 255 - img_arr

# Blends a transparent image with a white background by
# interpolating linearly. In the end, an RGBA image
# is turned into RGB
def alpha_blend(img_arr):
    r, g, b, a = cv2.split(img_arr)
    n_alpha = a / 255

    r = (255 * (1 - n_alpha) + r * n_alpha).astype(np.uint8)
    g = (255 * (1 - n_alpha) + g * n_alpha).astype(np.uint8)
    b = (255 * (1 - n_alpha) + b * n_alpha).astype(np.uint8)

    return cv2.merge((r, g, b)).astype(np.uint8)

# Creates bitmap to be traced by potrace
def make_bitmap(img_arr):
    shape = img_arr.shape
    channel_count = shape[-1]
    pixel_count = shape[0] * shape[1]
    inverted_arr = invert(img_arr)

    if channel_count == 4:
        img_arr = alpha_blend(img_arr)
        inverted_arr = alpha_blend(inverted_arr)
    
    img_arr = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)
    inverted_arr = cv2.cvtColor(inverted_arr, cv2.COLOR_RGB2GRAY)
    
    bitmap = threshold(img_arr)
    inverted_bitmap = threshold(inverted_arr)

    foreground_area = np.sum(bitmap)

    if foreground_area == 0:
        # If the non-inverted foreground has an area of zero, 
        # return a black rectangle
        # i.e Fully transparent image
        return np.ones(bitmap.shape)

    if (foreground_area / pixel_count) < 0.01:
        # If total area of the foreground is less than 1 percent of the image's,
        # prefer the inverted one
        return inverted_bitmap.astype(np.uint32)

    return bitmap.astype(np.uint32)