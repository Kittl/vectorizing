import json
import logging
import os
import sentry_sdk
from s3 import upload_markup
from bounds import get_bounds
from flask import Flask, request, jsonify
from gevent.pywsgi import WSGIServer
from environ import check_environment_variables
from read import ReadError, ChannelCountError, SizeError
from markup import build_markup
from process_binary import process as process_binary, DEFAULTS as PROCESS_DEFAULTS
from logging.config import dictConfig

# Set up Flask logging to STDOUT
dictConfig({
    'version': 1,
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://sys.stdout',
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})


(
    PORT, 
    VECTORIZING_S3_BUCKET, 
    AWS_ACCESS_KEY_ID, 
    AWS_SECRET_ACCESS_KEY,
) = check_environment_variables()

app = Flask(__name__)

@app.route('/', methods = ['POST'])
def process():

    content_type = request.headers['Content-Type']

    if content_type == 'application/json':
        args = request.json
    else:
        args = request.form
        
    if not 'url' in args:
        return jsonify({
            "success": False,
            "error": "INVALID_PARAMETERS"
        }), 400

    url = args.get('url')
    
    thresholding_method = args.get(
        'thresholding_method', 
        PROCESS_DEFAULTS['thresholding_method']
    )

    try:
        traced_bitmaps, colors, img_width, img_height = process_binary(url, thresholding_method)

        markup = build_markup(
            traced_bitmaps,
            colors,
            img_width,
            img_height,
        )

        bounds = get_bounds(traced_bitmaps)
        cuid_str = upload_markup(markup, VECTORIZING_S3_BUCKET)
        app.logger.info(f'Generated objectId {cuid_str}')
        return jsonify({ 
            'success': True,
            'objectId': cuid_str, 
            'info': {
                'bounds': bounds,
                'image_width': img_width,
                'image_height': img_height
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

if __name__ == '__main__':
    app.logger.info(f'Vectorizing server running on port: {PORT}')
    if "SENTRY_DSN" in os.environ:
        sentry_sdk.init(
            dsn=os.environ.get("SENTRY_DSN"),
            traces_sample_rate=0.1
        )
    http_server = WSGIServer(('0.0.0.0', PORT), app)
    http_server.serve_forever()