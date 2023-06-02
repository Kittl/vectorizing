import cv2
import potrace
import numpy as np
from skimage.measure import label
from scipy import ndimage as nd
from misc.kmeans import optimal_kmeans
from markup import build_markup
from solvers.preprocess_input import validate_input

MIN_PIXEL_COUNT = 64
MAX_PIXEL_COUNT = 1024 ** 2
MAX_COLOR_COUNT = 24    

def remove_edge_artifacts(img, mapping, color_centers):
    img_dims = img.shape[:2]

    # Mapping contains values in the range 0 <= v <= color_count - 1
    # We use mapping + 1 from now on since 0 will hold a special meaning
    mapping = np.reshape(mapping + 1, img_dims)
    
    # Here we convert our mapping into a list of mappings, one for each color
    # NOTE: from now on we refer to these mappings as "color mappings"
    color_mappings = [
        np.where(mapping == idx + 1, idx + 1, 0).astype(np.uint16) 
        for idx, _ in enumerate(color_centers)
    ]

    # Sort them in descending order based on area of mapping
    # i.e color mappings that assign a center/color to more pixels come first
    # i.e color mappings that represent a larger area in the image come first
    color_mappings.sort(key = lambda entry: np.sum(np.where(entry != 0, 1, 0)), reverse = True)

    # For each color mapping, store a labeling of its elements based on cell connectivity
    # NOTE: see https://scikit-image.org/docs/stable/api/skimage.measure.html#skimage.measure.label
    color_islands = list(map(lambda mapping: label(mapping) + 1, color_mappings))
    color_islands_without_overlap = list(map(lambda item: np.array(item, copy = True), color_islands))

    # A matrix where all individual color mappings will be dilated and stacked on top of each other
    dilated_compound = np.zeros(img_dims).astype(np.uint16)

    # A kernel used for dilation
    dilate_kernel = np.ones((3,3)).astype(np.uint16)

    for x in range(len(color_mappings)):
        # The current color mapping
        color_mapping = color_mappings[x]

        # Dilate it using our dilate kernel
        dilated_mapping = cv2.dilate(color_mapping, dilate_kernel).astype(np.uint16)

        # Where dilated_compound was still not written, write dilated_mapping, else keep what was there already
        # NOTE: due to how color mappings are sorted, it's not possible for a color mapping B to override color
        # mapping A if area(A) > area(B)
        dilated_compound = np.where(dilated_compound == 0, dilated_mapping, dilated_compound)

        for y in range(len(color_mappings)):
            if x == y:
                continue
            overlap = np.logical_and(dilated_mapping, color_mappings[y])
            color_islands_without_overlap[y] = np.where(overlap == True, 0, color_islands_without_overlap[y])

    for x in range(len(color_islands)):
        labeling = color_islands[x]
        labeling_without_overlap = color_islands_without_overlap[x]

        bincount = np.bincount(labeling.flatten())
        bincount_without_overlap = np.bincount(labeling_without_overlap.flatten(), minlength = len(bincount))
        remaining_area_percentages = np.divide(
            bincount_without_overlap.astype(np.float32),
            bincount.astype(np.float32),
            out = np.zeros_like(bincount_without_overlap, np.float32),
            where = bincount != 0
        )

        color_mappings[x] = np.where(remaining_area_percentages[labeling] <= 0.1, 0, color_mappings[x])

    mapping = np.zeros(img_dims).astype(np.uint8)
    for isolated_mapping in color_mappings:
        mapping = np.where(mapping == 0, isolated_mapping, mapping)

    closest = nd.distance_transform_edt(np.logical_not(mapping), return_distances = False, return_indices = True)
    mapping = np.where(mapping != 0, mapping, mapping[closest[0], closest[1]])

    return mapping - 1, color_centers

def prepare_bitmaps(labels, colors):
    bitmaps = []

    for x in range(len(colors)):
        # Bitmap of color {colors[x]}
        bitmap = np.where(labels == x, 1, 0).astype(np.uint32)
        for y in range(x + 1, len(colors)):
            # Bitmap of color {colors[y]}
            bitmap_y = np.where(labels == y, 1, 0).astype(np.uint32)
            bitmap += bitmap_y
        bitmaps.append(bitmap)

    return bitmaps, colors

def solve(img, options):
    img, options = validate_input(img, options)
    opt_k, labels, centers = optimal_kmeans(cv2.bilateralFilter(img, 13, 50, 50), options.get('color_count'))
    labels, centers = remove_edge_artifacts(img, labels, centers)
    bitmaps, centers = prepare_bitmaps(labels, centers)
    markup = build_markup(
        [potrace.Bitmap(bitmap).trace() for bitmap in bitmaps],
        centers,
        img.shape[1],
        img.shape[0]
    )
    return opt_k, markup