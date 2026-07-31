"""Migration and constraint behaviour against a real PostgreSQL database.

Covers the testing requirements in docs/database/migrations.md: the migration
runs against an empty database, keys, constraints and indexes are verified, and
the downgrade path is exercised.

Constraints are asserted by attempting the write they exist to prevent. A
constraint that is documented but not enforced is indistinguishable from one
that is, until real learner data depends on it.
"""

import uuid

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.curriculum import (
    CurriculumVersion,
    LearningProgram,
    Subject,
    Topic,
    TopicRelationship,
)

CURRICULUM_TABLES = {
    "learning_programs",
    "curriculum_versions",
    "subjects",
    "topics",
    "topic_relationships",
}


def make_program(session: Session, code: str = "gate-cse") -> LearningProgram:
    program = LearningProgram(code=code, name="GATE Computer Science")
    session.add(program)
    session.commit()
    return program


def make_version(
    session: Session,
    program: LearningProgram,
    version_label: str = "2026",
    status: str = "active",
) -> CurriculumVersion:
    version = CurriculumVersion(
        learning_program_id=program.id, version_label=version_label, status=status
    )
    session.add(version)
    session.commit()
    return version


def make_subject(session: Session, version: CurriculumVersion, position: int = 1) -> Subject:
    subject = Subject(
        curriculum_version_id=version.id,
        code=f"subject-{position}",
        name="Operating Systems",
        position=position,
    )
    session.add(subject)
    session.commit()
    return subject


def make_topic(session: Session, subject: Subject, name: str, position: int = 1) -> Topic:
    topic = Topic(subject_id=subject.id, name=name, position=position, is_trackable=True)
    session.add(topic)
    session.commit()
    return topic


def test_upgrade_creates_every_curriculum_table(migrated_database: Engine):
    tables = set(inspect(migrated_database).get_table_names())

    assert CURRICULUM_TABLES <= tables


def test_models_match_the_migrated_schema(migrated_database: Engine):
    """The hand-written migration must describe exactly what the models map.

    Drift here means a fresh database and a developer's models disagree, which
    surfaces later as a failing query rather than a failing migration.
    """
    with migrated_database.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        differences = compare_metadata(context, Base.metadata)

    assert differences == []


def test_downgrade_returns_the_database_to_empty(migrated_database: Engine, alembic_config: Config):
    migrated_database.dispose()

    command.downgrade(alembic_config, "base")

    remaining = set(inspect(migrated_database).get_table_names())
    assert remaining & CURRICULUM_TABLES == set()


def test_learning_program_code_is_unique(session: Session):
    make_program(session, code="gate-cse")

    session.add(LearningProgram(code="gate-cse", name="A second program"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_only_one_curriculum_version_can_be_active_per_program(session: Session):
    program = make_program(session)
    make_version(session, program, version_label="2026", status="active")

    session.add(
        CurriculumVersion(learning_program_id=program.id, version_label="2027", status="active")
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_draft_and_retired_versions_may_accompany_an_active_one(session: Session):
    program = make_program(session)
    make_version(session, program, version_label="2026", status="active")

    session.add_all(
        [
            CurriculumVersion(learning_program_id=program.id, version_label="2027", status="draft"),
            CurriculumVersion(
                learning_program_id=program.id, version_label="2025", status="retired"
            ),
        ]
    )
    session.commit()

    assert session.query(CurriculumVersion).count() == 3


def test_curriculum_version_status_must_be_a_documented_value(session: Session):
    program = make_program(session)

    session.add(
        CurriculumVersion(learning_program_id=program.id, version_label="2026", status="published")
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_version_label_is_unique_within_a_program(session: Session):
    program = make_program(session)
    make_version(session, program, version_label="2026", status="active")

    session.add(
        CurriculumVersion(learning_program_id=program.id, version_label="2026", status="draft")
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_subject_position_is_unique_within_a_curriculum_version(session: Session):
    version = make_version(session, make_program(session))
    make_subject(session, version, position=1)

    session.add(
        Subject(curriculum_version_id=version.id, code="another", name="Databases", position=1)
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_two_root_topics_in_a_subject_cannot_share_a_name(session: Session):
    """The NULLS NOT DISTINCT case: both parents are NULL, and the constraint
    must still apply."""
    subject = make_subject(session, make_version(session, make_program(session)))
    make_topic(session, subject, name="Deadlock", position=1)

    session.add(Topic(subject_id=subject.id, name="Deadlock", position=2, is_trackable=True))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_two_topics_in_a_subject_cannot_share_a_code(session: Session):
    subject = make_subject(session, make_version(session, make_program(session)))
    session.add(
        Topic(
            subject_id=subject.id, code="deadlock", name="Deadlock", position=1, is_trackable=True
        )
    )
    session.commit()

    session.add(
        Topic(
            subject_id=subject.id,
            code="deadlock",
            name="Deadlock handling",
            position=2,
            is_trackable=True,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_subtopic_cannot_reuse_a_code_used_by_a_topic_under_another_parent(session: Session):
    """Code uniqueness spans the whole subject, unlike name uniqueness, which
    applies only among siblings."""
    subject = make_subject(session, make_version(session, make_program(session)))
    first_parent = make_topic(session, subject, name="Scheduling", position=1)
    second_parent = make_topic(session, subject, name="Memory", position=2)

    session.add(
        Topic(
            subject_id=subject.id,
            parent_topic_id=first_parent.id,
            code="overview",
            name="Overview",
            position=1,
            is_trackable=True,
        )
    )
    session.commit()

    session.add(
        Topic(
            subject_id=subject.id,
            parent_topic_id=second_parent.id,
            code="overview",
            name="Overview",
            position=1,
            is_trackable=True,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_two_subjects_may_use_the_same_topic_code(session: Session):
    version = make_version(session, make_program(session))
    first = make_subject(session, version, position=1)
    second = make_subject(session, version, position=2)

    session.add_all(
        [
            Topic(subject_id=first.id, code="basics", name="Basics", position=1, is_trackable=True),
            Topic(
                subject_id=second.id, code="basics", name="Basics", position=1, is_trackable=True
            ),
        ]
    )
    session.commit()

    assert session.query(Topic).filter_by(code="basics").count() == 2


def test_many_topics_in_a_subject_may_leave_the_code_null(session: Session):
    """`code` is optional and the curated GATE CSE curriculum omits it entirely,
    so this constraint keeps the default NULLS DISTINCT behaviour. Declaring it
    NULLS NOT DISTINCT, as the name constraint does, would allow only one
    uncoded topic per subject."""
    subject = make_subject(session, make_version(session, make_program(session)))

    session.add_all(
        [
            Topic(subject_id=subject.id, name="Deadlock", position=1, is_trackable=True),
            Topic(subject_id=subject.id, name="File systems", position=2, is_trackable=True),
            Topic(subject_id=subject.id, name="Paging", position=3, is_trackable=True),
        ]
    )
    session.commit()

    assert session.query(Topic).filter(Topic.code.is_(None)).count() == 3


def test_a_subtopic_may_reuse_a_name_used_under_a_different_parent(session: Session):
    subject = make_subject(session, make_version(session, make_program(session)))
    first_parent = make_topic(session, subject, name="Scheduling", position=1)
    second_parent = make_topic(session, subject, name="Memory", position=2)

    session.add_all(
        [
            Topic(
                subject_id=subject.id,
                parent_topic_id=first_parent.id,
                name="Overview",
                position=1,
                is_trackable=True,
            ),
            Topic(
                subject_id=subject.id,
                parent_topic_id=second_parent.id,
                name="Overview",
                position=1,
                is_trackable=True,
            ),
        ]
    )
    session.commit()

    assert session.query(Topic).filter_by(name="Overview").count() == 2


def test_a_topic_cannot_be_its_own_prerequisite(session: Session):
    subject = make_subject(session, make_version(session, make_program(session)))
    topic = make_topic(session, subject, name="Paging", position=1)

    session.add(
        TopicRelationship(
            source_topic_id=topic.id,
            target_topic_id=topic.id,
            relationship_type="prerequisite",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_topic_relationship_type_must_be_a_documented_value(session: Session):
    subject = make_subject(session, make_version(session, make_program(session)))
    source = make_topic(session, subject, name="Paging", position=1)
    target = make_topic(session, subject, name="Segmentation", position=2)

    session.add(
        TopicRelationship(
            source_topic_id=source.id,
            target_topic_id=target.id,
            relationship_type="see_also",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_topic_cannot_reference_a_subject_that_does_not_exist(session: Session):
    session.add(Topic(subject_id=uuid.uuid4(), name="Orphan", position=1, is_trackable=True))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_audit_timestamps_are_populated_by_the_database(session: Session):
    program = make_program(session)

    session.refresh(program)

    assert program.created_at is not None
    assert program.updated_at is not None
    assert program.created_at.tzinfo is not None
