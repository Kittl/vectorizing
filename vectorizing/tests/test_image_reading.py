"""Preserve image modes, request options and public loading-error behavior."""

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from vectorizing.util import read


@pytest.mark.parametrize(
    "mode, expected_mode",
    [
        ("RGB", "RGB"),
        ("RGBA", "RGBA"),
        ("1", "RGB"),
        ("L", "RGB"),
        ("P", "RGBA"),
        ("PA", "RGBA"),
    ],
)
def test_supported_image_modes(mode: str, expected_mode: str) -> None:
    """Keep RGB/RGBA identity and preserve pixels when converting other modes."""
    image = Image.new(mode, (8, 8))
    actual = read.convert_RGB_A(image)
    assert actual.mode == expected_mode
    assert actual.tobytes() == image.convert(expected_mode).tobytes()
    if mode in {"RGB", "RGBA"}:
        assert actual is image


@pytest.mark.parametrize("reader", ["path", "url"])
@pytest.mark.parametrize(
    "exception_type",
    [OSError, ValueError, MemoryError, KeyboardInterrupt, SystemExit],
)
def test_loading_failures_keep_the_public_wrapper(
    reader: str,
    exception_type: type[BaseException],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retain catch-all wrapping, original context and the public exception args."""
    cause = exception_type("loading failed")
    if reader == "path":
        monkeypatch.setattr(read.Image, "open", Mock(side_effect=cause))
        loader, error_type = read.try_read_image_from_path, read.PathReadError
        message = "Failed to read image from provided path."
    else:
        monkeypatch.setattr(read.requests, "get", Mock(side_effect=cause))
        loader, error_type = read.try_read_image_from_url, read.URLReadError
        message = "Failed to read image from provided URL."
    with pytest.raises(error_type) as caught:
        loader("source")
    assert caught.value.args == (caught.value, message)
    assert caught.value.__context__ is cause
    assert not caught.value.__suppress_context__


@pytest.mark.parametrize("reader", ["path", "url"])
def test_unsupported_modes_are_not_wrapped_as_loading_errors(
    reader: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Leave mode conversion outside the image-loading exception wrapper."""
    monkeypatch.setattr(
        read.Image,
        "open",
        Mock(return_value=Image.new("CMYK", (8, 8))),
    )
    monkeypatch.setattr(
        read.requests,
        "get",
        Mock(return_value=SimpleNamespace(content=b"")),
    )
    loader = (
        read.try_read_image_from_path
        if reader == "path"
        else read.try_read_image_from_url
    )
    with pytest.raises(read.ImageFormatError):
        loader("source")


@pytest.mark.parametrize("status_code", [200, 404])
def test_url_reader_preserves_request_and_decoding_contract(
    status_code: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Send the service user agent and decode images regardless of HTTP status."""
    image = Image.new("RGBA", (8, 8), (20, 30, 40, 128))
    encoded = BytesIO()
    image.save(encoded, format="PNG")
    get = Mock(
        return_value=SimpleNamespace(
            content=encoded.getvalue(),
            status_code=status_code,
        ),
    )
    monkeypatch.setattr(read.requests, "get", get)
    url = "https://example.invalid/image.png?signature=fixture"
    actual = read.try_read_image_from_url(url)
    get.assert_called_once_with(url, headers={"User-Agent": "KittlVectorizing/1.0.0"})
    assert actual.mode == "RGBA"
    assert actual.tobytes() == image.tobytes()


def test_path_reader_accepts_path_objects(tmp_path: Path) -> None:
    """Read Path objects and normalize grayscale pixels to RGB."""
    path = tmp_path / "gray.png"
    Image.new("L", (8, 8), 64).save(path)
    actual = read.try_read_image_from_path(path)
    assert actual.mode == "RGB"
    assert actual.getpixel((0, 0)) == (64, 64, 64)
