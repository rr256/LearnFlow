"""Request and response schemas for a source-grounded study answer (MNT-001).

A separate representation from the application DTOs, so a change to the HTTP
contract does not reach back into the use case
(docs/architecture/dependency-rules.md).

Every field name is `snake_case`, per docs/api/conventions.md. No schema here
accepts a `learner_id`: the effective learner is resolved server-side, and only
their own notes are ever consulted.

**`answer` and `passage` are both plain text.** Neither is markup, and neither is
rendered as any: the model is asked for prose, and a passage is an exact
substring of a stored note. The frontend escapes both and preserves the learner's
own line breaks with CSS, exactly as it does on the retrieval screen.

**The citations are not the model's claims.** `passages` carries what LearnFlow
retrieved and sent, recorded before the provider was asked. Nothing parses a
source out of the answer text, so an answer cannot cite a note that was not
consulted.

**No figure of any kind appears in this contract** — no score, no confidence, no
relevance, and no count of passages or notes.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.application.dto.study_answer import (
    MAX_QUESTION_LENGTH,
    StudyAnswer,
    StudyAnswerOutcome,
)
from app.presentation.api.schemas.note_retrieval import NotePassageSchema


class StudyQuestionRequest(BaseModel):
    """One question, about one topic.

    The whole request body. There is no conversation identifier, no message
    history, no model name, no temperature, and no provider selection: a caller
    cannot choose what their question is sent to, because that is a deployment
    decision read from configuration in the composition root.
    """

    topic_id: uuid.UUID = Field(description="The curriculum topic the question is about.")
    question: str = Field(
        min_length=1,
        max_length=MAX_QUESTION_LENGTH,
        description=(
            "What the learner wants explained. Sent verbatim to the AI provider "
            "alongside the retrieved passages, and **never stored** — no question "
            "history exists."
        ),
    )


class StudyAnswerSchema(BaseModel):
    """What one question is answered with."""

    topic_id: uuid.UUID
    topic_name: str
    subject_name: str
    question: str = Field(description="The question, echoed back as it was asked.")
    outcome: str = Field(
        description=(
            "Why this is the answer. `answered` means the provider was asked and "
            "replied. `no_linked_material`, `no_active_notes`, and "
            "`no_matching_passage` each mean **the provider was never asked**: "
            "there was nothing of the learner's to ground an answer in. "
            "`provider_unavailable`, `provider_timed_out`, and "
            "`provider_unusable_reply` mean passages were found and the provider "
            "could not answer — the passages are still returned."
        )
    )
    answer: str | None = Field(
        default=None,
        description=(
            "The answer as plain text, or null when there is none. Grounded in "
            "`passages` and nothing else: no other learner data was sent."
        ),
    )
    passages: list[NotePassageSchema] = Field(
        description=(
            "The passages from the learner's own notes that the answer was "
            "grounded in — the citations. Recorded from what was **sent**, so they "
            "describe what was consulted rather than what the model claimed. "
            "Empty only when no passage was found, in which case no answer was "
            "generated either."
        )
    )

    @classmethod
    def of(cls, result: StudyAnswer) -> StudyAnswerSchema:
        """Build the schema from its application DTO."""
        return cls(
            topic_id=result.topic_id,
            topic_name=result.topic_name,
            subject_name=result.subject_name,
            question=result.question,
            outcome=result.outcome.value,
            answer=result.answer,
            passages=[NotePassageSchema.of(passage) for passage in result.passages],
        )


class StudyAnswerResponse(BaseModel):
    """One answer, under the documented `data` envelope."""

    data: StudyAnswerSchema


ANSWER_OUTCOME_VALUES: tuple[str, ...] = tuple(outcome.value for outcome in StudyAnswerOutcome)
"""Every outcome this endpoint can report, for the route's documentation."""
