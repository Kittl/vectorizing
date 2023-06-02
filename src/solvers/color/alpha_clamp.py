import numpy as np
from cv2 import split, merge
from sys import float_info

eps = float_info.epsilon

def clamp(rgba_img_array):
    r, g, b, a = split(rgba_img_array)
    a = np.where(a < eps, 0, 1)
    return merge((r, g, b, a))