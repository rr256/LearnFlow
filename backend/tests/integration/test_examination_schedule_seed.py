"""The examination schedule seed and the study goal, against a real PostgreSQL database.

The unit tests prove the reconcile and goal logic against fakes. These prove the
part a fake cannot: that the writes those use cases choose satisfy the
constraints migration ``20260801_01`` created, that a second run against real
rows is genuinely a no-op, and that the whole local setup path -- curriculum,
schedule, goal -- works end to end against the bundled data files.

Skipped unless ``TEST_DATABASE_URL`` names a disposable database; see
tests/integration/conftest.py.
"""

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.dto.study_goal import RecordChange, StudyGoalRequest
from app.application.use_cases.seed_curriculum import SeedCurriculum
from app.application.use_cases.seed_examination_schedule import (
    SeedExaminationSchedule,
    UnknownLearningProgramError,
)
from app.application.use_cases.set_study_goal import (
    ExaminationScheduleNotFoundError,
    MissingGoalTargetError,
    SetStudyGoal,
)
from app.infrastructure.persistence.curriculum_seed_repository import (
    SqlAlchemyCurriculumSeedRepository,
)
from app.infrastructure.persistence.examination_schedule import (
    ExaminationPeriod,
    ExaminationSchedule,
)
from app.infrastructure.persistence.examination_schedule_seed_repository import (
    SqlAlchemyExaminationScheduleSeedRepository,
)
from app.infrastructure.persistence.learner_planning import Learner, StudyGoal
from app.infrastructure.persistence.study_goal_repository import SqlAlchemyStudyGoalRepository
from scripts.curriculum_seed_file import GATE_CSE_CURRICULUM_FILE, load_curriculum_seed
from scripts.examination_schedule_file import (
    GATE_CSE_EXAMINATION_SCHEDULE_FILE,
    load_examination_schedule,
)

SEED_TIME = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
TIMEZONE = "Asia/Kolkata"


@pytest.fixture
def seed_curriculum(session: Session):
    """Load the bundled GATE CSE curriculum, as the local setup does first."""

    def run():
        use_case = SeedCurriculum(
            SqlAlchemyCurriculumSeedRepository(session), clock=lambda: SEED_TIME
        )
        result = use_case(load_curriculum_seed(GATE_CSE_CURRICULUM_FILE))
        session.commit()
        return result

    return run


@pytest.fixture
def seed_schedule(session: Session):
    """Apply a schedule through the real repository and commit, as the script does."""

    def run(seed=None):
        use_case = SeedExaminationSchedule(SqlAlchemyExaminationScheduleSeedRepository(session))
        result = use_case(seed or load_examination_schedule(GATE_CSE_EXAMINATION_SCHEDULE_FILE))
        session.commit()
        return result

    return run


@pytest.fixture
def set_goal(session: Session):
    """Set a study goal through the real repository and commit, as the script does."""

    def run(**overrides):
        fields = {
            "program_code": "gate-cse",
            "learner_timezone": TIMEZONE,
            "examination_cycle_label": "2027",
        }
        fields.update(overrides)
        use_case = SetStudyGoal(SqlAlchemyStudyGoalRepository(session))
        summary = use_case(StudyGoalRequest(**fields))
        session.commit()
        return summary

    return run


def count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_bundled_schedule_seeds_and_reseeds_cleanly(seed_curriculum, seed_schedule, session):
    seed_curriculum()

    first = seed_schedule()
    second = seed_schedule()

    assert first.examination_schedule.created == 1
    assert first.examination_periods.created == 6
    assert second.changed is False
    assert count(session, ExaminationSchedule) == 1
    assert count(session, ExaminationPeriod) == 6


def test_repeated_runs_do_not_duplicate_periods(seed_curriculum, seed_schedule, session):
    seed_curriculum()

    for _ in range(3):
        seed_schedule()

    assert count(session, ExaminationPeriod) == 6


def test_bundled_schedule_is_provisional_and_names_its_source(
    seed_curriculum, seed_schedule, session
):
    seed_curriculum()
    seed_schedule()

    schedule = session.scalar(select(ExaminationSchedule))

    assert schedule is not None
    assert schedule.schedule_status == "provisional"
    assert schedule.source_reference == "https://gate2027.iitm.ac.in/"
    assert schedule.source_checked_on == date(2026, 8, 1)
    assert schedule.organising_body == "IIT Madras"


def test_bundled_schedule_stores_three_separate_examination_weekends(
    seed_curriculum, seed_schedule, session
):
    """Not one 6-21 February range: eleven of those days hold no examination."""
    seed_curriculum()
    seed_schedule()

    sittings = sorted(
        (row.starts_on, row.ends_on)
        for row in session.scalars(
            select(ExaminationPeriod).where(ExaminationPeriod.period_type == "examination")
        )
    )

    assert sittings == [
        (date(2027, 2, 6), date(2027, 2, 7)),
        (date(2027, 2, 13), date(2027, 2, 14)),
        (date(2027, 2, 20), date(2027, 2, 21)),
    ]


def test_seeding_a_schedule_before_the_curriculum_is_refused(seed_schedule, session):
    with pytest.raises(UnknownLearningProgramError):
        seed_schedule()

    session.rollback()
    assert count(session, ExaminationSchedule) == 0


def test_local_setup_creates_the_learner_and_the_goal(
    seed_curriculum, seed_schedule, set_goal, session
):
    seed_curriculum()
    seed_schedule()

    summary = set_goal()

    assert summary.learner_change is RecordChange.created
    assert summary.study_goal_change is RecordChange.created
    assert count(session, Learner) == 1
    assert count(session, StudyGoal) == 1


def test_the_goal_reports_the_published_examination_window(
    seed_curriculum, seed_schedule, set_goal
):
    seed_curriculum()
    seed_schedule()

    summary = set_goal()

    assert summary.examination is not None
    assert summary.examination.window_starts_on == date(2027, 2, 6)
    assert summary.examination.window_ends_on == date(2027, 2, 21)
    assert summary.examination.dates_may_change is True


def test_the_stored_goal_holds_a_schedule_reference_and_no_examination_date(
    seed_curriculum, seed_schedule, set_goal, session
):
    seed_curriculum()
    seed_schedule()
    set_goal()

    goal = session.scalar(select(StudyGoal))

    assert goal is not None
    assert goal.examination_schedule_id is not None
    assert goal.target_date is None
    assert goal.status == "active"


def test_the_goal_binds_to_the_active_curriculum_version(seed_curriculum, seed_schedule, set_goal):
    seed_curriculum()
    seed_schedule()

    summary = set_goal()

    assert summary.curriculum_version_label == "2027"


def test_setting_the_same_goal_twice_writes_nothing(
    seed_curriculum, seed_schedule, set_goal, session
):
    seed_curriculum()
    seed_schedule()
    first = set_goal()

    second = set_goal()

    assert second.changed is False
    assert second.study_goal_id == first.study_goal_id
    assert count(session, StudyGoal) == 1
    assert count(session, Learner) == 1


def test_a_goal_with_a_target_date_and_no_examination_is_stored(seed_curriculum, set_goal, session):
    seed_curriculum()

    summary = set_goal(examination_cycle_label=None, target_date=date(2027, 6, 30))

    assert summary.examination is None
    assert session.scalar(select(StudyGoal.target_date)) == date(2027, 6, 30)


def test_a_goal_aiming_at_nothing_is_refused_before_the_database_sees_it(
    seed_curriculum, set_goal, session
):
    seed_curriculum()

    with pytest.raises(MissingGoalTargetError):
        set_goal(examination_cycle_label=None)

    session.rollback()
    assert count(session, StudyGoal) == 0


def test_a_goal_for_an_unseeded_examination_cycle_is_refused(seed_curriculum, set_goal, session):
    seed_curriculum()

    with pytest.raises(ExaminationScheduleNotFoundError):
        set_goal()

    session.rollback()
    assert count(session, StudyGoal) == 0
    assert count(session, Learner) == 0


def test_a_corrected_schedule_reaches_an_existing_goal(
    seed_curriculum, seed_schedule, set_goal, session
):
    """The goal holds a reference, so a re-seeded date needs no goal rewrite."""
    seed_curriculum()
    seed_schedule()
    set_goal()

    published = load_examination_schedule(GATE_CSE_EXAMINATION_SCHEDULE_FILE)
    moved = replace(
        published,
        schedule_status="confirmed",
        periods=tuple(
            replace(period, ends_on=date(2027, 2, 8))
            if period.starts_on == date(2027, 2, 6)
            else period
            for period in published.periods
        ),
    )
    seed_schedule(moved)

    summary = set_goal()

    assert summary.study_goal_change is RecordChange.unchanged
    assert summary.examination is not None
    assert summary.examination.dates_may_change is False
    assert summary.examination.window_ends_on == date(2027, 2, 21)
    assert count(session, StudyGoal) == 1
