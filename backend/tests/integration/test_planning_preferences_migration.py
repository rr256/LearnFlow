"""Planning-preference constraints against a real PostgreSQL database.

Covers the testing requirements in docs/database/migrations.md for migration
``20260806_02``: it runs against an empty database, its constraints are verified,
and the downgrade path is exercised by the fixture teardown.

Constraints are asserted by attempting the write they exist to prevent. A
constraint that is documented but not enforced is indistinguishable from one that
is, until real learner data depends on it.

The columns are checked to be typed and separate rather than one ``jsonb``
payload, which is the substance of ADR-019: docs/database/schema.md first
described ``planning_preferences jsonb``, and no CHECK can guard a key inside
JSON.
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
    TOPIC_SEQUENCING_CHOICES,
    Learner,
    StudyGoal,
)

PREFERENCE_COLUMNS = {"preferred_session_minutes", "topic_sequencing"}


def make_goal(session: Session, **preferences) -> StudyGoal:
    """A learner with a goal, which is what a preference hangs off."""
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
        **preferences,
    )
    session.add(goal)
    return goal


def test_upgrade_adds_the_preference_columns_to_study_goals(migrated_database: Engine):
    columns = {column["name"] for column in inspect(migrated_database).get_columns("study_goals")}

    assert PREFERENCE_COLUMNS <= columns


def test_downgrade_removes_them_and_leaves_the_goal_table_behind(
    migrated_database: Engine, alembic_config: Config
):
    """This migration adds columns rather than a table, so the step before it
    still holds `study_goals` -- unlike the availability downgrade, which drops
    a whole table."""
    migrated_database.dispose()

    command.downgrade(alembic_config, "20260806_01")

    inspector = inspect(migrated_database)
    assert "study_goals" in set(inspector.get_table_names())
    columns = {column["name"] for column in inspector.get_columns("study_goals")}
    assert columns & PREFERENCE_COLUMNS == set()


def test_preferences_are_separate_typed_columns_rather_than_one_json_payload(
    migrated_database: Engine,
):
    """ADR-019. A CHECK cannot guard a key inside `jsonb`, and a controlled value
    needs guarding -- the same risk ADR-018 removed from `day_of_week`."""
    columns = {
        column["name"]: str(column["type"]).upper()
        for column in inspect(migrated_database).get_columns("study_goals")
    }

    assert "planning_preferences" not in columns
    assert "INT" in columns["preferred_session_minutes"]
    assert "CHAR" in columns["topic_sequencing"]


def test_a_goal_may_hold_no_preference_at_all(session: Session):
    """Every goal stored before this migration reads back this way, which is true
    of it: the learner had no way to express a preference."""
    goal = make_goal(session)
    session.commit()

    session.refresh(goal)

    assert goal.preferred_session_minutes is None
    assert goal.topic_sequencing is None


def test_one_preference_may_be_set_without_the_other(session: Session):
    """A learner who answered one question and not the other is a real state, not
    a half-filled form."""
    goal = make_goal(session, topic_sequencing="syllabus_order")
    session.commit()

    session.refresh(goal)

    assert goal.topic_sequencing == "syllabus_order"
    assert goal.preferred_session_minutes is None


@pytest.mark.parametrize("choice", TOPIC_SEQUENCING_CHOICES)
def test_every_documented_topic_order_is_accepted(session: Session, choice: str):
    make_goal(session, topic_sequencing=choice)
    session.commit()

    assert session.query(StudyGoal).count() == 1


def test_an_unknown_topic_order_is_refused(session: Session):
    make_goal(session, topic_sequencing="alphabetical_order")

    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


@pytest.mark.parametrize("minutes", [15, 60, 480])
def test_a_session_length_on_or_inside_the_bounds_is_accepted(session: Session, minutes: int):
    make_goal(session, preferred_session_minutes=minutes)
    session.commit()

    assert session.query(StudyGoal).count() == 1


@pytest.mark.parametrize("minutes", [0, 14, 481, 1441, -30])
def test_a_session_length_outside_the_bounds_is_refused(session: Session, minutes: int):
    """Below a quarter of an hour a block is scheduling overhead; above eight
    hours it cannot be honoured inside a day holding anything else."""
    make_goal(session, preferred_session_minutes=minutes)

    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_topic_order_longer_than_the_column_is_refused(session: Session):
    """`varchar(32)` is a typo guard: the longest documented choice is nineteen
    characters."""
    make_goal(session, topic_sequencing="s" * 33)

    with pytest.raises((DataError, IntegrityError)):
        session.commit()
    session.rollback()
