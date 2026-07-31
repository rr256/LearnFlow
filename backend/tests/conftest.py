"""Shared pytest fixtures for the LearnFlow backend test suite."""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.composition.app_factory import create_app

# A syntactically valid URL that is never connected to. Tests needing a real
# database live under tests/integration/ and read TEST_DATABASE_URL instead.
PLACEHOLDER_DATABASE_URL = "postgresql+psycopg://learnflow:learnflow@127.0.0.1:5432/learnflow"

# Set at import time, not in a fixture: `app/main.py` builds the application
# when it is imported, and DATABASE_URL has no default, so the variable must
# exist before pytest collects the test module that imports it. `setdefault`
# leaves a value from the environment alone.
#
# Creating an engine opens no connection, so a placeholder suffices for every
# test that does not execute SQL. Individual tests still override or delete the
# variable through `monkeypatch`, which restores it afterwards.
os.environ.setdefault("DATABASE_URL", PLACEHOLDER_DATABASE_URL)


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Return a test client bound to a freshly wired application instance.

    Building through the factory keeps tests exercising the same wiring path the
    running application uses. Entering the client as a context manager runs the
    lifespan, so startup and shutdown wiring is covered too.
    """
    with TestClient(create_app()) as test_client:
        yield test_client
