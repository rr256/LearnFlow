"""Contract tests for the plan adaptation endpoint (PLN-005).

These run over the real application factory and the real use case, with only the
repositories and the clock replaced, so they exercise routing, validation,
response mapping, and error mapping over the code the running backend uses. The
database counterpart is tests/integration/test_study_plan_api.py.

The fixtures are shared with the other planning endpoints, so a plan is generated
here through exactly the code PLN-001 runs and completed through PLN-004.
"""

import uuid

PLANS = "/api/v1/study-plans"
ITEMS = "/api/v1/plan-items"
GOALS = "/api/v1/study-goals"


def generate(client, study_goal_id):
    return client.post(f"{PLANS}/generate", json={"study_goal_id": str(study_goal_id)})


def adapt(client, study_goal_id):
    return client.post(f"{GOALS}/{study_goal_id}/adapt")


def plan_of_type(payload, plan_type):
    return next(plan for plan in payload["data"]["plans"] if plan["plan_type"] == plan_type)


def complete(client, plan_item_id):
    return client.patch(f"{ITEMS}/{plan_item_id}", json={"status": "completed"})


# -- adapting ---------------------------------------------------------------


def test_adapting_returns_201_with_the_new_plans(planning_client, planning):
    generate(planning_client, planning.goal.id)

    response = adapt(planning_client, planning.goal.id)

    assert response.status_code == 201, response.text
    payload = response.json()
    assert set(payload) == {"data"}
    assert payload["data"]["study_goal_id"] == str(planning.goal.id)
    assert payload["data"]["adapted_on"] == "2026-08-06"
    assert [plan["plan_type"] for plan in payload["data"]["plans"]] == ["roadmap", "weekly"]


def test_adapting_reports_what_it_set_aside(planning_client, planning):
    first = generate(planning_client, planning.goal.id).json()

    adapted = adapt(planning_client, planning.goal.id).json()["data"]

    assert sorted(adapted["superseded_plan_ids"]) == sorted(
        plan["id"] for plan in first["data"]["plans"]
    )


def test_a_completed_topic_is_not_planned_again(planning_client, planning):
    created = generate(planning_client, planning.goal.id).json()
    done = plan_of_type(created, "weekly")["items"][0]
    complete(planning_client, done["id"])

    adapted = adapt(planning_client, planning.goal.id).json()["data"]

    roadmap = next(plan for plan in adapted["plans"] if plan["plan_type"] == "roadmap")
    assert done["topic"]["id"] not in {item["topic"]["id"] for item in roadmap["items"]}
    assert adapted["completed_topic_count"] == 1
    assert adapted["remaining_topic_count"] == 2


def test_an_overdue_item_is_reported_and_stored_as_postponed(planning_client, planning):
    from datetime import UTC, datetime

    created = generate(planning_client, planning.goal.id).json()
    overdue = plan_of_type(created, "weekly")["items"][0]
    planning.clock.instant = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)

    adapted = adapt(planning_client, planning.goal.id).json()["data"]

    assert overdue["id"] in adapted["postponed_plan_item_ids"]
    superseded_id = plan_of_type(created, "weekly")["id"]
    stored = planning_client.get(f"{PLANS}/{superseded_id}").json()["data"]
    line = next(item for item in stored["items"] if item["id"] == overdue["id"])
    assert line["status"] == "postponed"


def test_the_superseded_plan_still_reads_back(planning_client, planning):
    created = generate(planning_client, planning.goal.id).json()
    week = plan_of_type(created, "weekly")
    adapt(planning_client, planning.goal.id)

    stored = planning_client.get(f"{PLANS}/{week['id']}").json()["data"]

    assert stored["status"] == "superseded"
    assert stored["generation_reason"] == week["generation_reason"]
    assert stored["items"]


def test_the_adapted_plan_explains_itself(planning_client, planning):
    created = generate(planning_client, planning.goal.id).json()
    complete(planning_client, plan_of_type(created, "weekly")["items"][0]["id"])

    adapted = adapt(planning_client, planning.goal.id).json()["data"]

    roadmap = next(plan for plan in adapted["plans"] if plan["plan_type"] == "roadmap")
    assert "still to work through" in roadmap["generation_reason"]
    assert "already completed" in roadmap["generation_reason"]
    assert all(item["recommendation_reason"] for item in roadmap["items"])


def test_every_adapted_item_starts_planned(planning_client, planning):
    created = generate(planning_client, planning.goal.id).json()
    complete(planning_client, plan_of_type(created, "weekly")["items"][0]["id"])

    adapted = adapt(planning_client, planning.goal.id).json()["data"]

    items = [item for plan in adapted["plans"] for item in plan["items"]]
    assert all(item["status"] == "planned" for item in items)
    assert all(item["completed_at"] is None for item in items)


def test_adapting_reports_no_total_for_a_day_or_a_week(planning_client, planning):
    generate(planning_client, planning.goal.id)

    adapted = adapt(planning_client, planning.goal.id).json()["data"]

    for plan in adapted["plans"]:
        assert "total" not in plan["generation_reason"].lower()


def test_the_counts_describe_the_plan_and_never_rate_the_learner(planning_client, planning):
    """docs/domain/terminology.md draws this line: a plan may say how much of the
    curriculum it covers, and may never turn that into a score. A ratio has a
    denominator, and a denominator invites the comparison the rule rules out."""
    import re

    created = generate(planning_client, planning.goal.id).json()
    complete(planning_client, plan_of_type(created, "weekly")["items"][0]["id"])

    body = adapt(planning_client, planning.goal.id).text

    assert "%" not in body
    for forbidden in ("percent", "completion rate", "streak", "score"):
        assert forbidden not in body.lower(), forbidden
    # No "N of M" or "N/M" shape anywhere in the prose the learner reads.
    reasons = " ".join(
        plan["generation_reason"]
        for plan in adapt(planning_client, planning.goal.id).json()["data"]["plans"]
    )
    assert not re.search(r"\d+\s*(of|/)\s*\d+", reasons), reasons


# -- refusals ---------------------------------------------------------------


def test_adapting_a_goal_with_no_active_plan_is_409(planning_client, planning):
    response = adapt(planning_client, planning.goal.id)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_adapting_a_goal_that_is_not_stored_is_404(planning_client, planning):
    generate(planning_client, planning.goal.id)

    response = adapt(planning_client, uuid.uuid4())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_adapting_before_setup_has_run_is_409(planning_client, planning):
    generate(planning_client, planning.goal.id)
    planning.learners.learners = []

    response = adapt(planning_client, planning.goal.id)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_a_malformed_goal_identifier_is_422(planning_client):
    response = planning_client.post(f"{GOALS}/not-a-uuid/adapt")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_the_endpoint_takes_no_request_body(planning_client, planning):
    """Everything adaptation reads is already stored, so no caller can adapt
    toward a preference the learner never set."""
    generate(planning_client, planning.goal.id)

    response = planning_client.post(
        f"{GOALS}/{planning.goal.id}/adapt",
        json={"preferred_session_minutes": 45, "learner_id": str(uuid.uuid4())},
    )

    assert response.status_code == 201
    adapted = response.json()["data"]
    roadmap = next(plan for plan in adapted["plans"] if plan["plan_type"] == "roadmap")
    assert "45 minutes" not in roadmap["generation_reason"]
