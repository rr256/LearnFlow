"""SQLAlchemy implementation of the study-goal management repository port.

Serves GOAL-001 to GOAL-005. It maps rows to the application's plain records and
back, reads the curriculum reference data a goal binds to, and reads and writes
the availability slots a goal owns.

It decides nothing. Whether a goal aims at enough to be valid, whether a second
active goal may exist, which curriculum version a new goal binds to, which days a
week may name, and which of a week's days are added, rewritten, or removed are
all settled by the use case (docs/architecture/dependency-rules.md). In
particular, nothing here deletes a slot the use case did not name.

The session's transaction is owned by the caller. Nothing here commits.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.dto.planning_preferences import PlanningPreferences
from app.application.ports.curriculum_seed_repository import (
    CurriculumVersionRecord,
    LearningProgramRecord,
)
from app.application.ports.study_goal_management_repository import AvailabilitySlotRecord
from app.application.ports.study_goal_repository import StudyGoalRecord
from app.infrastructure.persistence.curriculum import CurriculumVersion, LearningProgram
from app.infrastructure.persistence.learner_planning import AvailabilitySlot, StudyGoal

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
                preferred_session_minutes=record.planning_preferences.preferred_session_minutes,
                topic_sequencing=record.planning_preferences.topic_sequencing,
            )
        )

    def update_study_goal(self, record: StudyGoalRecord) -> None:
        """Overwrite the stored goal identified by ``record.id``.

        The preference columns are written from the record's whole group, so a
        preference the use case resolved to None is cleared rather than left
        behind. Deciding which of them the update meant to change is the use
        case's work, not this method's.
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

    def list_availability_slots(
        self, study_goal_ids: Sequence[uuid.UUID]
    ) -> tuple[AvailabilitySlotRecord, ...]:
        """Every availability slot belonging to the goals named, in no order.

        Unordered deliberately: week order is Monday-first presentation, and
        nothing stored ranks one day above another, so the use case sorts.
        """
        if not study_goal_ids:
            return ()
        models = self._session.scalars(
            select(AvailabilitySlot).where(AvailabilitySlot.study_goal_id.in_(study_goal_ids))
        )
        return tuple(_availability_record(model) for model in models)

    def add_availability_slot(self, record: AvailabilitySlotRecord) -> None:
        """Store a new availability slot."""
        self._session.add(
            AvailabilitySlot(
                id=record.id,
                study_goal_id=record.study_goal_id,
                day_of_week=record.day_of_week,
                available_minutes=record.available_minutes,
            )
        )

    def update_availability_slot(self, record: AvailabilitySlotRecord) -> None:
        """Overwrite the stored slot identified by ``record.id``.

        Only the minutes are written. A slot's goal and day are its identity --
        moving Monday's time to Tuesday is removing one day and adding another,
        which the use case expresses as exactly that.
        """
        model = self._session.get(AvailabilitySlot, record.id)
        if model is None:
            raise LookupError(f"Availability slot {record.id} is not stored.")
        model.available_minutes = record.available_minutes

    def delete_availability_slot(self, availability_slot_id: uuid.UUID) -> None:
        """Remove the stored slot with this identifier."""
        model = self._session.get(AvailabilitySlot, availability_slot_id)
        if model is None:
            raise LookupError(f"Availability slot {availability_slot_id} is not stored.")
        self._session.delete(model)


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


def _availability_record(model: AvailabilitySlot) -> AvailabilitySlotRecord:
    return AvailabilitySlotRecord(
        id=model.id,
        study_goal_id=model.study_goal_id,
        day_of_week=model.day_of_week,
        available_minutes=model.available_minutes,
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
        planning_preferences=PlanningPreferences(
            preferred_session_minutes=model.preferred_session_minutes,
            topic_sequencing=model.topic_sequencing,
        ),
    )
