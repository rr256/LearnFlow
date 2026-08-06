"""SQLAlchemy implementation of the study goal repository port.

Maps the application's plain records onto the learner-planning ORM models and
back, and reads the three pieces of reference data a goal points at: the
learning program, its active curriculum version, and the published examination
schedule.

It decides nothing. Which curriculum version counts as active is a stored
status; which periods form the examination window is settled by the use case
(docs/architecture/dependency-rules.md).

The session's transaction is owned by the caller. Nothing here commits.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.dto.planning_preferences import PlanningPreferences
from app.application.ports.examination_schedule_repository import (
    ExaminationPeriodRecord,
    ExaminationScheduleRecord,
)
from app.application.ports.study_goal_repository import (
    CurriculumVersionSummary,
    LearnerRecord,
    StudyGoalRecord,
)
from app.infrastructure.persistence.curriculum import CurriculumVersion, LearningProgram
from app.infrastructure.persistence.examination_schedule import (
    ExaminationPeriod,
    ExaminationSchedule,
)
from app.infrastructure.persistence.learner_planning import Learner, StudyGoal

ACTIVE_STATUS = "active"


class SqlAlchemyStudyGoalRepository:
    """Reads and writes learner goal records through a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one unit of work."""
        self._session = session

    def list_learners(self) -> tuple[LearnerRecord, ...]:
        """Every stored learner, oldest first."""
        models = self._session.scalars(select(Learner).order_by(Learner.created_at))
        return tuple(
            LearnerRecord(id=model.id, display_name=model.display_name, timezone=model.timezone)
            for model in models
        )

    def add_learner(self, record: LearnerRecord) -> None:
        """Store a new learner."""
        self._session.add(
            Learner(
                id=record.id,
                display_name=record.display_name,
                timezone=record.timezone,
            )
        )

    def find_learning_program_id(self, code: str) -> uuid.UUID | None:
        """The identifier of the program with this code, or None."""
        return self._session.scalar(select(LearningProgram.id).where(LearningProgram.code == code))

    def find_active_curriculum_version(
        self, learning_program_id: uuid.UUID
    ) -> CurriculumVersionSummary | None:
        """The program's active curriculum version, or None."""
        model = self._session.scalar(
            select(CurriculumVersion).where(
                CurriculumVersion.learning_program_id == learning_program_id,
                CurriculumVersion.status == ACTIVE_STATUS,
            )
        )
        return (
            None
            if model is None
            else CurriculumVersionSummary(id=model.id, version_label=model.version_label)
        )

    def find_examination_schedule(
        self, *, learning_program_id: uuid.UUID, cycle_label: str
    ) -> ExaminationScheduleRecord | None:
        """The program's published schedule for this cycle, or None."""
        model = self._session.scalar(
            select(ExaminationSchedule).where(
                ExaminationSchedule.learning_program_id == learning_program_id,
                ExaminationSchedule.cycle_label == cycle_label,
            )
        )
        if model is None:
            return None
        return ExaminationScheduleRecord(
            id=model.id,
            learning_program_id=model.learning_program_id,
            cycle_label=model.cycle_label,
            name=model.name,
            organising_body=model.organising_body,
            source_reference=model.source_reference,
            source_checked_on=model.source_checked_on,
            schedule_status=model.schedule_status,
        )

    def list_examination_periods(
        self, examination_schedule_id: uuid.UUID
    ) -> tuple[ExaminationPeriodRecord, ...]:
        """Every period of this schedule, in date order."""
        models = self._session.scalars(
            select(ExaminationPeriod)
            .where(ExaminationPeriod.examination_schedule_id == examination_schedule_id)
            .order_by(ExaminationPeriod.starts_on, ExaminationPeriod.period_type)
        )
        return tuple(
            ExaminationPeriodRecord(
                id=model.id,
                examination_schedule_id=model.examination_schedule_id,
                period_type=model.period_type,
                starts_on=model.starts_on,
                ends_on=model.ends_on,
            )
            for model in models
        )

    def find_active_study_goal(
        self, *, learner_id: uuid.UUID, learning_program_id: uuid.UUID
    ) -> StudyGoalRecord | None:
        """The learner's active goal for this program, or None."""
        model = self._session.scalar(
            select(StudyGoal).where(
                StudyGoal.learner_id == learner_id,
                StudyGoal.learning_program_id == learning_program_id,
                StudyGoal.status == ACTIVE_STATUS,
            )
        )
        return None if model is None else _goal_record(model)

    def add_study_goal(self, record: StudyGoalRecord) -> None:
        """Store a new study goal."""
        self._session.add(
            StudyGoal(
                id=record.id,
                learner_id=record.learner_id,
                learning_program_id=record.learning_program_id,
                curriculum_version_id=record.curriculum_version_id,
                examination_schedule_id=record.examination_schedule_id,
                target_date=record.target_date,
                status=record.status,
                preferred_session_minutes=record.planning_preferences.preferred_session_minutes,
                topic_sequencing=record.planning_preferences.topic_sequencing,
            )
        )

    def update_study_goal(self, record: StudyGoalRecord) -> None:
        """Overwrite the stored goal identified by ``record.id``.

        Every writable column is written, the preference columns included. The
        command using this port does not manage preferences and copies the stored
        ones onto the record it writes, so writing them here changes nothing --
        and it keeps this method from being one that silently ignores a field its
        record carries.
        """
        model = self._session.get(StudyGoal, record.id)
        if model is None:
            raise LookupError(f"Study goal {record.id} is not stored.")
        model.curriculum_version_id = record.curriculum_version_id
        model.examination_schedule_id = record.examination_schedule_id
        model.target_date = record.target_date
        model.status = record.status
        model.preferred_session_minutes = record.planning_preferences.preferred_session_minutes
        model.topic_sequencing = record.planning_preferences.topic_sequencing


def _goal_record(model: StudyGoal) -> StudyGoalRecord:
    return StudyGoalRecord(
        id=model.id,
        learner_id=model.learner_id,
        learning_program_id=model.learning_program_id,
        curriculum_version_id=model.curriculum_version_id,
        examination_schedule_id=model.examination_schedule_id,
        target_date=model.target_date,
        status=model.status,
        planning_preferences=PlanningPreferences(
            preferred_session_minutes=model.preferred_session_minutes,
            topic_sequencing=model.topic_sequencing,
        ),
    )
