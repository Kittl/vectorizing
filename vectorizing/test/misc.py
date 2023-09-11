import os
import sys

from vectorizing.server.s3 import get_object_url, upload_file
from vectorizing.server.env import get_optional

S3_BUCKET = get_optional()[1]
IMAGES_PATH_PREFIX = 'images'

# Gets url to image. Uploads it to S3 first, if not uploaded already
def get_image_url(image_name):
    object_url = get_object_url(image_name, S3_BUCKET)
    print('OBJECT -===================', file = sys.stderr)
    print(object_url, file = sys.stderr)

    if object_url:
        return object_url
    
    return upload_file('vectorizing/test/' + os.path.join(IMAGES_PATH_PREFIX, image_name), S3_BUCKET, image_name)

def read_svg_file(path_to_file):
    f = open(path_to_file, 'r')
    content = f.read()
    f.close()
    return content

def write_svg_file(path_to_file, content):
    f = open(path_to_file, 'w')
    f.write(content)
    f.close()