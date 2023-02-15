import os
from flask import Flask, request
from process_binary import process as process_binary
from markup import build_markup
from read import ReadError, ChannelCountError, SizeError
import boto3
import cuid
import json
import check_variables

check_variables(); # Halt if the required environment variables are not defined

app = Flask(__name__)

NO_URL_ERROR = 'Image URL not provided.'
PORT = os.environ['PORT']
S3_UPLOADS_BUCKET = os.environ['VECTORIZING_S3_BUCKET']
S3 = boto3.client("s3")

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
        cuidStr = cuid.cuid()
        S3.put_object(
            Body=markup.encode('utf-8'),
            Bucket=S3_UPLOADS_BUCKET,
            Key=cuidStr,
            ContentType="image/svg+xml",
        )
        return json.dumps({ "objectId": cuidStr })
    
    except (ReadError, ChannelCountError, SizeError) as e:
        return str(e), 400

@app.route('/health', methods = ['GET'])
def healthcheck():
    return "OK"

print(f"Vectorizing running in port {PORT}")
app.run(host='0.0.0.0', port=PORT)