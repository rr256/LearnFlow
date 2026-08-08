"""Contract tests for the study-plan endpoints (PLN-001 to PLN-003).

These run over the real application factory and the real use case, with only the
repositories and the clock replaced, so they exercise routing, validation,
response mapping, and error mapping over the code the running backend uses. The
database counterpart is tests/integration/test_study_plan_api.py.
"""

import uuid

PLANS = "/api/v1/study-plans"
GENERATE = f"{PLANS}/generate"


def generate(client, study_goal_id):
    return client.post(GENERATE, json={"study_goal_id": str(study_goal_id)})


def plan_of_type(payload, plan_type):
    return next(plan for plan in payload["data"]["plans"] if plan["plan_type"] == plan_type)


# -- PLN-001 ----------------------------------------------------------------


def test_generating_a_plan_returns_201_with_the_plans_and_their_items(planning_client, planning):
    response = generate(planning_client, planning.goal.id)

    assert response.status_code == 201
    payload = response.json()
    assert set(payload) == {"data"}
    assert payload["data"]["study_goal_id"] == str(planning.goal.id)
    assert payload["data"]["generated_on"] == "2026-08-06"
    assert [plan["plan_type"] for plan in payload["data"]["plans"]] == ["roadmap", "weekly"]


def test_a_generated_roadmap_carries_its_reason_and_its_items(planning_client, planning):
    payload = generate(planning_client, planning.goal.id).json()

    roadmap = plan_of_type(payload, "roadmap")
    assert roadmap["status"] == "active"
    assert roadmap["period_start"] == "2026-08-06"
    assert roadmap["generation_reason"]
    assert roadmap["item_count"] == 3
    assert len(roadmap["items"]) == 3


def test_a_plan_item_names_its_topic_and_subject(planning_client, planning):
    payload = generate(planning_client, planning.goal.id).json()

    item = plan_of_type(payload, "roadmap")["items"][0]
    assert item["topic"]["id"] == str(planning.logic.id)
    assert item["topic"]["name"] == "Propositional logic"
    assert item["topic"]["subject_name"] == "Engineering Mathematics"
    assert item["action_type"] == "study"
    assert item["status"] == "planned"
    assert item["priority"] == 1
    assert item["recommendation_reason"]


def test_a_roadmap_item_has_no_date_and_a_weekly_item_does(planning_client, planning):
    payload = generate(planning_client, planning.goal.id).json()

    assert all(item["scheduled_for"] is None for item in plan_of_type(payload, "roadmap")["items"])
    assert all(item["scheduled_for"] for item in plan_of_type(payload, "weekly")["items"])


def test_generating_again_reports_what_it_superseded(planning_client, planning):
    first = generate(planning_client, planning.goal.id).json()

    second = generate(planning_client, planning.goal.id).json()

    assert sorted(second["data"]["superseded_plan_ids"]) == sorted(
        plan["id"] for plan in first["data"]["plans"]
    )


def test_generating_for_a_goal_that_is_not_stored_is_404(planning_client):
    response = generate(planning_client, uuid.uuid4())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_generating_without_a_learner_is_409(planning_client, planning):
    planning.learners.learners = []

    response = generate(planning_client, planning.goal.id)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_generating_with_a_malformed_goal_identifier_is_422(planning_client):
    response = planning_client.post(GENERATE, json={"study_goal_id": "not-a-uuid"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_generating_with_an_unknown_field_is_refused(planning_client, planning):
    """A client that thought it could pass a session length is told so, rather
    than having it silently ignored: the plan is built from what the learner
    stored, never from what a caller asks for."""
    response = planning_client.post(
        GENERATE,
        json={"study_goal_id": str(planning.goal.id), "preferred_session_minutes": 45},
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"]


def test_generating_without_a_goal_is_422(planning_client):
    response = planning_client.post(GENERATE, json={})

    assert response.status_code == 422


def test_generation_accepts_no_learner_id(planning_client, planning):
    """The effective learner is resolved server-side; naming one is an unknown
    field, not a way to plan for somebody else."""
    response = planning_client.post(
        GENERATE,
        json={"study_goal_id": str(planning.goal.id), "learner_id": str(uuid.uuid4())},
    )

    assert response.status_code == 422


# -- PLN-002 ----------------------------------------------------------------


def test_listing_plans_returns_the_documented_collection_envelope(planning_client, planning):
    generate(planning_client, planning.goal.id)

    response = planning_client.get(PLANS)

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"data", "pagination"}
    assert payload["pagination"] == {"limit": 25, "offset": 0, "total": 2}


def test_a_listed_plan_reports_its_size_without_its_items(planning_client, planning):
    generate(planning_client, planning.goal.id)

    plans = planning_client.get(PLANS).json()["data"]

    assert all(plan["items"] == [] for plan in plans)
    assert sorted(plan["item_count"] for plan in plans) == [2, 3]


def test_plans_can_be_filtered(planning_client, planning):
    generate(planning_client, planning.goal.id)

    plans = planning_client.get(
        PLANS,
        params={"study_goal_id": str(planning.goal.id), "plan_type": "roadmap", "status": "active"},
    ).json()["data"]

    assert [plan["plan_type"] for plan in plans] == ["roadmap"]


def test_a_goal_filter_matching_nothing_is_an_empty_page(planning_client, planning):
    generate(planning_client, planning.goal.id)

    payload = planning_client.get(PLANS, params={"study_goal_id": str(uuid.uuid4())}).json()

    assert payload["data"] == []
    assert payload["pagination"]["total"] == 0


def test_an_unknown_plan_type_filter_is_422(planning_client):
    response = planning_client.get(PLANS, params={"plan_type": "fortnightly"})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "query.plan_type"


def test_an_unknown_status_filter_is_422(planning_client):
    response = planning_client.get(PLANS, params={"status": "finished"})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "query.status"


def test_a_limit_outside_the_documented_bounds_is_422(planning_client):
    assert planning_client.get(PLANS, params={"limit": 0}).status_code == 422
    assert planning_client.get(PLANS, params={"limit": 101}).status_code == 422
    assert planning_client.get(PLANS, params={"offset": -1}).status_code == 422


def test_listing_before_setup_has_run_is_an_empty_page(planning_client, planning):
    planning.learners.learners = []

    payload = planning_client.get(PLANS).json()

    assert payload["data"] == []
    assert payload["pagination"]["total"] == 0


# -- PLN-003 ----------------------------------------------------------------


def test_reading_one_plan_returns_it_with_its_items_in_order(planning_client, planning):
    created = generate(planning_client, planning.goal.id).json()
    roadmap_id = plan_of_type(created, "roadmap")["id"]

    response = planning_client.get(f"{PLANS}/{roadmap_id}")

    assert response.status_code == 200
    plan = response.json()["data"]
    assert plan["id"] == roadmap_id
    assert [item["priority"] for item in plan["items"]] == [1, 2, 3]


def test_a_superseded_plan_still_reads_back(planning_client, planning):
    """Superseding rather than deleting is what makes a plan history worth
    keeping, so the earlier plan has to remain readable."""
    first = generate(planning_client, planning.goal.id).json()
    roadmap_id = plan_of_type(first, "roadmap")["id"]
    generate(planning_client, planning.goal.id)

    plan = planning_client.get(f"{PLANS}/{roadmap_id}").json()["data"]

    assert plan["status"] == "superseded"
    assert plan["items"]


def test_reading_a_plan_that_is_not_stored_is_404(planning_client):
    response = planning_client.get(f"{PLANS}/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_reading_a_plan_with_a_malformed_identifier_is_422(planning_client):
    response = planning_client.get(f"{PLANS}/not-a-uuid")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_a_generated_item_is_always_planned_and_never_completed(planning_client, planning):
    """Generation writes one status. Moving an item is PLN-004's work, and it is
    addressed at its own path -- these endpoints do not move one."""
    payload = generate(planning_client, planning.goal.id).json()

    items = [item for plan in payload["data"]["plans"] for item in plan["items"]]
    assert all(item["status"] == "planned" for item in items)
    assert all(item["completed_at"] is None for item in items)
    assert planning_client.patch(f"{PLANS}/{uuid.uuid4()}").status_code in (404, 405)
