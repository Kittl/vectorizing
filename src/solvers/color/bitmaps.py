import numpy as np

def create_bitmaps(labels, colors):
    bitmaps = [np.where(labels == label, 1, 0).astype(np.uint32) for label in range(len(colors))]
    zipped = list(zip(bitmaps, colors))
    zipped = [[bitmap, color] for bitmap, color in zipped if np.sum(bitmap) > 0]
    bitmaps = [bitmap for bitmap, _ in zipped]
    colors = [color for _, color in zipped]
    return bitmaps, np.array(colors)