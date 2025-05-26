import os
import sentry_sdk
from types import SimpleNamespace
from flask import Flask, request, jsonify

from vectorizing.server.timer import Timer
from vectorizing.server.logs import setup_logs
from vectorizing.server.s3 import upload_markup
from vectorizing.svg.markup import create_markup
from vectorizing.util.read import try_read_image_from_url
from vectorizing.server.env import get_required, get_optional
from vectorizing.solvers.color.ColorSolver import ColorSolver
from vectorizing.solvers.binary.BinarySolver import BinarySolver
from vectorizing.geometry.bounds import compound_path_list_bounds

# 0 -> BinarySolver
# 1 -> ColorSolver
SOLVERS = [0, 1]
DEFAULT_SOLVER = 0
PYTHON_ENV = os.getenv("PYTHON_ENV", "development")

(
    PORT,
    S3_BUCKET,
) = get_required()

(
    SENTRY_DSN,
    S3_TEST_BUCKET
) = get_optional()

setup_logs()

def process_binary(img):
    solver = BinarySolver(img)
    return solver.solve()

def process_color(img, color_count, tolerance, timer):
    solver = ColorSolver(img, color_count, tolerance, timer)
    return solver.solve()

def validate_args(args):
    if not 'url' in args:
        return False

    solver = args.get('solver', DEFAULT_SOLVER)
    if not solver in SOLVERS:
        return False

    box = args.get('crop_box')
    if box:
        if len(box) != 4:
            return False

        only_numbers = all([isinstance(item, int) for item in box])
        if not only_numbers:
            return False

    tolerance = args.get("tolerance")
    if tolerance is not None and tolerance < 0:
        return False
    
    return SimpleNamespace(
        crop_box=box,
        solver=solver,
        url=args.get("url"),
        raw=args.get("raw"),
        color_count=args.get("color_count"),
        tolerance=args.get("tolerance"),
    )

def invalid_args():
    return jsonify({
        "success": False,
        "error": "INVALID_PARAMETERS"
    }), 400

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.debug = PYTHON_ENV == 'development'

    @app.route('/', methods = ['POST'])
    def index():
        args = request.json

        args = validate_args(args)
        if not args:
            return invalid_args()

        url = args.url
        solver = args.solver
        color_count = args.color_count
        raw = args.raw
        crop_box = args.crop_box
        tolerance = args.tolerance

        if tolerance is None:
            tolerance = 0.2

        try:
            timer = Timer()

            timer.start_timer('Image Reading')
            img = try_read_image_from_url(url)
            timer.end_timer()

            if crop_box:
                img = img.crop(tuple(crop_box))

            if solver == 0:
                timer.start_timer('Binary Solver - Total')
                solved = process_binary(img)
                timer.end_timer()

            else:
                timer.start_timer('Color Solver - Total')
                solved = process_color(img, color_count, tolerance, timer)
                timer.end_timer()

            compound_paths, colors, width, height = solved

            timer.start_timer('Markup Creation')
            markup = create_markup(compound_paths, colors, width, height)
            timer.end_timer()

            if raw:
                return markup

            timer.start_timer('Markup Upload')
            cuid_str = upload_markup(markup, S3_BUCKET)
            timer.end_timer()

            timer.start_timer('Bounds Creation')
            bounds = compound_path_list_bounds(compound_paths, tolerance)
            timer.end_timer()

            app.logger.info(timer.timelog())

            return jsonify({
                'success': True,
                'objectId': cuid_str,
                'info': {
                    'bounds': bounds.to_dict(),
                    'image_width': width,
                    'image_height': height
                }
            })

        except (Exception) as e:
            app.logger.error(e)
            return jsonify({
                "success": False,
                "error": "INTERNAL_SERVER_ERROR"
            }), 500

    @app.route('/health', methods = ['GET'])
    def healthcheck():
        return jsonify({
            "success": True,
        }), 200

    @app.route('/test-error', methods = ['GET'])
    def test_error():
        raise Exception('Test Error')

    app.logger.info(f'Vectorizing server running on port: {PORT}, environment: {PYTHON_ENV}')
    if SENTRY_DSN:
        sentry_sdk.init(
            dsn = SENTRY_DSN,
            traces_sample_rate = 0.1,
            environment = PYTHON_ENV,
        )
    return app
