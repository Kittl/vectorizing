import cv2
import numpy as np

def bilateral_filter(arr_img, img_info, d = 9, s = 50):
    channel_count = img_info.channel_count

    if channel_count == 4:
        r, g, b, a = cv2.split(arr_img)
        rgb = cv2.merge((r, g, b))
        filtered = cv2.bilateralFilter(rgb, d, s, s)
        filtered = cv2.cvtColor(filter, cv2.COLOR_RGB2RGBA)
        filtered[:, :, 3] = a
        return filtered
    
    return cv2.bilateralFilter(arr_img, d, s, s)

def sharpen(arr_img):
    kernel = np.array([[0,-1,0], [-1,5,-1], [0,-1,0]])
    return cv2.filter2D(arr_img, -1, kernel)