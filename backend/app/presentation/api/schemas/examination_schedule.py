"""Response schemas for the examination schedule endpoint (EXM-001).

Each schema is built from an application DTO by an explicit constructor rather
than by attribute inference, so adding a field to a DTO cannot silently widen the
public contract (docs/architecture/dependency-rules.md).

The examination is reported as a **window**, never as one date, and the
provenance travels with it: the organising body, the source it was read from, the
day it was read, and whether that source still calls the dates provisional. A
client showing these dates has everything it needs to say so.
"""

import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.application.dto.examination_schedule import (
    ExaminationPeriodSummary,
    ExaminationScheduleDetail,
    ExaminationSchedulePage,
)
from app.presentation.api.schemas.pagination import Pagination


class ExaminationWindowSchema(BaseModel):
    """The span from the first published sitting day to the last.

    Derived from the schedule's `examination` periods alone, so it excludes the
    registration and results dates that bracket them. It is not a claim that the
    learner sits the paper on any particular day inside it.
    """

    starts_on: date = Field(description="First published sitting day.")
    ends_on: date = Field(description="Last published sitting day.")

    @classmethod
    def of(cls, starts_on: date | None, ends_on: date | None) -> ExaminationWindowSchema | None:
        """Build the schema, or None when the schedule publishes no sitting day."""
        if starts_on is None or ends_on is None:
            return None
        return cls(starts_on=starts_on, ends_on=ends_on)


class ExaminationPeriodSchema(BaseModel):
    """One dated period of a schedule. A single-day event starts and ends on it."""

    period_type: str = Field(
        description="One of `registration`, `late_registration`, `examination`, or `results`."
    )
    starts_on: date
    ends_on: date

    @classmethod
    def of(cls, summary: ExaminationPeriodSummary) -> ExaminationPeriodSchema:
        """Build the schema from its application DTO."""
        return cls(
            period_type=summary.period_type,
            starts_on=summary.starts_on,
            ends_on=summary.ends_on,
        )


class ExaminationScheduleSchema(BaseModel):
    """One published examination schedule, with its provenance and its window."""

    id: uuid.UUID
    learning_program_id: uuid.UUID
    cycle_label: str = Field(description="Stable cycle label within the program, such as `2027`.")
    name: str = Field(description="Display name, such as `GATE 2027`.")
    organising_body: str | None = Field(description="Body publishing the schedule.")
    source_reference: str = Field(description="Official source the dates were transcribed from.")
    source_checked_on: date = Field(description="When that source was read.")
    schedule_status: str = Field(
        description=(
            "`provisional` while the source says the dates are liable to change, "
            "`confirmed` once the examining body confirms them. Show it wherever "
            "the dates are shown."
        )
    )
    examination_window: ExaminationWindowSchema | None = Field(
        description="Null when the stored schedule publishes no sitting day."
    )
    periods: list[ExaminationPeriodSchema] = Field(
        description="Every dated period, in date order, including registration deadlines."
    )

    @classmethod
    def of(cls, detail: ExaminationScheduleDetail) -> ExaminationScheduleSchema:
        """Build the schema from its application DTO."""
        return cls(
            id=detail.id,
            learning_program_id=detail.learning_program_id,
            cycle_label=detail.cycle_label,
            name=detail.name,
            organising_body=detail.organising_body,
            source_reference=detail.source_reference,
            source_checked_on=detail.source_checked_on,
            schedule_status=detail.schedule_status,
            examination_window=ExaminationWindowSchema.of(
                detail.window_starts_on, detail.window_ends_on
            ),
            periods=[ExaminationPeriodSchema.of(period) for period in detail.periods],
        )


class ExaminationScheduleCollectionResponse(BaseModel):
    """A page of published schedules, under the documented collection envelope."""

    data: list[ExaminationScheduleSchema]
    pagination: Pagination

    @classmethod
    def of(cls, page: ExaminationSchedulePage) -> ExaminationScheduleCollectionResponse:
        """Build the response from its application DTO."""
        return cls(
            data=[ExaminationScheduleSchema.of(detail) for detail in page.schedules],
            pagination=Pagination(limit=page.limit, offset=page.offset, total=page.total),
        )
