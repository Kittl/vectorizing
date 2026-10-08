"""Keep both selectable color pipelines covered by their independent outputs."""

import hashlib
import tracemalloc
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import potrace
import pytest
from flask.testing import FlaskClient
from PIL import Image

import vectorizing
from vectorizing.server.timer import Timer
from vectorizing.solvers.color import legacy
from vectorizing.solvers.color.bitmaps import create_bitmaps
from vectorizing.solvers.color.ColorSolver import ColorSolver
from vectorizing.svg.markup import generate_original_SVG_markup, generate_SVG_markup
from vectorizing.tests.color_reference import original_area_cleanup
from vectorizing.util.limit_size import limit_size
from vectorizing.util.read import convert_RGB_A


def transparent_artwork() -> Image.Image:
    """Build opaque nested colors with transparent exterior and an alpha hole."""
    pixels = np.zeros((36, 36, 4), dtype=np.uint8)
    pixels[:] = [30, 100, 220, 0]
    pixels[3:33, 3:33] = [240, 230, 190, 255]
    pixels[9:27, 9:27] = [35, 60, 130, 255]
    pixels[16:20, 16:20] = [220, 10, 40, 255]
    pixels[13:15, 13:15, 3] = 0
    return Image.fromarray(pixels)


def test_default_quantization_matches_original_rgba_output() -> None:
    """Pin the original palette, transparent cluster, label dtype and mask bytes."""
    labels, colors, has_background = legacy.quantize(
        np.asarray(transparent_artwork()),
        4,
    )
    assert has_background
    assert labels.dtype == np.uint16
    assert hashlib.sha256(labels.tobytes()).hexdigest() == (
        "e410dd6134fe3fe03bf99b184f1dd4f0bf5a03d007d3c42b6b36e6bd8f9bc226"
    )
    np.testing.assert_array_equal(
        colors,
        [
            [0, 0, 0, 0],
            [30, 100, 220, 1],
            [35, 59, 130, 1],
            [220, 10, 40, 1],
            [240, 230, 190, 1],
        ],
    )


def test_original_rgb_component_cleanup_matches_reference() -> None:
    """Check the original connected-component decisions, including tiny clusters."""
    path = Path(__file__).parent / "images" / "shapes_2.png"
    with Image.open(path) as image:
        labels, colors, has_background = legacy.quantize(
            np.asarray(limit_size(image.convert("RGB"))).astype(np.uint8),
            7,
        )
    assert not has_background
    assert hashlib.sha256(labels.tobytes()).hexdigest() == (
        "a5455fcdb7c920fa369f9ab26304277bde52f3267d195712b1ecf4df132ab831"
    )
    np.testing.assert_array_equal(
        colors,
        [
            [22, 22, 22],
            [31, 172, 153],
            [101, 205, 35],
            [169, 20, 20],
            [201, 20, 20],
            [225, 21, 178],
            [227, 230, 39],
        ],
    )


@pytest.mark.parametrize("count", [2, 6, 16, 64])
@pytest.mark.parametrize("transparent", [False, True])
@pytest.mark.parametrize("seed", range(4))
def test_original_cleanup_matches_pairwise_reference(
    count: int,
    transparent: bool,
    seed: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stream components without changing overlap ratios or filled labels."""
    rng = np.random.default_rng(seed)
    assigned = rng.integers(0, count, (11, 13), dtype=np.uint8)
    colors = rng.integers(0, 256, (count, 3), dtype=np.uint8)
    image = np.zeros((11, 13, 4 if transparent else 3), dtype=np.uint8)
    if transparent:
        image[:, :, 3] = 255
        image[2:5, 3:6, 3] = 0
        original_labels = np.where(image[:, :, 3] == 0, 0, assigned + 1)
    else:
        original_labels = assigned
    monkeypatch.setattr(legacy, "get_initial_centroids", lambda *_: colors)
    monkeypatch.setattr(legacy, "kmeans", lambda *_: (assigned.reshape(-1, 1), colors))
    actual, palette, has_background = legacy.quantize(image, count)
    np.testing.assert_array_equal(
        actual,
        original_area_cleanup(original_labels, count + int(transparent)),
    )
    assert actual.dtype == np.uint16
    assert has_background is transparent
    assert len(palette) == count + int(transparent)


def test_original_cleanup_keeps_working_memory_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 64-color image must not retain a component grid per palette entry."""
    rng = np.random.default_rng(731)
    assigned = rng.integers(0, 64, (256, 256), dtype=np.uint8)
    colors = rng.integers(0, 256, (64, 3), dtype=np.uint8)
    monkeypatch.setattr(legacy, "get_initial_centroids", lambda *_: colors)
    monkeypatch.setattr(legacy, "kmeans", lambda *_: (assigned.reshape(-1, 1), colors))
    tracemalloc.start()
    try:
        legacy.quantize(np.zeros((256, 256, 3), dtype=np.uint8), 64)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 32 * 1024 * 1024


def test_original_opaque_svg_matches_reference(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pin the opaque API output captured from the original implementation."""
    path = Path(__file__).parent / "images" / "black_rectangle.png"
    with Image.open(path) as source:
        image = convert_RGB_A(source).copy()
    monkeypatch.setattr(
        vectorizing,
        "try_read_image_from_url",
        Mock(return_value=image),
    )
    response = client.post(
        "/",
        json={"url": "image", "solver": 1, "color_count": 5, "raw": True},
    )
    assert response.status_code == 200
    assert hashlib.sha256(response.data).hexdigest() == (
        "6cc923711ade26ecda686ded32401cee8d3d730c4adc9e5a5e85151089d4bea1"
    )


def test_original_transparent_serialization_matches_reference() -> None:
    """Pin the original stages independently of numeric palette-slot recovery."""
    image = transparent_artwork()
    labels, colors, has_background = legacy.quantize(np.asarray(image), 4)
    bitmaps, colors = create_bitmaps(labels, colors, has_background)
    paths = legacy.remove_layering(
        [potrace.Bitmap(bitmap).trace() for bitmap in bitmaps],
        image.width,
        image.height,
        has_background,
    )
    markup = generate_original_SVG_markup(paths, colors, image.width, image.height)
    # Captured from the original stages, not regenerated to match recovery.
    assert hashlib.sha256(markup.encode()).hexdigest() == (
        "901127e424e2944c199af568da7bf136373b825a8f2939b1df109ed0c1269632"
    )


def test_original_profile_is_http_default_and_experimental_is_independent(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the original serializer as HTTP default and profiles selectable."""
    image = transparent_artwork()
    monkeypatch.setattr(
        vectorizing,
        "try_read_image_from_url",
        Mock(return_value=image),
    )
    base = {"url": "image", "solver": 1, "color_count": 4, "raw": True}
    default = client.post("/", json=base)
    original = client.post("/", json={**base, "configuration": "current"})
    experimental = client.post("/", json={**base, "configuration": "experimental"})
    assert all(r.status_code == 200 for r in (default, original, experimental))
    assert default.data == original.data
    assert default.data.decode() == generate_original_SVG_markup(
        *ColorSolver(image, 4, Timer(), "current").solve(),
    )
    assert experimental.data != default.data
    assert experimental.data.decode() == generate_SVG_markup(
        *ColorSolver(image, 4, Timer(), "experimental").solve(),
    )
    assert client.post("/", json=base).data == default.data
