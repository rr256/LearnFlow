"""Examination schedule and learner goal constraints against a real PostgreSQL database.

Covers the testing requirements in docs/database/migrations.md for migration
``20260801_01``: it runs against an empty database, its keys and constraints are
verified, and the downgrade path is exercised by the fixture teardown.

Constraints are asserted by attempting the write they exist to prevent. A
constraint that is documented but not enforced is indistinguishable from one that
is, until real learner data depends on it.
"""

import uuid
from datetime import date

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.persistence.curriculum import CurriculumVersion, LearningProgram
from app.infrastructure.persistence.examination_schedule import (
    ExaminationPeriod,
    ExaminationSchedule,
)
from app.infrastructure.persistence.learner_planning import Learner, StudyGoal

EXAMINATION_TABLES = {"examination_schedules", "examination_periods"}
LEARNER_PLANNING_TABLES = {"learners", "study_goals"}


def make_program(session: Session, code: str = "gate-cse") -> LearningProgram:
    program = LearningProgram(code=code, name="GATE Computer Science")
    session.add(program)
    session.commit()
    return program


def make_version(session: Session, program: LearningProgram) -> CurriculumVersion:
    version = CurriculumVersion(
        learning_program_id=program.id, version_label="2027", status="active"
    )
    session.add(version)
    session.commit()
    return version


def make_schedule(
    session: Session,
    program: LearningProgram,
    cycle_label: str = "2027",
    schedule_status: str = "provisional",
) -> ExaminationSchedule:
    schedule = ExaminationSchedule(
        learning_program_id=program.id,
        cycle_label=cycle_label,
        name=f"GATE {cycle_label}",
        organising_body="IIT Madras",
        source_reference="https://gate2027.iitm.ac.in/",
        source_checked_on=date(2026, 7, 31),
        schedule_status=schedule_status,
    )
    session.add(schedule)
    session.commit()
    return schedule


def make_learner(session: Session) -> Learner:
    learner = Learner(display_name="Local learner", timezone="Asia/Kolkata")
    session.add(learner)
    session.commit()
    return learner


def test_upgrade_creates_every_new_table(migrated_database: Engine):
    tables = set(inspect(migrated_database).get_table_names())

    assert EXAMINATION_TABLES | LEARNER_PLANNING_TABLES <= tables


def test_downgrade_returns_the_database_to_empty(migrated_database: Engine, alembic_config: Config):
    migrated_database.dispose()

    command.downgrade(alembic_config, "base")

    remaining = set(inspect(migrated_database).get_table_names())
    assert remaining & (EXAMINATION_TABLES | LEARNER_PLANNING_TABLES) == set()


def test_a_program_cannot_hold_two_schedules_for_one_cycle(session: Session):
    program = make_program(session)
    make_schedule(session, program, cycle_label="2027")

    session.add(
        ExaminationSchedule(
            learning_program_id=program.id,
            cycle_label="2027",
            name="A rival GATE 2027",
            source_reference="https://example.invalid/",
            source_checked_on=date(2026, 7, 31),
            schedule_status="provisional",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_two_programs_may_hold_a_schedule_for_the_same_cycle(session: Session):
    """A cycle label is unique within a program, not across the platform."""
    first = make_program(session, code="gate-cse")
    second = make_program(session, code="gate-ee")

    make_schedule(session, first, cycle_label="2027")
    make_schedule(session, second, cycle_label="2027")

    assert session.query(ExaminationSchedule).count() == 2


def test_schedule_status_must_be_a_documented_value(session: Session):
    program = make_program(session)

    session.add(
        ExaminationSchedule(
            learning_program_id=program.id,
            cycle_label="2027",
            name="GATE 2027",
            source_reference="https://gate2027.iitm.ac.in/",
            source_checked_on=date(2026, 7, 31),
            schedule_status="announced",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_schedule_cannot_omit_the_source_it_came_from(session: Session):
    program = make_program(session)

    session.add(
        ExaminationSchedule(
            learning_program_id=program.id,
            cycle_label="2027",
            name="GATE 2027",
            source_reference=None,
            source_checked_on=date(2026, 7, 31),
            schedule_status="provisional",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_schedule_may_hold_three_examination_periods(session: Session):
    """GATE 2027 is sat over three separate weekends, not one continuous range."""
    schedule = make_schedule(session, make_program(session))

    session.add_all(
        [
            ExaminationPeriod(
                examination_schedule_id=schedule.id,
                period_type="examination",
                starts_on=starts_on,
                ends_on=ends_on,
            )
            for starts_on, ends_on in (
                (date(2027, 2, 6), date(2027, 2, 7)),
                (date(2027, 2, 13), date(2027, 2, 14)),
                (date(2027, 2, 20), date(2027, 2, 21)),
            )
        ]
    )
    session.commit()

    assert session.query(ExaminationPeriod).filter_by(period_type="examination").count() == 3


def test_two_periods_cannot_share_a_type_and_start_date(session: Session):
    schedule = make_schedule(session, make_program(session))
    session.add(
        ExaminationPeriod(
            examination_schedule_id=schedule.id,
            period_type="examination",
            starts_on=date(2027, 2, 6),
            ends_on=date(2027, 2, 7),
        )
    )
    session.commit()

    session.add(
        ExaminationPeriod(
            examination_schedule_id=schedule.id,
            period_type="examination",
            starts_on=date(2027, 2, 6),
            ends_on=date(2027, 2, 8),
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_period_cannot_end_before_it_starts(session: Session):
    schedule = make_schedule(session, make_program(session))

    session.add(
        ExaminationPeriod(
            examination_schedule_id=schedule.id,
            period_type="examination",
            starts_on=date(2027, 2, 7),
            ends_on=date(2027, 2, 6),
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_single_day_period_starts_and_ends_on_the_same_date(session: Session):
    """The results announcement. The constraint is `>=`, so this must be accepted."""
    schedule = make_schedule(session, make_program(session))

    session.add(
        ExaminationPeriod(
            examination_schedule_id=schedule.id,
            period_type="results",
            starts_on=date(2027, 3, 19),
            ends_on=date(2027, 3, 19),
        )
    )
    session.commit()

    assert session.query(ExaminationPeriod).count() == 1


def test_period_type_must_be_a_documented_value(session: Session):
    schedule = make_schedule(session, make_program(session))

    session.add(
        ExaminationPeriod(
            examination_schedule_id=schedule.id,
            period_type="counselling",
            starts_on=date(2027, 4, 1),
            ends_on=date(2027, 4, 2),
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_period_cannot_reference_a_schedule_that_does_not_exist(session: Session):
    session.add(
        ExaminationPeriod(
            examination_schedule_id=uuid.uuid4(),
            period_type="examination",
            starts_on=date(2027, 2, 6),
            ends_on=date(2027, 2, 7),
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_goal_may_aim_at_an_examination_with_no_target_date(session: Session):
    """The published paper date is unknown, so the goal must not need one."""
    program = make_program(session)
    version = make_version(session, program)
    schedule = make_schedule(session, program)
    learner = make_learner(session)

    session.add(
        StudyGoal(
            learner_id=learner.id,
            learning_program_id=program.id,
            curriculum_version_id=version.id,
            examination_schedule_id=schedule.id,
            target_date=None,
            status="active",
        )
    )
    session.commit()

    assert session.query(StudyGoal).count() == 1


def test_a_goal_may_aim_at_a_target_date_with_no_examination(session: Session):
    program = make_program(session)
    version = make_version(session, program)
    learner = make_learner(session)

    session.add(
        StudyGoal(
            learner_id=learner.id,
            learning_program_id=program.id,
            curriculum_version_id=version.id,
            examination_schedule_id=None,
            target_date=date(2027, 6, 30),
            status="active",
        )
    )
    session.commit()

    assert session.query(StudyGoal).count() == 1


def test_a_goal_aiming_at_neither_is_refused(session: Session):
    program = make_program(session)
    version = make_version(session, program)
    learner = make_learner(session)

    session.add(
        StudyGoal(
            learner_id=learner.id,
            learning_program_id=program.id,
            curriculum_version_id=version.id,
            examination_schedule_id=None,
            target_date=None,
            status="active",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_study_goal_status_must_be_a_documented_value(session: Session):
    program = make_program(session)
    version = make_version(session, program)
    learner = make_learner(session)

    session.add(
        StudyGoal(
            learner_id=learner.id,
            learning_program_id=program.id,
            curriculum_version_id=version.id,
            target_date=date(2027, 6, 30),
            status="paused_indefinitely",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_goal_cannot_reference_a_learner_that_does_not_exist(session: Session):
    program = make_program(session)
    version = make_version(session, program)

    session.add(
        StudyGoal(
            learner_id=uuid.uuid4(),
            learning_program_id=program.id,
            curriculum_version_id=version.id,
            target_date=date(2027, 6, 30),
            status="active",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_learner_must_carry_a_timezone(session: Session):
    session.add(Learner(display_name="No zone", timezone=None))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_learner_audit_timestamps_are_populated_by_the_database(session: Session):
    learner = make_learner(session)

    session.refresh(learner)

    assert learner.created_at is not None
    assert learner.updated_at is not None
    assert learner.created_at.tzinfo is not None
