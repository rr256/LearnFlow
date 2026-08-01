"""The curriculum endpoints against a real PostgreSQL database.

The API tests prove the contract against a fake repository. These prove the part
a fake cannot: that the SQL the repository emits returns the curriculum the seed
actually wrote, with its subjects in syllabus order and its subtopics under the
right parents, through the same composition root the running backend uses.

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
from app.infrastructure.persistence.curriculum import Topic
from app.infrastructure.persistence.curriculum_seed_repository import (
    SqlAlchemyCurriculumSeedRepository,
)
from scripts.curriculum_seed_file import GATE_CSE_CURRICULUM_FILE, load_curriculum_seed

CURRICULUM = "/api/v1/curriculum"
SEED_TIME = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)


@pytest.fixture
def seeded_curriculum(session: Session) -> None:
    """Load the bundled GATE CSE curriculum, as `scripts.seed_curriculum` does."""
    use_case = SeedCurriculum(SqlAlchemyCurriculumSeedRepository(session), clock=lambda: SEED_TIME)
    use_case(load_curriculum_seed(GATE_CSE_CURRICULUM_FILE))
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
def gate_cse(client: TestClient) -> dict:
    """The seeded GATE CSE program, read back through CUR-001."""
    programs = client.get(f"{CURRICULUM}/programs").json()["data"]
    return next(program for program in programs if program["code"] == "gate-cse")


def test_listing_programs_returns_the_seeded_learning_program(gate_cse):
    assert gate_cse["name"] == "GATE Computer Science and Information Technology"
    assert gate_cse["active_curriculum_version"]["version_label"] == "2027"
    assert gate_cse["active_curriculum_version"]["status"] == "active"


def test_listing_programs_reports_one_stored_program(client):
    body = client.get(f"{CURRICULUM}/programs").json()

    assert body["pagination"]["total"] == 1


def test_reading_the_program_by_its_identifier_returns_the_same_record(client, gate_cse):
    data = client.get(f"{CURRICULUM}/programs/{gate_cse['id']}").json()["data"]

    assert data == gate_cse


def test_tree_returns_every_seeded_subject_in_syllabus_order(client, gate_cse):
    version_id = gate_cse["active_curriculum_version"]["id"]

    subjects = client.get(f"{CURRICULUM}/versions/{version_id}/tree").json()["data"]["subjects"]

    assert len(subjects) == 11
    assert [subject["position"] for subject in subjects] == list(range(1, 12))
    assert subjects[0]["code"] == "engineering-mathematics"


def test_tree_nests_the_seeded_subtopics_under_their_parent_topic(client, gate_cse):
    version_id = gate_cse["active_curriculum_version"]["id"]

    subjects = client.get(f"{CURRICULUM}/versions/{version_id}/tree").json()["data"]["subjects"]

    nested = [topic for subject in subjects for topic in subject["topics"] if topic["subtopics"]]
    assert nested, "the bundled curriculum has at least one topic with subtopics"
    for topic in nested:
        assert topic["is_trackable"] is False
        assert all(subtopic["subtopics"] == [] for subtopic in topic["subtopics"])


def test_tree_reports_the_version_it_was_asked_for(client, gate_cse):
    version = gate_cse["active_curriculum_version"]

    data = client.get(f"{CURRICULUM}/versions/{version['id']}/tree").json()["data"]

    assert data["curriculum_version"]["id"] == version["id"]
    assert data["curriculum_version"]["learning_program_id"] == gate_cse["id"]
    assert data["curriculum_version"]["published_at"].startswith("2026-07-31T12:00:00")


def test_every_seeded_topic_reaches_the_client(client, gate_cse, session):
    """A topic dropped by the tree assembly would be invisible to a learner."""
    stored = session.scalar(select(func.count()).select_from(Topic))
    version_id = gate_cse["active_curriculum_version"]["id"]

    subjects = client.get(f"{CURRICULUM}/versions/{version_id}/tree").json()["data"]["subjects"]

    assert _count_topics(subjects) == stored


def test_reading_an_unseeded_curriculum_version_returns_not_found(client):
    response = client.get(f"{CURRICULUM}/versions/00000000-0000-4000-8000-000000000000/tree")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "resource_not_found"


def _count_topics(subjects: list[dict]) -> int:
    return sum(_count_topic_nodes(subject["topics"]) for subject in subjects)


def _count_topic_nodes(topics: list[dict]) -> int:
    return sum(1 + _count_topic_nodes(topic["subtopics"]) for topic in topics)
