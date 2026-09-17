"""HTTP/S3 integration, raster diagnostics and rendered SVG seam checks.

The persisted raster gallery is a tolerant smoke test and creates missing
baselines. Exact before/after output checks live in test_color_equivalence.py;
RGBA assertions here independently protect transparency and anti-aliased edges.
"""

import os
from io import BytesIO
from pathlib import Path

import numpy as np
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
    """Exercise HTTP vectorization against the persisted raster fixture gallery."""
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

            # Historical behavior: seed missing baselines, but do not count this
            # as before/after equivalence evidence. Exact tests never seed results.
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

    np.testing.assert_equal(all(diff <= MAX_IMAGE_DIFFERENCE for diff in diffs), True)


def test_write_img_difference_handles_rgba_baselines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep RGB diagnostics compatible with saved RGBA raster baselines."""
    baseline = tmp_path / "baseline.png"
    output = tmp_path / "difference.png"
    Image.new("RGBA", (2, 2), (0, 0, 0, 0)).save(baseline)
    monkeypatch.setattr(testutil, "DIFF_OUTPUT_FOLDER_PATH", tmp_path)

    testutil.write_img_difference(
        Image.new("RGB", (2, 2), (255, 255, 255)),
        baseline,
        output.name,
    )

    np.testing.assert_equal(output.exists(), True)


def test_color_solver_renders_shared_edges_opaque() -> None:
    """Keep a shared color edge opaque without adding SVG strokes."""
    image = Image.new("RGB", (10, 10), (40, 81, 180))
    for x in range(2, 8):
        for y in range(2, 8):
            image.putpixel((x, y), (26, 54, 127))

    paths, colors, width, height = ColorSolver(image, 2, Timer()).solve()
    markup = generate_SVG_markup(paths, colors, width, height)
    rendered = Image.open(
        BytesIO(svg2png(bytestring=markup, output_width=101, output_height=101)),
    ).convert("RGBA")

    # The non-integer 10 -> 101 scale exposes anti-aliased gaps between fills.
    np.testing.assert_equal("stroke=" in markup, False)
    np.testing.assert_equal(rendered.getpixel((20, 50))[3], 255)


def test_color_solver_renders_transparent_shared_edges_opaque() -> None:
    """Overlap interior fills while leaving the exterior fully transparent."""
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

    # Check alpha separately: RGB-only comparisons cannot detect transparency loss.
    np.testing.assert_equal("stroke=" in markup, False)
    np.testing.assert_equal(rendered.getpixel((0, 0))[3], 0)
    np.testing.assert_equal(rendered.getpixel((20, 50))[3], 255)


@pytest.mark.parametrize(
    "image_name, color_count",
    [("bubbles.png", 5), ("shapes_2.png", 7)],
)
def test_color_solver_renders_real_multicolor_edges_opaque(
    image_name: str,
    color_count: int,
) -> None:
    """Keep every pixel opaque when vectorizing opaque multicolor fixtures."""
    image = Image.open(Path(__file__).parent / "images" / image_name)
    paths, colors, width, height = ColorSolver(image, color_count, Timer()).solve()
    markup = generate_SVG_markup(paths, colors, width, height)
    rendered = Image.open(BytesIO(svg2png(bytestring=markup))).convert("RGBA")

    np.testing.assert_equal("stroke=" in markup, False)
    np.testing.assert_equal(rendered.getchannel("A").getextrema(), (255, 255))


def test_color_solver_avoids_transparent_inner_seams_in_aftermath() -> None:
    """Catch widespread inner seams without forbidding smooth exterior edges."""
    image = Image.open(Path(__file__).parent / "images" / "aftermath.png")
    paths, colors, width, height = ColorSolver(image, 16, Timer()).solve()
    markup = generate_SVG_markup(paths, colors, width, height)
    rendered = Image.open(BytesIO(svg2png(bytestring=markup))).convert("RGBA")
    alpha = list(rendered.getchannel("A").getdata())

    np.testing.assert_equal(min(alpha), 0)
    np.testing.assert_equal(max(alpha), 255)
    # Partial alpha is valid along the exterior; this budget catches broad seam
    # regressions, not the spatial location of every partially transparent pixel.
    np.testing.assert_equal(sum(0 < value < 255 for value in alpha) < 10_000, True)


def test_color_solver_preserves_empty_transparent_image() -> None:
    """Keep fully transparent artwork transparent after tracing and rendering."""
    image = Image.open(Path(__file__).parent / "images" / "empty.png")
    paths, colors, width, height = ColorSolver(image, 6, Timer()).solve()
    markup = generate_SVG_markup(paths, colors, width, height)
    rendered = Image.open(BytesIO(svg2png(bytestring=markup))).convert("RGBA")

    np.testing.assert_equal(rendered.getchannel("A").getextrema(), (0, 0))


def test_uploads_markup_to_s3(client: FlaskClient) -> None:
    """Verify uploads store SVG markup in the isolated test bucket."""
    response = client.post(
        "/",
        json={
            "url": get_image_url("black_rectangle.png"),
            "solver": 0,
            "raw": False,
        },
    )

    np.testing.assert_equal(response.status_code, 200)
    payload = response.get_json()
    test_bucket = os.environ["S3_TEST_BUCKET"]
    s3 = get_s3_client()
    try:
        stored = s3.get_object(
            Bucket=test_bucket,
            Key=payload["objectId"],
        )
        np.testing.assert_equal(stored["ContentType"], "image/svg+xml")
        np.testing.assert_equal(stored["Body"].read().startswith(b"<svg"), True)
    finally:
        s3.delete_object(Bucket=test_bucket, Key=payload["objectId"])
