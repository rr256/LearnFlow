"""MNT-001 against a real PostgreSQL database, with a fake provider.

The API tests prove the contract against fake repositories. These prove the part
a fake repository cannot: that **PostgreSQL's own full-text search** is what
decides whether a model is asked at all. The whole feature turns on that branch,
and until now it had only ever been exercised against an in-memory search that
matches by splitting on word characters.

**The provider is always a fake.** Nothing here reaches Ollama, opens a socket,
or needs a model installed — the composition root is overridden for the AI
provider alone, so retrieval, the database, and every rule between them are the
real ones. A test that needed a model running would fail on a machine that had
not pulled one, and would make the suite's answer depend on a model's.

**Every note in this file is invented for the test.** Nothing in this repository
holds a learner's real notes, and nothing here reads a file from disk.

Skipped unless ``TEST_DATABASE_URL`` names a disposable database; see
tests/integration/conftest.py.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.application.use_cases.answer_topic_question import AnswerTopicQuestion
from app.application.use_cases.retrieve_topic_notes import RetrieveTopicNotes
from app.application.use_cases.seed_curriculum import SeedCurriculum
from app.composition.app_factory import create_app
from app.composition.config import Settings
from app.infrastructure.persistence.curriculum_seed_repository import (
    SqlAlchemyCurriculumSeedRepository,
)
from app.infrastructure.persistence.engine import create_database_engine, create_session_factory
from app.infrastructure.persistence.learner_repository import SqlAlchemyLearnerRepository
from app.infrastructure.persistence.note_search_repository import SqlAlchemyNoteSearchRepository
from app.infrastructure.persistence.resource_repository import SqlAlchemyResourceRepository
from app.presentation.api.dependencies import STUDY_ANSWER_PROVIDER
from scripts.curriculum_seed_file import GATE_CSE_CURRICULUM_FILE, load_curriculum_seed
from tests.unit.fake_ai_provider import FakeAIProvider

CURRICULUM = "/api/v1/curriculum"
LEARNER = "/api/v1/learner"
RESOURCES = "/api/v1/resources"
QUESTIONS = "/api/v1/mentor/questions"
SEED_TIME = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
QUESTION = "How does the scheduler decide what runs next?"


@pytest.fixture
def seeded_curriculum(session: Session) -> None:
    """Load the curated GATE CSE curriculum, as `scripts.seed_curriculum` does."""
    SeedCurriculum(SqlAlchemyCurriculumSeedRepository(session), clock=lambda: SEED_TIME)(
        load_curriculum_seed(GATE_CSE_CURRICULUM_FILE)
    )
    session.commit()


@pytest.fixture
def provider() -> FakeAIProvider:
    """The AI provider the mentor endpoint is bound to. Never a real one."""
    return FakeAIProvider(answer="Each process runs for one quantum, then yields.")


@pytest.fixture
def client(
    migrated_database: Engine,
    database_url: str,
    seeded_curriculum: None,
    provider: FakeAIProvider,
) -> Iterator[TestClient]:
    """A client wired to the test database, with only the provider replaced.

    Retrieval, the repositories, the session handling, and the routes are the
    real ones the running backend uses. **Only the outbound call is faked**, so
    what these tests exercise is exactly the branch that decides whether it
    happens.
    """
    app = create_app(Settings(database_url=database_url))
    session_factory = create_session_factory(create_database_engine(database_url))

    @contextmanager
    def provide() -> Iterator[AnswerTopicQuestion]:
        with session_factory() as db:
            yield AnswerTopicQuestion(
                retrieval=RetrieveTopicNotes(
                    learners=SqlAlchemyLearnerRepository(db),
                    resources=SqlAlchemyResourceRepository(db),
                    notes=SqlAlchemyNoteSearchRepository(db),
                ),
                provider=provider,
            )

    setattr(app.state, STUDY_ANSWER_PROVIDER, provide)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def learner(client: TestClient) -> dict:
    """The local learner, created through LRN-002 as the setup screen does."""
    response = client.patch(f"{LEARNER}/profile", json={"display_name": "Asha"})
    assert response.status_code == 200
    return response.json()["data"]


@pytest.fixture
def topics(client: TestClient) -> list[dict]:
    """Every seeded trackable topic, from the real curated syllabus."""
    programs = client.get(f"{CURRICULUM}/programs").json()["data"]
    program = next(entry for entry in programs if entry["code"] == "gate-cse")
    version = program["active_curriculum_version"]
    tree = client.get(f"{CURRICULUM}/versions/{version['id']}/tree").json()["data"]

    found: list[dict] = []

    def walk(entries: list[dict]) -> None:
        for topic in entries:
            if topic["is_trackable"]:
                found.append(topic)
            walk(topic["subtopics"])

    for subject in tree["subjects"]:
        walk(subject["topics"])
    return found


@pytest.fixture
def scheduling(topics: list[dict]) -> dict:
    """A real curriculum topic whose name stems usefully."""
    return next(topic for topic in topics if "schedul" in topic["name"].lower())


@pytest.fixture
def unrelated(topics: list[dict], scheduling: dict) -> dict:
    """A different real topic, for the case where nothing is linked."""
    return next(topic for topic in topics if topic["id"] != scheduling["id"])


def register(client: TestClient, topic_ids: list[str]) -> dict:
    response = client.post(
        RESOURCES,
        json={
            "resource_type": "note",
            "title": "Operating Systems notes",
            "source_label": "Blue binder",
            "topic_ids": topic_ids,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def write_note(client: TestClient, resource_id: str, *, title: str, body: str) -> dict:
    response = client.post(f"{RESOURCES}/{resource_id}/notes", json={"title": title, "body": body})
    assert response.status_code == 201, response.text
    return response.json()["data"]


def ask(client: TestClient, topic_id: str, question: str = QUESTION):
    return client.post(QUESTIONS, json={"topic_id": topic_id, "question": question})


# -- an answer over real retrieval -------------------------------------------


def test_a_question_is_answered_from_a_note_real_retrieval_found(
    client: TestClient, learner: dict, scheduling: dict, provider: FakeAIProvider
):
    """The whole path: PostgreSQL matched, the provider was asked, passages cited.

    The note never repeats the topic's exact words — it says "Schedulers" and
    "scheduled" — so this only passes because the real full-text search stems.
    """
    resource = register(client, [scheduling["id"]])
    note = write_note(
        client,
        resource["id"],
        title="Round robin",
        body="Schedulers pick the next process. Work is scheduled in quanta.",
    )

    data = ask(client, scheduling["id"]).json()["data"]

    assert data["outcome"] == "answered"
    assert data["answer"] == provider.answer
    assert provider.was_asked is True
    assert [passage["note_id"] for passage in data["passages"]] == [note["id"]]
    assert data["passages"][0]["resource_title"] == "Operating Systems notes"
    assert data["passages"][0]["topic_name"] == scheduling["name"]


def test_only_the_question_and_passages_reach_the_provider_over_real_retrieval(
    client: TestClient, learner: dict, scheduling: dict, provider: FakeAIProvider
):
    """The privacy boundary, asserted against a payload built from real rows."""
    resource = register(client, [scheduling["id"]])
    note = write_note(
        client, resource["id"], title="Round robin", body="Schedulers pick the next process."
    )

    ask(client, scheduling["id"])

    sent = provider.requests[0]
    everything = " ".join((sent.question, sent.topic_name, sent.subject_name, *sent.passages))
    for identifier in (learner["id"], note["id"], resource["id"], scheduling["id"]):
        assert identifier not in everything
    assert note["title"] not in everything
    assert resource["title"] not in everything
    assert sent.question == QUESTION


def test_a_passage_survives_real_retrieval_character_for_character(
    client: TestClient, learner: dict, scheduling: dict, provider: FakeAIProvider
):
    """Code-like text reaches both the provider and the response unmangled."""
    resource = register(client, [scheduling["id"]])
    write_note(
        client,
        resource["id"],
        title="Queues",
        body="The scheduler holds vector<int> ready queues and compares a < b.",
    )

    data = ask(client, scheduling["id"]).json()["data"]

    assert "vector<int>" in data["passages"][0]["passage"]
    assert "a < b" in data["passages"][0]["passage"]
    assert "vector<int>" in provider.requests[0].passages[0]


# -- no evidence, no provider call, over real retrieval ----------------------


def test_no_linked_material_reaches_no_provider(
    client: TestClient, learner: dict, unrelated: dict, provider: FakeAIProvider
):
    data = ask(client, unrelated["id"]).json()["data"]

    assert data["outcome"] == "no_linked_material"
    assert data["answer"] is None
    assert data["passages"] == []
    assert provider.was_asked is False
    assert provider.requests == []


def test_no_active_note_reaches_no_provider(
    client: TestClient, learner: dict, scheduling: dict, provider: FakeAIProvider
):
    resource = register(client, [scheduling["id"]])
    note = write_note(
        client, resource["id"], title="Round robin", body="Schedulers pick the next process."
    )
    archived = client.patch(f"/api/v1/resource-notes/{note['id']}", json={"status": "archived"})
    assert archived.status_code == 200, archived.text

    data = ask(client, scheduling["id"]).json()["data"]

    assert data["outcome"] == "no_active_notes"
    assert provider.was_asked is False


def test_a_note_that_does_not_mention_the_topic_reaches_no_provider(
    client: TestClient, learner: dict, scheduling: dict, provider: FakeAIProvider
):
    """The case the feature exists for, decided by PostgreSQL rather than a fake.

    The learner has material linked to this topic and a real note on it. The note
    is about something else, so full-text search matches nothing and **no model
    is asked** — LearnFlow does not answer from what a model happens to know.
    """
    resource = register(client, [scheduling["id"]])
    write_note(
        client,
        resource["id"],
        title="Networks",
        body="TCP retransmits lost segments after a timeout expires.",
    )

    data = ask(client, scheduling["id"]).json()["data"]

    assert data["outcome"] == "no_matching_passage"
    assert data["answer"] is None
    assert data["passages"] == []
    assert provider.was_asked is False


def test_material_put_aside_reaches_no_provider(
    client: TestClient, learner: dict, scheduling: dict, provider: FakeAIProvider
):
    """Archived material drops out of grounding as it does everywhere else."""
    resource = register(client, [scheduling["id"]])
    write_note(
        client, resource["id"], title="Round robin", body="Schedulers pick the next process."
    )
    archived = client.patch(f"{RESOURCES}/{resource['id']}", json={"status": "archived"})
    assert archived.status_code == 200, archived.text

    data = ask(client, scheduling["id"]).json()["data"]

    assert data["outcome"] in {"no_linked_material", "no_active_notes"}
    assert provider.was_asked is False


# -- refusals -----------------------------------------------------------------


def test_a_blank_question_is_refused_before_the_database_is_read(
    client: TestClient, learner: dict, scheduling: dict, provider: FakeAIProvider
):
    response = ask(client, scheduling["id"], "   ")

    assert response.status_code == 422, response.text
    assert provider.was_asked is False


def test_an_unknown_topic_is_a_404_and_reaches_no_provider(
    client: TestClient, learner: dict, provider: FakeAIProvider
):
    response = ask(client, "11111111-1111-4111-8111-111111111111")

    assert response.status_code == 404, response.text
    assert provider.was_asked is False


# -- nothing is written -------------------------------------------------------


def test_asking_stores_no_question_or_answer(
    client: TestClient, learner: dict, scheduling: dict, session: Session
):
    """Nothing is stored, so no table exists to hold it and no row appears.

    Asserted two ways: the schema has no table for a question or an answer, and
    the row counts of every table that does exist are unchanged by asking twice.
    """
    resource = register(client, [scheduling["id"]])
    write_note(
        client, resource["id"], title="Round robin", body="Schedulers pick the next process."
    )

    before = _row_counts(session)
    ask(client, scheduling["id"])
    ask(client, scheduling["id"], "And what is a quantum?")

    assert _row_counts(session) == before

    tables = set(before)
    assert "mentor_questions" not in tables
    assert "mentor_answers" not in tables
    assert "study_answers" not in tables


def _row_counts(session: Session) -> dict[str, int]:
    """Every public table and how many rows it holds, read fresh."""
    session.commit()
    names = [
        row[0]
        for row in session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )
        )
    ]
    return {
        name: session.execute(text(f'SELECT count(*) FROM "{name}"')).scalar_one() for name in names
    }


def test_asking_twice_returns_the_same_answer(client: TestClient, learner: dict, scheduling: dict):
    resource = register(client, [scheduling["id"]])
    write_note(
        client, resource["id"], title="Round robin", body="Schedulers pick the next process."
    )

    first = ask(client, scheduling["id"]).json()["data"]
    second = ask(client, scheduling["id"]).json()["data"]

    assert first == second
