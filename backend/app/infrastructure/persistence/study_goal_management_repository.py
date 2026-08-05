"""SQLAlchemy implementation of the study-goal management repository port.

Serves GOAL-001 to GOAL-004. It maps rows to the application's plain records and
back, and reads the curriculum reference data a goal binds to.

It decides nothing. Whether a goal aims at enough to be valid, whether a second
active goal may exist, and which curriculum version a new goal binds to are all
settled by the use case (docs/architecture/dependency-rules.md).

The session's transaction is owned by the caller. Nothing here commits.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.ports.curriculum_seed_repository import (
    CurriculumVersionRecord,
    LearningProgramRecord,
)
from app.application.ports.study_goal_repository import StudyGoalRecord
from app.infrastructure.persistence.curriculum import CurriculumVersion, LearningProgram
from app.infrastructure.persistence.learner_planning import StudyGoal

ACTIVE_STATUS = "active"


class SqlAlchemyStudyGoalManagementRepository:
    """Reads and writes study goals through a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one unit of work."""
        self._session = session

    def find_learning_program(self, learning_program_id: uuid.UUID) -> LearningProgramRecord | None:
        """The program with this identifier, or None."""
        model = self._session.get(LearningProgram, learning_program_id)
        return None if model is None else _program_record(model)

    def find_active_curriculum_version(
        self, learning_program_id: uuid.UUID
    ) -> CurriculumVersionRecord | None:
        """The program's active curriculum version, or None."""
        model = self._session.scalar(
            select(CurriculumVersion).where(
                CurriculumVersion.learning_program_id == learning_program_id,
                CurriculumVersion.status == ACTIVE_STATUS,
            )
        )
        return None if model is None else _version_record(model)

    def find_curriculum_version(
        self, curriculum_version_id: uuid.UUID
    ) -> CurriculumVersionRecord | None:
        """The curriculum version with this identifier, or None."""
        model = self._session.get(CurriculumVersion, curriculum_version_id)
        return None if model is None else _version_record(model)

    def count_study_goals(self, learner_id: uuid.UUID) -> int:
        """How many goals this learner has, ignoring any page window."""
        total = self._session.scalar(
            select(func.count()).select_from(StudyGoal).where(StudyGoal.learner_id == learner_id)
        )
        return total or 0

    def list_study_goals(
        self, *, learner_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[StudyGoalRecord, ...]:
        """One page of the learner's goals, newest first.

        `id` breaks a tie on `created_at`, so a page boundary cannot repeat or
        skip a goal when two are created in the same transaction.
        """
        models = self._session.scalars(
            select(StudyGoal)
            .where(StudyGoal.learner_id == learner_id)
            .order_by(StudyGoal.created_at.desc(), StudyGoal.id)
            .limit(limit)
            .offset(offset)
        )
        return tuple(_goal_record(model) for model in models)

    def find_study_goal(self, study_goal_id: uuid.UUID) -> StudyGoalRecord | None:
        """The goal with this identifier, or None."""
        model = self._session.get(StudyGoal, study_goal_id)
        return None if model is None else _goal_record(model)

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
            )
        )

    def update_study_goal(self, record: StudyGoalRecord) -> None:
        """Overwrite the stored goal identified by ``record.id``."""
        model = self._session.get(StudyGoal, record.id)
        if model is None:
            raise LookupError(f"Study goal {record.id} is not stored.")
        model.curriculum_version_id = record.curriculum_version_id
        model.examination_schedule_id = record.examination_schedule_id
        model.target_date = record.target_date
        model.status = record.status


def _program_record(model: LearningProgram) -> LearningProgramRecord:
    return LearningProgramRecord(
        id=model.id, code=model.code, name=model.name, description=model.description
    )


def _version_record(model: CurriculumVersion) -> CurriculumVersionRecord:
    return CurriculumVersionRecord(
        id=model.id,
        learning_program_id=model.learning_program_id,
        version_label=model.version_label,
        status=model.status,
        source_reference=model.source_reference,
        published_at=model.published_at,
    )


def _goal_record(model: StudyGoal) -> StudyGoalRecord:
    return StudyGoalRecord(
        id=model.id,
        learner_id=model.learner_id,
        learning_program_id=model.learning_program_id,
        curriculum_version_id=model.curriculum_version_id,
        examination_schedule_id=model.examination_schedule_id,
        target_date=model.target_date,
        status=model.status,
    )
