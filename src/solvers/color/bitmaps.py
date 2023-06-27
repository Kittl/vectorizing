import numpy as np

def create_bitmaps(labels, colors, has_background):
    
    bitmaps = [
        np.where(labels == label, 1, 0).astype(np.uint32) 
        for label in range(len(colors))
    ]

    if has_background:
        bitmaps = bitmaps[1 : len(bitmaps)]
        colors = colors[1 : len(colors)]

    zipped = list(zip(bitmaps, colors))
    # Empty bitmaps should be ignored
    zipped = [[bitmap, color] for bitmap, color in zipped if np.sum(bitmap) > 0]

    bitmaps = [bitmap for bitmap, _ in zipped]
    colors = [color for _, color in zipped]

    # Layer bitmaps so that holes are not produced after tracing
    for x in range(len(bitmaps)):
        bitmap_x = bitmaps[x]
        for y in range(x + 1, len(bitmaps)):
            bitmap_x += bitmaps[y]
        bitmaps[x] = bitmap_x

    return bitmaps, colors