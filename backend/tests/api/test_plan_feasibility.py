"""Contract tests for the plan feasibility endpoint (PLN-006).

These run over the real application factory and the real use case, with only the
repositories and the clock replaced, so they exercise routing, the envelope, the
response shape, and error mapping over the code the running backend uses. The
database counterpart is in tests/integration.

The endpoint is the only one in the planning group that writes nothing, so the
tests below assert both halves of that: what it returns, and that a plan read
back after asking is unchanged.
"""

import uuid

PLANS = "/api/v1/study-plans"
ITEMS = "/api/v1/plan-items"
GOALS = "/api/v1/study-goals"


def generate(client, study_goal_id):
    return client.post(f"{PLANS}/generate", json={"study_goal_id": str(study_goal_id)})


def feasibility(client, study_goal_id):
    return client.get(f"{GOALS}/{study_goal_id}/plan-feasibility")


def plan_of_type(payload, plan_type):
    return next(plan for plan in payload["data"]["plans"] if plan["plan_type"] == plan_type)


# -- the contract -----------------------------------------------------------


def test_a_feasibility_reading_answers_200_under_the_data_envelope(planning_client, planning):
    generate(planning_client, planning.goal.id)

    response = feasibility(planning_client, planning.goal.id)

    assert response.status_code == 200
    assert set(response.json()) == {"data"}


def test_the_reading_carries_every_documented_field(planning_client, planning):
    generate(planning_client, planning.goal.id)

    data = feasibility(planning_client, planning.goal.id).json()["data"]

    assert set(data) == {
        "study_goal_id",
        "assessed_on",
        "verdict",
        "reason",
        "unknown_reason",
        "horizon_ends_on",
        "remaining_topic_count",
        "session_minutes",
        "session_minutes_chosen_by_planner",
        "study_days",
        "available_minutes",
        "required_minutes",
        "shortfall_minutes",
        "coverable_topic_count",
    }


def test_the_verdict_is_one_of_the_three_documented_values(planning_client, planning):
    generate(planning_client, planning.goal.id)

    data = feasibility(planning_client, planning.goal.id).json()["data"]

    assert data["verdict"] in {"sufficient", "insufficient", "unknown"}


def test_the_reading_names_the_goal_and_the_learners_own_date(planning_client, planning):
    generate(planning_client, planning.goal.id)

    data = feasibility(planning_client, planning.goal.id).json()["data"]

    assert data["study_goal_id"] == str(planning.goal.id)
    assert data["assessed_on"] == "2026-08-06"


def test_a_goal_with_a_saved_week_and_a_horizon_reaches_a_verdict(planning_client, planning):
    generate(planning_client, planning.goal.id)

    data = feasibility(planning_client, planning.goal.id).json()["data"]

    assert data["verdict"] in {"sufficient", "insufficient"}
    assert data["unknown_reason"] is None
    assert data["horizon_ends_on"] == "2027-02-06"
    assert data["study_days"] > 0


def test_the_reading_reports_durations_rather_than_a_ratio(planning_client, planning):
    generate(planning_client, planning.goal.id)

    data = feasibility(planning_client, planning.goal.id).json()["data"]

    assert isinstance(data["available_minutes"], int)
    assert isinstance(data["required_minutes"], int)
    assert data["shortfall_minutes"] >= 0
    assert "%" not in data["reason"]


def test_the_reading_can_be_taken_before_any_plan_exists(planning_client, planning):
    """No plan is not an error: PLN-001 is what creates one."""
    response = feasibility(planning_client, planning.goal.id)

    assert response.status_code == 200
    assert response.json()["data"]["remaining_topic_count"] == 0


# -- it writes nothing ------------------------------------------------------


def test_asking_changes_no_plan_and_no_item(planning_client, planning):
    generated = generate(planning_client, planning.goal.id).json()
    roadmap_id = plan_of_type(generated, "roadmap")["id"]
    before = planning_client.get(f"{PLANS}/{roadmap_id}").json()

    feasibility(planning_client, planning.goal.id)
    feasibility(planning_client, planning.goal.id)

    assert planning_client.get(f"{PLANS}/{roadmap_id}").json() == before


def test_asking_does_not_supersede_or_generate_a_plan(planning_client, planning):
    generate(planning_client, planning.goal.id)
    before = planning_client.get(PLANS, params={"study_goal_id": str(planning.goal.id)}).json()

    feasibility(planning_client, planning.goal.id)

    assert (
        planning_client.get(PLANS, params={"study_goal_id": str(planning.goal.id)}).json() == before
    )


def test_the_endpoint_refuses_a_write_method(planning_client, planning):
    """A reading is a GET, and nothing else is offered at that path."""
    response = planning_client.post(f"{GOALS}/{planning.goal.id}/plan-feasibility")

    assert response.status_code == 405


# -- errors -----------------------------------------------------------------


def test_an_unknown_goal_is_404_with_the_documented_error_envelope(planning_client):
    response = feasibility(planning_client, uuid.uuid4())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_a_goal_identifier_that_is_not_a_uuid_is_422(planning_client):
    response = planning_client.get(f"{GOALS}/not-a-uuid/plan-feasibility")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_no_request_accepts_a_learner_id(planning_client, planning):
    """The effective learner is resolved server-side, as every other route does."""
    generate(planning_client, planning.goal.id)

    response = planning_client.get(
        f"{GOALS}/{planning.goal.id}/plan-feasibility",
        params={"learner_id": str(uuid.uuid4())},
    )

    assert response.status_code == 200
    assert response.json()["data"]["study_goal_id"] == str(planning.goal.id)
