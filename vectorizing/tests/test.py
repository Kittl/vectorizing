import os
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from cairosvg import svg2png
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


def test_write_img_difference_handles_rgba_baselines(tmp_path, monkeypatch):
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


def test_color_solver_renders_shared_edges_opaque():
    image = Image.new("RGB", (10, 10), (40, 81, 180))
    for x in range(2, 8):
        for y in range(2, 8):
            image.putpixel((x, y), (26, 54, 127))

    paths, colors, width, height = ColorSolver(image, 2, Timer()).solve()
    markup = generate_SVG_markup(paths, colors, width, height)
    rendered = Image.open(
        BytesIO(svg2png(bytestring=markup, output_width=101, output_height=101)),
    ).convert("RGBA")

    assert "stroke=" not in markup
    assert rendered.getpixel((20, 50))[3] == 255


def test_color_solver_renders_transparent_shared_edges_opaque():
    image = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    for x in range(1, 9):
        for y in range(1, 9):
            image.putpixel((x, y), (40, 81, 180, 255))
    for x in range(2, 8):
        for y in range(2, 8):
            image.putpixel((x, y), (26, 54, 127, 255))

    paths, colors, width, height = ColorSolver(image, 2, Timer()).solve()
    markup = generate_SVG_markup(paths, colors, width, height)
    rendered = Image.open(
        BytesIO(svg2png(bytestring=markup, output_width=101, output_height=101)),
    ).convert("RGBA")

    assert "stroke=" not in markup
    assert rendered.getpixel((0, 0))[3] == 0
    assert rendered.getpixel((20, 50))[3] == 255


@pytest.mark.parametrize(
    "image_name, color_count",
    [("bubbles.png", 5), ("shapes_2.png", 7)],
)
def test_color_solver_renders_real_multicolor_edges_opaque(image_name, color_count):
    image = Image.open(Path(__file__).parent / "images" / image_name)
    paths, colors, width, height = ColorSolver(image, color_count, Timer()).solve()
    markup = generate_SVG_markup(paths, colors, width, height)
    rendered = Image.open(BytesIO(svg2png(bytestring=markup))).convert("RGBA")

    assert "stroke=" not in markup
    assert rendered.getchannel("A").getextrema() == (255, 255)


def test_color_solver_avoids_transparent_inner_seams_in_aftermath():
    image = Image.open(Path(__file__).parent / "images" / "aftermath.png")
    paths, colors, width, height = ColorSolver(image, 16, Timer()).solve()
    markup = generate_SVG_markup(paths, colors, width, height)
    rendered = Image.open(BytesIO(svg2png(bytestring=markup))).convert("RGBA")
    alpha = list(rendered.getchannel("A").getdata())

    assert min(alpha) == 0
    assert max(alpha) == 255
    assert sum(0 < value < 255 for value in alpha) < 10_000


def test_color_solver_preserves_empty_transparent_image():
    image = Image.open(Path(__file__).parent / "images" / "empty.png")
    paths, colors, width, height = ColorSolver(image, 6, Timer()).solve()
    markup = generate_SVG_markup(paths, colors, width, height)
    rendered = Image.open(BytesIO(svg2png(bytestring=markup))).convert("RGBA")

    assert rendered.getchannel("A").getextrema() == (0, 0)


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
