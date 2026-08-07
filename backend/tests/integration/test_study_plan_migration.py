"""Study-plan constraints against a real PostgreSQL database.

Covers the testing requirements in docs/database/migrations.md for migration
``20260806_03``: it runs against an empty database, its keys, constraints, and
indexes are verified, and the downgrade path is exercised by the fixture
teardown.

Constraints are asserted by attempting the write they exist to prevent. A
constraint that is documented but not enforced is indistinguishable from one that
is, until real learner data depends on it.

The controlled columns are checked to be text guarded by a `CHECK` rather than
the bare `text` docs/database/schema.md describes, which is the substance of
ADR-020's one departure from that document's tables.
"""

import uuid
from datetime import date

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
from app.infrastructure.persistence.learner_planning import (
    PLAN_ITEM_ACTIONS,
    PLAN_ITEM_STATUSES,
    PLAN_STATUSES,
    PLAN_TYPES,
    Learner,
    PlanItem,
    StudyGoal,
    StudyPlan,
)

PLAN_TABLES = {"study_plans", "plan_items"}


class Fixture:
    """A learner, a goal, and one topic — the minimum a plan can hang off."""

    def __init__(self, goal: StudyGoal, topic: Topic) -> None:
        self.goal = goal
        self.topic = topic


def make_fixture(session: Session) -> Fixture:
    """Store the reference data a plan and its items point at."""
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
    session.commit()
    return Fixture(goal, topic)


def make_plan(session: Session, fixture: Fixture, *, plan_type: str = "roadmap") -> StudyPlan:
    """A stored plan belonging to the fixture's goal."""
    plan = StudyPlan(
        learner_id=fixture.goal.learner_id,
        study_goal_id=fixture.goal.id,
        plan_type=plan_type,
        period_start=date(2026, 8, 6),
        period_end=date(2027, 1, 31),
        status="active",
        generation_reason="Because the learner asked for one.",
    )
    session.add(plan)
    session.commit()
    return plan


def test_upgrade_creates_the_plan_tables(migrated_database: Engine):
    tables = set(inspect(migrated_database).get_table_names())

    assert PLAN_TABLES <= tables


def test_downgrade_returns_the_database_to_empty(migrated_database: Engine, alembic_config: Config):
    migrated_database.dispose()

    command.downgrade(alembic_config, "base")

    assert set(inspect(migrated_database).get_table_names()) & PLAN_TABLES == set()


def test_the_documented_plan_columns_are_created_and_no_others(migrated_database: Engine):
    columns = {column["name"] for column in inspect(migrated_database).get_columns("study_plans")}

    assert columns == {
        "id",
        "learner_id",
        "study_goal_id",
        "plan_type",
        "period_start",
        "period_end",
        "status",
        "generation_reason",
        "created_at",
        "updated_at",
    }


def test_the_documented_item_columns_are_created_and_no_others(migrated_database: Engine):
    columns = {column["name"] for column in inspect(migrated_database).get_columns("plan_items")}

    assert columns == {
        "id",
        "study_plan_id",
        "topic_id",
        "action_type",
        "scheduled_for",
        "estimated_minutes",
        "priority",
        "status",
        "recommendation_reason",
        "completed_at",
        "created_at",
        "updated_at",
    }


def test_the_controlled_columns_hold_text_rather_than_a_number(migrated_database: Engine):
    """ADR-020. Every other controlled value in this schema is validated text
    guarded by a CHECK, and a number would make these the exception."""
    inspector = inspect(migrated_database)
    plan_type = next(
        column for column in inspector.get_columns("study_plans") if column["name"] == "plan_type"
    )
    action_type = next(
        column for column in inspector.get_columns("plan_items") if column["name"] == "action_type"
    )

    assert "CHAR" in str(plan_type["type"]).upper()
    assert "CHAR" in str(action_type["type"]).upper()


def test_the_required_indexes_are_created(migrated_database: Engine):
    """The two docs/database/schema.md lists for these tables."""
    inspector = inspect(migrated_database)

    plan_indexes = {index["name"] for index in inspector.get_indexes("study_plans")}
    item_indexes = {index["name"] for index in inspector.get_indexes("plan_items")}

    assert "ix_study_plans_learner_id_study_goal_id_status_period_start" in plan_indexes
    assert "ix_plan_items_study_plan_id_scheduled_for_status" in item_indexes


@pytest.mark.parametrize("plan_type", PLAN_TYPES)
def test_every_documented_plan_type_is_accepted(session: Session, plan_type: str):
    fixture = make_fixture(session)

    make_plan(session, fixture, plan_type=plan_type)

    assert session.query(StudyPlan).count() == 1


def test_an_unknown_plan_type_is_refused(session: Session):
    fixture = make_fixture(session)

    with pytest.raises(IntegrityError):
        make_plan(session, fixture, plan_type="fortnightly")
    session.rollback()


@pytest.mark.parametrize("status", PLAN_STATUSES)
def test_every_documented_plan_status_is_accepted(session: Session, status: str):
    fixture = make_fixture(session)
    plan = make_plan(session, fixture)

    plan.status = status
    session.commit()

    assert session.get(StudyPlan, plan.id).status == status


def test_an_unknown_plan_status_is_refused(session: Session):
    fixture = make_fixture(session)
    plan = make_plan(session, fixture)

    plan.status = "finished"
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_a_plan_may_cover_no_dates_at_all(session: Session):
    """A goal whose examination schedule publishes no sitting day, and which
    carries no target date, leaves a roadmap with no horizon to state."""
    fixture = make_fixture(session)

    session.add(
        StudyPlan(
            learner_id=fixture.goal.learner_id,
            study_goal_id=fixture.goal.id,
            plan_type="roadmap",
            period_start=None,
            period_end=None,
            status="active",
            generation_reason=None,
        )
    )
    session.commit()

    assert session.query(StudyPlan).count() == 1


def test_a_plan_cannot_reference_a_goal_that_does_not_exist(session: Session):
    fixture = make_fixture(session)

    session.add(
        StudyPlan(
            learner_id=fixture.goal.learner_id,
            study_goal_id=uuid.uuid4(),
            plan_type="roadmap",
            period_start=None,
            period_end=None,
            status="active",
            generation_reason=None,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


@pytest.mark.parametrize("action_type", PLAN_ITEM_ACTIONS)
def test_every_documented_item_action_is_accepted(session: Session, action_type: str):
    fixture = make_fixture(session)
    plan = make_plan(session, fixture)

    session.add(
        PlanItem(
            study_plan_id=plan.id,
            topic_id=fixture.topic.id,
            action_type=action_type,
            scheduled_for=None,
            estimated_minutes=60,
            priority=1,
            status="planned",
            recommendation_reason="First in syllabus order.",
        )
    )
    session.commit()

    assert session.query(PlanItem).count() == 1


def test_an_unknown_item_action_is_refused(session: Session):
    fixture = make_fixture(session)
    plan = make_plan(session, fixture)

    session.add(
        PlanItem(
            study_plan_id=plan.id,
            topic_id=fixture.topic.id,
            action_type="watch_a_video",
            scheduled_for=None,
            estimated_minutes=60,
            priority=1,
            status="planned",
            recommendation_reason=None,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


@pytest.mark.parametrize("status", PLAN_ITEM_STATUSES)
def test_every_documented_item_status_is_accepted(session: Session, status: str):
    fixture = make_fixture(session)
    plan = make_plan(session, fixture)

    session.add(
        PlanItem(
            study_plan_id=plan.id,
            topic_id=fixture.topic.id,
            action_type="study",
            scheduled_for=None,
            estimated_minutes=60,
            priority=1,
            status=status,
            recommendation_reason=None,
        )
    )
    session.commit()

    assert session.query(PlanItem).count() == 1


@pytest.mark.parametrize("minutes", [0, -30])
def test_an_item_estimated_at_no_time_is_refused(session: Session, minutes: int):
    """schema.md approves the bound: an item of zero minutes is scheduling
    overhead rather than study."""
    fixture = make_fixture(session)
    plan = make_plan(session, fixture)

    session.add(
        PlanItem(
            study_plan_id=plan.id,
            topic_id=fixture.topic.id,
            action_type="study",
            scheduled_for=None,
            estimated_minutes=minutes,
            priority=1,
            status="planned",
            recommendation_reason=None,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_an_item_may_carry_no_estimate_and_no_topic(session: Session):
    """Both are nullable in docs/database/schema.md. Nothing writes such an item
    today; the columns allow one so a later action that belongs to no single
    topic needs no migration."""
    fixture = make_fixture(session)
    plan = make_plan(session, fixture)

    session.add(
        PlanItem(
            study_plan_id=plan.id,
            topic_id=None,
            action_type="review_mistakes",
            scheduled_for=None,
            estimated_minutes=None,
            priority=1,
            status="planned",
            recommendation_reason=None,
        )
    )
    session.commit()

    assert session.query(PlanItem).count() == 1


def test_an_item_cannot_reference_a_plan_that_does_not_exist(session: Session):
    fixture = make_fixture(session)

    session.add(
        PlanItem(
            study_plan_id=uuid.uuid4(),
            topic_id=fixture.topic.id,
            action_type="study",
            scheduled_for=None,
            estimated_minutes=60,
            priority=1,
            status="planned",
            recommendation_reason=None,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_two_items_may_share_a_topic_across_plans(session: Session):
    """A roadmap and its week both name the same topics, which is what makes the
    week the first stretch of the roadmap rather than a separate plan of work."""
    fixture = make_fixture(session)
    roadmap = make_plan(session, fixture, plan_type="roadmap")
    weekly = make_plan(session, fixture, plan_type="weekly")

    session.add_all(
        [
            PlanItem(
                study_plan_id=plan.id,
                topic_id=fixture.topic.id,
                action_type="study",
                scheduled_for=None,
                estimated_minutes=60,
                priority=1,
                status="planned",
                recommendation_reason=None,
            )
            for plan in (roadmap, weekly)
        ]
    )
    session.commit()

    assert session.query(PlanItem).count() == 2
