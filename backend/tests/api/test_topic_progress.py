"""API tests for the topic-progress endpoints (PRG-002, PRG-004).

They exercise the documented contract over the real application factory: the
`data` envelope, the `pagination` block, the error envelope and its codes, and
the rejections that name the offending field. The database counterpart is
tests/integration/test_topic_progress_api.py.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.application.use_cases.manage_topic_progress import LEARNING_STAGES
from tests.api.conftest import Progress
from tests.unit.fake_learner_repository import learner

PROGRESS_PATH = "/api/v1/progress/topics"


def record(client: TestClient, topic_id: uuid.UUID | str, stage: str = "practice_ready"):
    return client.patch(f"{PROGRESS_PATH}/{topic_id}", json={"learning_stage": stage})


# -- PRG-004: recording a stage --------------------------------------------


def test_recording_a_stage_returns_it_under_the_data_envelope(
    progress_client: TestClient, progress: Progress
):
    response = record(progress_client, progress.trackable.id, "building_foundation")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["learning_stage"] == "building_foundation"
    assert data["stage_source"] == "learner"
    assert data["learner_id"] == str(progress.learner.id)
    assert data["topic"]["id"] == str(progress.trackable.id)
    assert data["topic"]["name"] == "CPU scheduling"
    assert data["topic"]["curriculum_version_id"] == str(progress.curriculum_version_id)


@pytest.mark.parametrize("stage", LEARNING_STAGES)
def test_every_approved_stage_is_accepted_over_http(
    progress_client: TestClient, progress: Progress, stage: str
):
    response = record(progress_client, progress.trackable.id, stage)

    assert response.status_code == 200
    assert response.json()["data"]["learning_stage"] == stage


def test_a_second_request_updates_the_stage_rather_than_adding_a_record(
    progress_client: TestClient, progress: Progress
):
    record(progress_client, progress.trackable.id, "building_foundation")
    response = record(progress_client, progress.trackable.id, "practice_ready")

    assert response.status_code == 200
    assert response.json()["data"]["learning_stage"] == "practice_ready"
    assert len(progress.progress.records) == 1


def test_repeating_the_same_stage_succeeds(progress_client: TestClient, progress: Progress):
    """A resubmitted form must not fail on its second attempt."""
    record(progress_client, progress.trackable.id, "practice_ready")
    response = record(progress_client, progress.trackable.id, "practice_ready")

    assert response.status_code == 200
    assert len(progress.progress.records) == 1


def test_an_unknown_stage_is_a_validation_error_naming_the_field(
    progress_client: TestClient, progress: Progress
):
    response = record(progress_client, progress.trackable.id, "mastered")

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["field"] == "body.learning_stage"
    assert error["details"][0]["type"] == "unknown_learning_stage"


def test_the_rejected_stage_is_not_echoed_back(progress_client: TestClient, progress: Progress):
    """`details` never carries the rejected input (docs/api/conventions.md).

    The message names the accepted values instead, which is what a caller needs.
    """
    response = record(progress_client, progress.trackable.id, "definitely-not-a-stage")

    assert "definitely-not-a-stage" not in response.text


def test_a_grouping_topic_is_refused_and_names_the_path_segment(
    progress_client: TestClient, progress: Progress
):
    response = record(progress_client, progress.grouping.id, "practice_ready")

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["field"] == "path.topic_id"
    assert error["details"][0]["type"] == "topic_not_trackable"


def test_an_unstored_topic_is_reported_as_not_found(progress_client: TestClient):
    response = record(progress_client, uuid.uuid4(), "practice_ready")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_a_topic_id_that_is_not_a_uuid_is_a_validation_error(progress_client: TestClient):
    response = record(progress_client, "not-a-uuid")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_an_unknown_request_field_is_rejected(progress_client: TestClient, progress: Progress):
    """`extra="forbid"` is what keeps a hopeful `learner_id` from being sent and
    silently ignored."""
    response = progress_client.patch(
        f"{PROGRESS_PATH}/{progress.trackable.id}",
        json={"learning_stage": "practice_ready", "learner_id": str(uuid.uuid4())},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_a_null_stage_is_rejected_rather_than_clearing_the_record(
    progress_client: TestClient, progress: Progress
):
    """A stage always holds a value, so null cannot mean "remove it". A learner
    who has changed their mind sets `not_explored`."""
    response = progress_client.patch(
        f"{PROGRESS_PATH}/{progress.trackable.id}", json={"learning_stage": None}
    )

    assert response.status_code == 422


def test_recording_before_setup_has_created_a_learner_is_a_conflict(
    progress_client: TestClient, progress: Progress
):
    progress.learners.learners.clear()

    response = record(progress_client, progress.trackable.id, "practice_ready")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_recording_with_more_than_one_learner_stored_is_a_conflict(
    progress_client: TestClient, progress: Progress
):
    progress.learners.learners.append(learner())

    response = record(progress_client, progress.trackable.id, "practice_ready")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_neither_endpoint_exposes_a_learner_id_parameter(progress_client: TestClient):
    """The effective learner is resolved server-side, so no request can address
    another learner's records (docs/api/conventions.md). Checked against the
    published schema rather than one hand-written URL, so a parameter added later
    is caught wherever it appears."""
    schema = progress_client.get("/openapi.json").json()
    operations = [
        operation
        for path, methods in schema["paths"].items()
        if path.startswith(PROGRESS_PATH)
        for operation in methods.values()
    ]

    assert operations
    names = {
        parameter["name"]
        for operation in operations
        for parameter in operation.get("parameters", [])
    }
    assert "learner_id" not in names


# -- PRG-002: listing recorded progress ------------------------------------


def test_listing_returns_the_data_array_and_pagination_block(progress_client: TestClient):
    response = progress_client.get(PROGRESS_PATH)

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == []
    assert body["pagination"] == {"limit": 25, "offset": 0, "total": 0}


def test_a_recorded_stage_reads_back(progress_client: TestClient, progress: Progress):
    record(progress_client, progress.trackable.id, "developing_confidence")

    body = progress_client.get(PROGRESS_PATH).json()

    assert body["pagination"]["total"] == 1
    assert body["data"][0]["learning_stage"] == "developing_confidence"
    assert body["data"][0]["topic"]["name"] == "CPU scheduling"


def test_listing_can_be_restricted_to_one_curriculum_version(
    progress_client: TestClient, progress: Progress
):
    record(progress_client, progress.trackable.id, "practice_ready")

    matching = progress_client.get(
        PROGRESS_PATH, params={"curriculum_version_id": str(progress.curriculum_version_id)}
    )
    other = progress_client.get(PROGRESS_PATH, params={"curriculum_version_id": str(uuid.uuid4())})

    assert matching.json()["pagination"]["total"] == 1
    assert other.json()["pagination"]["total"] == 0
    assert other.json()["data"] == []


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"curriculum_version_id": "not-a-uuid"}],
)
def test_a_window_outside_the_documented_bounds_is_rejected(
    progress_client: TestClient, params: dict[str, object]
):
    response = progress_client.get(PROGRESS_PATH, params=params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_listing_with_more_than_one_learner_stored_is_a_conflict(
    progress_client: TestClient, progress: Progress
):
    progress.learners.learners.append(learner())

    response = progress_client.get(PROGRESS_PATH)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_listing_before_setup_has_created_a_learner_is_an_empty_page(
    progress_client: TestClient, progress: Progress
):
    progress.learners.learners.clear()

    response = progress_client.get(PROGRESS_PATH)

    assert response.status_code == 200
    assert response.json()["data"] == []
