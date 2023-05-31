import os

REQUIRED_ENVIRONMENT_VARIABLES={
    'PORT': int,
    'S3_BUCKET': str,
    'AWS_ACCESS_KEY_ID': str,
    'AWS_SECRET_ACCESS_KEY': str
}

print(REQUIRED_ENVIRONMENT_VARIABLES)

class VariableNotDefinedException(Exception):
    pass

def check_environment_variables():
    for key in REQUIRED_ENVIRONMENT_VARIABLES:
        if not os.environ.get(key):
            raise VariableNotDefinedException(key)

    return [cast(os.environ[key]) for key, cast in REQUIRED_ENVIRONMENT_VARIABLES.items()]