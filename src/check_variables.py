import os
import sys

REQUIRED_ENVIRONMENT_VARIABLES=['PORT', 'VECTORIZING_S3_BUCKET', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY'];

class VariableNotDefinedException(Exception):
    pass

def check_variables():
    for env in REQUIRED_ENVIRONMENT_VARIABLES:
        if not os.environ.get(env):
            raise VariableNotDefinedException(env);

sys.modules[__name__] = check_variables