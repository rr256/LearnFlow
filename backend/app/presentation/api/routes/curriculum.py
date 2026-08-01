"""Curriculum endpoints (CUR-001 to CUR-003).

They expose the curated learning program a learner browses, so the frontend
renders backend-provided curriculum data rather than embedding GATE CSE topics
in code (FR-001).

Every route here is thin: validate, call the use case, map the result or its
error to a documented response. No route touches a session, a model, or a query
(docs/architecture/dependency-rules.md).

Curriculum data is reference data. None of it is learner-owned, so no route
resolves a learner identity.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.status import HTTP_404_NOT_FOUND

from app.application.use_cases.read_curriculum import (
    CurriculumVersionNotFoundError,
    LearningProgramNotFoundError,
    ReadCurriculum,
)
from app.presentation.api import API_V1_PREFIX
from app.presentation.api.dependencies import provide_read_curriculum
from app.presentation.api.errors import ErrorResponse
from app.presentation.api.schemas.curriculum import (
    CurriculumTreeResponse,
    CurriculumTreeSchema,
    LearningProgramCollectionResponse,
    LearningProgramResponse,
    LearningProgramSchema,
)
from app.presentation.api.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

router = APIRouter(prefix=f"{API_V1_PREFIX}/curriculum", tags=["curriculum"])

_NOT_FOUND_RESPONSE = {HTTP_404_NOT_FOUND: {"model": ErrorResponse}}

CurriculumReader = Annotated[ReadCurriculum, Depends(provide_read_curriculum)]


@router.get(
    "/programs",
    summary="List available learning programs",
    response_model=LearningProgramCollectionResponse,
)
def list_learning_programs(
    reader: CurriculumReader,
    limit: Annotated[
        int,
        Query(ge=1, le=MAX_PAGE_SIZE, description="Maximum number of programs to return."),
    ] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, description="Number of programs to skip.")] = 0,
) -> LearningProgramCollectionResponse:
    """Read the learning programs LearnFlow offers, newest curriculum included.

    CUR-001. Serves FR-001.
    """
    return LearningProgramCollectionResponse.of(
        reader.list_learning_programs(limit=limit, offset=offset)
    )


@router.get(
    "/programs/{program_id}",
    summary="Read one learning program",
    response_model=LearningProgramResponse,
    responses=_NOT_FOUND_RESPONSE,
)
def read_learning_program(
    program_id: uuid.UUID, reader: CurriculumReader
) -> LearningProgramResponse:
    """Read one program's metadata and its active curriculum-version reference.

    CUR-002. Serves FR-001.
    """
    try:
        program = reader.read_learning_program(program_id)
    except LearningProgramNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    return LearningProgramResponse(data=LearningProgramSchema.of(program))


@router.get(
    "/versions/{curriculum_version_id}/tree",
    summary="Read a curriculum version's subjects, topics, and subtopics",
    response_model=CurriculumTreeResponse,
    responses=_NOT_FOUND_RESPONSE,
)
def read_curriculum_tree(
    curriculum_version_id: uuid.UUID, reader: CurriculumReader
) -> CurriculumTreeResponse:
    """Read the full data-driven curriculum hierarchy for one version.

    CUR-003. Serves FR-001.
    """
    try:
        tree = reader.read_curriculum_tree(curriculum_version_id)
    except CurriculumVersionNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    return CurriculumTreeResponse(data=CurriculumTreeSchema.of(tree))
