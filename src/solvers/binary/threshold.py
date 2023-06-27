import cv2
import numpy as np

def threshold (img_grayscale_arr):
    thresholded = cv2.threshold(
        img_grayscale_arr,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )[1].astype(np.uint8)

    # Dark is foreground
    return np.where(thresholded >= 128, 0, 1)