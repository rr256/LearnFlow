"""Topic-note retrieval against a real PostgreSQL database (RES-013).

The API tests prove the contract against fakes. These prove the part a fake
cannot, and deliberately does not try to: **PostgreSQL's own full-text search**.
Stemming, `ts_headline` fragmenting, relevance ordering, and the eligibility
rules as they are actually expressed in SQL are all exercised here, through the
same composition root the running backend uses.

**Every note in this file is invented for the test.** Nothing in this repository
holds a learner's real notes, and nothing here reads a file from disk.

Skipped unless ``TEST_DATABASE_URL`` names a disposable database; see
tests/integration/conftest.py.
"""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.application.dto.note_retrieval import MAX_PASSAGE_WORDS
from app.application.use_cases.seed_curriculum import SeedCurriculum
from app.composition.app_factory import create_app
from app.composition.config import Settings
from app.infrastructure.persistence.curriculum_seed_repository import (
    SqlAlchemyCurriculumSeedRepository,
)
from app.infrastructure.persistence.resources import ResourceNote
from scripts.curriculum_seed_file import GATE_CSE_CURRICULUM_FILE, load_curriculum_seed

CURRICULUM = "/api/v1/curriculum"
LEARNER = "/api/v1/learner"
RESOURCES = "/api/v1/resources"
SEARCH = "/api/v1/resource-notes/search"
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


def register(client: TestClient, topic_ids: list[str], **fields) -> dict:
    body = {
        "resource_type": "note",
        "title": "Operating Systems notes",
        "source_label": "Blue binder",
        "topic_ids": topic_ids,
    }
    body.update(fields)
    response = client.post(RESOURCES, json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def write_note(client: TestClient, resource_id: str, *, title: str, body: str) -> dict:
    response = client.post(f"{RESOURCES}/{resource_id}/notes", json={"title": title, "body": body})
    assert response.status_code == 201, response.text
    return response.json()["data"]


def search(client: TestClient, topic_id: str) -> dict:
    response = client.get(SEARCH, params={"topic_id": topic_id})
    assert response.status_code == 200, response.text
    return response.json()["data"]


# -- real full-text behaviour -------------------------------------------------


def test_stemming_finds_a_note_that_never_repeats_the_topic_name(
    client: TestClient, learner: dict, topics: list[dict]
):
    """The reason this uses `english` rather than `simple`.

    The note never contains the topic's exact words; it says "schedulers" and
    "scheduled". A literal match would find nothing.
    """
    topic = next(t for t in topics if "schedul" in t["name"].lower())
    resource = register(client, [topic["id"]])
    write_note(
        client,
        resource["id"],
        title="Round robin",
        body="Schedulers pick the next process. Work is scheduled in quanta.",
    )

    data = search(client, topic["id"])

    assert data["outcome"] == "found"
    assert len(data["passages"]) == 1
    assert "Schedulers" in data["passages"][0]["passage"]


def test_a_note_about_something_else_does_not_match(
    client: TestClient, learner: dict, topics: list[dict]
):
    topic = next(t for t in topics if "schedul" in t["name"].lower())
    resource = register(client, [topic["id"]])
    write_note(client, resource["id"], title="Shopping", body="Milk, bread, and apples.")

    data = search(client, topic["id"])

    assert data["outcome"] == "no_matching_passage"
    assert data["passages"] == []


def test_a_long_note_comes_back_as_a_bounded_fragment(
    client: TestClient, learner: dict, topics: list[dict], session: Session
):
    """`ts_headline` returns the matching part, not the whole note."""
    topic = next(t for t in topics if "schedul" in t["name"].lower())
    resource = register(client, [topic["id"]])
    # Long, but inside MAX_NOTE_BODY_LENGTH: a longer note is refused at RES-009,
    # so a fixture that exceeded it would be testing the bound rather than the
    # fragmenting.
    filler = "Padding sentence with no relevance whatsoever. " * 150
    write_note(
        client,
        resource["id"],
        title="A very long note",
        body=f"{filler}\n\nRound robin scheduling gives each process a quantum.\n\n{filler}",
    )

    stored_length = session.scalar(select(func.length(ResourceNote.body)))
    passage = search(client, topic["id"])["passages"][0]["passage"]

    assert stored_length > 12_000
    # Bounded by MaxWords per fragment, across at most MaxFragments fragments.
    assert len(passage.split()) <= MAX_PASSAGE_WORDS * 3 + 10
    assert len(passage) < stored_length


def test_code_like_text_survives_retrieval_against_a_real_database(
    client: TestClient, learner: dict, topics: list[dict], session: Session
):
    """The regression this rewrite exists for, proved end to end.

    An earlier build rendered the passage with `ts_headline`, whose parser reads
    `<int>` as an HTML tag and **dropped it**, so `vector<int>` came back as
    `vector`. Nothing renders a passage now: PostgreSQL matches and orders, and
    the application cuts an exact substring from the stored body.
    """
    topic = next(t for t in topics if "schedul" in t["name"].lower())
    resource = register(client, [topic["id"]])
    body = (
        "Scheduling notes:\n\n"
        "    std::vector<int> ready;\n"
        "    if (a < b) { swap(a, b); }\n\n"
        "See <https://example.test/os> and <em>chapter 3</em> for the rest."
    )
    written = write_note(client, resource["id"], title="Ready queue", body=body)

    passage = search(client, topic["id"])["passages"][0]["passage"]

    # Every literal the old implementation destroyed.
    assert "vector<int>" in passage
    assert "if (a < b) { swap(a, b); }" in passage
    assert "<https://example.test/os>" in passage
    assert "<em>chapter 3</em> for the rest." in passage

    # And the whole thing is an exact substring of what is stored.
    assert passage in body
    session.expire_all()
    assert session.scalar(select(ResourceNote.body)) == body
    assert client.get(f"/api/v1/resource-notes/{written['id']}").json()["data"]["body"] == body


def test_no_stored_note_text_is_changed_by_searching(
    client: TestClient, learner: dict, topics: list[dict], session: Session
):
    """Retrieval is a read. The bytes in the table do not move."""
    topic = next(t for t in topics if "schedul" in t["name"].lower())
    resource = register(client, [topic["id"]])
    body = "Scheduling <b>and</b> vector<int> with a < b and a>>b intact."
    write_note(client, resource["id"], title="Literals", body=body)

    before = session.scalar(select(ResourceNote.body))
    for _ in range(3):
        search(client, topic["id"])
    session.expire_all()

    assert before == body
    assert session.scalar(select(ResourceNote.body)) == body


def test_a_passage_of_a_long_note_is_still_an_exact_substring(
    client: TestClient, learner: dict, topics: list[dict], session: Session
):
    """Truncation must cut, never rewrite."""
    topic = next(t for t in topics if "schedul" in t["name"].lower())
    resource = register(client, [topic["id"]])
    filler = "Padding sentence with no relevance whatsoever. " * 150
    body = f"{filler}\n\nScheduling uses vector<int> here.\n\n{filler}"
    write_note(client, resource["id"], title="Long", body=body)

    passage = search(client, topic["id"])["passages"][0]["passage"]

    assert passage in body
    assert len(passage) < len(body)
    assert "vector<int>" in passage
    # Nothing was inserted where the cut happened.
    assert "…" not in passage
    assert "..." not in passage


def test_a_passage_carries_no_highlight_markup(
    client: TestClient, learner: dict, topics: list[dict]
):
    """No highlighting is added at all, so a learner's own tags are all there is."""
    topic = next(t for t in topics if "schedul" in t["name"].lower())
    resource = register(client, [topic["id"]])
    write_note(
        client,
        resource["id"],
        title="Markup",
        body="Scheduling uses a queue and a comparison a < b holds.",
    )

    passage = search(client, topic["id"])["passages"][0]["passage"]

    assert "<b>" not in passage
    assert "</b>" not in passage
    assert "a < b" in passage


def test_the_learners_own_characters_survive_retrieval(
    client: TestClient, learner: dict, topics: list[dict]
):
    topic = next(t for t in topics if "schedul" in t["name"].lower())
    resource = register(client, [topic["id"]])
    write_note(
        client,
        resource["id"],
        title="Unicode",
        body="Scheduling: quantum ≈ 10 ms — see §4.2 for the Résumé of results ⇒ fairness.",
    )

    passage = search(client, topic["id"])["passages"][0]["passage"]

    for character in ("≈", "—", "§", "Résumé", "⇒"):
        assert character in passage


def test_more_relevant_notes_come_first(client: TestClient, learner: dict, topics: list[dict]):
    topic = next(t for t in topics if "schedul" in t["name"].lower())
    resource = register(client, [topic["id"]])
    write_note(
        client,
        resource["id"],
        title="Passing mention",
        body="A paragraph about memory that mentions scheduling once at the end.",
    )
    write_note(
        client,
        resource["id"],
        title="All about it",
        body=(
            "Scheduling, scheduling, scheduling. The scheduler schedules processes "
            "and every scheduling decision is a scheduling trade-off."
        ),
    )

    passages = search(client, topic["id"])["passages"]

    assert [p["note_title"] for p in passages] == ["All about it", "Passing mention"]


def test_the_same_search_twice_returns_the_same_order(
    client: TestClient, learner: dict, topics: list[dict]
):
    topic = next(t for t in topics if "schedul" in t["name"].lower())
    resource = register(client, [topic["id"]])
    for index in range(4):
        write_note(client, resource["id"], title=f"Note {index}", body="Scheduling matters here.")

    first = [p["note_id"] for p in search(client, topic["id"])["passages"]]
    second = [p["note_id"] for p in search(client, topic["id"])["passages"]]

    assert first == second
    assert len(first) == 4


# -- eligibility, as the SQL expresses it -------------------------------------


def test_a_note_put_aside_is_not_retrieved(client: TestClient, learner: dict, topics: list[dict]):
    topic = next(t for t in topics if "schedul" in t["name"].lower())
    resource = register(client, [topic["id"]])
    note = write_note(client, resource["id"], title="Scheduling", body="Scheduling notes.")
    client.patch(f"/api/v1/resource-notes/{note['id']}", json={"status": "archived"})

    assert search(client, topic["id"])["outcome"] == "no_active_notes"


def test_a_note_on_material_put_aside_is_not_retrieved(
    client: TestClient, learner: dict, topics: list[dict]
):
    topic = next(t for t in topics if "schedul" in t["name"].lower())
    resource = register(client, [topic["id"]])
    write_note(client, resource["id"], title="Scheduling", body="Scheduling notes.")
    client.patch(f"{RESOURCES}/{resource['id']}", json={"status": "archived"})

    assert search(client, topic["id"])["outcome"] == "no_linked_material"


def test_a_note_on_material_linked_elsewhere_is_not_retrieved(
    client: TestClient, learner: dict, topics: list[dict]
):
    """Linkage is what bounds the search, so an unlinked topic finds nothing."""
    scheduling = next(t for t in topics if "schedul" in t["name"].lower())
    other = next(t for t in topics if t["id"] != scheduling["id"])
    resource = register(client, [other["id"]])
    write_note(client, resource["id"], title="Scheduling", body="All about scheduling.")

    assert search(client, scheduling["id"])["outcome"] == "no_linked_material"


def test_bringing_material_back_makes_its_notes_retrievable_again(
    client: TestClient, learner: dict, topics: list[dict]
):
    """Archiving is reversible here as everywhere else."""
    topic = next(t for t in topics if "schedul" in t["name"].lower())
    resource = register(client, [topic["id"]])
    write_note(client, resource["id"], title="Scheduling", body="Scheduling notes.")
    client.patch(f"{RESOURCES}/{resource['id']}", json={"status": "archived"})
    client.patch(f"{RESOURCES}/{resource['id']}", json={"status": "registered"})

    assert search(client, topic["id"])["outcome"] == "found"


def test_correcting_a_note_changes_what_the_next_search_finds(
    client: TestClient, learner: dict, topics: list[dict]
):
    """A live read, so a correction is reflected immediately.

    This is why ADR-037's correction argument survives: nothing derived is
    stored, so there is no record that could disagree with the corrected note.
    """
    topic = next(t for t in topics if "schedul" in t["name"].lower())
    resource = register(client, [topic["id"]])
    note = write_note(client, resource["id"], title="Draft", body="Nothing relevant here.")

    assert search(client, topic["id"])["outcome"] == "no_matching_passage"

    client.patch(
        f"/api/v1/resource-notes/{note['id']}",
        json={"body": "Corrected: this is about scheduling after all."},
    )

    data = search(client, topic["id"])
    assert data["outcome"] == "found"
    assert "scheduling" in data["passages"][0]["passage"].lower()


# -- what a search does not do ------------------------------------------------


def test_searching_writes_nothing_at_all(
    client: TestClient, learner: dict, topics: list[dict], session: Session
):
    from app.infrastructure.persistence.learner_planning import PlanItem, StudyPlan
    from app.infrastructure.persistence.progress import LearnerTopicProgress, RevisionRecord

    topic = next(t for t in topics if "schedul" in t["name"].lower())
    resource = register(client, [topic["id"]])
    write_note(client, resource["id"], title="Scheduling", body="Scheduling notes.")
    before = session.scalar(select(ResourceNote.updated_at))

    search(client, topic["id"])
    search(client, topic["id"])

    session.expire_all()
    assert session.scalar(select(ResourceNote.updated_at)) == before
    assert session.scalar(select(func.count()).select_from(LearnerTopicProgress)) == 0
    assert session.scalar(select(func.count()).select_from(RevisionRecord)) == 0
    assert session.scalar(select(func.count()).select_from(StudyPlan)) == 0
    assert session.scalar(select(func.count()).select_from(PlanItem)) == 0


def test_no_table_records_that_a_search_happened(
    client: TestClient, learner: dict, topics: list[dict], migrated_database: Engine
):
    """There is deliberately no search history."""
    from sqlalchemy import inspect

    topic = next(t for t in topics if "schedul" in t["name"].lower())
    search(client, topic["id"])

    tables = set(inspect(migrated_database).get_table_names())

    for absent in ("note_searches", "search_history", "retrieval_log", "queries"):
        assert absent not in tables


def test_searching_before_setup_is_a_conflict(client: TestClient, topics: list[dict]):
    """No learner exists to own notes until LRN-002 has run."""
    response = client.get(SEARCH, params={"topic_id": topics[0]["id"]})

    assert response.status_code == 409
