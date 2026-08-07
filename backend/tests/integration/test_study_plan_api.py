"""The study-plan endpoints against a real PostgreSQL database.

The API tests prove the contract against fakes. These prove the part a fake
cannot: that the SQL the repository emits reads and writes the rows the seeds
actually created, that the `CHECK` constraints agree with the rules the use case
enforces, and that a plan generated over HTTP is stored and reads back — all
through the same composition root the running backend uses.

The curriculum is the bundled GATE CSE one, so the plan generated here is over
real syllabus rows: 60 trackable topics across 11 subjects. That is what makes
the size assertions below meaningful rather than a restatement of a fixture.

Skipped unless ``TEST_DATABASE_URL`` names a disposable database; see
tests/integration/conftest.py.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.application.use_cases.seed_curriculum import SeedCurriculum
from app.composition.app_factory import create_app
from app.composition.config import Settings
from app.infrastructure.persistence.curriculum_seed_repository import (
    SqlAlchemyCurriculumSeedRepository,
)
from app.infrastructure.persistence.learner_planning import PlanItem, StudyPlan
from scripts.curriculum_seed_file import GATE_CSE_CURRICULUM_FILE, load_curriculum_seed

CURRICULUM = "/api/v1/curriculum"
LEARNER = "/api/v1/learner"
GOALS = "/api/v1/study-goals"
PLANS = "/api/v1/study-plans"
SEED_TIME = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)


@pytest.fixture
def seeded_curriculum(session: Session) -> None:
    """Load the curated GATE CSE curriculum, as `scripts.seed_curriculum` does."""
    SeedCurriculum(SqlAlchemyCurriculumSeedRepository(session), clock=lambda: SEED_TIME)(
        load_curriculum_seed(GATE_CSE_CURRICULUM_FILE)
    )
    session.commit()


@pytest.fixture
def client(
    migrated_database: Engine, database_url: str, seeded_curriculum: None
) -> Iterator[TestClient]:
    """A client wired to the test database through the real composition root."""
    app = create_app(Settings(database_url=database_url))
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def goal(client: TestClient) -> dict:
    """A learner with a goal and a saved study week, as the setup screen creates.

    The goal aims at a target date rather than an examination cycle, so this test
    needs only the curriculum seed: the examination schedule seed is exercised by
    its own tests.
    """
    assert client.patch(f"{LEARNER}/profile", json={"display_name": "Asha"}).status_code == 200
    programs = client.get(f"{CURRICULUM}/programs").json()["data"]
    program = next(entry for entry in programs if entry["code"] == "gate-cse")

    created = client.post(
        GOALS,
        json={
            "learning_program_id": program["id"],
            "target_date": "2027-02-07",
            "planning_preferences": {"preferred_session_minutes": 90},
        },
    )
    assert created.status_code == 201, created.text
    stored = created.json()["data"]

    saved = client.put(
        f"{GOALS}/{stored['id']}/availability",
        json={
            "slots": [
                {"day_of_week": "monday", "available_minutes": 180},
                {"day_of_week": "saturday", "available_minutes": 240},
                {"day_of_week": "sunday", "available_minutes": 0},
            ]
        },
    )
    assert saved.status_code == 200, saved.text
    return stored


def generate(client: TestClient, goal: dict):
    return client.post(PLANS + "/generate", json={"study_goal_id": goal["id"]})


def test_a_plan_is_generated_over_the_seeded_curriculum(client: TestClient, goal: dict):
    """FR-002's last acceptance criterion, against real syllabus rows: a learner
    with no recorded progress still receives a plan."""
    response = generate(client, goal)

    assert response.status_code == 201, response.text
    plans = response.json()["data"]["plans"]
    roadmap = next(plan for plan in plans if plan["plan_type"] == "roadmap")
    assert roadmap["item_count"] == 60
    assert len(roadmap["items"]) == 60
    assert roadmap["period_end"] == "2027-02-07"


def test_the_roadmap_follows_the_seeded_syllabus_order(client: TestClient, goal: dict):
    """The order CUR-003 renders and the frontend is forbidden to re-sort, so the
    plan and the curriculum screen cannot disagree."""
    version = client.get(f"{CURRICULUM}/programs").json()["data"]
    program = next(entry for entry in version if entry["code"] == "gate-cse")
    tree = client.get(
        f"{CURRICULUM}/versions/{program['active_curriculum_version']['id']}/tree"
    ).json()["data"]

    trackable: list[str] = []

    def walk(topics: list[dict]) -> None:
        for topic in topics:
            if topic["is_trackable"]:
                trackable.append(topic["id"])
            walk(topic["subtopics"])

    for subject in tree["subjects"]:
        walk(subject["topics"])

    plans = generate(client, goal).json()["data"]["plans"]
    roadmap = next(plan for plan in plans if plan["plan_type"] == "roadmap")

    assert [item["topic"]["id"] for item in roadmap["items"]] == trackable


def test_the_week_uses_the_saved_availability_and_session_length(client: TestClient, goal: dict):
    plans = generate(client, goal).json()["data"]["plans"]
    weekly = next(plan for plan in plans if plan["plan_type"] == "weekly")

    assert weekly["items"]
    assert all(item["estimated_minutes"] == 90 for item in weekly["items"])
    # Sunday is stored as zero minutes -- a day deliberately kept free -- so no
    # item may fall on it, and no day the learner did not name may either.
    scheduled = {item["scheduled_for"] for item in weekly["items"]}
    assert all(datetime.fromisoformat(day).weekday() in {0, 5} for day in scheduled), scheduled


def test_a_generated_plan_is_stored(client: TestClient, goal: dict, session: Session):
    generate(client, goal)

    assert session.scalar(select(func.count()).select_from(StudyPlan)) == 2
    assert session.scalar(select(func.count()).select_from(PlanItem)) > 60


def test_generating_again_supersedes_rather_than_duplicating(
    client: TestClient, goal: dict, session: Session
):
    first = generate(client, goal).json()["data"]

    second = generate(client, goal).json()["data"]

    assert sorted(second["superseded_plan_ids"]) == sorted(plan["id"] for plan in first["plans"])
    active = session.scalars(select(StudyPlan).where(StudyPlan.status == "active")).all()
    assert {str(plan.id) for plan in active} == {plan["id"] for plan in second["plans"]}
    assert session.scalar(select(func.count()).select_from(StudyPlan)) == 4


def test_a_generated_plan_reads_back_over_the_read_endpoints(client: TestClient, goal: dict):
    created = generate(client, goal).json()["data"]
    roadmap = next(plan for plan in created["plans"] if plan["plan_type"] == "roadmap")

    listed = client.get(PLANS, params={"study_goal_id": goal["id"]}).json()
    read = client.get(f"{PLANS}/{roadmap['id']}").json()["data"]

    assert listed["pagination"]["total"] == 2
    assert all(plan["items"] == [] for plan in listed["data"])
    assert read["id"] == roadmap["id"]
    assert [item["priority"] for item in read["items"]] == list(range(1, 61))
    assert read["items"][0]["topic"]["subject_name"]


def test_a_recorded_stage_reaches_the_plan_that_explains_it(client: TestClient, goal: dict):
    """The one learner-owned input beside availability and preferences. It changes
    no order and no length; it appears in the reason, which is what FR-003 asks
    a recommendation to carry."""
    programs = client.get(f"{CURRICULUM}/programs").json()["data"]
    program = next(entry for entry in programs if entry["code"] == "gate-cse")
    tree = client.get(
        f"{CURRICULUM}/versions/{program['active_curriculum_version']['id']}/tree"
    ).json()["data"]

    trackable: list[dict] = []

    def walk(topics: list[dict]) -> None:
        for topic in topics:
            if topic["is_trackable"]:
                trackable.append(topic)
            walk(topic["subtopics"])

    for subject in tree["subjects"]:
        walk(subject["topics"])

    recorded = trackable[0]
    assert (
        client.patch(
            f"/api/v1/progress/topics/{recorded['id']}",
            json={"learning_stage": "developing_confidence"},
        ).status_code
        == 200
    )

    plans = generate(client, goal).json()["data"]["plans"]
    roadmap = next(plan for plan in plans if plan["plan_type"] == "roadmap")
    item = next(entry for entry in roadmap["items"] if entry["topic"]["id"] == recorded["id"])

    assert "Developing confidence" in item["recommendation_reason"]


def test_generating_for_a_goal_that_is_not_stored_commits_nothing(
    client: TestClient, goal: dict, session: Session
):
    response = client.post(PLANS + "/generate", json={"study_goal_id": str(uuid.uuid4())})

    assert response.status_code == 404
    assert session.scalar(select(func.count()).select_from(StudyPlan)) == 0


def test_a_plan_belonging_to_no_learner_yet_cannot_be_generated(
    client: TestClient, session: Session
):
    """A goal cannot exist without a learner, so this is reached by asking for a
    plan before setup has run at all."""
    response = client.post(PLANS + "/generate", json={"study_goal_id": str(uuid.uuid4())})

    assert response.status_code in (404, 409)
    assert session.scalar(select(func.count()).select_from(StudyPlan)) == 0


def test_both_plans_persist_their_items(client: TestClient, goal: dict, session: Session):
    """Regression: every generated plan's items reach the database.

    Generation writes a plan and then the items that reference it. Nothing
    declares a `relationship` between `StudyPlan` and `PlanItem`, so SQLAlchemy
    has no dependency to order the two INSERTs by and falls back to mapper sort
    order -- which puts `plan_items` first and violates
    `fk_plan_items_study_plan_id_study_plans`. The use case flushes each plan
    before its items to fix that.

    This asserts it for **both** plans a generation writes, because flushing only
    the first would leave the second broken and every other test in this file
    would still pass.
    """
    created = generate(client, goal).json()["data"]
    written = {plan["plan_type"]: plan for plan in created["plans"]}
    assert set(written) == {"roadmap", "weekly"}, written.keys()

    for plan_type, plan in written.items():
        stored = session.scalars(
            select(PlanItem).where(PlanItem.study_plan_id == uuid.UUID(plan["id"]))
        ).all()
        assert len(stored) == plan["item_count"] > 0, (
            f"the {plan_type} plan reported {plan['item_count']} items but stored {len(stored)}"
        )
        assert all(item.study_plan_id == uuid.UUID(plan["id"]) for item in stored)


def test_a_failed_generation_writes_nothing(client: TestClient, goal: dict, session: Session):
    """Flushing a plan before its items must not make a partial plan durable.

    A flush is not a commit. Asking for a plan against a goal that is not the
    learner's fails after the first read and before any write, so the request
    that follows it must still find an empty database -- and the successful
    generation after that must be the only thing stored.
    """
    refused = client.post(PLANS + "/generate", json={"study_goal_id": str(uuid.uuid4())})
    assert refused.status_code == 404

    assert session.scalar(select(func.count()).select_from(StudyPlan)) == 0
    assert session.scalar(select(func.count()).select_from(PlanItem)) == 0

    assert generate(client, goal).status_code == 201
    assert session.scalar(select(func.count()).select_from(StudyPlan)) == 2
