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

def handle_palette_mode(img):
    if img.mode == 'P' or img.mode == 'L':
        return img.convert(mode = 'RGB')
    if img.mode == 'PA':
        return img.convert(mode = 'RGBA')
    return img

def prepare(img):
    return handle_palette_mode(img)

def try_read_image_from_path(path):
    try:
        img = Image.open(path)
    except:
        raise PathReadError()
    return prepare(img)

def try_read_image_from_url(url):
    try:
        resp = requests.get(url)
        img = Image.open(BytesIO(resp.content))
    except:
        raise URLReadError()
    return prepare(img)