"""Learning-resource constraints against a real PostgreSQL database.

Covers the testing requirements in docs/database/migrations.md for migration
``20260816_01``: it runs against an empty database, its keys, constraints, and
indexes are verified, and the downgrade path is exercised by the fixture
teardown.

Constraints are asserted by attempting the write they exist to prevent. A
constraint that is documented but not enforced is indistinguishable from one that
is, until real learner data depends on it.

Two of ADR-032's departures from docs/database/schema.md are asserted directly:
the *names a location* check, which expresses the approved "at least one of
`storage_key` or `external_reference`" invariant over the two columns a catalogue
that stores no files actually has, and the absence of `storage_key` and
`metadata` themselves.
"""

import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.persistence.curriculum import (
    CurriculumVersion,
    LearningProgram,
    Subject,
    Topic,
)
from app.infrastructure.persistence.learner_planning import Learner
from app.infrastructure.persistence.resources import (
    RESOURCE_STATUSES,
    RESOURCE_TOPIC_ROLES,
    RESOURCE_TYPES,
    Resource,
    ResourceTopicLink,
)


class Fixture:
    """A learner and a topic for a resource to belong to and cover."""

    def __init__(self, learner: Learner, topic: Topic, heading: Topic) -> None:
        self.learner = learner
        self.topic = topic
        self.heading = heading


def make_fixture(session: Session) -> Fixture:
    """Store the reference data and learner a resource points at."""
    program = LearningProgram(code=f"gate-{uuid.uuid4().hex[:8]}", name="GATE Computer Science")
    session.add(program)
    session.flush()
    version = CurriculumVersion(
        learning_program_id=program.id, version_label="2027", status="active"
    )
    session.add(version)
    session.flush()
    subject = Subject(
        curriculum_version_id=version.id, code="operating-systems", name="OS", position=1
    )
    session.add(subject)
    session.flush()
    heading = Topic(subject_id=subject.id, name="Operating Systems", position=1, is_trackable=False)
    session.add(heading)
    session.flush()
    topic = Topic(
        subject_id=subject.id,
        parent_topic_id=heading.id,
        name="CPU scheduling",
        position=1,
        is_trackable=True,
    )
    session.add(topic)
    learner = Learner(display_name="Local learner", timezone="Asia/Kolkata")
    session.add(learner)
    session.commit()
    return Fixture(learner, topic, heading)


def make_resource(fixture: Fixture, **overrides) -> Resource:
    """A resource of the fixture's learner, with one field varied at a time."""
    values = {
        "owner_learner_id": fixture.learner.id,
        "resource_type": "note",
        "title": "Process scheduling notes",
        "source_label": "Blue binder, chapter 3",
        "external_reference": None,
        "status": "registered",
    }
    values.update(overrides)
    return Resource(**values)


def test_upgrade_creates_both_resource_tables(migrated_database: Engine):
    tables = set(inspect(migrated_database).get_table_names())

    assert "resources" in tables
    assert "resource_topic_links" in tables


def test_ingestion_is_not_created(migrated_database: Engine):
    """It arrives with the extractor and the vector index that give it work."""
    assert "resource_ingestions" not in set(inspect(migrated_database).get_table_names())


def test_no_file_columns_are_created(migrated_database: Engine):
    """`storage_key` and `metadata` describe a stored file, and nothing uploads one."""
    columns = {column["name"] for column in inspect(migrated_database).get_columns("resources")}

    assert "storage_key" not in columns
    assert "metadata" not in columns


def test_downgrade_removes_both_resource_tables(migrated_database: Engine, alembic_config: Config):
    """Alembic keeps its own version table, so the assertion is on ours."""
    migrated_database.dispose()

    command.downgrade(alembic_config, "base")

    tables = set(inspect(migrated_database).get_table_names())
    assert "resources" not in tables
    assert "resource_topic_links" not in tables


def test_the_documented_indexes_exist(migrated_database: Engine):
    """The two access patterns schema.md lists for this area."""
    inspector = inspect(migrated_database)
    resources = {
        index["name"]: index["column_names"] for index in inspector.get_indexes("resources")
    }
    links = {
        index["name"]: index["column_names"]
        for index in inspector.get_indexes("resource_topic_links")
    }

    assert resources["ix_resources_owner_learner_id_status"] == ["owner_learner_id", "status"]
    assert links["ix_resource_topic_links_topic_id_resource_id"] == ["topic_id", "resource_id"]


def test_a_resource_stores_and_reads_back(migrated_database: Engine):
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_resource(fixture))
        session.commit()

        stored = session.query(Resource).one()
        assert stored.title == "Process scheduling notes"
        assert stored.resource_type == "note"
        assert stored.status == "registered"
        assert stored.source_label == "Blue binder, chapter 3"
        assert stored.external_reference is None


@pytest.mark.parametrize("resource_type", RESOURCE_TYPES)
def test_every_permitted_type_is_accepted(migrated_database: Engine, resource_type: str):
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_resource(fixture, resource_type=resource_type))
        session.commit()

        assert session.query(Resource).one().resource_type == resource_type


@pytest.mark.parametrize("resource_type", ["image", "attachment", "invented"])
def test_a_type_this_build_does_not_catalogue_is_refused(
    migrated_database: Engine, resource_type: str
):
    """`image` and `attachment` name uploaded files, and nothing uploads one."""
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_resource(fixture, resource_type=resource_type))

        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.parametrize("status", RESOURCE_STATUSES)
def test_every_permitted_status_is_accepted(migrated_database: Engine, status: str):
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_resource(fixture, status=status))
        session.commit()

        assert session.query(Resource).one().status == status


@pytest.mark.parametrize("status", ["processing", "ready", "failed"])
def test_an_ingestion_status_is_refused(migrated_database: Engine, status: str):
    """A resource could enter one and never leave it: nothing runs an ingestion."""
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_resource(fixture, status=status))

        with pytest.raises(IntegrityError):
            session.commit()


def test_a_resource_naming_no_location_is_refused(migrated_database: Engine):
    """schema.md's "at least one of storage_key or external_reference", read for a
    catalogue that stores no files."""
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_resource(fixture, source_label=None, external_reference=None))

        with pytest.raises(IntegrityError):
            session.commit()


def test_a_link_alone_is_a_location(migrated_database: Engine):
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(
            make_resource(
                fixture,
                source_label=None,
                external_reference="https://example.test/notes.pdf",
            )
        )
        session.commit()

        assert session.query(Resource).one().source_label is None


def test_a_resource_may_belong_to_no_learner(migrated_database: Engine):
    """Reserved for curated or shared content; the application writes no such row."""
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_resource(fixture, owner_learner_id=None))
        session.commit()

        assert session.query(Resource).one().owner_learner_id is None


def test_a_resource_belonging_to_no_stored_learner_is_refused(migrated_database: Engine):
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_resource(fixture, owner_learner_id=uuid.uuid4()))

        with pytest.raises(IntegrityError):
            session.commit()


def test_a_topic_link_stores_and_reads_back(migrated_database: Engine):
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        resource = make_resource(fixture)
        session.add(resource)
        session.flush()
        session.add(
            ResourceTopicLink(
                resource_id=resource.id, topic_id=fixture.topic.id, relationship_type="primary"
            )
        )
        session.commit()

        stored = session.query(ResourceTopicLink).one()
        assert stored.topic_id == fixture.topic.id
        assert stored.relationship_type == "primary"


def test_a_resource_may_cover_a_topic_that_only_groups_subtopics(migrated_database: Engine):
    """Where this differs from `learner_topic_progress`, which the application
    restricts to a trackable topic."""
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        resource = make_resource(fixture)
        session.add(resource)
        session.flush()
        session.add(
            ResourceTopicLink(
                resource_id=resource.id, topic_id=fixture.heading.id, relationship_type="primary"
            )
        )
        session.commit()

        assert session.query(ResourceTopicLink).one().topic_id == fixture.heading.id


@pytest.mark.parametrize("role", RESOURCE_TOPIC_ROLES)
def test_every_documented_link_role_is_accepted(migrated_database: Engine, role: str):
    """All four, although only `primary` is written: offering the rest later is a
    use-case change rather than a migration."""
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        resource = make_resource(fixture)
        session.add(resource)
        session.flush()
        session.add(
            ResourceTopicLink(
                resource_id=resource.id, topic_id=fixture.topic.id, relationship_type=role
            )
        )
        session.commit()

        assert session.query(ResourceTopicLink).one().relationship_type == role


def test_an_unknown_link_role_is_refused(migrated_database: Engine):
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        resource = make_resource(fixture)
        session.add(resource)
        session.flush()
        session.add(
            ResourceTopicLink(
                resource_id=resource.id, topic_id=fixture.topic.id, relationship_type="essential"
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()


def test_the_same_topic_cannot_be_linked_twice_in_the_same_role(migrated_database: Engine):
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        resource = make_resource(fixture)
        session.add(resource)
        session.flush()
        session.add(
            ResourceTopicLink(
                resource_id=resource.id, topic_id=fixture.topic.id, relationship_type="primary"
            )
        )
        session.flush()
        session.add(
            ResourceTopicLink(
                resource_id=resource.id, topic_id=fixture.topic.id, relationship_type="primary"
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()


def test_a_link_to_a_topic_that_is_not_stored_is_refused(migrated_database: Engine):
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        resource = make_resource(fixture)
        session.add(resource)
        session.flush()
        session.add(
            ResourceTopicLink(
                resource_id=resource.id, topic_id=uuid.uuid4(), relationship_type="primary"
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()


def test_a_learner_row_cannot_be_removed_while_material_references_it(
    migrated_database: Engine,
):
    """Nothing deletes a resource, and the foreign key is deliberately not a
    cascade: learner-owned records outlive the screen that created them."""
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_resource(fixture))
        session.commit()

        session.delete(session.get(Learner, fixture.learner.id))
        with pytest.raises(IntegrityError):
            session.commit()


def test_registering_material_touches_no_other_learner_record(migrated_database: Engine):
    """A resource is metadata beside the learner's work, never part of it."""
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_resource(fixture))
        session.commit()

        assert session.query(Resource).count() == 1
        assert session.query(Topic).count() == 2
        assert session.get(Learner, fixture.learner.id) is not None


def test_a_resource_records_when_it_was_registered_and_changed(migrated_database: Engine):
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_resource(fixture))
        session.commit()

        stored = session.query(Resource).one()
        assert stored.created_at is not None
        assert stored.updated_at is not None


def test_a_topic_link_records_only_when_it_was_created(migrated_database: Engine):
    """Write-once, as `topic_relationships` is."""
    columns = {
        column["name"] for column in inspect(migrated_database).get_columns("resource_topic_links")
    }

    assert "created_at" in columns
    assert "updated_at" not in columns


def test_the_link_primary_key_covers_resource_topic_and_role(migrated_database: Engine):
    key = inspect(migrated_database).get_pk_constraint("resource_topic_links")

    assert key["constrained_columns"] == ["resource_id", "topic_id", "relationship_type"]


def test_a_stored_resource_reads_back_with_its_topics(migrated_database: Engine):
    """The join the catalogue, curriculum, and revision screens all read."""
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        resource = make_resource(fixture)
        session.add(resource)
        session.flush()
        session.add(
            ResourceTopicLink(
                resource_id=resource.id, topic_id=fixture.topic.id, relationship_type="primary"
            )
        )
        session.commit()

        linked = (
            session.query(Topic)
            .join(ResourceTopicLink, ResourceTopicLink.topic_id == Topic.id)
            .filter(ResourceTopicLink.resource_id == resource.id)
            .all()
        )
        assert [topic.name for topic in linked] == ["CPU scheduling"]
