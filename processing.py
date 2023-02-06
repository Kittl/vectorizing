import cv2
import numpy as np
import potrace
from skimage import io

def read_image (url):
    return io.imread(url)

def lowpass (img, sigma):
    return cv2.GaussianBlur(img, (0,0), sigma)

def highpass (img, sigma):
    return img - cv2.GaussianBlur(img, (0,0), sigma) + 127

def k_means_cluster (img, k):

    img_height, img_width, channel_count = img.shape

    # img is represented as a img_height x img_width x channel_count matrix
    # data needs to be formatted as (img_height * img_width) x channel_count matrix
    # i.e one column for each color channel

    data = np.float32(
        img.reshape(
            (-1, channel_count)
        )
    )

    # Termination criteria
    max_iterations = 5
    epsilon = 1.0 # Error threshold
    attempts = 1 # Number of times the whole procedure is run, best outcome is kept

    criteria = (
        # Terminate if either specified accuracy is reached, or after max_iterations
        cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 
        max_iterations,   
        epsilon,
    )

    _, labels, centers = cv2.kmeans(
        data,
        k,
        None,
        criteria,
        attempts,
        # Choose initial centers randomly
        cv2.KMEANS_PP_CENTERS
    )

    labels = np.reshape(labels, (img_height, img_width, 1))

    return {
        'dominant_colors': centers,
        'label_count': len(centers),
        'labels': labels
    }

def build_potrace_bitmaps (k_means_result):
    labels = k_means_result['labels']
    label_count = k_means_result['label_count']
    bitmaps = [np.where(labels == x, 1, 0) for x in range(label_count)]
    return [potrace.Bitmap(np.uint32(bitmap)) for bitmap in bitmaps]

def trace_bitmaps (potrace_bitmaps):
    return [bitmap.trace() for bitmap in potrace_bitmaps]

def process_color(img):
    k_means_result = k_means_cluster(img, 16)
    potrace_bitmaps = build_potrace_bitmaps(k_means_result)
    traced_bitmaps = trace_bitmaps(potrace_bitmaps)
    return [traced_bitmaps, k_means_result['dominant_colors']]

def process_black_white(img):
    img = highpass(img, 5)

    potrace_bitmap = potrace.Bitmap(np.uint32(bitmap))
    return [potrace_bitmap.trace()]


def process (path_or_url, color):
    img = read_image(path_or_url)
    img_height, img_width, _ = img.shape

    if (color):
        bitmaps, colors = process_color(img)

        return [
            bitmaps, 
            colors,
            img_height,
            img_width
        ]
    
    return [
        process_black_white(img), 
        [(0, 0, 0, 1), (255, 255, 255, 1)],
        img_height,
        img_width
    ]