"""The learning-resource endpoints against a real PostgreSQL database.

The API tests prove the contract against fakes. These prove the part a fake
cannot: that the SQL the repository emits reads and writes the topics the
curriculum seed actually created, that replacing a link set really removes the
rows it drops, that the `CHECK` constraints agree with the rules the use case
enforces, and that a request reporting a failure commits nothing — all through
the same composition root the running backend uses.

The curriculum is the bundled GATE CSE one, so the topics linked here are real
syllabus rows rather than invented ones.

Skipped unless ``TEST_DATABASE_URL`` names a disposable database; see
tests/integration/conftest.py.
"""

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
from app.infrastructure.persistence.resources import Resource, ResourceTopicLink
from scripts.curriculum_seed_file import GATE_CSE_CURRICULUM_FILE, load_curriculum_seed

CURRICULUM = "/api/v1/curriculum"
LEARNER = "/api/v1/learner"
RESOURCES = "/api/v1/resources"
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
def seeded_topics(client: TestClient) -> dict[str, list[dict]]:
    """Every seeded topic, split by whether it groups subtopics.

    A resource may cover either, which is where the catalogue differs from
    PRG-004; both halves are asserted below against real syllabus rows.
    """
    programs = client.get(f"{CURRICULUM}/programs").json()["data"]
    program = next(entry for entry in programs if entry["code"] == "gate-cse")
    version = program["active_curriculum_version"]
    tree = client.get(f"{CURRICULUM}/versions/{version['id']}/tree").json()["data"]

    trackable: list[dict] = []
    grouping: list[dict] = []

    def walk(topics: list[dict]) -> None:
        for topic in topics:
            (trackable if topic["is_trackable"] else grouping).append(topic)
            walk(topic["subtopics"])

    for subject in tree["subjects"]:
        walk(subject["topics"])
    return {"trackable": trackable, "grouping": grouping}


def register(client: TestClient, **fields) -> dict:
    """Register one resource over RES-001 and return it."""
    body = {"resource_type": "note", "title": "Notes", "source_label": "Blue binder"}
    body.update(fields)
    response = client.post(RESOURCES, json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_material_registered_over_http_is_stored_and_reads_back(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]], session: Session
):
    topic = seeded_topics["trackable"][0]

    registered = register(
        client,
        title="Process scheduling notes",
        external_reference="https://example.test/os.pdf",
        topic_ids=[topic["id"]],
    )

    stored = session.scalar(select(Resource))
    assert stored is not None
    assert stored.title == "Process scheduling notes"
    assert stored.status == "registered"
    assert str(stored.owner_learner_id) == learner["id"]
    assert session.scalar(select(func.count()).select_from(ResourceTopicLink)) == 1

    listed = client.get(RESOURCES).json()
    assert listed["pagination"]["total"] == 1
    assert listed["data"][0]["topics"][0]["name"] == topic["name"]
    assert listed["data"][0]["topics"][0]["subject_name"]
    assert listed["data"][0]["id"] == registered["id"]


def test_material_can_be_found_by_the_topic_it_covers(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]]
):
    """FR-007's fourth acceptance criterion, over the curated syllabus."""
    first, second = seeded_topics["trackable"][0], seeded_topics["trackable"][1]
    register(client, title="Covers the first", topic_ids=[first["id"]])
    register(client, title="Covers the second", topic_ids=[second["id"]])

    body = client.get(RESOURCES, params={"topic_id": first["id"]}).json()

    assert [item["title"] for item in body["data"]] == ["Covers the first"]
    assert body["pagination"]["total"] == 1


def test_one_resource_may_cover_several_topics(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]], session: Session
):
    covered = seeded_topics["trackable"][:3]

    registered = register(client, topic_ids=[topic["id"] for topic in covered])

    assert len(registered["topics"]) == 3
    assert session.scalar(select(func.count()).select_from(ResourceTopicLink)) == 3
    for topic in covered:
        found = client.get(RESOURCES, params={"topic_id": topic["id"]}).json()
        assert [item["id"] for item in found["data"]] == [registered["id"]]


def test_material_may_cover_a_grouping_topic_from_the_curated_curriculum(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]]
):
    """The curated syllabus really does contain grouping topics, and a textbook
    may genuinely cover one — where PRG-004 refuses a stage on the same row."""
    grouping = seeded_topics["grouping"]
    assert grouping, "the curated curriculum should contain at least one grouping topic"

    registered = register(client, title="Whole-subject textbook", topic_ids=[grouping[0]["id"]])

    assert [topic["name"] for topic in registered["topics"]] == [grouping[0]["name"]]


def test_replacing_the_topics_removes_the_rows_it_drops(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]], session: Session
):
    first, second = seeded_topics["trackable"][0], seeded_topics["trackable"][1]
    registered = register(client, topic_ids=[first["id"]])

    changed = client.patch(f"{RESOURCES}/{registered['id']}", json={"topic_ids": [second["id"]]})

    assert changed.status_code == 200
    assert [topic["name"] for topic in changed.json()["data"]["topics"]] == [second["name"]]
    assert session.scalar(select(func.count()).select_from(ResourceTopicLink)) == 1
    assert client.get(RESOURCES, params={"topic_id": first["id"]}).json()["data"] == []


def test_archiving_keeps_the_row_and_is_reversible(
    client: TestClient, learner: dict, session: Session
):
    registered = register(client)

    client.patch(f"{RESOURCES}/{registered['id']}", json={"status": "archived"})
    assert session.scalar(select(func.count()).select_from(Resource)) == 1
    assert client.get(RESOURCES, params={"status": "registered"}).json()["data"] == []

    client.patch(f"{RESOURCES}/{registered['id']}", json={"status": "registered"})
    assert len(client.get(RESOURCES, params={"status": "registered"}).json()["data"]) == 1
    assert session.scalar(select(func.count()).select_from(Resource)) == 1


def test_a_rejected_registration_commits_nothing(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]], session: Session
):
    """The provider rolls back when the route raises, so a reported failure
    cannot leave a half-written record behind."""
    response = client.post(
        RESOURCES,
        json={
            "resource_type": "note",
            "title": "Local notes",
            "external_reference": "D:\\GATE\\os-notes.pdf",
        },
    )

    assert response.status_code == 422
    assert session.scalar(select(func.count()).select_from(Resource)) == 0


def test_a_rejected_topic_link_commits_neither_the_resource_nor_a_link(
    client: TestClient, learner: dict, session: Session
):
    response = client.post(
        RESOURCES,
        json={
            "resource_type": "note",
            "title": "Notes",
            "source_label": "Shelf",
            "topic_ids": ["00000000-0000-0000-0000-000000000001"],
        },
    )

    assert response.status_code == 422
    assert session.scalar(select(func.count()).select_from(Resource)) == 0
    assert session.scalar(select(func.count()).select_from(ResourceTopicLink)) == 0


def test_registering_material_writes_nothing_else(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]], session: Session
):
    """A resource says where material is, never that a topic is understood or
    that work happened, so no stage, plan, or revision is created."""
    from app.infrastructure.persistence.learner_planning import PlanItem, StudyPlan
    from app.infrastructure.persistence.progress import LearnerTopicProgress, RevisionRecord

    register(client, topic_ids=[seeded_topics["trackable"][0]["id"]])

    assert session.scalar(select(func.count()).select_from(LearnerTopicProgress)) == 0
    assert session.scalar(select(func.count()).select_from(RevisionRecord)) == 0
    assert session.scalar(select(func.count()).select_from(StudyPlan)) == 0
    assert session.scalar(select(func.count()).select_from(PlanItem)) == 0


def test_registering_before_setup_is_a_conflict(client: TestClient, session: Session):
    """No learner exists to own the material until LRN-002 has run."""
    response = client.post(
        RESOURCES,
        json={"resource_type": "note", "title": "Notes", "source_label": "Shelf"},
    )

    assert response.status_code == 409
    assert session.scalar(select(func.count()).select_from(Resource)) == 0
