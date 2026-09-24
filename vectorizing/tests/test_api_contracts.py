"""Preserve argument validation and raw/error HTTP response contracts."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask.testing import FlaskClient
from PIL import Image

import vectorizing


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"solver": 0},
        {"url": "image", "solver": 2},
        {"url": "image", "solver": "1"},
        {"url": "image", "crop_box": [0, 0, 3]},
        {"url": "image", "crop_box": [0, 0, 3.5, 4]},
    ],
)
def test_invalid_arguments_return_the_same_error(
    payload: dict[str, object],
    client: FlaskClient,
) -> None:
    """Keep rejected inputs false and return the established 400 JSON response."""
    assert vectorizing.validate_args(payload) is False
    response = client.post("/", json=payload)
    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": "INVALID_PARAMETERS"}


@pytest.mark.parametrize(
    "payload",
    [
        {"url": "image"},
        {"url": None},
        {"url": "image", "solver": True},
        {"url": "image", "crop_box": []},
        {"url": "image", "crop_box": [True, 0, 3, 4]},
    ],
)
def test_argument_validation_preserves_accepted_values(
    payload: dict[str, object],
) -> None:
    """Preserve presence-only URL checks, falsey crop boxes and integer booleans."""
    result = vectorizing.validate_args(payload)
    assert isinstance(result, SimpleNamespace)
    assert vars(result) == {
        "url": payload["url"],
        "solver": payload.get("solver", 0),
        "crop_box": payload.get("crop_box"),
        "raw": None,
        "color_count": None,
    }


@pytest.mark.parametrize("solver", [0, 1])
def test_raw_requests_crop_before_vectorizing_and_do_not_upload(
    solver: int,
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep raw responses as SVG bytes and preserve crop ordering for both solvers."""
    image = Image.new("RGB", (8, 8), (40, 50, 60))
    load = Mock(return_value=image)
    binary = Mock(wraps=vectorizing.process_binary)
    color = Mock(wraps=vectorizing.process_color)
    upload = Mock()
    monkeypatch.setattr(vectorizing, "try_read_image_from_url", load)
    monkeypatch.setattr(vectorizing, "process_binary", binary)
    monkeypatch.setattr(vectorizing, "process_color", color)
    monkeypatch.setattr(vectorizing, "upload_markup", upload)
    response = client.post(
        "/",
        json={
            "url": "image",
            "solver": solver,
            "color_count": 2,
            "crop_box": [0, 1, 4, 5],
            "raw": True,
        },
    )
    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    assert response.data.startswith(b"<svg ")
    assert b'width="8" height="8"' in response.data
    chosen, unused = (binary, color) if solver == 0 else (color, binary)
    chosen.assert_called_once()
    assert chosen.call_args.args[0].size == (4, 4)
    unused.assert_not_called()
    load.assert_called_once_with("image")
    upload.assert_not_called()


def test_processing_failure_keeps_json_error(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return the established 500 payload when image processing raises an error."""
    monkeypatch.setattr(
        vectorizing,
        "try_read_image_from_url",
        Mock(side_effect=ValueError("bad image")),
    )
    response = client.post("/", json={"url": "image"})
    assert response.status_code == 500
    assert response.get_json() == {"success": False, "error": "INTERNAL_SERVER_ERROR"}


def test_health_response(client: FlaskClient) -> None:
    """Keep the health endpoint's status and JSON payload stable."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"success": True}
