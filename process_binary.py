import cv2
import numpy as np
import potrace
from read import read_image, is_single_channel, is_RGB, get_width, get_height

BLACK = [0, 0, 0, 1]
TRANSPARENT = [0, 0, 0, 0]

THRESHOLDING_METHODS = {
    'Simple': 0,
    'Adaptive': 1
}

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
        127,
        255,
        cv2.THRESH_BINARY_INV
    )[1].astype(np.uint8)

def make_bitmap (img, method):

    if not is_single_channel(img):
        conversion_method = cv2.COLOR_RGB2GRAY if is_RGB(img) else cv2.COLOR_RGBA2GRAY
        
        img_grayscale = cv2.cvtColor(
            img, 
            conversion_method
        )

    else:
        img_grayscale = img

    if method == THRESHOLDING_METHODS['Simple']:
        thresholded = threshold_simple(img_grayscale)

    else:
        thresholded = threshold_adaptive(img_grayscale)
    
    return np.where(thresholded < 128, 0, 1).astype(np.uint32)

def process (url, thresholding_method = THRESHOLDING_METHODS['Simple']):
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
