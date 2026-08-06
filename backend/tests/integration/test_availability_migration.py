"""Availability-slot constraints against a real PostgreSQL database.

Covers the testing requirements in docs/database/migrations.md for migration
``20260806_01``: it runs against an empty database, its keys and constraints are
verified, and the downgrade path is exercised by the fixture teardown.

Constraints are asserted by attempting the write they exist to prevent. A
constraint that is documented but not enforced is indistinguishable from one that
is, until real learner data depends on it.

``day_of_week`` is checked to be a text column holding a day *name*, which is the
substance of ADR-018: the numbering convention docs/database/schema.md left open
is not answered but removed, so no reader has one to get wrong.
"""

import uuid
from datetime import date

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.persistence.curriculum import CurriculumVersion, LearningProgram
from app.infrastructure.persistence.learner_planning import (
    WEEKDAYS,
    AvailabilitySlot,
    Learner,
    StudyGoal,
)

AVAILABILITY_TABLES = {"availability_slots"}


def make_goal(session: Session) -> StudyGoal:
    """A learner with a goal, the minimum a slot can hang off."""
    program = LearningProgram(code=f"gate-{uuid.uuid4().hex[:8]}", name="GATE Computer Science")
    session.add(program)
    session.flush()
    version = CurriculumVersion(
        learning_program_id=program.id, version_label="2027", status="active"
    )
    session.add(version)
    learner = Learner(display_name="Local learner", timezone="Asia/Kolkata")
    session.add(learner)
    session.flush()
    goal = StudyGoal(
        learner_id=learner.id,
        learning_program_id=program.id,
        curriculum_version_id=version.id,
        # A goal must aim at something; a date is the cheaper of the two, because
        # an examination schedule would need seeding beside it.
        target_date=date(2027, 1, 31),
        examination_schedule_id=None,
        status="active",
    )
    session.add(goal)
    session.commit()
    return goal


def test_upgrade_creates_the_availability_table(migrated_database: Engine):
    tables = set(inspect(migrated_database).get_table_names())

    assert AVAILABILITY_TABLES <= tables


def test_downgrade_returns_the_database_to_empty(migrated_database: Engine, alembic_config: Config):
    migrated_database.dispose()

    command.downgrade(alembic_config, "base")

    assert set(inspect(migrated_database).get_table_names()) & AVAILABILITY_TABLES == set()


def test_the_documented_columns_are_created_and_no_others(migrated_database: Engine):
    columns = {
        column["name"] for column in inspect(migrated_database).get_columns("availability_slots")
    }

    assert columns == {
        "id",
        "study_goal_id",
        "day_of_week",
        "available_minutes",
        "created_at",
        "updated_at",
    }


def test_the_day_of_week_column_holds_text_rather_than_a_number(migrated_database: Engine):
    """ADR-018. schema.md first described a `smallint` holding 0-6 "according to
    documented convention"; a stored name leaves no convention to mis-map."""
    day_of_week = next(
        column
        for column in inspect(migrated_database).get_columns("availability_slots")
        if column["name"] == "day_of_week"
    )

    assert "CHAR" in str(day_of_week["type"]).upper()


@pytest.mark.parametrize("day", WEEKDAYS)
def test_every_day_of_the_week_is_accepted(session: Session, day: str):
    goal = make_goal(session)

    session.add(AvailabilitySlot(study_goal_id=goal.id, day_of_week=day, available_minutes=120))
    session.commit()

    assert session.query(AvailabilitySlot).count() == 1


def test_an_unknown_day_is_refused(session: Session):
    goal = make_goal(session)

    session.add(
        AvailabilitySlot(study_goal_id=goal.id, day_of_week="moonday", available_minutes=120)
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_numbered_day_is_refused(session: Session):
    """There is no numbering to accept: a row carrying an index is refused rather
    than stored as a day nobody can name."""
    goal = make_goal(session)

    session.add(AvailabilitySlot(study_goal_id=goal.id, day_of_week="0", available_minutes=120))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_goal_cannot_hold_two_slots_for_one_day(session: Session):
    """What makes saving a week rewrite the days it names rather than append."""
    goal = make_goal(session)
    session.add(
        AvailabilitySlot(study_goal_id=goal.id, day_of_week="monday", available_minutes=120)
    )
    session.commit()

    session.add(AvailabilitySlot(study_goal_id=goal.id, day_of_week="monday", available_minutes=90))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_two_goals_may_each_hold_the_same_day(session: Session):
    """Uniqueness is per goal and day, not per day."""
    first, second = make_goal(session), make_goal(session)

    session.add_all(
        [
            AvailabilitySlot(study_goal_id=goal.id, day_of_week="monday", available_minutes=120)
            for goal in (first, second)
        ]
    )
    session.commit()

    assert session.query(AvailabilitySlot).count() == 2


def test_a_day_with_no_available_time_is_accepted(session: Session):
    """Zero records a day the learner deliberately keeps free, which is why the
    approved constraint is `>= 0` rather than `> 0`."""
    goal = make_goal(session)

    session.add(AvailabilitySlot(study_goal_id=goal.id, day_of_week="sunday", available_minutes=0))
    session.commit()

    assert session.query(AvailabilitySlot).count() == 1


def test_a_full_day_of_available_time_is_accepted(session: Session):
    goal = make_goal(session)

    session.add(
        AvailabilitySlot(study_goal_id=goal.id, day_of_week="saturday", available_minutes=1440)
    )
    session.commit()

    assert session.query(AvailabilitySlot).count() == 1


@pytest.mark.parametrize("minutes", [-1, 1441])
def test_minutes_outside_a_day_are_refused(session: Session, minutes: int):
    goal = make_goal(session)

    session.add(
        AvailabilitySlot(study_goal_id=goal.id, day_of_week="monday", available_minutes=minutes)
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_slot_cannot_reference_a_goal_that_does_not_exist(session: Session):
    session.add(
        AvailabilitySlot(study_goal_id=uuid.uuid4(), day_of_week="monday", available_minutes=120)
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_day_and_its_minutes_are_both_required(session: Session):
    goal = make_goal(session)

    session.add(
        AvailabilitySlot(study_goal_id=goal.id, day_of_week="monday", available_minutes=None)
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_day_longer_than_the_column_is_refused(session: Session):
    """`varchar(16)` is a typo guard: the longest day name is nine characters."""
    goal = make_goal(session)

    session.add(
        AvailabilitySlot(study_goal_id=goal.id, day_of_week="w" * 17, available_minutes=120)
    )
    with pytest.raises((DataError, IntegrityError)):
        session.commit()
    session.rollback()


def test_availability_audit_timestamps_are_populated_by_the_database(session: Session):
    goal = make_goal(session)
    slot = AvailabilitySlot(study_goal_id=goal.id, day_of_week="monday", available_minutes=120)
    session.add(slot)
    session.commit()

    session.refresh(slot)

    assert slot.created_at is not None
    assert slot.updated_at is not None
    assert slot.created_at.tzinfo is not None
