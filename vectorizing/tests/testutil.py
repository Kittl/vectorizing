"""Support the image gallery with S3 fixtures and RGB difference images."""

from pathlib import Path

import cv2
import numpy as np
from flask.testing import FlaskClient
from PIL import Image
from sewar.full_ref import uqi

from vectorizing.server.env import get_optional
from vectorizing.server.s3 import get_object_url, upload_file
from vectorizing.solvers.binary.bitmap import alpha_blend
from vectorizing.util.read import try_read_image_from_path

(_, S3_TEST_BUCKET) = get_optional()

MAX_IMAGE_DIFFERENCE = 0.01
MIN_UQI_PIXEL_COUNT = 64

TESTS_FOLDER_PATH = Path(__file__).parent
TMP_FOLDER_PATH = TESTS_FOLDER_PATH / "tmp"
IMAGES_FOLDER_PATH = TESTS_FOLDER_PATH / "images"
RESULTS_FOLDER_PATH = TESTS_FOLDER_PATH / "results"
DIFF_OUTPUT_FOLDER_PATH = TESTS_FOLDER_PATH / "diff_output"


def get_image_url(img_name: str) -> str | None:
    """Return a fixture's S3 URL, uploading the fixture if it is not present."""
    object_url = get_object_url(img_name, S3_TEST_BUCKET)

    if object_url:
        return object_url

    return upload_file(IMAGES_FOLDER_PATH / img_name, S3_TEST_BUCKET, img_name)


def get_markup(
    client: FlaskClient,
    img_name: str,
    request_params: dict[str, object],
) -> bytes:
    """Vectorize an S3 fixture through the HTTP API and return raw response bytes."""
    image_url = get_image_url(img_name)

    request_params = {
        "url": image_url,
        "solver": request_params.get("solver"),
        "color_count": request_params.get("color_count"),
        "raw": True,
    }
    return client.post("/", json=request_params).data


def compute_img_difference(
    img: Image.Image,
    expected_img_path: Path,
    small_image_test_factor: float = 0.1,
) -> float:
    """Compare equal-sized RGB images with UQI or a small-image pixel threshold."""
    expected_img = try_read_image_from_path(expected_img_path).convert("RGB")
    expected_img_arr = np.asarray(expected_img).astype(np.uint8)
    img_arr = np.asarray(img.convert("RGB")).astype(np.uint8)

    (height, width, _) = img_arr.shape
    px_count = width * height
    if px_count <= MIN_UQI_PIXEL_COUNT:
        # For very small images, uqi sometimes returns nan

        # Use a pixel-count threshold instead of UQI for these small images.

        diff = img_arr - expected_img_arr
        norm = np.linalg.norm(diff, axis=2)

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


def convert_to_RGBGray(img_arr: np.ndarray) -> np.ndarray:
    """Return RGB grayscale pixels, compositing RGBA inputs over white."""
    if img_arr.shape[-1] == 4:
        img_arr = alpha_blend(img_arr)
    img_arr = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)
    img_arr = cv2.cvtColor(img_arr, cv2.COLOR_GRAY2RGB)
    return img_arr


def write_img_difference(
    predicted_img: Image.Image,
    expected_img_path: Path,
    output_name: str,
) -> None:
    """Write a grayscale baseline with red highlights proportional to pixel error."""
    expected_img = try_read_image_from_path(expected_img_path).convert("RGB")

    predicted_img_arr = np.asarray(predicted_img.convert("RGB")).astype(np.uint8)
    expected_img_arr = np.asarray(expected_img).astype(np.uint8)
    expected_img_rgbgray_arr = convert_to_RGBGray(expected_img_arr)

    # Difference between the two images
    diff = predicted_img_arr - expected_img_arr

    # Per-pixel distance between images
    diffnorm = np.linalg.norm(diff, axis=2)

    # Maximum distance between any two (matching) pixels
    maxnorm = np.max(diffnorm)

    # Per-pixel distance between images (normalized between 0 and 1)
    normalized_norm = diffnorm / maxnorm

    # We use the normalized distances to assign a highlight intensity to each pixel
    # Note that pixels that don't differ will have an intensity of zero,
    # and the most differing pixels, 255
    hightlights = normalized_norm * 255

    (r, g, b) = cv2.split(expected_img_rgbgray_arr)

    # Weighted addition of grayscale baseline image red channel, and highlights
    r = (1 - normalized_norm) * r + hightlights * normalized_norm
    r = r.astype(np.uint8)

    # Re-merge channels
    img_difference = cv2.merge((r, g, b))
    Image.fromarray(img_difference).save(DIFF_OUTPUT_FOLDER_PATH / output_name)
