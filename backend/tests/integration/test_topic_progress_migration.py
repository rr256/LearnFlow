"""Topic-progress constraints against a real PostgreSQL database.

Covers the testing requirements in docs/database/migrations.md for migration
``20260805_01``: it runs against an empty database, its keys and constraints are
verified, and the downgrade path is exercised by the fixture teardown.

Constraints are asserted by attempting the write they exist to prevent. A
constraint that is documented but not enforced is indistinguishable from one that
is, until real learner data depends on it.
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
from app.infrastructure.persistence.progress import LEARNING_STAGES, LearnerTopicProgress

PROGRESS_TABLES = {"learner_topic_progress"}


def make_topic(session: Session, *, name: str = "CPU scheduling") -> Topic:
    program = LearningProgram(code=f"gate-{uuid.uuid4().hex[:8]}", name="GATE Computer Science")
    session.add(program)
    session.flush()
    version = CurriculumVersion(
        learning_program_id=program.id, version_label="2027", status="active"
    )
    session.add(version)
    session.flush()
    subject = Subject(
        curriculum_version_id=version.id,
        code="operating-systems",
        name="Operating Systems",
        position=1,
    )
    session.add(subject)
    session.flush()
    topic = Topic(subject_id=subject.id, name=name, position=1, is_trackable=True)
    session.add(topic)
    session.commit()
    return topic


def make_learner(session: Session) -> Learner:
    learner = Learner(display_name="Local learner", timezone="Asia/Kolkata")
    session.add(learner)
    session.commit()
    return learner


def test_upgrade_creates_the_progress_table(migrated_database: Engine):
    tables = set(inspect(migrated_database).get_table_names())

    assert PROGRESS_TABLES <= tables


def test_downgrade_returns_the_database_to_empty(migrated_database: Engine, alembic_config: Config):
    migrated_database.dispose()

    command.downgrade(alembic_config, "base")

    assert set(inspect(migrated_database).get_table_names()) & PROGRESS_TABLES == set()


def test_the_columns_awaiting_their_own_code_are_not_created(migrated_database: Engine):
    """`material_status`, `material_completed_at`, and `last_studied_at` remain an
    approved target in schema.md. Each arrives with the change that writes it."""
    columns = {
        column["name"]
        for column in inspect(migrated_database).get_columns("learner_topic_progress")
    }

    assert columns == {
        "id",
        "learner_id",
        "topic_id",
        "learning_stage",
        "stage_source",
        "created_at",
        "updated_at",
    }


@pytest.mark.parametrize("stage", LEARNING_STAGES)
def test_every_approved_stage_is_accepted(session: Session, stage: str):
    topic = make_topic(session)
    learner = make_learner(session)

    session.add(
        LearnerTopicProgress(
            learner_id=learner.id,
            topic_id=topic.id,
            learning_stage=stage,
            stage_source="learner",
        )
    )
    session.commit()

    assert session.query(LearnerTopicProgress).count() == 1


def test_an_unknown_learning_stage_is_refused(session: Session):
    topic = make_topic(session)
    learner = make_learner(session)

    session.add(
        LearnerTopicProgress(
            learner_id=learner.id,
            topic_id=topic.id,
            learning_stage="mastered",
            stage_source="learner",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_an_unknown_stage_source_is_refused(session: Session):
    topic = make_topic(session)
    learner = make_learner(session)

    session.add(
        LearnerTopicProgress(
            learner_id=learner.id,
            topic_id=topic.id,
            learning_stage="practice_ready",
            stage_source="the_mentor",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_learner_cannot_hold_two_records_for_one_topic(session: Session):
    """What makes recording a stage an update rather than an append."""
    topic = make_topic(session)
    learner = make_learner(session)
    session.add(
        LearnerTopicProgress(
            learner_id=learner.id,
            topic_id=topic.id,
            learning_stage="building_foundation",
            stage_source="learner",
        )
    )
    session.commit()

    session.add(
        LearnerTopicProgress(
            learner_id=learner.id,
            topic_id=topic.id,
            learning_stage="practice_ready",
            stage_source="learner",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_two_learners_may_each_record_a_stage_for_one_topic(session: Session):
    """Uniqueness is per learner and topic, not per topic."""
    topic = make_topic(session)
    first, second = make_learner(session), make_learner(session)

    session.add_all(
        [
            LearnerTopicProgress(
                learner_id=learner.id,
                topic_id=topic.id,
                learning_stage="practice_ready",
                stage_source="learner",
            )
            for learner in (first, second)
        ]
    )
    session.commit()

    assert session.query(LearnerTopicProgress).count() == 2


def test_progress_cannot_reference_a_topic_that_does_not_exist(session: Session):
    learner = make_learner(session)

    session.add(
        LearnerTopicProgress(
            learner_id=learner.id,
            topic_id=uuid.uuid4(),
            learning_stage="practice_ready",
            stage_source="learner",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_progress_cannot_reference_a_learner_that_does_not_exist(session: Session):
    topic = make_topic(session)

    session.add(
        LearnerTopicProgress(
            learner_id=uuid.uuid4(),
            topic_id=topic.id,
            learning_stage="practice_ready",
            stage_source="learner",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_stage_and_its_source_are_both_required(session: Session):
    topic = make_topic(session)
    learner = make_learner(session)

    session.add(
        LearnerTopicProgress(
            learner_id=learner.id, topic_id=topic.id, learning_stage=None, stage_source="learner"
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_progress_audit_timestamps_are_populated_by_the_database(session: Session):
    topic = make_topic(session)
    learner = make_learner(session)
    record = LearnerTopicProgress(
        learner_id=learner.id,
        topic_id=topic.id,
        learning_stage="practice_ready",
        stage_source="learner",
    )
    session.add(record)
    session.commit()

    session.refresh(record)

    assert record.created_at is not None
    assert record.updated_at is not None
    assert record.created_at.tzinfo is not None
