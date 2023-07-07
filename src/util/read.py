import math
import requests
import numpy as np
from PIL import Image
from io import BytesIO

MIN_PIXEL_COUNT = 64
MAX_PIXEL_COUNT = 1024 ** 2
SMALL_PIXEL_COUNT = 512 ** 2

class URLReadError (Exception):
    def __init__ (self):
        super().__init__(self, 'Failed to read image from provided URL.')

class PathReadError (Exception):
    def __init__ (self):
        super().__init__(self, 'Failed to read image from provided path.')

class ImageFormatError (Exception):
    def __init__(self):
        super().__init__(self, 'Image format not supported.')

def convert_RGB_A(img):
    if img.mode == 'RGB' or img.mode == 'RGBA':
        return img
    
    map = {
        '1': 'RGB',
        'L': 'RGB',
        'P': 'RGBA',
        'PA': 'RGBA',
    }

    if not img.mode in map:
        raise ImageFormatError()
    
    return img.convert(map.get(img.mode))

def try_read_image_from_path(path):
    try:
        img = Image.open(path)
    except:
        raise PathReadError()
    return convert_RGB_A(img)

def try_read_image_from_url(url):
    try:
        resp = requests.get(url)
        img = Image.open(BytesIO(resp.content))
    except:
        raise URLReadError()
    return convert_RGB_A(img)