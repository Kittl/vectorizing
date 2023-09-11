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

TESTS_FOLDER_PATH = Path(__file__).parent
TMP_FOLDER_PATH = TESTS_FOLDER_PATH / 'tmp'
IMAGES_FOLDER_PATH = TESTS_FOLDER_PATH / 'images'
RESULTS_FOLDER_PATH = TESTS_FOLDER_PATH / 'results'
DIFF_OUTPUT_FOLDER_PAATH = TESTS_FOLDER_PATH / 'diff_output'

def get_image_url(img_name):
    object_url = get_object_url(img_name, S3_TEST_BUCKET)

    if object_url:
        return object_url
    
    return upload_file(IMAGES_FOLDER_PATH / img_name, S3_TEST_BUCKET, img_name)    

def get_markup(client, image_name, request_params):
    image_url = get_image_url(image_name)

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
):
    expected_img = try_read_image_from_path(expected_img_path)

    image_quality_index = uqi(
        np.asarray(img).astype(np.uint8),
        np.asarray(expected_img).astype(np.uint8),
    )

    return 1 - image_quality_index

def convert_to_RGBGray(img_arr):
    if img_arr.shape[-1] == 4:
        img_arr = alpha_blend(img_arr)
    img_arr = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)
    img_arr = cv2.cvtColor(img_arr, cv2.COLOR_GRAY2RGB)
    return img_arr

def write_img_difference(predicted_img, expected_img_path, output_name):
    expected_img = try_read_image_from_path(expected_img_path)
    
    predicted_img_arr = np.asarray(predicted_img).astype(np.uint8)
    expected_img_arr = np.asarray(expected_img).astype(np.uint8)
    expected_img_rgbgray_arr = convert_to_RGBGray(expected_img_arr)

    diff = predicted_img_arr - expected_img_arr
    diffnorm = np.linalg.norm(diff, axis = 2)
    maxnorm = np.max(diffnorm)

    normalized_norm = diffnorm / maxnorm
    red_values = (normalized_norm * 255)
    (r, g, b) = cv2.split(expected_img_rgbgray_arr)

    r = (1 - normalized_norm) * r + red_values * normalized_norm
    r = r.astype(np.uint8)

    img_difference = cv2.merge((r, g, b))
    Image.fromarray(img_difference).save(DIFF_OUTPUT_FOLDER_PAATH / output_name)