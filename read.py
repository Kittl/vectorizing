from skimage import io
import numpy as np

CHANNEL_COUNT_ERROR = 'Image channel count not supported.'
READ_ERROR = 'Failed to read image from provided URL.'
SIZE_ERROR = 'Images with more than 1M pixels are not supported.'

class ReadError (Exception):
    def __init__ (self):
        Exception.__init__(self, READ_ERROR)

class ChannelCountError (Exception):
    def __init__ (self):
        Exception.__init__(self, CHANNEL_COUNT_ERROR)

class SizeError (Exception):
    def __init__ (self):
        Exception.__init__(self, SIZE_ERROR)

def error (message):
    return { 'error': message }

def get_shape (img):
    shape = img.shape
    height = shape[0]
    width = shape[1]
    channel_count = shape[2] if len(shape) > 2 else 1
    return (width, height, channel_count)

def get_width (img):
    return get_shape(img)[0]

def get_height (img):
    return get_shape(img)[1]

def get_channel_count (img):
    return get_shape(img)[2]

def check_channel_count (n):
    def check (img):
        return get_channel_count(img) == n

    return check

def is_single_channel (img):
    return check_channel_count(1)(img)

def is_RGB (img):
    return check_channel_count(3)(img)

def is_RGBA (img):
    return check_channel_count(4)(img)

def validate_channel_count (img):
    return is_single_channel(img) or is_RGB(img) or is_RGBA(img)

def get_pixel_count (img):
    width, height, _ = get_shape(img)
    return width * height

def validate_size(img):
    return get_pixel_count(img) <= 10 ** 6

def read_image (url):
    try:
        img = io.imread(url).astype(np.uint8)

    except:
        raise ReadError()

    if not validate_channel_count(img):
        raise ChannelCountError()
    
    if not validate_size(img):
        raise SizeError()

    return img
