"""Shared pytest fixtures for the LearnFlow backend test suite."""

import pytest
from fastapi.testclient import TestClient

from app.composition.app_factory import create_app


@pytest.fixture
def client() -> TestClient:
    """Return a test client bound to a freshly wired application instance.

    Building through the factory keeps tests exercising the same wiring path the
    running application uses.
    """
    return TestClient(create_app())
