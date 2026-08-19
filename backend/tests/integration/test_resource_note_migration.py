"""Resource-note constraints against a real PostgreSQL database.

Covers the testing requirements in docs/database/migrations.md for migration
``20260819_01``: it runs against an empty database, its key, constraints, and
index are verified, and the downgrade path is exercised by the fixture teardown.

Constraints are asserted by attempting the write they exist to prevent. A
constraint that is documented but not enforced is indistinguishable from one that
is, until real learner data depends on it.

Two properties peculiar to this table are asserted directly, because both are
promises made to the learner rather than ordinary schema facts:

- ``body`` is **unbounded** ``text``, so the 20,000-character limit stays an
  application rule that can be raised without a migration.
- **No derived representation is stored beside a note.** Chunks, embeddings, and
  vectors are docs/domain/entities.md non-entities; if retrieval is ever built
  they belong in the vector index, rebuildable from this table, never in it.
"""

import uuid

import pytest
from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.persistence.learner_planning import Learner
from app.infrastructure.persistence.resources import (
    RESOURCE_NOTE_STATUSES,
    Resource,
    ResourceNote,
)


def make_resource(session: Session) -> Resource:
    """A learner and one piece of catalogued material for a note to belong to."""
    learner = Learner(display_name="Asha", timezone="Asia/Kolkata")
    session.add(learner)
    session.flush()
    resource = Resource(
        owner_learner_id=learner.id,
        resource_type="note",
        title="Operating Systems notes",
        source_label="Blue binder",
        status="registered",
    )
    session.add(resource)
    session.flush()
    return resource


def note(resource: Resource, **fields) -> ResourceNote:
    """One storable note, with any field overridden."""
    values = {
        "resource_id": resource.id,
        "title": "Deadlock conditions",
        "body": "Mutual exclusion, hold and wait.",
        "status": "active",
    }
    values.update(fields)
    return ResourceNote(**values)


def test_the_table_and_its_index_are_created(migrated_database: Engine):
    inspector = inspect(migrated_database)

    assert "resource_notes" in inspector.get_table_names()
    indexes = {index["name"] for index in inspector.get_indexes("resource_notes")}
    assert "ix_resource_notes_resource_id_status" in indexes


def test_the_index_covers_the_documented_access_pattern(migrated_database: Engine):
    """One resource's notes, and whether they are put aside."""
    inspector = inspect(migrated_database)

    index = next(
        entry
        for entry in inspector.get_indexes("resource_notes")
        if entry["name"] == "ix_resource_notes_resource_id_status"
    )

    assert index["column_names"] == ["resource_id", "status"]


def test_the_primary_key_follows_the_naming_convention(migrated_database: Engine):
    inspector = inspect(migrated_database)

    key = inspector.get_pk_constraint("resource_notes")

    assert key["name"] == "pk_resource_notes"
    assert key["constrained_columns"] == ["id"]


def test_a_note_references_the_material_it_was_written_against(migrated_database: Engine):
    inspector = inspect(migrated_database)

    keys = inspector.get_foreign_keys("resource_notes")

    assert len(keys) == 1
    assert keys[0]["name"] == "fk_resource_notes_resource_id_resources"
    assert keys[0]["referred_table"] == "resources"
    # Not a cascade: nothing deletes a resource, so a cascade would describe a
    # path that does not exist.
    assert not keys[0]["options"].get("ondelete")


def test_a_note_carries_no_topic_of_its_own(migrated_database: Engine):
    """It inherits the topics its resource covers, so the two cannot disagree."""
    inspector = inspect(migrated_database)

    columns = {column["name"] for column in inspector.get_columns("resource_notes")}

    assert "topic_id" not in columns
    assert "resource_note_topic_links" not in inspector.get_table_names()


def test_the_body_column_is_unbounded_text(migrated_database: Engine):
    """So the 20,000-character limit stays an application rule, not a column width.

    Raising it later is then a use-case change rather than a migration, which is
    the argument ADR-020 made for `plan_items.status`.
    """
    inspector = inspect(migrated_database)

    body = next(
        column for column in inspector.get_columns("resource_notes") if column["name"] == "body"
    )

    assert str(body["type"]).upper() == "TEXT"
    assert body["nullable"] is False


def test_no_derived_representation_is_stored_beside_a_note(migrated_database: Engine):
    """Chunks, embeddings, and vectors stay out of the source-of-truth table."""
    inspector = inspect(migrated_database)

    columns = {column["name"] for column in inspector.get_columns("resource_notes")}

    for absent in ("embedding", "vector", "chunk_index", "embedding_model", "fingerprint"):
        assert absent not in columns


def test_the_ingestion_table_is_still_absent(migrated_database: Engine):
    """Storing a learner's typed text is not ingestion, and does not create one.

    `resource_ingestions` tracks extraction and indexing, neither of which
    exists, and `resources.storage_key` and `resources.metadata` describe a
    stored file that nothing uploads.
    """
    inspector = inspect(migrated_database)

    assert "resource_notes" in inspector.get_table_names()
    assert "resource_ingestions" not in inspector.get_table_names()
    resource_columns = {column["name"] for column in inspector.get_columns("resources")}
    assert "storage_key" not in resource_columns
    assert "metadata" not in resource_columns


def test_a_note_status_outside_the_two_is_refused(session: Session):
    resource = make_resource(session)

    session.add(note(resource, status="indexed"))

    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("status", RESOURCE_NOTE_STATUSES)
def test_both_documented_statuses_are_storable(session: Session, status: str):
    """Both are written, unlike the resource statuses: nothing here waits on
    storage that does not exist."""
    resource = make_resource(session)

    session.add(note(resource, status=status))
    session.flush()
    session.expire_all()

    assert session.scalars(select(ResourceNote)).one().status == status


def test_a_note_with_no_text_is_refused(session: Session):
    resource = make_resource(session)

    session.add(note(resource, body=""))

    with pytest.raises(IntegrityError):
        session.flush()


def test_a_note_of_only_whitespace_is_refused(session: Session):
    """Tabs and newlines are not text either.

    `length(btrim(body)) > 0` would pass this, because PostgreSQL's one-argument
    `btrim` strips spaces alone. The check asks for a non-whitespace character
    instead.
    """
    resource = make_resource(session)

    session.add(note(resource, body="   \n\t  "))

    with pytest.raises(IntegrityError):
        session.flush()


def test_a_note_must_belong_to_stored_material(session: Session):
    orphan = ResourceNote(
        resource_id=uuid.uuid4(), title="Nowhere", body="Some text.", status="active"
    )
    session.add(orphan)

    with pytest.raises(IntegrityError):
        session.flush()


def test_a_long_note_is_stored_whole_and_unchanged(session: Session):
    """The column imposes no bound, and PostgreSQL alters nothing it stores."""
    resource = make_resource(session)
    pasted = 'Line one.\n\n\tIndented — with §, ⇒, and "quotes".\n' * 500

    session.add(note(resource, body=pasted))
    session.flush()
    session.expire_all()

    stored = session.scalars(select(ResourceNote)).one()
    assert stored.body == pasted


def test_the_body_column_does_not_truncate(session: Session):
    """A `varchar(n)` would raise here; `text` does not, which is the point."""
    resource = make_resource(session)
    long_note = "x" * 100_000

    session.add(note(resource, body=long_note))
    try:
        session.flush()
    except DataError as error:  # pragma: no cover - only if the column gains a width
        pytest.fail(f"The body column imposed a width: {error}")

    assert session.scalar(text("SELECT length(body) FROM resource_notes")) == 100_000


def test_timestamps_default_on_insert(session: Session):
    resource = make_resource(session)

    stored = note(resource)
    session.add(stored)
    session.flush()

    assert stored.created_at is not None
    assert stored.updated_at is not None
