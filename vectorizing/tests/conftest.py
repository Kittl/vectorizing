import pytest
from vectorizing import create_app

@pytest.fixture()
def client():
    app = create_app()
    app.config.update({ "TESTING": True })
    return app.test_client()
