import json
from s3 import upload_markup
from flask import Flask, request
from gevent.pywsgi import WSGIServer
from environ import check_environment_variables
from read import ReadError, ChannelCountError, SizeError
from markup import build_markup, DEFAULTS as MARKUP_DEFAULTS
from process_binary import process as process_binary, DEFAULTS as PROCESS_DEFAULTS

(
    PORT, 
    VECTORIZING_S3_BUCKET, 
    AWS_ACCESS_KEY_ID, 
    AWS_SECRET_ACCESS_KEY
) = check_environment_variables()

app = Flask(__name__)

@app.route('/', methods = ['POST'])
def process():

    args = request.json
    
    if not 'url' in args:
        return 'Image URL not provided!', 400

    url = args.get('url')
    thresholding_method = args.get('thresholding_method', PROCESS_DEFAULTS['thresholding_method'])
    include_bounds = args.get('include_bounds', MARKUP_DEFAULTS['include_bounds'])

    try:
        traced_bitmaps, colors, img_width, img_height = process_binary(url, thresholding_method)

        markup = build_markup(
            traced_bitmaps,
            colors,
            img_width,
            img_height,
            include_bounds
        )
        
        cuid_str = upload_markup(markup, VECTORIZING_S3_BUCKET)
        return json.dumps({ 'objectId': cuid_str })
    
    except (ReadError, ChannelCountError, SizeError) as e:
        return str(e), 400

@app.route('/health', methods = ['GET'])
def healthcheck():
    return "OK"

if __name__ == '__main__':
    print(f'Vectorizing server running on port: {PORT}')
    http_server = WSGIServer(('0.0.0.0', PORT), app)
    http_server.serve_forever()