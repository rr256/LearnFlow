"""API tests for the learner onboarding endpoints (LRN-001, LRN-002, EXM-001, GOAL-001 to GOAL-004).

They check the public contract: the `data` envelope, `snake_case` fields, UUID
string identifiers, the pagination block, the documented error codes, and the
fields each response does and does not expose.
"""

import uuid

LEARNER = "/api/v1/learner"
SCHEDULES = "/api/v1/examination-schedules"
GOALS = "/api/v1/study-goals"


def create_profile(client, **body):
    return client.patch(f"{LEARNER}/profile", json=body or {"display_name": "Asha"})


# -- LRN-001: read the profile ---------------------------------------------


def test_reading_the_profile_before_setup_returns_a_null_data_envelope(onboarding_client):
    """A fresh installation is a real state, not a 404 a client must special-case."""
    response = onboarding_client.get(f"{LEARNER}/profile")

    assert response.status_code == 200
    assert response.json() == {"data": None}


def test_reading_the_profile_returns_the_stored_learner(onboarding_client):
    create_profile(onboarding_client, display_name="Asha", timezone="Europe/Lisbon")

    body = onboarding_client.get(f"{LEARNER}/profile").json()

    assert body["data"]["display_name"] == "Asha"
    assert body["data"]["timezone"] == "Europe/Lisbon"


def test_the_profile_exposes_no_persistence_detail(onboarding_client):
    """A response is a public contract, never a rendering of a table row."""
    create_profile(onboarding_client)

    profile = onboarding_client.get(f"{LEARNER}/profile").json()["data"]

    assert set(profile) == {"id", "display_name", "timezone"}


def test_reading_the_profile_creates_no_learner(onboarding_client, onboarding):
    onboarding_client.get(f"{LEARNER}/profile")

    assert onboarding.learners.learners == []


def test_more_than_one_stored_learner_is_reported_as_a_conflict(onboarding_client, onboarding):
    create_profile(onboarding_client, display_name="Asha")
    create_profile(onboarding_client, display_name="Ravi")
    onboarding.learners.add_learner(onboarding.learners.learners[0])

    response = onboarding_client.get(f"{LEARNER}/profile")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


# -- LRN-002: update the profile -------------------------------------------


def test_updating_the_profile_creates_the_learner_on_first_use(onboarding_client, onboarding):
    response = create_profile(onboarding_client, display_name="Asha")

    assert response.status_code == 200
    assert len(onboarding.learners.learners) == 1


def test_a_created_learner_takes_the_configured_default_timezone(onboarding_client):
    body = create_profile(onboarding_client, display_name="Asha").json()

    assert body["data"]["timezone"] == "Asia/Kolkata"


def test_updating_one_field_leaves_the_others_alone(onboarding_client):
    create_profile(onboarding_client, display_name="Asha", timezone="Europe/Lisbon")

    body = create_profile(onboarding_client, display_name="Asha Rao").json()

    assert body["data"]["timezone"] == "Europe/Lisbon"


def test_an_explicit_null_display_name_removes_it(onboarding_client):
    create_profile(onboarding_client, display_name="Asha")

    body = onboarding_client.patch(f"{LEARNER}/profile", json={"display_name": None}).json()

    assert body["data"]["display_name"] is None


def test_updating_rejects_an_unknown_timezone(onboarding_client):
    response = onboarding_client.patch(f"{LEARNER}/profile", json={"timezone": "Mars/Olympus_Mons"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_updating_rejects_a_null_timezone(onboarding_client):
    """A learner always has one, so null cannot mean "remove it"."""
    response = onboarding_client.patch(f"{LEARNER}/profile", json={"timezone": None})

    assert response.status_code == 422


def test_updating_rejects_an_empty_request(onboarding_client):
    response = onboarding_client.patch(f"{LEARNER}/profile", json={})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "body"


def test_updating_rejects_a_client_supplied_learner_id(onboarding_client):
    """A client must never choose whose profile it is writing."""
    response = onboarding_client.patch(
        f"{LEARNER}/profile", json={"display_name": "Asha", "learner_id": str(uuid.uuid4())}
    )

    assert response.status_code == 422


# -- EXM-001: list published examination schedules -------------------------


def test_listing_schedules_returns_them_under_the_collection_envelope(
    onboarding_client, onboarding
):
    body = onboarding_client.get(SCHEDULES).json()

    assert [item["id"] for item in body["data"]] == [str(onboarding.schedule.id)]
    assert body["pagination"] == {"limit": 25, "offset": 0, "total": 1}


def test_a_schedule_reports_the_examination_as_a_window(onboarding_client):
    schedule = onboarding_client.get(SCHEDULES).json()["data"][0]

    assert schedule["examination_window"] == {
        "starts_on": "2027-02-06",
        "ends_on": "2027-02-21",
    }


def test_a_schedule_reports_no_single_examination_date(onboarding_client):
    """Terminology forbids presenting a guess as the learner's paper day."""
    schedule = onboarding_client.get(SCHEDULES).json()["data"][0]

    assert "examination_date" not in schedule
    assert "exam_date" not in schedule


def test_a_schedule_carries_its_provenance_and_provisional_status(onboarding_client):
    schedule = onboarding_client.get(SCHEDULES).json()["data"][0]

    assert schedule["schedule_status"] == "provisional"
    assert schedule["organising_body"] == "IIT Madras"
    assert schedule["source_reference"] == "https://example.test/schedule"
    assert schedule["source_checked_on"] == "2026-08-01"


def test_a_schedule_reports_its_registration_deadlines(onboarding_client):
    """They are the nearest actionable dates a learner has; ADR-013."""
    schedule = onboarding_client.get(SCHEDULES).json()["data"][0]

    assert "registration" in {period["period_type"] for period in schedule["periods"]}


def test_filtering_schedules_by_an_unknown_program_returns_an_empty_page(onboarding_client):
    body = onboarding_client.get(f"{SCHEDULES}?learning_program_id={uuid.uuid4()}").json()

    assert body["data"] == []
    assert body["pagination"]["total"] == 0


def test_listing_schedules_rejects_a_window_outside_the_supported_bounds(onboarding_client):
    for query in ("limit=0", "limit=101", "offset=-1"):
        response = onboarding_client.get(f"{SCHEDULES}?{query}")

        assert response.status_code == 422, query
        assert response.json()["error"]["code"] == "validation_error"


# -- GOAL-001: create a study goal -----------------------------------------


def test_creating_a_goal_returns_201_with_the_data_envelope(onboarding_client, onboarding):
    create_profile(onboarding_client)

    response = onboarding_client.post(
        GOALS,
        json={
            "learning_program_id": str(onboarding.schedule.learning_program_id),
            "examination_schedule_id": str(onboarding.schedule.id),
        },
    )

    assert response.status_code == 201
    assert response.json()["data"]["status"] == "active"


def test_a_created_goal_reports_the_examination_window_and_its_source(
    onboarding_client, onboarding
):
    create_profile(onboarding_client)

    body = onboarding_client.post(
        GOALS,
        json={
            "learning_program_id": str(onboarding.schedule.learning_program_id),
            "examination_schedule_id": str(onboarding.schedule.id),
        },
    ).json()

    examination = body["data"]["examination"]
    assert examination["examination_window"]["starts_on"] == "2027-02-06"
    assert examination["schedule_status"] == "provisional"


def test_a_created_goal_names_the_program_and_curriculum_version(onboarding_client, onboarding):
    create_profile(onboarding_client)

    body = onboarding_client.post(
        GOALS,
        json={
            "learning_program_id": str(onboarding.schedule.learning_program_id),
            "target_date": "2027-01-31",
        },
    ).json()

    assert body["data"]["learning_program"]["code"] == "gate-cse"
    assert body["data"]["curriculum_version"]["version_label"] == "2027"


def test_creating_a_goal_rejects_a_request_aiming_at_nothing(onboarding_client, onboarding):
    create_profile(onboarding_client)

    response = onboarding_client.post(
        GOALS, json={"learning_program_id": str(onboarding.schedule.learning_program_id)}
    )

    assert response.status_code == 422
    fields = {detail["field"] for detail in response.json()["error"]["details"]}
    assert fields == {"body.examination_schedule_id", "body.target_date"}


def test_creating_a_goal_rejects_an_unknown_program(onboarding_client):
    create_profile(onboarding_client)

    response = onboarding_client.post(
        GOALS, json={"learning_program_id": str(uuid.uuid4()), "target_date": "2027-01-31"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "body.learning_program_id"


def test_creating_a_goal_before_a_learner_exists_is_a_conflict(onboarding_client, onboarding):
    response = onboarding_client.post(
        GOALS,
        json={
            "learning_program_id": str(onboarding.schedule.learning_program_id),
            "target_date": "2027-01-31",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_a_second_active_goal_for_the_same_program_is_a_conflict(onboarding_client, onboarding):
    create_profile(onboarding_client)
    body = {
        "learning_program_id": str(onboarding.schedule.learning_program_id),
        "target_date": "2027-01-31",
    }
    onboarding_client.post(GOALS, json=body)

    response = onboarding_client.post(GOALS, json=body)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_creating_a_goal_rejects_a_client_supplied_learner_id(onboarding_client, onboarding):
    create_profile(onboarding_client)

    response = onboarding_client.post(
        GOALS,
        json={
            "learning_program_id": str(onboarding.schedule.learning_program_id),
            "target_date": "2027-01-31",
            "learner_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 422


def test_creating_a_goal_rejects_a_client_chosen_curriculum_version(onboarding_client, onboarding):
    """A goal binds to the active version; a client cannot pick a retired one."""
    create_profile(onboarding_client)

    response = onboarding_client.post(
        GOALS,
        json={
            "learning_program_id": str(onboarding.schedule.learning_program_id),
            "target_date": "2027-01-31",
            "curriculum_version_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 422


# -- GOAL-002 and GOAL-003: read -------------------------------------------


def test_listing_goals_before_setup_returns_an_empty_page(onboarding_client):
    body = onboarding_client.get(GOALS).json()

    assert body["data"] == []
    assert body["pagination"] == {"limit": 25, "offset": 0, "total": 0}


def test_listing_goals_returns_the_learners_goals(onboarding_client, onboarding):
    create_profile(onboarding_client)
    created = onboarding_client.post(
        GOALS,
        json={
            "learning_program_id": str(onboarding.schedule.learning_program_id),
            "target_date": "2027-01-31",
        },
    ).json()["data"]

    body = onboarding_client.get(GOALS).json()

    assert [goal["id"] for goal in body["data"]] == [created["id"]]


def test_reading_one_goal_returns_it_under_the_data_envelope(onboarding_client, onboarding):
    create_profile(onboarding_client)
    created = onboarding_client.post(
        GOALS,
        json={
            "learning_program_id": str(onboarding.schedule.learning_program_id),
            "target_date": "2027-01-31",
        },
    ).json()["data"]

    body = onboarding_client.get(f"{GOALS}/{created['id']}").json()

    assert body["data"]["id"] == created["id"]


def test_reading_an_unknown_goal_returns_the_documented_not_found(onboarding_client):
    create_profile(onboarding_client)

    response = onboarding_client.get(f"{GOALS}/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_reading_a_goal_with_a_malformed_identifier_is_a_validation_error(onboarding_client):
    response = onboarding_client.get(f"{GOALS}/not-a-uuid")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_a_goal_exposes_no_persistence_detail(onboarding_client, onboarding):
    create_profile(onboarding_client)

    goal = onboarding_client.post(
        GOALS,
        json={
            "learning_program_id": str(onboarding.schedule.learning_program_id),
            "target_date": "2027-01-31",
        },
    ).json()["data"]

    assert set(goal) == {
        "id",
        "learner_id",
        "status",
        "target_date",
        "learning_program",
        "curriculum_version",
        "examination",
    }


# -- GOAL-004: update a study goal -----------------------------------------


def existing_goal(client, onboarding):
    create_profile(client)
    return client.post(
        GOALS,
        json={
            "learning_program_id": str(onboarding.schedule.learning_program_id),
            "examination_schedule_id": str(onboarding.schedule.id),
            "target_date": "2027-01-31",
        },
    ).json()["data"]


def test_updating_a_goal_changes_only_what_it_names(onboarding_client, onboarding):
    goal = existing_goal(onboarding_client, onboarding)

    body = onboarding_client.patch(f"{GOALS}/{goal['id']}", json={"status": "paused"}).json()

    assert body["data"]["status"] == "paused"
    assert body["data"]["target_date"] == "2027-01-31"


def test_an_explicit_null_target_date_clears_it(onboarding_client, onboarding):
    goal = existing_goal(onboarding_client, onboarding)

    body = onboarding_client.patch(f"{GOALS}/{goal['id']}", json={"target_date": None}).json()

    assert body["data"]["target_date"] is None
    assert body["data"]["examination"] is not None


def test_updating_refuses_to_leave_a_goal_aiming_at_nothing(onboarding_client, onboarding):
    goal = existing_goal(onboarding_client, onboarding)
    onboarding_client.patch(f"{GOALS}/{goal['id']}", json={"target_date": None})

    response = onboarding_client.patch(
        f"{GOALS}/{goal['id']}", json={"examination_schedule_id": None}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_updating_rejects_an_unknown_status(onboarding_client, onboarding):
    goal = existing_goal(onboarding_client, onboarding)

    response = onboarding_client.patch(f"{GOALS}/{goal['id']}", json={"status": "finished"})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "body.status"


def test_updating_a_goal_rejects_an_empty_request(onboarding_client, onboarding):
    goal = existing_goal(onboarding_client, onboarding)

    response = onboarding_client.patch(f"{GOALS}/{goal['id']}", json={})

    assert response.status_code == 422


def test_updating_rejects_planning_preferences(onboarding_client, onboarding):
    """The column does not exist, so the field would promise storage we have not got."""
    goal = existing_goal(onboarding_client, onboarding)

    response = onboarding_client.patch(
        f"{GOALS}/{goal['id']}", json={"planning_preferences": {"pace": "steady"}}
    )

    assert response.status_code == 422


def test_updating_an_unknown_goal_returns_the_documented_not_found(onboarding_client):
    create_profile(onboarding_client)

    response = onboarding_client.patch(f"{GOALS}/{uuid.uuid4()}", json={"status": "paused"})

    assert response.status_code == 404


# -- GOAL-005 is not implemented -------------------------------------------


def test_replacing_availability_is_not_served(onboarding_client, onboarding):
    """`availability_slots` does not exist; GOAL-005 waits on the day_of_week decision."""
    goal = existing_goal(onboarding_client, onboarding)

    response = onboarding_client.put(f"{GOALS}/{goal['id']}/availability", json={"slots": []})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
