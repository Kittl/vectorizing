"""Read and cast the application's ordered environment settings."""

import os

REQUIRED_ENVIRONMENT_VARIABLES = {"PORT": int, "S3_BUCKET": str}

OPTIONAL_ENVIRONMENT_VARIABLES = {"SENTRY_DSN": str, "S3_TEST_BUCKET": str}


class VariableNotDefinedException(Exception):
    """Signal that at least one required environment setting is missing."""


def get_required() -> list[int | str]:
    """Return port and bucket, raising if either required setting is missing."""
    missing_required = any(
        [key not in os.environ for key in REQUIRED_ENVIRONMENT_VARIABLES],
    )

    if missing_required:
        raise VariableNotDefinedException()

    return [
        cast(os.environ[key]) for key, cast in REQUIRED_ENVIRONMENT_VARIABLES.items()
    ]


def get_optional() -> list[str | None]:
    """Return Sentry DSN and test bucket in order, using None for unset values."""
    return [
        cast(os.environ[key]) if key in os.environ else None
        for key, cast in OPTIONAL_ENVIRONMENT_VARIABLES.items()
    ]
