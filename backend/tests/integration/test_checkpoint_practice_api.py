"""The checkpoint-practice endpoints against a real PostgreSQL database.

The API tests prove the contract against fakes. These prove the part a fake
cannot: that the SQL the repository emits reads and writes the topics the
curriculum seed actually created, that a quiz assembled over HTTP really holds
its questions in `position` order, that the `jsonb` payloads survive a round
trip, and that a request reporting a failure commits nothing — all through the
same composition root the running backend uses.

The curriculum is the bundled GATE CSE one, so the topics practised here are real
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
from app.infrastructure.persistence.assessment import (
    CheckpointQuiz,
    Question,
    QuizAttempt,
    QuizAttemptAnswer,
)
from app.infrastructure.persistence.curriculum_seed_repository import (
    SqlAlchemyCurriculumSeedRepository,
)
from scripts.curriculum_seed_file import GATE_CSE_CURRICULUM_FILE, load_curriculum_seed

CURRICULUM = "/api/v1/curriculum"
LEARNER = "/api/v1/learner"
QUESTIONS = "/api/v1/practice-questions"
QUIZZES = "/api/v1/checkpoint-quizzes"
ATTEMPTS = "/api/v1/quiz-attempts"
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
    """Every seeded topic, split by whether it groups subtopics."""
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


def write(client: TestClient, topic_ids: list[str], **fields) -> dict:
    """Write one question over QZ-008 and return it."""
    body = {
        "prompt": "How many bits address 1 KiB?",
        "options": ["8", "10", "16", "1024"],
        "correct_option_index": 1,
        "explanation": "1 KiB is 2^10 bytes, so ten bits address it.",
        "topic_ids": topic_ids,
    }
    body.update(fields)
    response = client.post(QUESTIONS, json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def assemble(client: TestClient, topic_ids: list[str]) -> dict:
    """Assemble a quiz over QZ-001 and return it."""
    response = client.post(f"{QUIZZES}/generate", json={"topic_ids": topic_ids})
    assert response.status_code == 201, response.text
    return response.json()["data"]


def start(client: TestClient, quiz_id: str) -> dict:
    """Begin an attempt over QZ-003 and return it."""
    response = client.post(f"{QUIZZES}/{quiz_id}/attempts")
    assert response.status_code in (200, 201), response.text
    return response.json()["data"]


# -- the whole workflow -------------------------------------------------------


def test_a_learner_can_write_practise_and_read_an_honest_result(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]], session: Session
):
    """The workflow FR-009 asks for, end to end against real syllabus rows."""
    topic = seeded_topics["trackable"][0]
    first = write(client, [topic["id"]], prompt="How many bits address 1 KiB?")
    second = write(client, [topic["id"]], prompt="Which scheduler runs shortest job first?")

    quiz = assemble(client, [topic["id"]])
    assert [question["question_id"] for question in quiz["questions"]] == [
        first["id"],
        second["id"],
    ]

    attempt = start(client, quiz["id"])
    marked = client.post(
        f"{ATTEMPTS}/{attempt['id']}/submit",
        json={"answers": [{"question_id": first["id"], "option_key": "b"}]},
    )

    assert marked.status_code == 200, marked.text
    outcomes = marked.json()["data"]["outcomes"]
    assert outcomes[0]["is_correct"] is True
    assert outcomes[1]["is_correct"] is None
    assert outcomes[0]["expected_option_key"] == "b"
    assert session.scalar(select(func.count()).select_from(QuizAttemptAnswer)) == 2


def test_a_question_written_over_http_stores_its_payloads(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]], session: Session
):
    topic = seeded_topics["trackable"][0]
    written = write(client, [topic["id"]])

    stored = session.get(Question, written["id"])

    assert stored is not None
    assert stored.options == [
        {"key": "a", "text": "8"},
        {"key": "b", "text": "10"},
        {"key": "c", "text": "16"},
        {"key": "d", "text": "1024"},
    ]
    assert stored.expected_answer == {"option_key": "b"}
    assert stored.author_learner_id is not None


def test_a_question_may_cover_a_grouping_topic_from_the_curated_curriculum(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]]
):
    heading = seeded_topics["grouping"][0]

    response = client.post(
        QUESTIONS,
        json={
            "prompt": "Which of these is a systems topic?",
            "options": ["Yes", "No"],
            "correct_option_index": 0,
            "topic_ids": [heading["id"]],
        },
    )

    assert response.status_code == 201


def test_a_question_can_be_found_by_the_topic_it_covers(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]]
):
    first, second = seeded_topics["trackable"][0], seeded_topics["trackable"][1]
    write(client, [first["id"]], prompt="About the first")
    write(client, [second["id"]], prompt="About the second")

    body = client.get(QUESTIONS, params={"topic_id": second["id"]}).json()

    assert [question["prompt"] for question in body["data"]] == ["About the second"]


def test_a_retired_question_is_not_asked_by_a_new_quiz(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]]
):
    topic = seeded_topics["trackable"][0]
    kept = write(client, [topic["id"]], prompt="Kept")
    set_aside = write(client, [topic["id"]], prompt="Set aside")
    client.patch(f"{QUESTIONS}/{set_aside['id']}", json={"status": "retired"})

    quiz = assemble(client, [topic["id"]])

    assert [question["question_id"] for question in quiz["questions"]] == [kept["id"]]


def test_a_retired_question_stays_in_a_quiz_already_assembled(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]]
):
    """Dropping it would change a quiz that attempts already reference."""
    topic = seeded_topics["trackable"][0]
    written = write(client, [topic["id"]])
    quiz = assemble(client, [topic["id"]])
    client.patch(f"{QUESTIONS}/{written['id']}", json={"status": "retired"})

    read = client.get(f"{QUIZZES}/{quiz['id']}").json()["data"]

    assert [question["question_id"] for question in read["questions"]] == [written["id"]]


def test_asking_for_an_attempt_twice_stores_one(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]], session: Session
):
    topic = seeded_topics["trackable"][0]
    write(client, [topic["id"]])
    quiz = assemble(client, [topic["id"]])
    start(client, quiz["id"])

    second = client.post(f"{QUIZZES}/{quiz['id']}/attempts")

    assert second.status_code == 200
    assert session.scalar(select(func.count()).select_from(QuizAttempt)) == 1


def test_a_quiz_for_topics_with_no_questions_commits_nothing(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]], session: Session
):
    topic = seeded_topics["trackable"][0]

    response = client.post(f"{QUIZZES}/generate", json={"topic_ids": [topic["id"]]})

    assert response.status_code == 422
    assert session.scalar(select(func.count()).select_from(CheckpointQuiz)) == 0


def test_a_rejected_question_commits_neither_the_question_nor_a_link(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]], session: Session
):
    topic = seeded_topics["trackable"][0]

    response = client.post(
        QUESTIONS,
        json={
            "prompt": "Which is right?",
            "options": ["Same", "Same"],
            "correct_option_index": 0,
            "topic_ids": [topic["id"]],
        },
    )

    assert response.status_code == 422
    assert session.scalar(select(func.count()).select_from(Question)) == 0


def test_a_rejected_submission_commits_no_answer(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]], session: Session
):
    topic = seeded_topics["trackable"][0]
    written = write(client, [topic["id"]])
    quiz = assemble(client, [topic["id"]])
    attempt = start(client, quiz["id"])

    response = client.post(
        f"{ATTEMPTS}/{attempt['id']}/submit",
        json={"answers": [{"question_id": written["id"], "option_key": "z"}]},
    )

    assert response.status_code == 422
    assert session.scalar(select(func.count()).select_from(QuizAttemptAnswer)) == 0
    assert session.get(QuizAttempt, attempt["id"]).status == "in_progress"


def test_submitting_writes_nothing_else(
    client: TestClient, learner: dict, seeded_topics: dict[str, list[dict]], session: Session
):
    """No learning stage, no plan, no plan item, and no revision."""
    from app.infrastructure.persistence.progress import LearnerTopicProgress

    topic = seeded_topics["trackable"][0]
    written = write(client, [topic["id"]])
    quiz = assemble(client, [topic["id"]])
    attempt = start(client, quiz["id"])

    client.post(
        f"{ATTEMPTS}/{attempt['id']}/submit",
        json={"answers": [{"question_id": written["id"], "option_key": "b"}]},
    )

    assert session.scalar(select(func.count()).select_from(LearnerTopicProgress)) == 0


def test_practising_before_setup_is_a_conflict(
    client: TestClient, seeded_topics: dict[str, list[dict]], session: Session
):
    """No learner exists to own a question, so nothing is stored.

    Deliberately asks for no `learner` fixture: this is a fresh installation
    where setup has not run.
    """
    topic = seeded_topics["trackable"][0]

    response = client.post(
        QUESTIONS,
        json={
            "prompt": "Anything?",
            "options": ["Yes", "No"],
            "correct_option_index": 0,
            "topic_ids": [topic["id"]],
        },
    )

    assert response.status_code == 409
    assert session.scalar(select(func.count()).select_from(Question)) == 0
