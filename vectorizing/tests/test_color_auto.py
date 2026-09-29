"""Choose automatic palette sizes without changing numeric mode."""

from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
from cairosvg import svg2png
from flask.testing import FlaskClient
from PIL import Image

import vectorizing
from vectorizing.server.timer import Timer
from vectorizing.solvers.color.ColorSolver import ColorSolver
from vectorizing.svg.markup import generate_original_SVG_markup, generate_SVG_markup
from vectorizing.util.read import convert_RGB_A


@pytest.mark.parametrize(
    "name, expected",
    [
        # These artwork counts are contracts: never rebaseline them to fit a
        # new heuristic. aftermath.png has too many colors to pin this way.
        ("geo_logo.png", 3),
        ("midnight_strike.png", 3),
        ("shapes.png", 4),
        ("shapes_2.png", 6),
        ("test_logo.png", 3),
        ("bubbles.png", 4),
        ("black_rectangle.png", 1),
        ("empty.png", 1),
    ],
)
def test_auto_count_on_gallery(name: str, expected: int) -> None:
    """Pin curated palette sizes while ignoring blended edge colors."""
    with Image.open(Path(__file__).parent / "images" / name) as source:
        image = convert_RGB_A(source)
        solver = ColorSolver(image, "auto", Timer())
    assert solver.color_count == expected


@pytest.mark.parametrize("configuration", ["current", "experimental"])
def test_auto_traces_three_layers_on_midnight_strike(configuration: str) -> None:
    """Pass the selected count through real quantization and layer tracing."""
    with Image.open(Path(__file__).parent / "images" / "midnight_strike.png") as source:
        solver = ColorSolver(convert_RGB_A(source), "auto", Timer(), configuration)
    paths, colors, _, _ = solver.solve()
    assert solver.color_count == len(paths) == len(colors) == 3


@pytest.mark.parametrize("configuration", ["current", "experimental"])
def test_transparent_canvas_does_not_take_a_color_slot(configuration: str) -> None:
    """Hidden black must not desaturate two opaque colors on a transparent logo."""
    pixels = np.zeros((128, 128, 4), dtype=np.uint8)
    pixels[16:64, 16:64] = (255, 0, 0, 255)
    pixels[64:112, 64:112] = (0, 0, 255, 255)
    pixels[0, 0] = (0, 255, 0, 1)  # A rare edge must not dominate hidden RGB.
    solver = ColorSolver(Image.fromarray(pixels), "auto", Timer(), configuration)
    _, colors, _, _ = solver.solve()
    assert solver.color_count == 2
    assert {tuple(color[:3]) for color in colors} == {(255, 0, 0), (0, 0, 255)}


@pytest.mark.parametrize("configuration", ["current", "experimental"])
def test_thin_strokes_between_grid_points_keep_both_colors(configuration: str) -> None:
    """Transparent line art cannot vanish just because its columns miss a grid."""
    pixels = np.zeros((1024, 1024, 4), dtype=np.uint8)
    pixels[:, 1:4] = (255, 0, 0, 255)
    pixels[:, 5:8] = (0, 0, 255, 255)
    solver = ColorSolver(Image.fromarray(pixels), "auto", Timer(), configuration)
    _, colors, _, _ = solver.solve()
    assert solver.color_count == 2
    assert {tuple(color[:3]) for color in colors} == {(255, 0, 0), (0, 0, 255)}


@pytest.mark.parametrize("configuration", ["current", "experimental"])
def test_visible_pixel_sampling_cannot_lock_to_background_columns(
    configuration: str,
) -> None:
    """A single transparent pixel must not phase-lock sampling away from stripes."""
    pixels = np.full((1024, 1024, 4), 255, dtype=np.uint8)
    pixels[:, 5::16, :3] = (255, 0, 0)
    pixels[:, 6::16, :3] = (255, 0, 0)
    pixels[:, 7::16, :3] = (255, 0, 0)
    pixels[0, 0] = (0, 0, 0, 0)
    solver = ColorSolver(Image.fromarray(pixels), "auto", Timer(), configuration)
    _, colors, _, _ = solver.solve()
    assert solver.color_count == 2
    expected = {(255, 255, 255), (255, 0, 0)}
    assert {tuple(color[:3]) for color in colors} == expected


@pytest.mark.parametrize("configuration", ["current", "experimental"])
def test_shadow_masked_by_background_does_not_take_a_slot(
    configuration: str,
) -> None:
    """An alpha-60 shadow becomes background when the image also has alpha 0."""
    pixels = np.zeros((128, 128, 4), dtype=np.uint8)
    pixels[8:64, 8:64] = (255, 0, 0, 255)
    pixels[64:120, 64:120] = (0, 0, 255, 255)
    pixels[8:64, 64:120] = (0, 255, 0, 60)
    solver = ColorSolver(Image.fromarray(pixels), "auto", Timer(), configuration)
    _, colors, _, _ = solver.solve()
    assert solver.color_count == 2
    assert {tuple(color[:3]) for color in colors} == {(255, 0, 0), (0, 0, 255)}


@pytest.mark.parametrize("configuration", ["current", "experimental"])
def test_geo_logo_pattern_is_a_separate_layer(configuration: str) -> None:
    """Keep both large pale regions separate from each other and the dark logo."""
    with Image.open(Path(__file__).parent / "images" / "geo_logo.png") as source:
        solver = ColorSolver(convert_RGB_A(source), "auto", Timer(), configuration)
    paths, colors, width, height = solver.solve()
    assert solver.color_count == len(paths) == len(colors) == 3
    pale = [color[:3] for color in colors if np.min(color[:3]) > 200]
    assert len(pale) == 2
    assert np.linalg.norm(pale[0].astype(int) - pale[1].astype(int)) >= 5
    serialize = (
        generate_original_SVG_markup
        if configuration == "current"
        else generate_SVG_markup
    )
    markup = serialize(paths, colors, width, height)
    raster = Image.open(BytesIO(svg2png(bytestring=markup.encode()))).convert("RGB")
    assert raster.getpixel((0, 0)) != raster.getpixel((150, 0))


@pytest.mark.parametrize("configuration", ["current", "experimental"])
def test_kittl_logo_accent_has_its_own_layer(configuration: str) -> None:
    """Preserve the small neon mark as well as black lettering and white canvas."""
    with Image.open(Path(__file__).parent / "images" / "test_logo.png") as source:
        solver = ColorSolver(convert_RGB_A(source), "auto", Timer(), configuration)
    paths, colors, _, _ = solver.solve()
    assert solver.color_count == len(paths) == len(colors) == 3
    assert any(160 < color[1] and color[2] < 120 for color in colors)


def test_large_intermediate_color_is_not_treated_as_an_edge() -> None:
    """An entire gray panel between black and white is a third color."""
    pixels = np.zeros((100, 100, 3), dtype=np.uint8)
    pixels[40:75] = (255, 255, 255)
    pixels[75:] = (128, 128, 128)
    assert ColorSolver(Image.fromarray(pixels), "auto", Timer()).color_count == 3


def test_partially_transparent_pixels_count_as_visible() -> None:
    """The solver clusters nonzero-alpha RGB, so auto must count it too."""
    pixels = np.zeros((100, 100, 4), dtype=np.uint8)
    pixels[:50] = (255, 0, 0, 64)
    pixels[50:] = (0, 0, 255, 255)
    assert ColorSolver(Image.fromarray(pixels), "auto", Timer()).color_count == 2


def test_auto_request_and_numeric_default_remain_distinct(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the explicit auto string opts into estimation; numeric clamps remain."""
    monkeypatch.setattr(
        vectorizing,
        "try_read_image_from_url",
        Mock(return_value=Image.new("RGB", (8, 8))),
    )
    process = Mock(return_value=([], [], 8, 8))
    monkeypatch.setattr(vectorizing, "process_color", process)
    for count in ["auto", None, "", 1, 65]:
        response = client.post(
            "/",
            json={"url": "image", "solver": 1, "raw": True, "color_count": count},
        )
        assert response.status_code == 200
        assert process.call_args.args[1] == count
    assert ColorSolver(Image.new("RGB", (8, 8)), None, Timer()).color_count == 6
    assert ColorSolver(Image.new("RGB", (8, 8)), 1, Timer()).color_count == 2
    assert ColorSolver(Image.new("RGB", (8, 8)), 65, Timer()).color_count == 64
    assert ColorSolver(Image.new("RGB", (8, 8)), "", Timer()).color_count == 6
