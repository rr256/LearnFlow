"""API tests for the learner setup endpoints (LRN-001, LRN-002, EXM-001, GOAL-001 to GOAL-005).

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
        "availability",
        "planning_preferences",
    }
    # A brand-new goal has no availability, and the week says so by being empty
    # rather than by being absent -- so a client needs no branch for a goal
    # created before GOAL-005 was ever called.
    assert goal["availability"] == {"slots": []}
    # The same for preferences: an object whose members are null, never a null
    # group, so no client needs a branch for a goal stored before they existed.
    assert goal["planning_preferences"] == {
        "preferred_session_minutes": None,
        "topic_sequencing": None,
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


def test_updating_an_unknown_goal_returns_the_documented_not_found(onboarding_client):
    create_profile(onboarding_client)

    response = onboarding_client.patch(f"{GOALS}/{uuid.uuid4()}", json={"status": "paused"})

    assert response.status_code == 404


# -- planning preferences, on GOAL-001 and GOAL-004 ------------------------


def preferences_of(client, goal_id):
    """The preferences currently stored, read back through GOAL-003."""
    return client.get(f"{GOALS}/{goal_id}").json()["data"]["planning_preferences"]


def test_creating_a_goal_stores_the_preferences_it_names(onboarding_client, onboarding):
    create_profile(onboarding_client)

    body = onboarding_client.post(
        GOALS,
        json={
            "learning_program_id": str(onboarding.schedule.learning_program_id),
            "target_date": "2027-01-31",
            "planning_preferences": {
                "preferred_session_minutes": 90,
                "topic_sequencing": "prerequisites_first",
            },
        },
    ).json()

    assert body["data"]["planning_preferences"] == {
        "preferred_session_minutes": 90,
        "topic_sequencing": "prerequisites_first",
    }
    assert preferences_of(onboarding_client, body["data"]["id"]) == {
        "preferred_session_minutes": 90,
        "topic_sequencing": "prerequisites_first",
    }


def test_a_preference_the_learner_left_out_is_unset_rather_than_defaulted(
    onboarding_client, onboarding
):
    """Nothing invents a preference. A planner meeting null picks its own default
    visibly, rather than reading a value nobody chose."""
    create_profile(onboarding_client)

    body = onboarding_client.post(
        GOALS,
        json={
            "learning_program_id": str(onboarding.schedule.learning_program_id),
            "target_date": "2027-01-31",
            "planning_preferences": {"topic_sequencing": "syllabus_order"},
        },
    ).json()

    assert body["data"]["planning_preferences"] == {
        "preferred_session_minutes": None,
        "topic_sequencing": "syllabus_order",
    }


def test_updating_preferences_replaces_the_whole_group(onboarding_client, onboarding):
    """A supplied group is the goal's preferences, not a patch over them: a form
    shows every preference at once, so a member it left out was cleared."""
    goal = existing_goal(onboarding_client, onboarding)
    onboarding_client.patch(
        f"{GOALS}/{goal['id']}",
        json={
            "planning_preferences": {
                "preferred_session_minutes": 90,
                "topic_sequencing": "syllabus_order",
            }
        },
    )

    body = onboarding_client.patch(
        f"{GOALS}/{goal['id']}",
        json={"planning_preferences": {"topic_sequencing": "prerequisites_first"}},
    ).json()

    assert body["data"]["planning_preferences"] == {
        "preferred_session_minutes": None,
        "topic_sequencing": "prerequisites_first",
    }


def test_an_update_that_does_not_name_preferences_leaves_them_alone(onboarding_client, onboarding):
    goal = existing_goal(onboarding_client, onboarding)
    onboarding_client.patch(
        f"{GOALS}/{goal['id']}",
        json={"planning_preferences": {"preferred_session_minutes": 45}},
    )

    body = onboarding_client.patch(f"{GOALS}/{goal['id']}", json={"status": "paused"}).json()

    assert body["data"]["planning_preferences"]["preferred_session_minutes"] == 45


def test_an_explicit_null_preference_group_clears_every_preference(onboarding_client, onboarding):
    goal = existing_goal(onboarding_client, onboarding)
    onboarding_client.patch(
        f"{GOALS}/{goal['id']}",
        json={
            "planning_preferences": {
                "preferred_session_minutes": 45,
                "topic_sequencing": "syllabus_order",
            }
        },
    )

    body = onboarding_client.patch(
        f"{GOALS}/{goal['id']}", json={"planning_preferences": None}
    ).json()

    assert body["data"]["planning_preferences"] == {
        "preferred_session_minutes": None,
        "topic_sequencing": None,
    }


def test_an_empty_preference_group_clears_them_as_a_null_does(onboarding_client, onboarding):
    """Replacing with nothing and clearing are the same request, so no client has
    to know which spelling the API prefers."""
    goal = existing_goal(onboarding_client, onboarding)
    onboarding_client.patch(
        f"{GOALS}/{goal['id']}",
        json={"planning_preferences": {"preferred_session_minutes": 45}},
    )

    response = onboarding_client.patch(f"{GOALS}/{goal['id']}", json={"planning_preferences": {}})

    assert response.json()["data"]["planning_preferences"]["preferred_session_minutes"] is None


def test_saving_the_preferences_already_stored_is_accepted(onboarding_client, onboarding):
    """A repeated form submission must not fail on its second attempt, which is
    the rule GOAL-005 and PRG-004 already follow."""
    goal = existing_goal(onboarding_client, onboarding)
    group = {"planning_preferences": {"preferred_session_minutes": 60}}
    onboarding_client.patch(f"{GOALS}/{goal['id']}", json=group)

    response = onboarding_client.patch(f"{GOALS}/{goal['id']}", json=group)

    assert response.status_code == 200
    assert response.json()["data"]["planning_preferences"]["preferred_session_minutes"] == 60


def test_updating_rejects_an_unknown_topic_sequencing(onboarding_client, onboarding):
    goal = existing_goal(onboarding_client, onboarding)

    response = onboarding_client.patch(
        f"{GOALS}/{goal['id']}",
        json={"planning_preferences": {"topic_sequencing": "alphabetical_order"}},
    )

    assert response.status_code == 422
    detail = response.json()["error"]["details"][0]
    assert detail["field"] == "body.planning_preferences.topic_sequencing"
    assert detail["type"] == "unknown_topic_sequencing"
    # The rejected value is never echoed back; the choices available are enough.
    assert "alphabetical_order" not in detail["message"]


def test_updating_rejects_a_session_length_outside_the_bounds(onboarding_client, onboarding):
    goal = existing_goal(onboarding_client, onboarding)

    response = onboarding_client.patch(
        f"{GOALS}/{goal['id']}",
        json={"planning_preferences": {"preferred_session_minutes": 1200}},
    )

    assert response.status_code == 422
    detail = response.json()["error"]["details"][0]
    assert detail["field"] == "body.planning_preferences.preferred_session_minutes"
    assert detail["type"] == "session_minutes_out_of_range"


def test_creating_rejects_a_session_length_below_the_lower_bound(onboarding_client, onboarding):
    """Refused on the create path too, not only on the update: both accept the
    group, so both mirror the same CHECK."""
    create_profile(onboarding_client)

    response = onboarding_client.post(
        GOALS,
        json={
            "learning_program_id": str(onboarding.schedule.learning_program_id),
            "target_date": "2027-01-31",
            "planning_preferences": {"preferred_session_minutes": 5},
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["error"]["details"][0]["field"]
        == "body.planning_preferences.preferred_session_minutes"
    )


def test_an_unknown_preference_field_is_rejected(onboarding_client, onboarding):
    """A preference this build does not know is a mistake, not something to store
    and ignore."""
    goal = existing_goal(onboarding_client, onboarding)

    response = onboarding_client.patch(
        f"{GOALS}/{goal['id']}", json={"planning_preferences": {"pace": "steady"}}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_preferences_travel_on_every_goal_in_a_page(onboarding_client, onboarding):
    """GOAL-002 carries them too, so the home screen needs no further request."""
    goal = existing_goal(onboarding_client, onboarding)
    onboarding_client.patch(
        f"{GOALS}/{goal['id']}",
        json={"planning_preferences": {"topic_sequencing": "syllabus_order"}},
    )

    page = onboarding_client.get(GOALS).json()

    assert page["data"][0]["planning_preferences"]["topic_sequencing"] == "syllabus_order"


# -- GOAL-005: replace weekly availability ---------------------------------


def availability_of(client, goal_id):
    """The week currently stored, read back through GOAL-003."""
    return client.get(f"{GOALS}/{goal_id}").json()["data"]["availability"]


def replace_availability(client, goal_id, slots):
    return client.put(f"{GOALS}/{goal_id}/availability", json={"slots": slots})


def test_saving_a_week_returns_it_under_the_data_envelope(onboarding_client, onboarding):
    goal = existing_goal(onboarding_client, onboarding)

    response = replace_availability(
        onboarding_client,
        goal["id"],
        [
            {"day_of_week": "wednesday", "available_minutes": 90},
            {"day_of_week": "monday", "available_minutes": 120},
        ],
    )

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "slots": [
                {"day_of_week": "monday", "available_minutes": 120},
                {"day_of_week": "wednesday", "available_minutes": 90},
            ]
        }
    }


def test_a_saved_week_is_returned_in_week_order(onboarding_client, onboarding):
    """Monday first, whatever order the request named the days in."""
    goal = existing_goal(onboarding_client, onboarding)

    body = replace_availability(
        onboarding_client,
        goal["id"],
        [
            {"day_of_week": "sunday", "available_minutes": 30},
            {"day_of_week": "tuesday", "available_minutes": 60},
            {"day_of_week": "saturday", "available_minutes": 240},
        ],
    ).json()

    assert [slot["day_of_week"] for slot in body["data"]["slots"]] == [
        "tuesday",
        "saturday",
        "sunday",
    ]


def test_a_saved_week_is_read_back_on_the_goal(onboarding_client, onboarding):
    """The week travels with the goal, so a screen showing one needs no second call."""
    goal = existing_goal(onboarding_client, onboarding)
    replace_availability(
        onboarding_client, goal["id"], [{"day_of_week": "friday", "available_minutes": 45}]
    )

    assert availability_of(onboarding_client, goal["id"]) == {
        "slots": [{"day_of_week": "friday", "available_minutes": 45}]
    }


def test_a_saved_week_is_read_back_in_the_goal_collection(onboarding_client, onboarding):
    goal = existing_goal(onboarding_client, onboarding)
    replace_availability(
        onboarding_client, goal["id"], [{"day_of_week": "friday", "available_minutes": 45}]
    )

    goals = onboarding_client.get(GOALS).json()["data"]

    assert goals[0]["availability"]["slots"] == [{"day_of_week": "friday", "available_minutes": 45}]


def test_saving_a_week_replaces_the_days_it_does_not_name(onboarding_client, onboarding):
    """A replacement, not a merge: Tuesday is gone because the second save omits it."""
    goal = existing_goal(onboarding_client, onboarding)
    replace_availability(
        onboarding_client,
        goal["id"],
        [
            {"day_of_week": "monday", "available_minutes": 120},
            {"day_of_week": "tuesday", "available_minutes": 60},
        ],
    )

    body = replace_availability(
        onboarding_client, goal["id"], [{"day_of_week": "monday", "available_minutes": 150}]
    ).json()

    assert body["data"]["slots"] == [{"day_of_week": "monday", "available_minutes": 150}]


def test_an_empty_week_clears_the_stored_availability(onboarding_client, onboarding):
    """How a learner takes it all back. `PUT` replace makes it unambiguous."""
    goal = existing_goal(onboarding_client, onboarding)
    replace_availability(
        onboarding_client, goal["id"], [{"day_of_week": "monday", "available_minutes": 120}]
    )

    body = replace_availability(onboarding_client, goal["id"], []).json()

    assert body["data"]["slots"] == []
    assert availability_of(onboarding_client, goal["id"]) == {"slots": []}


def test_a_day_with_no_available_time_is_stored_rather_than_dropped(onboarding_client, onboarding):
    """Zero is a day the learner deliberately keeps free, which is not the same as
    a day they never set -- an unset day is absent from the week entirely."""
    goal = existing_goal(onboarding_client, onboarding)

    body = replace_availability(
        onboarding_client, goal["id"], [{"day_of_week": "sunday", "available_minutes": 0}]
    ).json()

    assert body["data"]["slots"] == [{"day_of_week": "sunday", "available_minutes": 0}]


def test_saving_the_same_week_twice_is_accepted(onboarding_client, onboarding):
    """A repeated form submission must not fail on its second attempt."""
    goal = existing_goal(onboarding_client, onboarding)
    week = [{"day_of_week": "monday", "available_minutes": 120}]
    replace_availability(onboarding_client, goal["id"], week)

    response = replace_availability(onboarding_client, goal["id"], week)

    assert response.status_code == 200
    assert response.json()["data"]["slots"] == week


def test_saving_a_week_reports_no_total(onboarding_client, onboarding):
    """Availability is a planning input. Turning a week into hours is planning
    work, and no plan is generated yet."""
    goal = existing_goal(onboarding_client, onboarding)

    body = replace_availability(
        onboarding_client, goal["id"], [{"day_of_week": "monday", "available_minutes": 120}]
    ).json()

    assert set(body["data"]) == {"slots"}
    assert set(body) == {"data"}


def test_a_slot_exposes_no_persistence_detail(onboarding_client, onboarding):
    """No slot identifier: GOAL-005 addresses a week, not a row, so an identifier
    no client can use would be a field the contract had to keep forever."""
    goal = existing_goal(onboarding_client, onboarding)

    body = replace_availability(
        onboarding_client, goal["id"], [{"day_of_week": "monday", "available_minutes": 120}]
    ).json()

    assert set(body["data"]["slots"][0]) == {"day_of_week", "available_minutes"}


def test_an_unknown_day_is_a_validation_error(onboarding_client, onboarding):
    goal = existing_goal(onboarding_client, onboarding)

    response = replace_availability(
        onboarding_client, goal["id"], [{"day_of_week": "moonday", "available_minutes": 60}]
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["field"] == "body.slots"
    assert error["details"][0]["type"] == "unknown_weekday"


def test_a_numeric_day_is_a_validation_error(onboarding_client, onboarding):
    """There is no numbering convention to accept. A client sending `0` gets a
    refusal naming the seven days rather than a silently misfiled week."""
    goal = existing_goal(onboarding_client, onboarding)

    response = replace_availability(
        onboarding_client, goal["id"], [{"day_of_week": "0", "available_minutes": 60}]
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_naming_one_day_twice_is_a_validation_error(onboarding_client, onboarding):
    """No database key can see two of the same day in one request, so this is the
    only place it can be caught."""
    goal = existing_goal(onboarding_client, onboarding)

    response = replace_availability(
        onboarding_client,
        goal["id"],
        [
            {"day_of_week": "monday", "available_minutes": 60},
            {"day_of_week": "monday", "available_minutes": 90},
        ],
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "duplicate_weekday"


def test_more_minutes_than_a_day_holds_is_a_validation_error(onboarding_client, onboarding):
    goal = existing_goal(onboarding_client, onboarding)

    response = replace_availability(
        onboarding_client, goal["id"], [{"day_of_week": "monday", "available_minutes": 1441}]
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "available_minutes_out_of_range"


def test_negative_minutes_is_a_validation_error(onboarding_client, onboarding):
    goal = existing_goal(onboarding_client, onboarding)

    response = replace_availability(
        onboarding_client, goal["id"], [{"day_of_week": "monday", "available_minutes": -1}]
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "available_minutes_out_of_range"


def test_a_week_naming_more_days_than_a_week_has_is_a_validation_error(
    onboarding_client, onboarding
):
    goal = existing_goal(onboarding_client, onboarding)

    response = replace_availability(
        onboarding_client,
        goal["id"],
        [{"day_of_week": "monday", "available_minutes": 60} for _ in range(8)],
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_a_body_omitting_the_week_is_a_validation_error(onboarding_client, onboarding):
    """`slots` is required, so a body that forgot it cannot silently clear a
    learner's availability. An explicit empty list is how they clear it."""
    goal = existing_goal(onboarding_client, onboarding)

    response = onboarding_client.put(f"{GOALS}/{goal['id']}/availability", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_an_unknown_field_in_a_slot_is_rejected(onboarding_client, onboarding):
    goal = existing_goal(onboarding_client, onboarding)

    response = replace_availability(
        onboarding_client,
        goal["id"],
        [{"day_of_week": "monday", "available_minutes": 60, "starts_at": "06:00"}],
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_saving_a_week_against_an_unknown_goal_returns_the_documented_not_found(
    onboarding_client,
):
    create_profile(onboarding_client)

    response = replace_availability(onboarding_client, uuid.uuid4(), [])

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_saving_a_week_before_setup_returns_the_documented_not_found(onboarding_client):
    """No learner means no goal of theirs to own a week."""
    response = replace_availability(onboarding_client, uuid.uuid4(), [])

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_a_refused_week_leaves_the_stored_week_alone(onboarding_client, onboarding):
    goal = existing_goal(onboarding_client, onboarding)
    replace_availability(
        onboarding_client, goal["id"], [{"day_of_week": "monday", "available_minutes": 120}]
    )

    replace_availability(
        onboarding_client,
        goal["id"],
        [
            {"day_of_week": "tuesday", "available_minutes": 60},
            {"day_of_week": "moonday", "available_minutes": 60},
        ],
    )

    assert availability_of(onboarding_client, goal["id"]) == {
        "slots": [{"day_of_week": "monday", "available_minutes": 120}]
    }


def test_saving_a_week_accepts_no_learner_identifier(onboarding_client, onboarding):
    """The effective learner is resolved server-side, so a client cannot address
    another learner's goal."""
    goal = existing_goal(onboarding_client, onboarding)

    response = onboarding_client.put(
        f"{GOALS}/{goal['id']}/availability",
        json={"slots": [], "learner_id": str(uuid.uuid4())},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_more_than_one_stored_learner_refuses_a_week(onboarding_client, onboarding):
    goal = existing_goal(onboarding_client, onboarding)
    onboarding.learners.add_learner(onboarding.learners.learners[0])

    response = replace_availability(onboarding_client, goal["id"], [])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
