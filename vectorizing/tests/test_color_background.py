"""Conservative background detection and all-or-nothing geometry isolation."""

from unittest.mock import Mock

import numpy as np
import pytest
from flask.testing import FlaskClient
from pathops import PathOp, PathOpsError, op
from PIL import Image

from vectorizing.server.timer import Timer
from vectorizing.solvers.color.bitmaps import (
    add_bitmap_rims,
    create_background_bitmap,
    create_bitmaps,
)
from vectorizing.solvers.color.ColorSolver import ColorSolver, trace_bitmap
from vectorizing.svg.markup import generate_SVG_markup
from vectorizing.tests.test_color_layers import render_layers, trace_layers


@pytest.fixture()
def background_labels() -> tuple[np.ndarray, np.ndarray]:
    """Provide two foreground colors surrounded by a frontmost white background."""
    labels = np.full((40, 40), 2, dtype=np.uint16)
    labels[5:35, 8:14] = 0
    labels[8:32, 20:36] = 1
    palette = np.array([[20, 80, 200], [230, 130, 20], [255, 255, 255]], np.uint8)
    return labels, palette


def test_background_mask_is_bounded_and_does_not_mutate_inputs(
    background_labels: tuple[np.ndarray, np.ndarray],
) -> None:
    """Match an independent square-neighborhood expansion, not full underpainting."""
    labels, palette = background_labels
    original_labels, original_palette = labels.copy(), palette.copy()
    expected = np.zeros(labels.shape, dtype=np.uint8)
    for y, x in np.argwhere(labels == 2):
        expected[max(0, y - 2) : y + 3, max(0, x - 2) : x + 3] = 1
    actual = create_background_bitmap(labels, palette, False)
    np.testing.assert_array_equal(actual, expected)
    assert actual.dtype == np.uint8
    assert actual[20, 28] == 0
    np.testing.assert_array_equal(labels, original_labels)
    np.testing.assert_array_equal(palette, original_palette)


@pytest.mark.parametrize(
    "case",
    ["transparent", "mixed-border", "first", "middle", "duplicate", "single"],
)
def test_unsupported_backgrounds_keep_the_original_svg(
    background_labels: tuple[np.ndarray, np.ndarray],
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    """Use the pre-isolation tracing sequence as the unchanged-output oracle."""
    labels, palette = background_labels
    transparent = case == "transparent"
    if case == "mixed-border":
        labels[0, 10] = 0
    elif case == "first":
        order = np.array([2, 0, 1])
        labels, palette = np.argsort(order)[labels], palette[order]
    elif case == "middle":
        order = np.array([0, 2, 1])
        labels, palette = np.argsort(order)[labels], palette[order]
    elif case == "duplicate":
        palette[0] = palette[2]
    elif case == "single":
        labels.fill(2)
    assert create_background_bitmap(labels, palette, transparent) is None
    masks, retained = create_bitmaps(labels, palette, transparent)
    add_bitmap_rims(masks)
    expected = generate_SVG_markup(
        [trace_bitmap(mask) for mask in masks],
        retained,
        40,
        40,
    )
    paths, colors = trace_layers(monkeypatch, labels, palette, transparent)
    assert generate_SVG_markup(paths, colors, 40, 40) == expected


def test_detection_uses_only_retained_palette_entries(
    background_labels: tuple[np.ndarray, np.ndarray],
) -> None:
    """Ignore unused higher colors, and recognize an already-first retained color."""
    labels, palette = background_labels
    palette = np.vstack([palette, [255, 255, 255]]).astype(np.uint8)
    assert create_background_bitmap(labels, palette, False) is not None
    labels[labels != 2] = 3
    assert create_background_bitmap(labels, palette, False) is None


def test_detection_supports_the_full_palette_range() -> None:
    """Keep 64-color labels intact while finding the frontmost border color."""
    palette = np.array([[i, i * 3 % 256, i * 17 % 256] for i in range(64)], np.uint8)
    labels = np.full((12, 12), 63, dtype=np.uint16)
    labels[2:10, 2:10] = np.arange(64).reshape(8, 8)
    mask = create_background_bitmap(labels, palette, False)
    assert mask is not None
    assert labels.dtype == np.uint16
    assert len(np.unique(labels)) == 64


@pytest.mark.parametrize("size", [1, 2, 3, 5])
def test_isolated_background_preserves_counters_and_boundedness(
    background_labels: tuple[np.ndarray, np.ndarray],
    monkeypatch: pytest.MonkeyPatch,
    size: int,
) -> None:
    """Keep small background-colored counters open without a full background fill."""
    labels, palette = background_labels
    labels[12 : 12 + size, 24 : 24 + size] = 2
    paths, colors = trace_layers(monkeypatch, labels, palette, False)
    np.testing.assert_array_equal(colors, palette[[2, 0, 1]])
    assert not paths[0].contains((28, 27))
    assert all(not path.contains((24 + size / 2, 12 + size / 2)) for path in paths[1:])
    assert all(0 <= v <= 40 for path in paths for v in path.bounds)
    assert render_layers(paths, colors)[:, :, 3].min() >= 240


def test_partial_alpha_uses_existing_transparency_classification(
    background_labels: tuple[np.ndarray, np.ndarray],
) -> None:
    """Do not introduce a stricter input-alpha rule than the current quantizer."""
    labels, palette = background_labels
    rgba = np.dstack([palette[labels], np.full(labels.shape, 255, np.uint8)])
    rgba[0, 0, 3] = 217
    result = ColorSolver(Image.fromarray(rgba), 3, Timer()).solve()
    assert isinstance(result, list)
    np.testing.assert_array_equal(result[1][0], palette[2])


@pytest.mark.parametrize("failure", ["background-clip", "second-difference"])
@pytest.mark.parametrize("raw", [False, True])
def test_isolation_failure_retains_complete_original_output(
    background_labels: tuple[np.ndarray, np.ndarray],
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    failure: str,
    raw: bool,
) -> None:
    """Recover the full original layer set and API response, never partial isolation."""
    labels, palette = background_labels
    masks, retained = create_bitmaps(labels, palette, False)
    add_bitmap_rims(masks)
    expected = generate_SVG_markup(
        [trace_bitmap(mask) for mask in masks],
        retained,
        40,
        40,
    )
    monkeypatch.setattr(
        "vectorizing.try_read_image_from_url",
        lambda url: Image.fromarray(palette[labels]),
    )
    monkeypatch.setattr(
        "vectorizing.solvers.color.ColorSolver.quantize",
        Mock(return_value=(labels, palette, False)),
    )
    # Of the original layers, only the background touches the canvas. Its clip
    # succeeds; fail either the new background's clip or a later subtraction.
    intersections = []
    differences = []

    def controlled_op(*args: object, **kwargs: object) -> object:
        if args[2] == PathOp.INTERSECTION:
            intersections.append(1)
            if failure == "background-clip" and len(intersections) == 2:
                raise PathOpsError("injected background clip failure")
        if args[2] == PathOp.DIFFERENCE:
            differences.append(1)
            if failure == "second-difference" and len(differences) == 2:
                raise PathOpsError("injected subtraction failure")
        return op(*args, **kwargs)

    monkeypatch.setattr("vectorizing.solvers.color.ColorSolver.op", controlled_op)
    upload = Mock(return_value="original-layers")
    monkeypatch.setattr("vectorizing.upload_markup", upload)
    response = client.post("/", json={"url": "unused", "solver": 1, "raw": raw})
    assert response.status_code == 200
    if raw:
        markup = response.data.decode()
        upload.assert_not_called()
    else:
        upload.assert_called_once()
        markup = upload.call_args.args[0]
        assert response.get_json()["objectId"] == "original-layers"
    assert markup == expected
    assert "Background isolation failed; retaining original layers" in caplog.text
    assert "retracing without padding" not in caplog.text
    assert len(intersections) == 2
    assert len(differences) == (2 if failure == "second-difference" else 0)
