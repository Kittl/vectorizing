"""Shared fixtures and offline solver execution for developer commands."""

import hashlib
import math
import os
import platform
import sys
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Explicit cases keep developer reports independent of pytest's module layout.
CASES = {
    "1px_binary": ("1px.jpg", "binary", None),
    "1px_color": ("1px.jpg", "color", 9),
    "black_rectangle_binary": ("black_rectangle.png", "binary", None),
    "black_rectangle_color": ("black_rectangle.png", "color", 5),
    "bubbles": ("bubbles.png", "color", 5),
    "geo_logo": ("geo_logo.png", "binary", None),
    "shapes": ("shapes.png", "color", 4),
    "shapes_2": ("shapes_2.png", "color", 7),
    "white_text": ("white_text.png", "binary", None),
    "aftermath-2": ("aftermath.png", "color", 2),
    "aftermath-6": ("aftermath.png", "color", 6),
    "aftermath-16": ("aftermath.png", "color", 16),
    "aftermath-64": ("aftermath.png", "color", 64),
    "empty-binary": ("empty.png", "binary", None),
    "empty-color": ("empty.png", "color", 6),
}


def file_hash(path: Path) -> str:
    """Hash file bytes without retaining the entire file in memory."""
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def fingerprint(svg: str, details: dict[str, object]) -> dict[str, object]:
    """Record exact SVG bytes alongside palette, dimensions, bounds and input."""
    return {"svg_sha256": hashlib.sha256(svg.encode("utf-8")).hexdigest(), **details}


def source_hash(source_root: Path) -> str:
    """Fingerprint runtime Python sources without requiring Git in the container."""
    digest = hashlib.sha256()
    for path in sorted((source_root / "vectorizing").rglob("*.py")):
        relative = path.relative_to(source_root)
        if "tests" not in relative.parts:
            digest.update(str(relative).replace(os.sep, "/").encode("utf-8") + b"\0")
            digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def environment() -> dict[str, object]:
    """Report the numerical runtime and native thread counts without credentials."""
    import cv2
    import faiss

    packages = (
        "numpy",
        "Pillow",
        "scipy",
        "scikit-image",
        "faiss-cpu",
        "opencv-python-headless",
        "pypotrace",
        "skia-pathops",
        "CairoSVG",
    )
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpus": os.cpu_count(),
        "faiss_threads": faiss.omp_get_max_threads(),
        "opencv_threads": cv2.getNumThreads(),
        "versions": {name: version(name) for name in packages},
    }


def prepare_case(
    name: str,
    source_root: Path,
) -> Callable[[], tuple[str, dict[str, object]]]:
    """Load a fixture once and return a fresh solver/SVG/bounds run for its checkout."""
    source_root = source_root.resolve()
    if not (source_root / "vectorizing" / "__init__.py").is_file():
        raise ValueError(f"Not a vectorizing checkout: {source_root}")
    sys.path.insert(0, str(source_root))
    # Package imports require these settings; no server or S3 client is created.
    os.environ.setdefault("PORT", "8000")
    os.environ.setdefault("S3_BUCKET", "unused-vectorization-tools")

    import numpy as np
    from PIL import Image

    import vectorizing
    from vectorizing.geometry.bounds import compound_paths_bounds
    from vectorizing.server.timer import Timer
    from vectorizing.solvers.binary.BinarySolver import BinarySolver
    from vectorizing.solvers.color.ColorSolver import ColorSolver
    from vectorizing.svg.markup import generate_SVG_markup
    from vectorizing.util.read import convert_RGB_A

    if Path(vectorizing.__file__).resolve().parent != source_root / "vectorizing":
        raise ValueError(
            "A different checkout is already imported; use a fresh process",
        )
    filename, solver, count = CASES[name]
    path = source_root / "vectorizing" / "tests" / "images" / filename
    with Image.open(path) as source:
        image = convert_RGB_A(source).copy()
    source_info = {
        "image": filename,
        "sha256": file_hash(path),
        "solver": solver,
        "color_count": count,
    }

    def run() -> tuple[str, dict[str, object]]:
        result = (
            BinarySolver(image).solve()
            if solver == "binary"
            else ColorSolver(image, count, Timer()).solve()
        )
        paths, colors, width, height = result
        bounds = compound_paths_bounds(paths)
        # Empty artwork has infinite bounds; strings keep the report valid JSON.
        bounds = {
            key: float(value) if math.isfinite(value) else str(float(value))
            for key, value in bounds.items()
        }
        palette = np.asarray(colors)
        return generate_SVG_markup(*result), {
            "input": source_info,
            "colors": palette.tolist(),
            "colors_dtype": str(palette.dtype),
            "dimensions": [width, height],
            "bounds": bounds,
        }

    return run
