import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from sewar.full_ref import uqi

from vectorizing.server.env import get_optional
from vectorizing.util.read import try_read_image_from_path
from vectorizing.server.s3 import get_object_url, upload_file
from vectorizing.solvers.binary.bitmap import alpha_blend

(_, S3_TEST_BUCKET) = get_optional()

MAX_IMAGE_DIFFERENCE = 0.01
MIN_UQI_PIXEL_COUNT = 64

TESTS_FOLDER_PATH = Path(__file__).parent
TMP_FOLDER_PATH = TESTS_FOLDER_PATH / 'tmp'
IMAGES_FOLDER_PATH = TESTS_FOLDER_PATH / 'images'
RESULTS_FOLDER_PATH = TESTS_FOLDER_PATH / 'results'
DIFF_OUTPUT_FOLDER_PATH = TESTS_FOLDER_PATH / 'diff_output'

def get_image_url(img_name):
    """
    Gets an image URL. Uploads it to the S3 testing bucket,
    if not there already

    Parameters
    ----------
    img_name : string
        The name of the image. It is used as key for the upload.

    Returns
    -------
    str
        The URL of the image in the S3 bucket
    """

    object_url = get_object_url(img_name, S3_TEST_BUCKET)

    if object_url:
        return object_url
    
    return upload_file(IMAGES_FOLDER_PATH / img_name, S3_TEST_BUCKET, img_name)    

def get_markup(client, img_name, request_params):
    """
    Vectorizes an image and returns the SVG markup

    Parameters
    ----------
    client : Flask
        A flask test client
    img_name: string
        The name of the image
    request_params:
        Parameters for the vectorize request

    Returns
    -------
    str
        SVG markup
    """
    image_url = get_image_url(img_name)

    request_params = {
        'url': image_url,
        'solver': request_params.get('solver'),
        'color_count': request_params.get('color_count'),
        'raw': True
    }
    return client.post('/', json = request_params).data

def compute_img_difference(
    img,
    expected_img_path,
    small_image_test_factor = 0.1
):
    """
    Computes difference between two images using UQI

    Parameters
    ----------
    img : PIL.Image
        An image
    expected_img_path:
        A path to a baseline image to compare [img] with

    Both images are assumed to have the same size

    Returns
    -------
    float
        A number between 0 and 1.
        0 means equal
        1 means completely different
    """
    expected_img = try_read_image_from_path(expected_img_path)
    expected_img_arr = np.asarray(expected_img).astype(np.uint8)
    img_arr = np.asarray(img).astype(np.uint8)

    (height, width, _) = img_arr.shape
    px_count = width * height
    if px_count <= MIN_UQI_PIXEL_COUNT:
        # For very small images, uqi sometimes returns nan

        # We then use a simple metric for these cases, we also don't particularly care too
        # much about such small images

        diff = img_arr - expected_img_arr
        norm = np.linalg.norm(diff, axis = 2)

        # A cell has label 0 for equal pixels, 1 for differing
        diff_labels = np.where(norm > 0, 1, 0)

        # Amount of differing pixels
        diff_count = np.sum(diff_labels)

        if diff_count < small_image_test_factor * px_count:
            return 0
        return 1

    image_quality_index = uqi(
        img_arr,
        expected_img_arr,
    )

    return 1 - image_quality_index

def convert_to_RGBGray(img_arr):
    """
    Converts an image's colors to grayscale, and returns it
    in RGB format. This is useful because to write image diffs,
    we display the baseline image in gray to be able to have an
    always-contrasting highlight color.

    This highlight color shouldn't be a shade of gray though,
    so a luminance image is not enough. RGB is needed.

    Parameters
    ----------
    img_arr : np.array
        An image array

    Returns
    -------
    np.array
        The converted image
    """
    if img_arr.shape[-1] == 4:
        img_arr = alpha_blend(img_arr)
    img_arr = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)
    img_arr = cv2.cvtColor(img_arr, cv2.COLOR_GRAY2RGB)
    return img_arr

def write_img_difference(predicted_img, expected_img_path, output_name):
    """
    Writes difference between two images to /diff_output

    Parameters
    ----------
    predicted_img : PIL.Image
        The predicted image
    expected_img_path: string
        A path to the expected, or baseline, image
    output_name:
        The name of the file to be placed in diff_output
    """
    expected_img = try_read_image_from_path(expected_img_path)
    
    predicted_img_arr = np.asarray(predicted_img).astype(np.uint8)
    expected_img_arr = np.asarray(expected_img).astype(np.uint8)
    expected_img_rgbgray_arr = convert_to_RGBGray(expected_img_arr)

    # Difference between the two images
    diff = predicted_img_arr - expected_img_arr

    # Per-pixel distance between images
    diffnorm = np.linalg.norm(diff, axis = 2)

    # Maximum distance between any two (matching) pixels
    maxnorm = np.max(diffnorm)

    # Per-pixel distance between images (normalized between 0 and 1) 
    normalized_norm = diffnorm / maxnorm

    # We use the normalized distances to assign a highlight intensity to each pixel
    # Note that pixels that don't differ will have an intensity of zero,
    # and the most differing pixels, 255
    hightlights = (normalized_norm * 255)

    (r, g, b) = cv2.split(expected_img_rgbgray_arr)

    # Weighted addition of grayscale baseline image red channel, and highlights
    r = (1 - normalized_norm) * r + hightlights * normalized_norm
    r = r.astype(np.uint8)

    # Re-merge channels
    img_difference = cv2.merge((r, g, b))
    Image.fromarray(img_difference).save(DIFF_OUTPUT_FOLDER_PATH / output_name)