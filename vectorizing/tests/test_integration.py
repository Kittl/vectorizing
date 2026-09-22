"""HTTP/S3 integration, raster diagnostics and transparent SVG checks.

The persisted raster gallery is a tolerant smoke test and creates missing
baselines. Exact before/after output checks live in test_color_equivalence.py.
Layer editability and anti-aliased edges are covered by the color layer suites.
"""

import os
from io import BytesIO
from pathlib import Path

import pytest
from cairosvg import svg2png
from flask.testing import FlaskClient
from PIL import Image

from vectorizing.server.s3 import get_s3_client
from vectorizing.server.timer import Timer
from vectorizing.solvers.color.ColorSolver import ColorSolver
from vectorizing.svg.markup import generate_SVG_markup
from vectorizing.tests import testutil
from vectorizing.tests.config import TESTS
from vectorizing.tests.testutil import (
    MAX_IMAGE_DIFFERENCE,
    RESULTS_FOLDER_PATH,
    compute_img_difference,
    get_image_url,
    get_markup,
    write_img_difference,
)


def test(client: FlaskClient) -> None:
    """Render the configured gallery and compare or seed its local PNG baselines."""
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
            img = Image.open(BytesIO(png)).convert("RGB")

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


def test_write_img_difference_handles_rgba_baselines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normalize transparent baseline pixels before computing RGB differences."""
    baseline = tmp_path / "baseline.png"
    output = tmp_path / "difference.png"
    Image.new("RGBA", (2, 2), (0, 0, 0, 0)).save(baseline)
    monkeypatch.setattr(testutil, "DIFF_OUTPUT_FOLDER_PATH", tmp_path)

    testutil.write_img_difference(
        Image.new("RGB", (2, 2), (255, 255, 255)),
        baseline,
        output.name,
    )

    assert output.exists()


def test_color_solver_preserves_empty_transparent_image() -> None:
    """Keep every rendered pixel transparent for an empty input image."""
    image = Image.open(Path(__file__).parent / "images" / "empty.png")
    paths, colors, width, height = ColorSolver(image, 6, Timer()).solve()
    markup = generate_SVG_markup(paths, colors, width, height)
    rendered = Image.open(BytesIO(svg2png(bytestring=markup))).convert("RGBA")

    assert rendered.getchannel("A").getextrema() == (0, 0)


def test_uploads_markup_to_s3(client: FlaskClient) -> None:
    """Store the generated SVG with its media type and return the object's key."""
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
