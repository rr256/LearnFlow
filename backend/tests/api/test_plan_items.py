"""Contract tests for the plan item endpoint (PLN-004).

These run over the real application factory and the real use case, with only the
repositories and the clock replaced, so they exercise routing, validation,
response mapping, and error mapping over the code the running backend uses. The
database counterpart is tests/integration/test_study_plan_api.py.

The fixtures are shared with the study-plan endpoints, so an item is completed
here through exactly the plan PLN-001 generated there.
"""

import uuid

PLANS = "/api/v1/study-plans"
ITEMS = "/api/v1/plan-items"


def generate(client, study_goal_id):
    return client.post(f"{PLANS}/generate", json={"study_goal_id": str(study_goal_id)})


def first_weekly_item(client, study_goal_id):
    """The first dated item of a freshly generated plan.

    The week is the panel a learner acts on daily, so it is the item a completion
    test should be about.
    """
    payload = generate(client, study_goal_id).json()
    week = next(plan for plan in payload["data"]["plans"] if plan["plan_type"] == "weekly")
    return week["items"][0]


def move(client, plan_item_id, status):
    return client.patch(f"{ITEMS}/{plan_item_id}", json={"status": status})


def complete(client, plan_item_id, status="completed"):
    return move(client, plan_item_id, status)


def skip(client, plan_item_id):
    return move(client, plan_item_id, "skipped")


def postpone(client, plan_item_id):
    return move(client, plan_item_id, "postponed")


# -- completing a plan item -------------------------------------------------


def test_completing_an_item_returns_200_with_the_whole_item(planning_client, planning):
    item = first_weekly_item(planning_client, planning.goal.id)

    response = complete(planning_client, item["id"])

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"data"}
    assert payload["data"]["id"] == item["id"]
    assert payload["data"]["status"] == "completed"
    assert payload["data"]["completed_at"] == "2026-08-06T09:00:00Z"


def test_a_completed_item_still_names_its_topic_and_its_reason(planning_client, planning):
    """The whole item comes back, so a client can re-render the line it changed
    without reading the plan again."""
    item = first_weekly_item(planning_client, planning.goal.id)

    updated = complete(planning_client, item["id"]).json()["data"]

    assert updated["topic"] == item["topic"]
    assert updated["recommendation_reason"] == item["recommendation_reason"]
    assert updated["priority"] == item["priority"]
    assert updated["scheduled_for"] == item["scheduled_for"]
    assert updated["estimated_minutes"] == item["estimated_minutes"]


def test_completing_an_item_can_be_undone(planning_client, planning):
    item = first_weekly_item(planning_client, planning.goal.id)
    complete(planning_client, item["id"])

    response = complete(planning_client, item["id"], status="planned")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "planned"
    assert response.json()["data"]["completed_at"] is None


def test_completing_an_item_twice_is_accepted(planning_client, planning):
    """A repeated form submission must not fail on its second attempt."""
    item = first_weekly_item(planning_client, planning.goal.id)
    first = complete(planning_client, item["id"]).json()["data"]

    second = complete(planning_client, item["id"])

    assert second.status_code == 200
    assert second.json()["data"]["completed_at"] == first["completed_at"]


def test_a_completion_reads_back_through_the_plan(planning_client, planning):
    """The sequence the plan screen performs: complete an item, then re-read the
    plan the panel is rendered from."""
    payload = generate(planning_client, planning.goal.id).json()
    week = next(plan for plan in payload["data"]["plans"] if plan["plan_type"] == "weekly")
    item = week["items"][0]
    complete(planning_client, item["id"])

    reread = planning_client.get(f"{PLANS}/{week['id']}").json()["data"]

    completed = next(line for line in reread["items"] if line["id"] == item["id"])
    assert completed["status"] == "completed"
    assert completed["completed_at"] == "2026-08-06T09:00:00Z"


def test_completing_one_item_leaves_the_roadmap_alone(planning_client, planning):
    """Nothing infers a link between the week and the roadmap that the schema
    does not store."""
    payload = generate(planning_client, planning.goal.id).json()
    plans = {plan["plan_type"]: plan for plan in payload["data"]["plans"]}
    complete(planning_client, plans["weekly"]["items"][0]["id"])

    roadmap = planning_client.get(f"{PLANS}/{plans['roadmap']['id']}").json()["data"]

    assert all(item["status"] == "planned" for item in roadmap["items"])


# -- skipping a plan item ---------------------------------------------------


def test_skipping_an_item_returns_200_with_the_whole_item(planning_client, planning):
    item = first_weekly_item(planning_client, planning.goal.id)

    response = skip(planning_client, item["id"])

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["id"] == item["id"]
    assert payload["data"]["status"] == "skipped"
    assert payload["data"]["completed_at"] is None


def test_a_skipped_item_still_names_its_topic_and_its_reason(planning_client, planning):
    """A skipped item keeps its place in the plan and everything that explains
    it, so a screen can render the line it changed without re-reading the plan."""
    item = first_weekly_item(planning_client, planning.goal.id)

    updated = skip(planning_client, item["id"]).json()["data"]

    assert updated["topic"] == item["topic"]
    assert updated["recommendation_reason"] == item["recommendation_reason"]
    assert updated["priority"] == item["priority"]
    assert updated["scheduled_for"] == item["scheduled_for"]


def test_skipping_an_item_can_be_undone(planning_client, planning):
    item = first_weekly_item(planning_client, planning.goal.id)
    skip(planning_client, item["id"])

    response = move(planning_client, item["id"], "planned")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "planned"


def test_skipping_a_completed_item_clears_the_completion_time(planning_client, planning):
    """Only a `completed` item carries an instant, so moving off it clears one."""
    item = first_weekly_item(planning_client, planning.goal.id)
    complete(planning_client, item["id"])

    response = skip(planning_client, item["id"])

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "skipped"
    assert response.json()["data"]["completed_at"] is None


def test_skipping_an_item_twice_is_accepted(planning_client, planning):
    """A repeated form submission must not fail on its second attempt."""
    item = first_weekly_item(planning_client, planning.goal.id)
    skip(planning_client, item["id"])

    assert skip(planning_client, item["id"]).status_code == 200


def test_a_skip_reads_back_through_the_plan(planning_client, planning):
    """The sequence the plan screen performs: skip an item, then re-read the plan
    the panel is rendered from."""
    payload = generate(planning_client, planning.goal.id).json()
    week = next(plan for plan in payload["data"]["plans"] if plan["plan_type"] == "weekly")
    item = week["items"][0]
    skip(planning_client, item["id"])

    reread = planning_client.get(f"{PLANS}/{week['id']}").json()["data"]

    skipped = next(line for line in reread["items"] if line["id"] == item["id"])
    assert skipped["status"] == "skipped"
    assert skipped["completed_at"] is None


def test_skipping_one_item_leaves_the_roadmap_alone(planning_client, planning):
    """Skipping a session says that session is not happening. It decides nothing
    about the roadmap item naming the same topic."""
    payload = generate(planning_client, planning.goal.id).json()
    plans = {plan["plan_type"]: plan for plan in payload["data"]["plans"]}
    skip(planning_client, plans["weekly"]["items"][0]["id"])

    roadmap = planning_client.get(f"{PLANS}/{plans['roadmap']['id']}").json()["data"]

    assert all(item["status"] == "planned" for item in roadmap["items"])


def test_skipping_an_item_on_a_superseded_plan_is_409(planning_client, planning):
    item = first_weekly_item(planning_client, planning.goal.id)
    generate(planning_client, planning.goal.id)

    response = skip(planning_client, item["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


# -- postponing a plan item -------------------------------------------------


def test_postponing_an_item_returns_200_with_the_whole_item(planning_client, planning):
    item = first_weekly_item(planning_client, planning.goal.id)

    response = postpone(planning_client, item["id"])

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"data"}
    assert payload["data"]["id"] == item["id"]
    assert payload["data"]["status"] == "postponed"
    assert payload["data"]["completed_at"] is None


def test_a_postponed_item_still_names_its_topic_its_day_and_its_reason(planning_client, planning):
    """Postponing names no new day, so the item reads back exactly as planned
    apart from its status."""
    item = first_weekly_item(planning_client, planning.goal.id)

    data = postpone(planning_client, item["id"]).json()["data"]

    assert data["topic"] == item["topic"]
    assert data["scheduled_for"] == item["scheduled_for"]
    assert data["priority"] == item["priority"]
    assert data["recommendation_reason"] == item["recommendation_reason"]


def test_postponing_an_item_can_be_undone(planning_client, planning):
    item = first_weekly_item(planning_client, planning.goal.id)
    postpone(planning_client, item["id"])

    response = move(planning_client, item["id"], "planned")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "planned"


def test_postponing_a_completed_item_clears_the_completion_time(planning_client, planning):
    item = first_weekly_item(planning_client, planning.goal.id)
    complete(planning_client, item["id"])

    data = postpone(planning_client, item["id"]).json()["data"]

    assert data["status"] == "postponed"
    assert data["completed_at"] is None


def test_postponing_an_item_twice_is_accepted(planning_client, planning):
    """A repeated form submission must not fail on its second attempt."""
    item = first_weekly_item(planning_client, planning.goal.id)
    postpone(planning_client, item["id"])

    assert postpone(planning_client, item["id"]).status_code == 200


def test_a_postponement_reads_back_through_the_plan(planning_client, planning):
    payload = generate(planning_client, planning.goal.id).json()
    week = next(plan for plan in payload["data"]["plans"] if plan["plan_type"] == "weekly")
    item = week["items"][0]
    postpone(planning_client, item["id"])

    reread = planning_client.get(f"{PLANS}/{week['id']}").json()["data"]

    postponed = next(line for line in reread["items"] if line["id"] == item["id"])
    assert postponed["status"] == "postponed"
    assert postponed["completed_at"] is None


def test_postponing_one_item_leaves_the_roadmap_alone(planning_client, planning):
    payload = generate(planning_client, planning.goal.id).json()
    plans = {plan["plan_type"]: plan for plan in payload["data"]["plans"]}
    postpone(planning_client, plans["weekly"]["items"][0]["id"])

    roadmap = planning_client.get(f"{PLANS}/{plans['roadmap']['id']}").json()["data"]

    assert all(item["status"] == "planned" for item in roadmap["items"])


def test_postponing_an_undated_roadmap_item_is_accepted(planning_client, planning):
    """The endpoint knows nothing about dated versus undated items."""
    payload = generate(planning_client, planning.goal.id).json()
    roadmap = next(plan for plan in payload["data"]["plans"] if plan["plan_type"] == "roadmap")

    response = postpone(planning_client, roadmap["items"][0]["id"])

    assert response.status_code == 200
    assert response.json()["data"]["scheduled_for"] is None


def test_postponing_an_item_on_a_superseded_plan_is_409(planning_client, planning):
    item = first_weekly_item(planning_client, planning.goal.id)
    generate(planning_client, planning.goal.id)

    response = postpone(planning_client, item["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


# -- refusals ---------------------------------------------------------------


def test_a_status_outside_the_four_is_refused(planning_client, planning):
    """Every value the column holds is now askable, so this reaches only a status
    that is not one of them at all."""
    item = first_weekly_item(planning_client, planning.goal.id)

    response = move(planning_client, item["id"], "abandoned")

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["field"] == "body.status"
    assert error["details"][0]["type"] == "unknown_plan_item_status"


def test_a_refused_status_is_not_echoed_back(planning_client, planning):
    """docs/api/conventions.md keeps the rejected input out of the envelope."""
    item = first_weekly_item(planning_client, planning.goal.id)

    body = complete(planning_client, item["id"], status="deleted-by-mistake").text

    assert "deleted-by-mistake" not in body


def test_completing_an_item_that_is_not_stored_is_404(planning_client, planning):
    generate(planning_client, planning.goal.id)

    response = complete(planning_client, uuid.uuid4())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_completing_an_item_on_a_superseded_plan_is_409(planning_client, planning):
    """A replaced plan is kept as a record of what was planned and reads exactly
    as it was written, so it cannot be written into."""
    item = first_weekly_item(planning_client, planning.goal.id)
    generate(planning_client, planning.goal.id)

    response = complete(planning_client, item["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_completing_before_setup_has_run_is_409(planning_client, planning):
    item = first_weekly_item(planning_client, planning.goal.id)
    planning.learners.learners = []

    response = complete(planning_client, item["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_a_malformed_item_identifier_is_422(planning_client):
    response = complete(planning_client, "not-a-uuid")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_a_request_without_a_status_is_422(planning_client, planning):
    item = first_weekly_item(planning_client, planning.goal.id)

    response = planning_client.patch(f"{ITEMS}/{item['id']}", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_an_unknown_field_is_refused_rather_than_ignored(planning_client, planning):
    """A caller sending `completed_at` is trying to backdate work. Ignoring it
    would accept the request and silently do something else."""
    item = first_weekly_item(planning_client, planning.goal.id)

    response = planning_client.patch(
        f"{ITEMS}/{item['id']}",
        json={"status": "completed", "completed_at": "2020-01-01T00:00:00Z"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_the_endpoint_accepts_no_learner_id(planning_client, planning):
    """The effective learner is resolved server-side, so no caller can complete
    another learner's plan item."""
    item = first_weekly_item(planning_client, planning.goal.id)

    response = planning_client.patch(
        f"{ITEMS}/{item['id']}",
        json={"status": "completed", "learner_id": str(uuid.uuid4())},
    )

    assert response.status_code == 422


def test_the_collection_path_is_not_a_route(planning_client):
    """PLN-004 addresses one item. Nothing completes a plan wholesale."""
    assert planning_client.patch(ITEMS, json={"status": "completed"}).status_code in (404, 405)
