def get_pixel_count(img):
    return img.shape[0] * img.shape[1]

def get_channel_count(img):
    return img.shape[2] if len(img.shape) == 3 else 1