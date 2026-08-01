"""The error envelope every API failure is reported in.

docs/api/conventions.md fixes the shape and the rules: a stable machine-readable
`code`, a message safe for a learner or developer, optional structured
`details`, and never a stack trace, a raw database error, or a secret.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.application.use_cases.read_curriculum import ReadCurriculum
from app.composition.app_factory import create_app
from tests.api.conftest import install_reader

CURRICULUM = "/api/v1/curriculum"


class UnreachableStore(Exception):
    """Stands in for a failure the API never anticipated, such as a dead database."""


class FailingRepository:
    """A repository whose every read fails, to exercise the unhandled path."""

    def count_learning_programs(self) -> int:
        raise UnreachableStore("connection to server at 'db' failed: password authentication")

    def list_learning_programs(self, *, limit: int, offset: int):
        raise UnreachableStore("connection to server at 'db' failed: password authentication")


@pytest.fixture
def failing_client():
    """A client whose curriculum reads raise, with server exceptions not re-raised."""
    app = create_app()
    install_reader(app, lambda: ReadCurriculum(FailingRepository()))
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_not_found_uses_the_documented_envelope(curriculum_client):
    body = curriculum_client.get(f"{CURRICULUM}/programs/{uuid.uuid4()}").json()

    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == "resource_not_found"


def test_an_unrouted_path_reports_a_message_a_reader_can_act_on(curriculum_client):
    """Starlette's bare `Not Found` is a status name, not an explanation."""
    body = curriculum_client.get("/api/v1/does-not-exist").json()

    assert body["error"]["code"] == "resource_not_found"
    assert body["error"]["message"] == "The requested resource was not found."


def test_an_unsupported_method_reports_its_own_code(curriculum_client):
    response = curriculum_client.post(f"{CURRICULUM}/programs")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_validation_failure_reports_the_offending_field_and_rule(curriculum_client):
    body = curriculum_client.get(f"{CURRICULUM}/programs?limit=0").json()

    assert body["error"]["code"] == "validation_error"
    detail = body["error"]["details"][0]
    assert detail["field"] == "query.limit"
    assert detail["type"] == "greater_than_equal"
    assert detail["message"]


def test_validation_details_do_not_echo_the_rejected_input(curriculum_client):
    """Pydantic reports the offending value; a response repeating it is one more copy."""
    detail = curriculum_client.get(f"{CURRICULUM}/programs?limit=0").json()["error"]["details"][0]

    assert set(detail) == {"field", "message", "type"}


def test_an_unhandled_failure_returns_a_safe_five_hundred(failing_client):
    response = failing_client.get(f"{CURRICULUM}/programs")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "An unexpected error occurred.",
            "details": [],
        }
    }


def test_an_unhandled_failure_leaks_no_internal_detail(failing_client):
    body = failing_client.get(f"{CURRICULUM}/programs").text

    assert "password" not in body
    assert "Traceback" not in body
    assert "UnreachableStore" not in body


def test_the_operational_endpoint_keeps_its_flat_success_body(curriculum_client):
    """OPS-001 is exempt from the envelope; registering handlers must not change that."""
    assert curriculum_client.get("/health").json() == {"status": "ok"}
