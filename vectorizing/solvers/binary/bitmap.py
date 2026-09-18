"""Prepare foreground masks for monochrome tracing."""

import cv2
import numpy as np


def invert(img_arr: np.ndarray) -> np.ndarray:
    """Invert RGB channels while leaving any alpha channel unchanged."""
    channel_count = img_arr.shape[-1]

    if channel_count == 4:
        r, g, b, a = cv2.split(img_arr)
        r = 255 - r
        g = 255 - g
        b = 255 - b
        return cv2.merge((r, g, b, a))

    return 255 - img_arr


def alpha_blend(img_arr: np.ndarray) -> np.ndarray:
    """Composite uint8 RGBA pixels over white and return uint8 RGB pixels."""
    r, g, b, a = cv2.split(img_arr)
    n_alpha = a / 255

    r = (255 * (1 - n_alpha) + r * n_alpha).astype(np.uint8)
    g = (255 * (1 - n_alpha) + g * n_alpha).astype(np.uint8)
    b = (255 * (1 - n_alpha) + b * n_alpha).astype(np.uint8)

    return cv2.merge((r, g, b)).astype(np.uint8)


def threshold(img_arr: np.ndarray) -> np.ndarray:
    """Apply Otsu thresholding, marking dark pixels as foreground."""
    channel_count = img_arr.shape[-1]

    if channel_count == 4:
        img_arr = alpha_blend(img_arr)

    img_arr = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)
    thresholded = cv2.threshold(img_arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[
        1
    ].astype(np.uint8)

    # Dark is foreground
    return np.where(thresholded >= 128, 0, 1)


def compute_bitmap(
    img_arr: np.ndarray,
    foreground_area_threshold: float = 0.01,
) -> np.ndarray:
    """Select a foreground mask, falling back to a solid mask when it is empty."""
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
