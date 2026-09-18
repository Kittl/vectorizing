"""Expose image vectorization and health checks through Flask."""

import os
from types import SimpleNamespace
from typing import Literal, NoReturn

import numpy as np
import sentry_sdk
from flask import Flask, Response, jsonify, request
from pathops import Path
from PIL import Image

from vectorizing.geometry.bounds import compound_paths_bounds
from vectorizing.server.env import get_optional, get_required
from vectorizing.server.logs import setup_logs
from vectorizing.server.s3 import upload_markup
from vectorizing.server.timer import Timer
from vectorizing.solvers.binary.BinarySolver import BinarySolver
from vectorizing.solvers.color.ColorSolver import ColorSolver
from vectorizing.svg.markup import generate_SVG_markup
from vectorizing.util.read import try_read_image_from_url

# 0 -> BinarySolver
# 1 -> ColorSolver
SOLVERS = [0, 1]
DEFAULT_SOLVER = 0
PYTHON_ENV = os.getenv("PYTHON_ENV", "development")

(
    PORT,
    S3_BUCKET,
) = get_required()

(SENTRY_DSN, S3_TEST_BUCKET) = get_optional()

setup_logs()


def process_binary(img: Image.Image) -> tuple[list[Path], list[list[int]], int, int]:
    """Trace an image into black paths and return its processed dimensions."""
    solver = BinarySolver(img)
    return solver.solve()


def process_color(
    img: Image.Image,
    color_count: int | None,
    timer: Timer,
) -> list[list[Path] | list[np.ndarray] | int]:
    """Trace color layers with bounded overlaps and return processed dimensions."""
    solver = ColorSolver(img, color_count, timer)
    return solver.solve()


def validate_args(args: dict[str, object]) -> SimpleNamespace | Literal[False]:
    """Validate the URL key, solver choice and optional four-integer crop box."""
    if "url" not in args:
        return False

    solver = args.get("solver", DEFAULT_SOLVER)
    if solver not in SOLVERS:
        return False

    box = args.get("crop_box")
    if box:
        if len(box) != 4:
            return False

        only_numbers = all([isinstance(item, int) for item in box])
        if not only_numbers:
            return False

    return SimpleNamespace(
        crop_box=box,
        solver=solver,
        url=args.get("url"),
        raw=args.get("raw"),
        color_count=args.get("color_count"),
    )


def invalid_args() -> tuple[Response, int]:
    """Return the API's invalid-parameters response."""
    return jsonify({"success": False, "error": "INVALID_PARAMETERS"}), 400


def create_app(test_config: dict[str, object] | None = None) -> Flask:
    """Create the HTTP app; the optional test_config argument is unused."""
    app = Flask(__name__, instance_relative_config=True)
    app.debug = PYTHON_ENV == "development"

    @app.route("/", methods=["POST"])
    def index() -> str | Response | tuple[Response, int]:
        args = request.json

        args = validate_args(args)
        if not args:
            return invalid_args()

        url = args.url
        solver = args.solver
        color_count = args.color_count
        raw = args.raw
        crop_box = args.crop_box

        try:
            timer = Timer()

            timer.start_timer("Image Reading")
            img = try_read_image_from_url(url)
            timer.end_timer()

            if crop_box:
                img = img.crop(tuple(crop_box))

            if solver == 0:
                timer.start_timer("Binary Solver - Total")
                solved = process_binary(img)
                timer.end_timer()

            else:
                timer.start_timer("Color Solver - Total")
                solved = process_color(img, color_count, timer)
                timer.end_timer()

            compound_paths, colors, width, height = solved

            timer.start_timer("Markup Creation")
            markup = generate_SVG_markup(compound_paths, colors, width, height)
            timer.end_timer()

            if raw:
                return markup

            timer.start_timer("Markup Upload")
            cuid_str = upload_markup(markup, S3_BUCKET)
            timer.end_timer()

            timer.start_timer("Bounds Creation")
            bounds = compound_paths_bounds(compound_paths)
            timer.end_timer()

            app.logger.info(timer.timelog())

            return jsonify(
                {
                    "success": True,
                    "objectId": cuid_str,
                    "info": {
                        "bounds": bounds,
                        "image_width": width,
                        "image_height": height,
                    },
                },
            )

        except Exception as e:
            app.logger.error(e)
            return jsonify({"success": False, "error": "INTERNAL_SERVER_ERROR"}), 500

    @app.route("/health", methods=["GET"])
    def healthcheck() -> tuple[Response, int]:
        return (
            jsonify(
                {
                    "success": True,
                },
            ),
            200,
        )

    @app.route("/test-error", methods=["GET"])
    def test_error() -> NoReturn:
        raise Exception("Test Error")

    app.logger.info(
        f"Vectorizing server running on port: {PORT}, environment: {PYTHON_ENV}",
    )
    if SENTRY_DSN:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            traces_sample_rate=0.1,
            environment=PYTHON_ENV,
        )
    return app
