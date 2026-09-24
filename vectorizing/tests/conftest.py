"""Provide an HTTP client isolated from the application's S3 bucket."""

import os

import pytest
from flask.testing import FlaskClient

import vectorizing


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> FlaskClient:
    """Route test uploads to a required, separate bucket and enable Flask testing."""
    test_bucket = os.getenv("S3_TEST_BUCKET")
    if not test_bucket:
        pytest.fail("S3_TEST_BUCKET must be set")
    if test_bucket == os.environ.get("S3_BUCKET"):
        pytest.fail("S3_TEST_BUCKET must differ from S3_BUCKET")

    monkeypatch.setattr(vectorizing, "S3_BUCKET", test_bucket)
    app = vectorizing.create_app()
    app.config.update({"TESTING": True})
    return app.test_client()
