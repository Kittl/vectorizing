import os
from flask import Flask, request
from process_binary import process as process_binary
from markup import build_markup
from read import ReadError, ChannelCountError, SizeError

app = Flask(__name__)

NO_URL_ERROR = 'Image URL not provided.'
PORT = os.environ['PORT']

@app.route('/', methods = ['GET'])
def process():

    args = request.args
    
    if not 'url' in args:
        return NO_URL_ERROR, 400

    url = args.get('url')

    try:
        traced_bitmaps, colors, img_width, img_height = process_binary(url)
        markup = build_markup(
            traced_bitmaps,
            colors,
            img_width,
            img_height
        )
        
        return markup
    
    except (ReadError, ChannelCountError, SizeError) as e:
        return str(e), 400

@app.route('/health', methods = ['GET'])
def healthcheck():
    return "OK"

print(f"Vectorizing running in port {PORT}")
app.run(host='0.0.0.0', port=PORT)