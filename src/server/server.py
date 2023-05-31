import os
import sentry_sdk
from types import SimpleNamespace
from gevent.pywsgi import WSGIServer
from flask import Flask, request, jsonify

from server.logs import setup_logs
from server.s3 import upload_markup
from svg.markup import create_markup
from util.read import try_read_image_from_url
from server.env import get_required, get_optional
from solvers.color.ColorSolver import ColorSolver
from solvers.binary.BinarySolver import BinarySolver
from geometry.bounds import compound_path_list_bounds

# 0 -> BinarySolver
# 1 -> ColorSolver
SOLVERS = [0, 1]
DEFAULT_SOLVER = 1

(
    PORT, 
    S3_BUCKET, 
    AWS_ACCESS_KEY_ID, 
    AWS_SECRET_ACCESS_KEY,
) = get_required()

(
    SENTRY_DSN,
    DEV_ENV
) = get_optional()

setup_logs()

def process_binary(img):
    solver = BinarySolver(img)
    return solver.solve()

def process_color(img, color_count):
    solver = ColorSolver(img, color_count)
    return solver.solve()

def validate_args(args):
    if not 'url' in args:
        return False
    
    solver = args.get('solver', DEFAULT_SOLVER)
    if not solver in SOLVERS:
        return False
    
    return SimpleNamespace(
        solver = solver,
        url = args.get('url'),
        raw = args.get('raw'),
        color_count = args.get('color_count')
    )

def invalid_args():
    return jsonify({
        "success": False,
        "error": "INVALID_PARAMETERS"
    }), 400
    
def create_server():
    server = Flask(__name__)
    server.debug = DEV_ENV

    @server.route('/', methods = ['POST'])
    def index():
        args = request.json
        
        args = validate_args(args)
        if not args:
            return invalid_args()

        url = args.url
        solver = args.solver
        color_count = args.color_count
        raw = args.raw

        try:
            img = try_read_image_from_url(url)
    
            if solver == 0:
                solved = process_binary(img)
            
            else:
                solved = process_color(img, color_count)

            compound_paths, colors, width, height = solved
            markup = create_markup(compound_paths, colors, width, height)

            if raw:
                return markup

            cuid_str = upload_markup(markup, S3_BUCKET)
            bounds = compound_path_list_bounds(compound_paths)
            
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
            server.logger.error(e)
            return jsonify({
                "success": False,
                "error": "INTERNAL_SERVER_ERROR"
            }), 500

    return server    
    
def serve_forever():
    server = create_server()
    server.logger.info(f'Vectorizing server running on port: {PORT}')
    
    if SENTRY_DSN:
        sentry_sdk.init(
            dsn = SENTRY_DSN,
            traces_sample_rate = 0.1
        )
    
    http_server = WSGIServer(('0.0.0.0', PORT), server)
    http_server.serve_forever()