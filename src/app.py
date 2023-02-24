import json
from flask import Flask, request
from markup import build_markup
from gevent.pywsgi import WSGIServer

from s3 import upload_markup
from read import ReadError, ChannelCountError, SizeError
from environ import check_environment_variables
from process_binary import process as process_binary

(
    PORT, 
    VECTORIZING_S3_BUCKET, 
    AWS_ACCESS_KEY_ID, 
    AWS_SECRET_ACCESS_KEY
) = check_environment_variables()

app = Flask(__name__)

@app.route('/', methods = ['POST'])
def process():

    args = request.form
    
    if not 'url' in args:
        return 'Image URL not provided!', 400

    url = args.get('url')

    try:
        traced_bitmaps, colors, img_width, img_height = process_binary(url)

        markup = build_markup(
            traced_bitmaps,
            colors,
            img_width,
            img_height
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