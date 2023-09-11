from vectorizing.test.config import TESTS
from vectorizing.test.misc import get_image_url
import sys

import pytest
from vectorizing import create_app

app = create_app()
app.config.update({ "TESTING": True })

def test():
    print(TESTS.items(), file = sys.stderr)
    for image_name, request_params_list in TESTS.items():
        for request_params in request_params_list:
            image_test(image_name, request_params)
    assert False

def image_test(image_name, request_params):
    image_url = get_image_url(image_name)
    print('URL =========================', file = sys.stderr)
    print(image_url, file=sys.stderr)
    request_params = {
        'url': image_url,
        'solver': request_params.get('solver'),
        'color_count': request_params.get('color_count'),
        'raw': True
    }
    response = app.test_client().post('/', json = request_params).data
    print(response, file = sys.stderr)
