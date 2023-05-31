import cv2
import numpy as np
from PIL import Image
import scipy.ndimage as ndi
from skimage.measure import label

BILATERAL_FILTER_DIAMETER = 9
BILATERAL_FILTER_SIGMA = 75

# Applies a strong bilateral filter to the image.
# This greatly improves results for clip art.
# NOTE: photographs migh lose quite some detail due to this.
def bilateral_filter(
    img_arr, 
    d = BILATERAL_FILTER_DIAMETER, 
    s = BILATERAL_FILTER_SIGMA
):
    return cv2.bilateralFilter(img_arr, d, s, s)

# First erodes a matrix, then dilates it
def dilate(matrix):
    kernel = np.ones((2, 2))
    return cv2.dilate(matrix, kernel)

# Fills holes (defined as cells that are zero) in a matrix
# By using the closes value found in the matrix that is not zero.
# See: https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.distance_transform_edt.html
def fill_holes(matrix):
    closest = ndi.distance_transform_edt(
        np.logical_not(matrix), 
        return_distances = False, 
        return_indices = True
    )
    matrix = np.where(matrix != 0, matrix, matrix[closest[0], closest[1]])
    return matrix

def enhance(img_arr, labels, colors):    
    dims = img_arr.shape[:2]

    # 0 will be reserved for "unwritten" cells, or holes
    labels = labels + 1

    clusters = [
        # Even though we don't allow it, technically the max
        # value in labels (before adding 1) is 255, so it's safer
        # to convert to uint16 to avoid overflows
        np.where(labels == idx + 1, idx + 1, 0).astype(np.uint16) 
        for idx, _ in enumerate(colors)
    ]

    # For each cluster, store a matrix of its connected components
    # NOTE: see https://scikit-image.org/docs/stable/api/skimage.measure.html#skimage.measure.label
    original_connected_components_list = [
        label(cluster) + 1 
        for cluster in clusters
    ]

    # Bincounts for each connected components matrix
    # Meaning bincount[i] = num_appearances(matrix, i)
    # It's used later to determine what should be erased
    connected_components_bincounts = [
        np.bincount(connected_components.flatten())
        for connected_components in original_connected_components_list
    ]

    # Make a copy of the connected components
    # These will be modified and compared with the originals later
    connected_components_list = [
        np.array(item, copy = True) 
        for item in original_connected_components_list
    ]

    for x, cluster_x in enumerate(clusters):
        dilated_cluster_x = dilate(cluster_x)

        for y, cluster_y in enumerate(clusters):
            if x == y:
                continue

            # The overlap between dilated_cluster_x and cluster_y,
            # meaning, the part of cluster_y that dilated_cluster_x covers
            overlap = np.logical_and(dilated_cluster_x, cluster_y)

            # Remove overlap from connected components
            connected_components_list[y] = np.where(
                overlap,
                0,
                connected_components_list[y]
            )

    for x, connected_components in enumerate(connected_components_list):
        original_bincount = connected_components_bincounts[x]
        count = original_bincount.shape[0]
        
        new_bincount = np.bincount(
            connected_components.flatten(), 
            minlength = count # Force same length
        )

        areas_ratio = np.divide(
            new_bincount.astype(np.float32),
            original_bincount.astype(np.float32),
            out = np.ones((count, ), dtype = np.float32),
            where = original_bincount != 0
        )

        # Update cluster
        # Connected components that lost more than 0.9 of their original area
        # are completely removed, others are kept
        clusters[x] = np.where(
            areas_ratio[original_connected_components_list[x]] <= 0.1, 
            0, 
            clusters[x]
        )

    # Update labels with new cluster data
    labels = np.zeros(dims).astype(np.uint8)
    for cluster in clusters:
        labels = np.where(labels == 0, cluster, labels)

    # Fill holes
    labels = fill_holes(labels)
    return labels - 1, colors

# Try to get the cluster of pixels that represent a transparent background
# If there is no transparent background, return None
# This is needed because RGBA quantization is very volatile, and sometimes
# opaque colors get assigned to the same clusters as highly transparent ones.
# So we focus on the solid image + transparent background case for now.
def get_background_cluster(img_arr, t = 0.5):
    r, g, b, a = cv2.split(img_arr)
    
    has_transparent_background = np.any(a < t)
    if has_transparent_background:
        a = np.where(a / 255 < t, 1, 0)
        return np.reshape(a, img_arr.shape[:2])
    
    return None

# Write the background cluster on top of a matrix of clusters (labels)
# The background cluster has priority
def write_background_cluster(labels, bg_cluster):
    labels = labels + 1
    labels = np.where(bg_cluster > 0, 0, labels)
    return labels

def add_alpha_channel_to_colors(colors):
    return [[r, g, b, 1] for r, g, b in colors]

def add_background_color(colors, color):
    return np.array([color] + colors)

def quantize(img_arr, color_count):
    channel_count = img_arr.shape[2]
    
    img_arr_original = img_arr
    if channel_count == 4:
        img = Image.fromarray(img_arr)
        img = img.convert('RGB')
        img_arr = np.asarray(img)

    filtered_arr = bilateral_filter(img_arr)
    filtered_img = Image.fromarray(filtered_arr)

    quantized_img = filtered_img.quantize(
        color_count, 
        kmeans = 1,
        method = Image.Quantize.MEDIANCUT
    ).convert('RGB')
    
    quantized_arr = np.asarray(quantized_img)

    colors, labels = np.unique(
        np.reshape(quantized_arr, (-1, 3)),
        axis = 0,
        return_inverse = True
    )
    labels = np.reshape(labels, img_arr.shape[:2]).astype(np.uint16)

    if channel_count == 4:
        bg_cluster = get_background_cluster(img_arr_original)
        if bg_cluster is not None:
            labels = write_background_cluster(labels, bg_cluster)
            colors = add_alpha_channel_to_colors(colors)
            colors = add_background_color(colors, [0, 0, 0, 0])

    colors = colors.astype(np.uint8)
    labels, colors = enhance(filtered_arr, labels, colors)
    return labels, colors