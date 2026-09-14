import os

import pytest

import vectorizing


@pytest.fixture()
def client(monkeypatch):
    test_bucket = os.environ["S3_TEST_BUCKET"]
    if test_bucket == os.environ.get("S3_BUCKET"):
        pytest.fail("S3_TEST_BUCKET must differ from S3_BUCKET")

    monkeypatch.setattr(vectorizing, "S3_BUCKET", test_bucket)
    app = vectorizing.create_app()
    app.config.update({"TESTING": True})
    return app.test_client()
