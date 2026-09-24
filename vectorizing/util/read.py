"""Read supported raster formats and normalize their color modes."""

from io import BytesIO
from os import PathLike

import requests
from PIL import Image

MIN_PIXEL_COUNT = 64
MAX_PIXEL_COUNT = 1024**2
SMALL_PIXEL_COUNT = 512**2


class URLReadError(Exception):
    """Wrap failures while downloading or opening an image URL."""

    def __init__(self) -> None:
        super().__init__(self, "Failed to read image from provided URL.")


class PathReadError(Exception):
    """Wrap failures while opening a local image."""

    def __init__(self) -> None:
        super().__init__(self, "Failed to read image from provided path.")


class ImageFormatError(Exception):
    """Signal an unsupported image color mode."""

    def __init__(self) -> None:
        super().__init__(self, "Image format not supported.")


def convert_RGB_A(img: Image.Image) -> Image.Image:
    """Keep RGB/RGBA images unchanged and convert supported grayscale/palette modes."""
    if img.mode == "RGB" or img.mode == "RGBA":
        return img

    map = {
        "1": "RGB",
        "L": "RGB",
        "P": "RGBA",
        "PA": "RGBA",
    }

    if img.mode not in map:
        raise ImageFormatError()

    return img.convert(map.get(img.mode))


def try_read_image_from_path(path: str | PathLike[str]) -> Image.Image:
    """Open an image, wrapping all loading exceptions including interrupts."""
    try:
        img = Image.open(path)
    except BaseException:  # noqa: B036 - All loading failures use the public wrapper.
        raise PathReadError()
    return convert_RGB_A(img)


def try_read_image_from_url(url: str) -> Image.Image:
    """Download without a time limit, wrapping all loading exceptions."""
    try:
        # Image downloads wait without a timeout.
        resp = requests.get(  # noqa: S113
            url,
            headers={"User-Agent": "KittlVectorizing/1.0.0"},
        )
        img = Image.open(BytesIO(resp.content))
    except BaseException:  # noqa: B036 - All loading failures use the public wrapper.
        raise URLReadError()
    return convert_RGB_A(img)
