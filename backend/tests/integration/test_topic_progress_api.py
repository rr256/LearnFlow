"""The topic-progress endpoints against a real PostgreSQL database.

The API tests prove the contract against fakes. These prove the part a fake
cannot: that the SQL the repository emits reads and writes the topics the
curriculum seed actually created, that the `CHECK` and uniqueness constraints
agree with the rules the use case enforces, and that a request reporting a
failure commits nothing -- all through the same composition root the running
backend uses.

The curriculum is the bundled GATE CSE one, so the trackable and grouping topics
here are real syllabus rows rather than invented ones.

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
from app.infrastructure.persistence.learner_planning import Learner
from app.infrastructure.persistence.progress import LearnerTopicProgress
from scripts.curriculum_seed_file import GATE_CSE_CURRICULUM_FILE, load_curriculum_seed

CURRICULUM = "/api/v1/curriculum"
LEARNER = "/api/v1/learner"
PROGRESS = "/api/v1/progress/topics"
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
def learner(client: TestClient) -> dict:
    """The local learner, created through LRN-002 as the setup screen does."""
    response = client.patch(f"{LEARNER}/profile", json={"display_name": "Asha"})
    assert response.status_code == 200
    return response.json()["data"]


@pytest.fixture
def curriculum_version(client: TestClient) -> dict:
    """The seeded GATE CSE active curriculum version, read through CUR-001."""
    programs = client.get(f"{CURRICULUM}/programs").json()["data"]
    program = next(entry for entry in programs if entry["code"] == "gate-cse")
    return program["active_curriculum_version"]


@pytest.fixture
def seeded_topics(client: TestClient, curriculum_version: dict) -> dict[str, list[dict]]:
    """Every seeded topic, split by whether progress can be recorded against it.

    The curated curriculum contains both: a leaf is trackable, and a topic that
    groups subtopics is not.
    """
    tree = client.get(f"{CURRICULUM}/versions/{curriculum_version['id']}/tree").json()["data"]
    trackable: list[dict] = []
    grouping: list[dict] = []

    def walk(topics: list[dict]) -> None:
        for topic in topics:
            (trackable if topic["is_trackable"] else grouping).append(topic)
            walk(topic["subtopics"])

    for subject in tree["subjects"]:
        walk(subject["topics"])
    return {"trackable": trackable, "grouping": grouping}


def test_a_stage_recorded_over_http_is_stored_and_reads_back(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]], session: Session
):
    topic = seeded_topics["trackable"][0]

    recorded = client.patch(
        f"{PROGRESS}/{topic['id']}", json={"learning_stage": "building_foundation"}
    )

    assert recorded.status_code == 200
    stored = session.scalar(select(LearnerTopicProgress))
    assert stored is not None
    assert stored.learning_stage == "building_foundation"
    assert stored.stage_source == "learner"
    assert str(stored.learner_id) == learner["id"]

    listed = client.get(PROGRESS).json()
    assert listed["pagination"]["total"] == 1
    assert listed["data"][0]["topic"]["name"] == topic["name"]


def test_updating_a_stage_rewrites_the_one_stored_row(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]], session: Session
):
    topic = seeded_topics["trackable"][0]
    client.patch(f"{PROGRESS}/{topic['id']}", json={"learning_stage": "building_foundation"})

    client.patch(f"{PROGRESS}/{topic['id']}", json={"learning_stage": "strong_understanding"})

    assert session.scalar(select(func.count()).select_from(LearnerTopicProgress)) == 1
    stored = session.scalar(select(LearnerTopicProgress))
    assert stored is not None
    assert stored.learning_stage == "strong_understanding"


def test_a_rejected_stage_commits_nothing(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]], session: Session
):
    """The provider rolls back when the route raises, so a reported failure
    cannot leave a half-written record behind."""
    topic = seeded_topics["trackable"][0]

    response = client.patch(f"{PROGRESS}/{topic['id']}", json={"learning_stage": "mastered"})

    assert response.status_code == 422
    assert session.scalar(select(func.count()).select_from(LearnerTopicProgress)) == 0


def test_a_grouping_topic_from_the_curated_curriculum_is_refused(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]], session: Session
):
    """The curated syllabus really does contain grouping topics, so this is the
    shape a learner meets rather than an invented one."""
    grouping = seeded_topics["grouping"]
    assert grouping, "the curated curriculum should contain at least one grouping topic"

    response = client.patch(
        f"{PROGRESS}/{grouping[0]['id']}", json={"learning_stage": "practice_ready"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "topic_not_trackable"
    assert session.scalar(select(func.count()).select_from(LearnerTopicProgress)) == 0


def test_recording_before_a_learner_exists_is_a_conflict_and_writes_nothing(
    client: TestClient, seeded_topics: dict[str, list[dict]], session: Session
):
    """No `learner` fixture here: nothing has created the profile yet."""
    topic = seeded_topics["trackable"][0]

    response = client.patch(f"{PROGRESS}/{topic['id']}", json={"learning_stage": "practice_ready"})

    assert response.status_code == 409
    assert session.scalar(select(func.count()).select_from(Learner)) == 0
    assert session.scalar(select(func.count()).select_from(LearnerTopicProgress)) == 0


def test_listing_filters_to_the_curriculum_version_the_topics_belong_to(
    client: TestClient,
    learner: dict,
    curriculum_version: dict,
    seeded_topics: dict[str, list[dict]],
):
    """The filter reaches through subjects to topics, which is the join only a
    real database exercises."""
    topic = seeded_topics["trackable"][0]
    client.patch(f"{PROGRESS}/{topic['id']}", json={"learning_stage": "practice_ready"})

    matching = client.get(
        PROGRESS, params={"curriculum_version_id": curriculum_version["id"]}
    ).json()
    other = client.get(PROGRESS, params={"curriculum_version_id": str(uuid.uuid4())}).json()

    assert matching["pagination"]["total"] == 1
    assert matching["data"][0]["topic"]["curriculum_version_id"] == curriculum_version["id"]
    assert other["pagination"]["total"] == 0


def test_a_page_reports_the_total_it_was_taken_from(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]]
):
    """The count and the page share one predicate, so a `total` cannot disagree
    with the rows it counts."""
    for topic in seeded_topics["trackable"][:3]:
        client.patch(f"{PROGRESS}/{topic['id']}", json={"learning_stage": "practice_ready"})

    body = client.get(PROGRESS, params={"limit": 2}).json()

    assert len(body["data"]) == 2
    assert body["pagination"] == {"limit": 2, "offset": 0, "total": 3}


def test_an_unstored_topic_is_reported_as_not_found(client: TestClient, learner: dict):
    response = client.patch(f"{PROGRESS}/{uuid.uuid4()}", json={"learning_stage": "practice_ready"})

    assert response.status_code == 404
