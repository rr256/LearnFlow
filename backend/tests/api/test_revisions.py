"""Contract tests for the revision endpoints (REV-001 to REV-004).

These run over the real application factory and the real use case, with only the
repositories and the clock replaced, so they exercise routing, validation,
response mapping, and error mapping over the code the running backend uses. The
database counterpart is tests/integration/test_revision_api.py.

The learner finished work on one topic on 2026-08-13 and the clock reports
2026-08-20, so a revision scheduled with no recorded stage falls due exactly
today.
"""

import uuid

REVISIONS = "/api/v1/revisions"


def schedule(client):
    return client.post(f"{REVISIONS}/schedule")


def move(client, revision_id, status):
    return client.patch(f"{REVISIONS}/{revision_id}", json={"status": status})


def first_revision(client):
    return client.get(REVISIONS).json()["data"][0]


# -- scheduling ---------------------------------------------------------------


def test_scheduling_creates_a_revision_for_finished_work(revision_client):
    response = schedule(revision_client)

    assert response.status_code == 201
    data = response.json()["data"]
    assert len(data["created"]) == 1
    assert data["created"][0]["due_on"] == "2026-08-20"
    assert data["created"][0]["status"] == "due"


def test_a_scheduled_revision_names_its_topic_and_explains_itself(revision_client):
    created = schedule(revision_client).json()["data"]["created"][0]

    assert created["topic"]["name"] == "CPU scheduling"
    assert created["topic"]["subject_name"] == "Operating Systems"
    assert "CPU scheduling" in created["recommendation_reason"]


def test_the_run_reports_the_date_it_was_made_for(revision_client):
    assert schedule(revision_client).json()["data"]["scheduled_on"] == "2026-08-20"


def test_scheduling_takes_no_request_body(revision_client):
    """Everything it reads is already stored, so no caller can steer it."""
    assert revision_client.post(f"{REVISIONS}/schedule").status_code == 201


def test_asking_twice_creates_nothing_the_second_time(revision_client):
    schedule(revision_client)

    second = schedule(revision_client).json()["data"]

    assert second["created"] == []
    assert second["already_scheduled_topic_count"] == 1


def test_the_run_explains_what_it_left_alone(revision_client):
    schedule(revision_client)

    assert "already has a revision waiting" in schedule(revision_client).json()["data"]["reason"]


# -- listing ------------------------------------------------------------------


def test_a_learner_with_no_revisions_reads_an_empty_page(revision_client):
    body = revision_client.get(REVISIONS).json()

    assert body["data"] == []
    assert body["pagination"]["total"] == 0


def test_listing_returns_the_documented_envelope(revision_client):
    schedule(revision_client)

    body = revision_client.get(REVISIONS).json()

    assert set(body) == {"data", "pagination"}
    assert body["pagination"] == {"limit": 25, "offset": 0, "total": 1}


def test_a_revision_whose_day_has_arrived_reads_as_due(revision_client):
    schedule(revision_client)

    assert first_revision(revision_client)["is_due"] is True


def test_a_settled_revision_is_left_out_of_the_due_filter(revision_client):
    schedule(revision_client)
    move(revision_client, first_revision(revision_client)["id"], "skipped")

    body = revision_client.get(REVISIONS, params={"due_only": "true"}).json()

    assert body["pagination"]["total"] == 0


def test_an_unknown_status_filter_is_refused(revision_client):
    response = revision_client.get(REVISIONS, params={"status": "invented"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_a_page_beyond_the_documented_bounds_is_refused(revision_client):
    assert revision_client.get(REVISIONS, params={"limit": 0}).status_code == 422
    assert revision_client.get(REVISIONS, params={"offset": -1}).status_code == 422


# -- reading one --------------------------------------------------------------


def test_one_revision_reads_back_with_its_topic(revision_client):
    schedule(revision_client)
    revision_id = first_revision(revision_client)["id"]

    body = revision_client.get(f"{REVISIONS}/{revision_id}").json()

    assert body["data"]["id"] == revision_id
    assert body["data"]["topic"]["name"] == "CPU scheduling"


def test_an_unknown_revision_is_a_404(revision_client):
    response = revision_client.get(f"{REVISIONS}/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_an_identifier_that_is_not_a_uuid_is_a_422(revision_client):
    assert revision_client.get(f"{REVISIONS}/not-a-uuid").status_code == 422


# -- recording what happened --------------------------------------------------


def test_a_learner_may_complete_a_revision(revision_client):
    schedule(revision_client)
    revision_id = first_revision(revision_client)["id"]

    body = move(revision_client, revision_id, "completed").json()

    assert body["data"]["status"] == "completed"
    assert body["data"]["completed_at"] is not None


def test_a_learner_may_take_a_completion_back(revision_client):
    schedule(revision_client)
    revision_id = first_revision(revision_client)["id"]
    move(revision_client, revision_id, "completed")

    body = move(revision_client, revision_id, "due").json()

    assert body["data"]["status"] == "due"
    assert body["data"]["completed_at"] is None


def test_a_learner_may_skip_and_postpone_a_revision(revision_client):
    schedule(revision_client)
    revision_id = first_revision(revision_client)["id"]

    assert move(revision_client, revision_id, "skipped").json()["data"]["status"] == "skipped"
    assert move(revision_client, revision_id, "postponed").json()["data"]["status"] == "postponed"


def test_a_status_change_never_rewrites_the_due_date(revision_client):
    schedule(revision_client)
    before = first_revision(revision_client)
    move(revision_client, before["id"], "postponed")

    assert first_revision(revision_client)["due_on"] == before["due_on"]


def test_scheduled_is_not_a_status_a_learner_may_set(revision_client):
    schedule(revision_client)
    revision_id = first_revision(revision_client)["id"]

    response = move(revision_client, revision_id, "scheduled")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_an_unknown_status_is_refused(revision_client):
    schedule(revision_client)
    revision_id = first_revision(revision_client)["id"]

    assert move(revision_client, revision_id, "invented").status_code == 422


def test_a_body_carrying_an_unknown_field_is_refused(revision_client):
    """An unknown field is a 422 rather than being silently ignored."""
    schedule(revision_client)
    revision_id = first_revision(revision_client)["id"]

    response = revision_client.patch(
        f"{REVISIONS}/{revision_id}", json={"status": "completed", "due_on": "2026-09-01"}
    )

    assert response.status_code == 422


def test_no_request_accepts_a_learner_id(revision_client):
    """The effective learner is resolved server-side, per the identity assumption."""
    schedule(revision_client)
    revision_id = first_revision(revision_client)["id"]

    response = revision_client.patch(
        f"{REVISIONS}/{revision_id}", json={"status": "completed", "learner_id": str(uuid.uuid4())}
    )

    assert response.status_code == 422


def test_moving_an_unknown_revision_is_a_404(revision_client):
    assert move(revision_client, uuid.uuid4(), "completed").status_code == 404
