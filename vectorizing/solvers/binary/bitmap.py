import cv2
import numpy as np


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


# Compute threshold
def threshold(img_arr):
    channel_count = img_arr.shape[-1]

    if channel_count == 4:
        img_arr = alpha_blend(img_arr)

    img_arr = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)
    thresholded = cv2.threshold(img_arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[
        1
    ].astype(np.uint8)

    # Dark is foreground
    return np.where(thresholded >= 128, 0, 1)


# Creates bitmap to be traced by potrace
# This deals with a very common edge case: when an image has a transparent
# background and a white foreground, the alpha blend strips all information, so in
# that case we choose the inverted version
def compute_bitmap(img_arr, foreground_area_threshold=0.01):
    # compute bitmap
    bitmap = threshold(img_arr)
    foreground_area = np.sum(bitmap)
    pixel_count = img_arr.shape[0] * img_arr.shape[1]

    # If the total area of the foreground is less than the defined threshold, check if
    # it's better to use the inverted bitmap instead
    chosen_image = bitmap
    if foreground_area / pixel_count < foreground_area_threshold:
        inverted_bitmap = threshold(invert(img_arr))
        inverted_foreground_area = np.sum(inverted_bitmap)

        if inverted_foreground_area > foreground_area:
            chosen_image = inverted_bitmap

    # If the chosen foreground has an area of zero, return a black rectangle
    # eg: if the input image was fully transparent
    chosen_area = np.sum(chosen_image)
    if chosen_area == 0:
        return np.ones(bitmap.shape)

    return chosen_image
