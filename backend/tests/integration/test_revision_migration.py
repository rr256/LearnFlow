"""Revision constraints against a real PostgreSQL database.

Covers the testing requirements in docs/database/migrations.md for migration
``20260813_01``: it runs against an empty database, its keys, constraints, and
index are verified, and the downgrade path is exercised by the fixture teardown.

Constraints are asserted by attempting the write they exist to prevent. A
constraint that is documented but not enforced is indistinguishable from one that
is, until real learner data depends on it.

`status` and `trigger_type` are checked to be text guarded by a `CHECK` rather
than the bare `text` docs/database/schema.md describes, which is one of ADR-028's
two departures from that document's table. The other — `recommendation_reason` —
is asserted to exist, because a revision's date and its explanation must not be
able to drift apart.
"""

import uuid
from datetime import UTC, date, datetime

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
from app.infrastructure.persistence.learner_planning import Learner, PlanItem, StudyGoal, StudyPlan
from app.infrastructure.persistence.progress import (
    REVISION_STATUSES,
    REVISION_TRIGGERS,
    LearnerTopicProgress,
    RevisionRecord,
)


class Fixture:
    """A learner, a topic, and a completed plan item to revise."""

    def __init__(self, learner: Learner, topic: Topic, plan_item: PlanItem) -> None:
        self.learner = learner
        self.topic = topic
        self.plan_item = plan_item


def make_fixture(session: Session) -> Fixture:
    """Store the reference data and finished work a revision points at."""
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
    topic = Topic(subject_id=subject.id, name="CPU scheduling", position=1, is_trackable=True)
    session.add(topic)
    learner = Learner(display_name="Local learner", timezone="Asia/Kolkata")
    session.add(learner)
    session.flush()
    goal = StudyGoal(
        learner_id=learner.id,
        learning_program_id=program.id,
        curriculum_version_id=version.id,
        target_date=date(2027, 1, 31),
        examination_schedule_id=None,
        status="active",
    )
    session.add(goal)
    session.flush()
    plan = StudyPlan(
        learner_id=learner.id,
        study_goal_id=goal.id,
        plan_type="roadmap",
        period_start=date(2026, 8, 6),
        period_end=date(2027, 1, 31),
        status="active",
        generation_reason="Because the learner asked for one.",
    )
    session.add(plan)
    session.flush()
    plan_item = PlanItem(
        study_plan_id=plan.id,
        topic_id=topic.id,
        action_type="study",
        scheduled_for=date(2026, 8, 13),
        estimated_minutes=60,
        priority=1,
        status="completed",
        completed_at=datetime(2026, 8, 13, 9, 0, tzinfo=UTC),
    )
    session.add(plan_item)
    session.commit()
    return Fixture(learner, topic, plan_item)


def make_revision(fixture: Fixture, **overrides) -> RevisionRecord:
    """A revision of the fixture's topic, with one field varied at a time."""
    values = {
        "learner_id": fixture.learner.id,
        "topic_id": fixture.topic.id,
        "plan_item_id": fixture.plan_item.id,
        "due_on": date(2026, 8, 20),
        "status": "due",
        "trigger_type": "completed_plan_item",
        "recommendation_reason": "You completed planned work on this on 2026-08-13.",
    }
    values.update(overrides)
    return RevisionRecord(**values)


def test_upgrade_creates_the_revision_table(migrated_database: Engine):
    assert "revision_records" in set(inspect(migrated_database).get_table_names())


def test_downgrade_removes_the_revision_table(migrated_database: Engine, alembic_config: Config):
    """Alembic keeps its own version table, so the assertion is on ours."""
    migrated_database.dispose()

    command.downgrade(alembic_config, "base")

    assert "revision_records" not in set(inspect(migrated_database).get_table_names())


def test_the_documented_index_exists(migrated_database: Engine):
    """The access pattern schema.md lists: one learner's revisions, by day and status."""
    indexes = inspect(migrated_database).get_indexes("revision_records")
    named = {index["name"]: index["column_names"] for index in indexes}

    assert named["ix_revision_records_learner_id_due_on_status"] == [
        "learner_id",
        "due_on",
        "status",
    ]


def test_a_revision_stores_and_reads_back(migrated_database: Engine):
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_revision(fixture))
        session.commit()

        stored = session.query(RevisionRecord).one()
        assert stored.due_on == date(2026, 8, 20)
        assert stored.status == "due"
        assert stored.trigger_type == "completed_plan_item"
        assert stored.scheduled_for is None
        assert stored.completed_at is None
        assert "2026-08-13" in (stored.recommendation_reason or "")


@pytest.mark.parametrize("status", REVISION_STATUSES)
def test_every_documented_status_is_accepted(migrated_database: Engine, status: str):
    """Including `scheduled`, which nothing writes: the CHECK carries it so a
    later change adding it is a use-case change rather than a migration."""
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_revision(fixture, status=status))
        session.commit()

        assert session.query(RevisionRecord).one().status == status


def test_an_unknown_status_is_refused(migrated_database: Engine):
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_revision(fixture, status="invented"))

        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.parametrize("trigger", REVISION_TRIGGERS)
def test_every_documented_trigger_is_accepted(migrated_database: Engine, trigger: str):
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_revision(fixture, trigger_type=trigger))
        session.commit()

        assert session.query(RevisionRecord).one().trigger_type == trigger


def test_an_unknown_trigger_is_refused(migrated_database: Engine):
    """Low evidence needs quiz and test records, which do not exist."""
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_revision(fixture, trigger_type="low_evidence"))

        with pytest.raises(IntegrityError):
            session.commit()


def test_a_revision_following_a_revision_needs_no_plan_item(migrated_database: Engine):
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_revision(fixture, plan_item_id=None, trigger_type="completed_revision"))
        session.commit()

        assert session.query(RevisionRecord).one().plan_item_id is None


def test_a_revision_must_name_a_stored_learner(migrated_database: Engine):
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_revision(fixture, learner_id=uuid.uuid4()))

        with pytest.raises(IntegrityError):
            session.commit()


def test_a_revision_must_name_a_stored_topic(migrated_database: Engine):
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_revision(fixture, topic_id=uuid.uuid4()))

        with pytest.raises(IntegrityError):
            session.commit()


def test_a_revision_must_name_a_stored_plan_item_when_it_names_one(
    migrated_database: Engine,
):
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_revision(fixture, plan_item_id=uuid.uuid4()))

        with pytest.raises(IntegrityError):
            session.commit()


def test_a_revision_needs_a_due_date(migrated_database: Engine):
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_revision(fixture, due_on=None))

        with pytest.raises(IntegrityError):
            session.commit()


def test_a_topic_may_hold_several_revisions_over_time(migrated_database: Engine):
    """Spaced review means one topic returns repeatedly; nothing is unique here."""
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(make_revision(fixture, status="completed", due_on=date(2026, 8, 20)))
        session.add(
            make_revision(
                fixture,
                plan_item_id=None,
                trigger_type="completed_revision",
                due_on=date(2026, 8, 27),
            )
        )
        session.commit()

        assert session.query(RevisionRecord).count() == 2


def test_a_revision_does_not_disturb_the_progress_record_for_its_topic(
    migrated_database: Engine,
):
    """Nothing here writes a learning stage: rule 4 of the domain model."""
    with Session(migrated_database) as session:
        fixture = make_fixture(session)
        session.add(
            LearnerTopicProgress(
                learner_id=fixture.learner.id,
                topic_id=fixture.topic.id,
                learning_stage="practice_ready",
                stage_source="learner",
            )
        )
        session.commit()

        session.add(make_revision(fixture, status="completed"))
        session.commit()

        assert session.query(LearnerTopicProgress).one().learning_stage == "practice_ready"
