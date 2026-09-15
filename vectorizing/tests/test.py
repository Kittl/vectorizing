import os
from io import BytesIO
from pathlib import Path

import numpy as np
from cairosvg import svg2png
from PIL import Image

from vectorizing.server.s3 import get_s3_client
from vectorizing.tests.config import TESTS
from vectorizing.tests.testutil import (
    MAX_IMAGE_DIFFERENCE,
    RESULTS_FOLDER_PATH,
    compute_img_difference,
    get_image_url,
    get_markup,
    write_img_difference,
)


def test(client):
    """
    Tests all images inside /images directory using the TESTS object
    in config.py
    """

    results_path = Path(RESULTS_FOLDER_PATH)

    # Create results folder if non-existent
    if not results_path.exists():
        results_path.mkdir()

    # Cache test results to allow all tests to run
    diffs = []

    for img_name, options_list in TESTS.items():
        for options in options_list:
            id = options.get("id")
            output_name = f"{id}.png"

            # Vectorized SVG markup
            markup = get_markup(client, img_name, options)

            # Rasterized SVG
            png = svg2png(bytestring=markup)
            img = Image.open(BytesIO(png))

            # Store result if it doesn't exist yet
            results_output_path = Path(RESULTS_FOLDER_PATH / output_name)
            if not results_output_path.exists():
                img.save(results_output_path)

            else:
                # Difference between result and expected result
                difference = compute_img_difference(
                    img,
                    RESULTS_FOLDER_PATH / output_name,
                )

                # Write image difference to diff_output
                if difference >= MAX_IMAGE_DIFFERENCE:
                    write_img_difference(
                        img,
                        RESULTS_FOLDER_PATH / output_name,
                        output_name,
                    )

                diffs.append(difference)

    assert all([diff <= MAX_IMAGE_DIFFERENCE for diff in diffs])


def test_uploads_markup_to_s3(client):
    response = client.post(
        "/",
        json={
            "url": get_image_url("black_rectangle.png"),
            "solver": 0,
            "raw": False,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    test_bucket = os.environ["S3_TEST_BUCKET"]
    s3 = get_s3_client()
    try:
        stored = s3.get_object(
            Bucket=test_bucket,
            Key=payload["objectId"],
        )
        assert stored["ContentType"] == "image/svg+xml"
        assert stored["Body"].read().startswith(b"<svg")
    finally:
        s3.delete_object(Bucket=test_bucket, Key=payload["objectId"])
