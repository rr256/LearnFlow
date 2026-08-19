"""The resource-note endpoints against a real PostgreSQL database.

The API tests prove the contract against fakes. These prove the part a fake
cannot: that the SQL the repository emits really stores and returns a learner's
own text byte for byte, that the `CHECK` constraints agree with the rules the use
case enforces, and that a request reporting a failure commits nothing — all
through the same composition root the running backend uses.

**The text stored here is invented for the test.** Nothing in this repository
holds a learner's real notes, and nothing in this suite reads a file from disk to
fill one.

Skipped unless ``TEST_DATABASE_URL`` names a disposable database; see
tests/integration/conftest.py.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.application.dto.resource_note import MAX_NOTE_BODY_LENGTH
from app.composition.app_factory import create_app
from app.composition.config import Settings
from app.infrastructure.persistence.resources import Resource, ResourceNote

LEARNER = "/api/v1/learner"
RESOURCES = "/api/v1/resources"
NOTES = "/api/v1/resource-notes"


@pytest.fixture
def client(migrated_database: Engine, database_url: str) -> Iterator[TestClient]:
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
def resource(client: TestClient, learner: dict) -> dict:
    """One piece of catalogued material to keep notes against."""
    response = client.post(
        RESOURCES,
        json={
            "resource_type": "note",
            "title": "Operating Systems notes",
            "source_label": "Blue binder",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def write(client: TestClient, resource_id: str, **fields) -> dict:
    """Write one note over RES-009 and return it."""
    body = {"title": "Deadlock conditions", "body": "Mutual exclusion, hold and wait."}
    body.update(fields)
    response = client.post(f"{RESOURCES}/{resource_id}/notes", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_a_note_written_over_http_is_stored_and_reads_back(
    client: TestClient, resource: dict, session: Session
):
    written = write(client, resource["id"], title="Deadlocks", body="Four conditions hold.")

    stored = session.scalar(select(ResourceNote))
    assert stored is not None
    assert stored.title == "Deadlocks"
    assert stored.body == "Four conditions hold."
    assert stored.status == "active"
    assert str(stored.resource_id) == resource["id"]

    read_back = client.get(f"{NOTES}/{written['id']}").json()["data"]
    assert read_back == written


def test_a_learners_own_formatting_survives_the_database(
    client: TestClient, resource: dict, session: Session
):
    """The promise of the feature, proved against real storage.

    Line breaks, blank lines, tabs, and non-ASCII characters come back exactly as
    they went in. A column or a driver that normalised any of them would break
    what the learner wrote, and only a real database can show that it does not.
    """
    pasted = (
        "Banker's algorithm — safety check:\n"
        "\n"
        "\t1. Work := Available\n"
        "\t2. Finish[i] := false ∀ i\n"
        "\n"
        "    Need[i][j] = Max[i][j] − Allocation[i][j]\n"
        "\n"
        'Quote: "safe state ⇒ no deadlock"\n'
        "Résumé of §3.4 — see p. 42."
    )

    written = write(client, resource["id"], body=pasted)

    assert written["body"] == pasted
    assert session.scalar(select(ResourceNote.body)) == pasted
    assert client.get(f"{NOTES}/{written['id']}").json()["data"]["body"] == pasted


def test_markup_is_stored_as_the_characters_it_is(
    client: TestClient, resource: dict, session: Session
):
    """Nothing stored here is interpreted: it is text, and it stays text."""
    pasted = "<script>alert(1)</script> & <b>bold?</b> -- 'quoted' \"double\" \\backslash"

    written = write(client, resource["id"], body=pasted)

    assert written["body"] == pasted
    assert session.scalar(select(ResourceNote.body)) == pasted


def test_a_note_at_the_full_permitted_length_is_stored_whole(
    client: TestClient, resource: dict, session: Session
):
    """`body` is unbounded `text`, so the application's bound is the only one."""
    long_note = "x" * MAX_NOTE_BODY_LENGTH

    written = write(client, resource["id"], body=long_note)

    assert len(written["body"]) == MAX_NOTE_BODY_LENGTH
    assert session.scalar(select(func.length(ResourceNote.body))) == MAX_NOTE_BODY_LENGTH


def test_a_refused_note_commits_nothing(client: TestClient, resource: dict, session: Session):
    response = client.post(
        f"{RESOURCES}/{resource['id']}/notes",
        json={"title": "A title", "body": "y" * (MAX_NOTE_BODY_LENGTH + 1)},
    )

    assert response.status_code == 422
    assert "yyyy" not in response.text
    assert session.scalar(select(func.count()).select_from(ResourceNote)) == 0


def test_notes_come_back_newest_first(client: TestClient, resource: dict):
    write(client, resource["id"], title="First")
    write(client, resource["id"], title="Second")
    write(client, resource["id"], title="Third")

    body = client.get(f"{RESOURCES}/{resource['id']}/notes").json()

    assert [note["title"] for note in body["data"]] == ["Third", "Second", "First"]
    assert body["pagination"]["total"] == 3


def test_a_page_of_notes_neither_repeats_nor_omits_one(client: TestClient, resource: dict):
    """The identifier tiebreak, proved where `created_at` can genuinely collide."""
    for index in range(6):
        write(client, resource["id"], title=f"Note {index}")

    first = client.get(f"{RESOURCES}/{resource['id']}/notes", params={"limit": 3}).json()
    second = client.get(
        f"{RESOURCES}/{resource['id']}/notes", params={"limit": 3, "offset": 3}
    ).json()

    ids = [note["id"] for note in first["data"]] + [note["id"] for note in second["data"]]
    assert len(ids) == 6
    assert len(set(ids)) == 6


def test_only_the_named_resources_notes_are_listed(
    client: TestClient, resource: dict, learner: dict, client_second_resource: dict
):
    write(client, resource["id"], title="Mine")
    write(client, client_second_resource["id"], title="The other one's")

    body = client.get(f"{RESOURCES}/{resource['id']}/notes").json()

    assert [note["title"] for note in body["data"]] == ["Mine"]


@pytest.fixture
def client_second_resource(client: TestClient, learner: dict) -> dict:
    """A second piece of material, so a note cannot leak between two."""
    response = client.post(
        RESOURCES,
        json={"resource_type": "pyq", "title": "PYQ set", "source_label": "Red folder"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_a_note_is_corrected_in_place_without_creating_a_second_row(
    client: TestClient, resource: dict, session: Session
):
    written = write(client, resource["id"], body="First draft.")

    corrected = client.patch(f"{NOTES}/{written['id']}", json={"body": "Second draft."})

    assert corrected.status_code == 200
    assert session.scalar(select(func.count()).select_from(ResourceNote)) == 1
    assert session.scalar(select(ResourceNote.body)) == "Second draft."


def test_putting_a_note_aside_keeps_the_row_and_its_text(
    client: TestClient, resource: dict, session: Session
):
    """Nothing deletes: archiving moves a status and destroys nothing."""
    written = write(client, resource["id"], body="Worth keeping.")

    client.patch(f"{NOTES}/{written['id']}", json={"status": "archived"})

    stored = session.scalar(select(ResourceNote))
    assert stored is not None
    assert stored.status == "archived"
    assert stored.body == "Worth keeping."

    brought_back = client.patch(f"{NOTES}/{written['id']}", json={"status": "active"})
    assert brought_back.json()["data"]["body"] == "Worth keeping."


def test_a_note_cannot_be_written_or_changed_while_its_material_is_put_aside(
    client: TestClient, resource: dict, session: Session
):
    written = write(client, resource["id"])
    client.patch(f"{RESOURCES}/{resource['id']}", json={"status": "archived"})

    refused_write = client.post(
        f"{RESOURCES}/{resource['id']}/notes", json={"title": "New", "body": "Text."}
    )
    refused_change = client.patch(f"{NOTES}/{written['id']}", json={"body": "Changed."})

    assert refused_write.status_code == 409
    assert refused_change.status_code == 409
    assert session.scalar(select(func.count()).select_from(ResourceNote)) == 1
    assert session.scalar(select(ResourceNote.body)) == "Mutual exclusion, hold and wait."


def test_the_notes_of_material_put_aside_are_still_readable(client: TestClient, resource: dict):
    written = write(client, resource["id"], body="Still here.")
    client.patch(f"{RESOURCES}/{resource['id']}", json={"status": "archived"})

    assert client.get(f"{NOTES}/{written['id']}").json()["data"]["body"] == "Still here."
    listed = client.get(f"{RESOURCES}/{resource['id']}/notes").json()
    assert [note["id"] for note in listed["data"]] == [written["id"]]


def test_writing_a_note_writes_nothing_else(client: TestClient, resource: dict, session: Session):
    """A note says what the learner wrote, never that a topic is understood or
    that work happened, so no stage, plan, revision, or quiz is created."""
    from app.infrastructure.persistence.assessment import CheckpointQuiz, Question
    from app.infrastructure.persistence.learner_planning import PlanItem, StudyPlan
    from app.infrastructure.persistence.progress import LearnerTopicProgress, RevisionRecord
    from app.infrastructure.persistence.resources import ResourceTopicLink

    before = session.scalar(select(Resource.updated_at))

    write(client, resource["id"])

    assert session.scalar(select(func.count()).select_from(LearnerTopicProgress)) == 0
    assert session.scalar(select(func.count()).select_from(RevisionRecord)) == 0
    assert session.scalar(select(func.count()).select_from(StudyPlan)) == 0
    assert session.scalar(select(func.count()).select_from(PlanItem)) == 0
    assert session.scalar(select(func.count()).select_from(Question)) == 0
    assert session.scalar(select(func.count()).select_from(CheckpointQuiz)) == 0
    assert session.scalar(select(func.count()).select_from(ResourceTopicLink)) == 0
    assert session.scalar(select(Resource.updated_at)) == before


def test_a_note_against_unknown_material_is_not_found(
    client: TestClient, learner: dict, session: Session
):
    response = client.post(
        f"{RESOURCES}/00000000-0000-0000-0000-000000000001/notes",
        json={"title": "A title", "body": "Some text."},
    )

    assert response.status_code == 404
    assert session.scalar(select(func.count()).select_from(ResourceNote)) == 0
