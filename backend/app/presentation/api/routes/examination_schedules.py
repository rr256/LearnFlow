"""Examination schedule endpoint (EXM-001).

It exposes the published calendars a learner chooses between when setting a goal
(FR-002). Before it existed, a schedule reached a client only through a goal that
already named one -- which a learner setting a first goal has not got.

The route is thin: validate, call the use case, map the result. It touches no
session, model, or query (docs/architecture/dependency-rules.md).

An examination schedule is reference data, like the curriculum. None of it is
learner-owned, so this route resolves no learner identity.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.application.use_cases.read_examination_schedules import ReadExaminationSchedules
from app.presentation.api import API_V1_PREFIX
from app.presentation.api.dependencies import provide_read_examination_schedules
from app.presentation.api.schemas.examination_schedule import (
    ExaminationScheduleCollectionResponse,
)
from app.presentation.api.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

router = APIRouter(prefix=f"{API_V1_PREFIX}/examination-schedules", tags=["examination-schedules"])

ExaminationScheduleReader = Annotated[
    ReadExaminationSchedules, Depends(provide_read_examination_schedules)
]


@router.get(
    "",
    summary="List published examination schedules",
    response_model=ExaminationScheduleCollectionResponse,
)
def list_examination_schedules(
    reader: ExaminationScheduleReader,
    learning_program_id: Annotated[
        uuid.UUID | None,
        Query(description="Restrict to one learning program's schedules."),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=MAX_PAGE_SIZE, description="Maximum number of schedules to return."),
    ] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, description="Number of schedules to skip.")] = 0,
) -> ExaminationScheduleCollectionResponse:
    """Read the published examination schedules, each with its window and periods.

    An unknown `learning_program_id` returns an empty page rather than `404`: a
    filter that matches nothing is an empty result, not a missing record.

    EXM-001. Serves FR-002.
    """
    return ExaminationScheduleCollectionResponse.of(
        reader.list_examination_schedules(
            learning_program_id=learning_program_id, limit=limit, offset=offset
        )
    )
