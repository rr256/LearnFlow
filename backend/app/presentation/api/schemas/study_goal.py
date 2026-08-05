"""Request and response schemas for the study-goal endpoints (GOAL-001 to GOAL-004).

No request accepts a `learner_id`: the effective learner is resolved server-side
(docs/api/conventions.md). No request accepts a `curriculum_version_id` either --
a goal binds to the program's *active* curriculum version, so a client cannot
attach a learner to a draft or retired syllabus.

A goal's examination is reported as a **window** with the schedule's provenance
beside it, never as a single date the examining body has not published (ADR-013).

`planning_preferences` is absent from the update request. The column does not
exist, so accepting the field would promise storage the database does not have.
"""

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.application.dto.study_goal import (
    ExaminationGoalSummary,
    NewStudyGoal,
    StudyGoalChanges,
    StudyGoalCurriculumVersion,
    StudyGoalDetail,
    StudyGoalPage,
    StudyGoalProgram,
)
from app.application.use_cases.manage_study_goals import STUDY_GOAL_STATUSES
from app.presentation.api.schemas.examination_schedule import ExaminationWindowSchema
from app.presentation.api.schemas.pagination import Pagination


class StudyGoalProgramSchema(BaseModel):
    """The learning program a goal is bound to."""

    id: uuid.UUID
    code: str = Field(description="Stable program code, such as `gate-cse`.")
    name: str

    @classmethod
    def of(cls, program: StudyGoalProgram) -> StudyGoalProgramSchema:
        """Build the schema from its application DTO."""
        return cls(id=program.id, code=program.code, name=program.name)


class StudyGoalCurriculumVersionSchema(BaseModel):
    """The curriculum version a goal is bound to.

    A goal keeps the version it was created against. `status` may therefore read
    `retired` on an older goal, which records what the learner actually planned
    against rather than what is active today.
    """

    id: uuid.UUID
    version_label: str
    status: str = Field(description="One of `draft`, `active`, or `retired`.")

    @classmethod
    def of(cls, version: StudyGoalCurriculumVersion) -> StudyGoalCurriculumVersionSchema:
        """Build the schema from its application DTO."""
        return cls(id=version.id, version_label=version.version_label, status=version.status)


class ExaminationGoalSchema(BaseModel):
    """The examination cycle a goal aims at, and how far its dates can be trusted."""

    id: uuid.UUID
    cycle_label: str
    name: str
    organising_body: str | None
    source_reference: str
    source_checked_on: date
    schedule_status: str = Field(
        description=(
            "`provisional` while the source says the dates are liable to change, "
            "`confirmed` once the examining body confirms them."
        )
    )
    examination_window: ExaminationWindowSchema | None = Field(
        description="Null when the stored schedule publishes no sitting day."
    )

    @classmethod
    def of(cls, summary: ExaminationGoalSummary) -> ExaminationGoalSchema:
        """Build the schema from its application DTO."""
        return cls(
            id=summary.id,
            cycle_label=summary.cycle_label,
            name=summary.name,
            organising_body=summary.organising_body,
            source_reference=summary.source_reference,
            source_checked_on=summary.source_checked_on,
            schedule_status=summary.schedule_status,
            examination_window=ExaminationWindowSchema.of(
                summary.window_starts_on, summary.window_ends_on
            ),
        )


class StudyGoalSchema(BaseModel):
    """One study goal, with the reference data it points at resolved.

    No availability summary is reported: `availability_slots` does not exist yet,
    and GOAL-005 -- which would fill it -- needs the `day_of_week` numbering
    convention that remains an open decision (ADR-011).
    """

    id: uuid.UUID
    learner_id: uuid.UUID
    status: str = Field(description="One of `active`, `paused`, `completed`, or `archived`.")
    target_date: date | None = Field(
        description="The learner's own completion date, where they set one."
    )
    learning_program: StudyGoalProgramSchema
    curriculum_version: StudyGoalCurriculumVersionSchema
    examination: ExaminationGoalSchema | None = Field(
        description="Null for a goal aiming at a target date alone."
    )

    @classmethod
    def of(cls, detail: StudyGoalDetail) -> StudyGoalSchema:
        """Build the schema from its application DTO."""
        return cls(
            id=detail.id,
            learner_id=detail.learner_id,
            status=detail.status,
            target_date=detail.target_date,
            learning_program=StudyGoalProgramSchema.of(detail.learning_program),
            curriculum_version=StudyGoalCurriculumVersionSchema.of(detail.curriculum_version),
            examination=(
                None if detail.examination is None else ExaminationGoalSchema.of(detail.examination)
            ),
        )


class StudyGoalResponse(BaseModel):
    """One study goal, under the documented `data` envelope."""

    data: StudyGoalSchema


class StudyGoalCollectionResponse(BaseModel):
    """A page of study goals, under the documented collection envelope."""

    data: list[StudyGoalSchema]
    pagination: Pagination

    @classmethod
    def of(cls, page: StudyGoalPage) -> StudyGoalCollectionResponse:
        """Build the response from its application DTO."""
        return cls(
            data=[StudyGoalSchema.of(detail) for detail in page.goals],
            pagination=Pagination(limit=page.limit, offset=page.offset, total=page.total),
        )


class CreateStudyGoalRequest(BaseModel):
    """A goal a learner is asking to create.

    At least one of `examination_schedule_id` and `target_date` must be present.
    The rule is checked by the use case rather than here, because it is a
    business invariant the database also enforces, not a shape constraint.
    """

    model_config = ConfigDict(extra="forbid")

    learning_program_id: uuid.UUID = Field(description="The program to study.")
    examination_schedule_id: uuid.UUID | None = Field(
        default=None, description="The published examination cycle to aim at."
    )
    target_date: date | None = Field(
        default=None,
        description=(
            "A plain completion date, for a learner following no published examination. "
            "Do not use it to guess a paper date inside an examination window."
        ),
    )

    def to_new_study_goal(self) -> NewStudyGoal:
        """Map the request onto the application's creation structure."""
        return NewStudyGoal(
            learning_program_id=self.learning_program_id,
            examination_schedule_id=self.examination_schedule_id,
            target_date=self.target_date,
        )


class UpdateStudyGoalRequest(BaseModel):
    """A partial update to a study goal.

    A field that is absent is left alone. An explicit null clears the stored
    value, which absence cannot express. The result must still aim at an
    examination cycle, a target date, or both.
    """

    model_config = ConfigDict(extra="forbid")

    examination_schedule_id: uuid.UUID | None = Field(
        default=None, description="New examination cycle, or null to stop aiming at one."
    )
    target_date: date | None = Field(
        default=None, description="New completion date, or null to remove it."
    )
    status: str | None = Field(
        default=None,
        description=f"One of: {', '.join(STUDY_GOAL_STATUSES)}.",
    )

    @model_validator(mode="after")
    def _reject_a_null_status(self) -> UpdateStudyGoalRequest:
        """A goal always has a status, so null cannot mean "remove it"."""
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null. Omit it to leave the stored value alone.")
        return self

    def to_changes(self) -> StudyGoalChanges:
        """Map the request onto the application's partial-update structure.

        `model_fields_set` is what distinguishes "absent" from "explicitly null";
        a default alone cannot, because both arrive as `None`.
        """
        supplied = self.model_fields_set
        return StudyGoalChanges(
            examination_schedule_id=(
                self.examination_schedule_id if "examination_schedule_id" in supplied else None
            ),
            clear_examination_schedule=(
                "examination_schedule_id" in supplied and self.examination_schedule_id is None
            ),
            target_date=self.target_date if "target_date" in supplied else None,
            clear_target_date="target_date" in supplied and self.target_date is None,
            status=self.status if "status" in supplied else None,
        )
