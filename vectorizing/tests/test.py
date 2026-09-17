import os
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
from cairosvg import svg2png
from PIL import Image

from vectorizing.geometry.bounds import compound_paths_bounds
from vectorizing.server.s3 import get_s3_client
from vectorizing.server.timer import Timer
from vectorizing.solvers.color import quantize as color_quantize
from vectorizing.solvers.color.bitmaps import create_bitmaps
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


def legacy_initial_centroids(img_arr: np.ndarray, color_count: int) -> np.ndarray:
    """Freeze the original RGB-pixel algorithm as an independent regression oracle."""
    img = (
        Image.fromarray(img_arr)
        .quantize(color_count, method=Image.Quantize.FASTOCTREE)
        .convert("RGB")
    )
    pixels = np.asarray(img)
    return np.unique(pixels.reshape(-1, pixels.shape[-1]), axis=0).astype(np.uint8)


@pytest.mark.parametrize(
    "variant",
    ["noise", "strided", "one-pixel", "solid", "sparse"],
)
@pytest.mark.parametrize("color_count", [2, 6, 16, 64])
@pytest.mark.parametrize("seed", range(5))
def test_initial_centroids_match_original(
    color_count: int,
    seed: int,
    variant: str,
) -> None:
    """Preserve exact dtype, values and ordering on random and sparse RGB inputs."""
    rng = np.random.default_rng(seed)
    noise = rng.integers(0, 256, size=(63, 67, 3), dtype=np.uint8)
    pixels = {
        "noise": noise,
        "strided": noise[::2, ::2],
        "one-pixel": noise[:1, :1],
        "solid": np.full_like(noise, (175, 80, 230)),  # Ignore unused black entries.
        "sparse": (noise // 128) * 128,
    }[variant]
    expected = legacy_initial_centroids(pixels, color_count)
    actual = color_quantize.get_initial_centroids(pixels, color_count)
    np.testing.assert_equal(actual.dtype, expected.dtype)
    np.testing.assert_equal(actual.dtype, np.dtype(np.uint8))
    np.testing.assert_array_equal(actual, expected)


def test_initial_centroids_ignore_unused_and_duplicate_palette_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep only used RGB colors, deduplicated and sorted rather than palette order."""
    indexed = Image.new("P", (3, 1))
    indexed.putdata([7, 3, 5])
    palette = np.zeros((256, 3), dtype=np.uint8)
    palette[1] = (255, 0, 0)  # Unused nonblack entry.
    palette[3] = palette[7] = (90, 10, 20)  # Duplicate used RGB entries.
    palette[5] = (10, 20, 30)
    indexed.putpalette(palette.ravel().tolist())
    with monkeypatch.context() as patch:
        patch.setattr(Image.Image, "quantize", lambda *args, **kwargs: indexed)
        pixels = np.zeros((1, 3, 3), dtype=np.uint8)
        actual = color_quantize.get_initial_centroids(pixels, 64)
        expected = legacy_initial_centroids(pixels, 64)
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(actual, [[10, 20, 30], [90, 10, 20]])


def legacy_create_bitmaps(
    labels: np.ndarray,
    colors: np.ndarray,
    has_background: bool,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Freeze the original pairwise accumulation as an independent regression oracle."""
    bitmaps = [
        np.where(labels == index, 1, 0).astype(np.uint32)
        for index in range(len(colors))
    ]
    if has_background:
        bitmaps = bitmaps[1:]
        colors = colors[1:]
    zipped = list(zip(bitmaps, colors))
    zipped = [[bitmap, color] for bitmap, color in zipped if np.sum(bitmap) > 0]
    bitmaps = [bitmap for bitmap, _ in zipped]
    colors = [color for _, color in zipped]
    for x in range(len(bitmaps)):
        bitmap_x = bitmaps[x]
        for y in range(x + 1, len(bitmaps)):
            bitmap_x += bitmaps[y]
        bitmaps[x] = bitmap_x
    return bitmaps, colors


@pytest.mark.parametrize(
    "variant",
    ["noise", "strided", "one-row", "one-column", "solid", "background", "sparse"],
)
@pytest.mark.parametrize("color_count", [1, 2, 6, 16, 64, 65])
@pytest.mark.parametrize("has_background", [False, True])
@pytest.mark.parametrize("seed", range(3))
def test_bitmap_layering_matches_original(
    color_count: int,
    has_background: bool,
    seed: int,
    variant: str,
) -> None:
    """Preserve masks, dtype, color order and read-only inputs across label patterns."""
    rng = np.random.default_rng(seed)
    noise = rng.integers(0, color_count, size=(19, 23), dtype=np.uint16)
    colors = rng.integers(0, 256, size=(color_count, 4), dtype=np.uint8)
    colors.setflags(write=False)
    labels = {
        "noise": noise,
        "strided": noise[::2, ::2],
        "one-row": noise[:1, :],
        "one-column": noise[:, :1],
        "solid": np.full_like(noise, color_count - 1),
        "background": np.zeros_like(noise),
        "sparse": noise % 2,
    }[variant]
    labels.setflags(write=False)
    expected_bitmaps, expected_colors = legacy_create_bitmaps(
        labels,
        colors,
        has_background,
    )
    actual_bitmaps, actual_colors = create_bitmaps(labels, colors, has_background)
    np.testing.assert_array_equal(actual_colors, expected_colors)
    np.testing.assert_equal(len(actual_bitmaps), len(expected_bitmaps))
    for actual, expected in zip(actual_bitmaps, expected_bitmaps):
        np.testing.assert_equal(actual.dtype, np.dtype(np.uint32))
        np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize("has_background", [False, True])
@pytest.mark.parametrize("color_count", [0, 1, 6])
def test_bitmap_layering_handles_empty_inputs(
    has_background: bool,
    color_count: int,
) -> None:
    """Return no layers for empty labels or an empty palette."""
    colors = np.zeros((color_count, 3), dtype=np.uint8)
    labels = np.empty((0, 3), dtype=np.uint8)
    np.testing.assert_equal(create_bitmaps(labels, colors, has_background), ([], []))
    np.testing.assert_equal(
        create_bitmaps(np.zeros((2, 2), dtype=np.uint8), colors[:0], has_background),
        ([], []),
    )


def test_bitmap_layering_preserves_overlap_and_transparency() -> None:
    """Keep suffix unions in palette order without including transparent pixels."""
    labels = np.array([[0, 1, 3, 4]], dtype=np.uint8)
    colors = np.arange(20, dtype=np.uint8).reshape(5, 4)
    # Label zero is transparent; label two is unused between visible layers.
    bitmaps, visible_colors = create_bitmaps(labels, colors, True)
    expected = np.array(
        [[[0, 1, 1, 1]], [[0, 0, 1, 1]], [[0, 0, 0, 1]]],
        dtype=np.uint32,
    )
    np.testing.assert_array_equal(bitmaps, expected)
    np.testing.assert_array_equal(visible_colors, colors[[1, 3, 4]])
    # The in-place accumulation must not make different layers share storage.
    bitmaps[0][0, 0] = 1
    np.testing.assert_array_equal(bitmaps[1:], expected[1:])
    np.testing.assert_array_equal(labels, [[0, 1, 3, 4]])


@pytest.mark.parametrize("optimization", ["centroids", "bitmaps"])
@pytest.mark.parametrize(
    "image_name, color_count",
    [
        ("bubbles.png", 5),
        ("shapes_2.png", 7),
        ("aftermath.png", 2),
        ("aftermath.png", 6),
        ("aftermath.png", 16),
        ("aftermath.png", 64),
        ("empty.png", 6),
        ("1px.jpg", 9),
    ],
)
def test_color_optimizations_preserve_vectorization(
    image_name: str,
    color_count: int,
    optimization: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compare final SVG, colors, dimensions and bounds against the old algorithm."""
    with Image.open(Path(__file__).parent / "images" / image_name) as image:
        actual = ColorSolver(image, color_count, Timer()).solve()
        target, legacy = {
            "centroids": (
                "vectorizing.solvers.color.quantize.get_initial_centroids",
                legacy_initial_centroids,
            ),
            "bitmaps": (
                "vectorizing.solvers.color.ColorSolver.create_bitmaps",
                legacy_create_bitmaps,
            ),
        }[optimization]
        # Patch each lookup site and verify the legacy implementation was used.
        reference = Mock(wraps=legacy)
        monkeypatch.setattr(target, reference)
        expected = ColorSolver(image, color_count, Timer()).solve()
        reference.assert_called_once()

    actual_paths, actual_colors, actual_width, actual_height = actual
    expected_paths, expected_colors, expected_width, expected_height = expected
    np.testing.assert_array_equal(actual_colors, expected_colors)
    np.testing.assert_equal(
        (actual_width, actual_height),
        (expected_width, expected_height),
    )
    np.testing.assert_equal(
        compound_paths_bounds(actual_paths),
        compound_paths_bounds(expected_paths),
    )
    # Byte-identical SVG is stricter than a raster tolerance and includes transparency.
    np.testing.assert_equal(
        generate_SVG_markup(*actual),
        generate_SVG_markup(*expected),
    )


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
