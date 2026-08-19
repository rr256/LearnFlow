"""Request and response schemas for topic-note retrieval (RES-013).

A separate representation from the application DTOs, so a change to the HTTP
contract does not reach back into the use case
(docs/architecture/dependency-rules.md).

Every field name is `snake_case`, per docs/api/conventions.md. No schema here
accepts a `learner_id`: the effective learner is resolved server-side, and only
their own notes are ever searched.

**`passage` is plain text, and an exact substring of the stored note.** One
contiguous stretch, cut on word boundaries: nothing is highlighted, marked up,
escaped, re-encoded, joined, or elided, so `vector<int>` and every other literal
arrives exactly as the learner typed it. The stored note is untouched, and
`note_id` leads to the rest of it.

**No relevance figure appears anywhere in this contract.** Relevance decided the
order and nothing else; a number beside a learner's own writing would read as a
mark on it.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.application.dto.note_retrieval import (
    TopicNotePassage,
    TopicNoteSearchOutcome,
    TopicNoteSearchResult,
)


class NotePassageSchema(BaseModel):
    """One passage from one of the learner's notes."""

    note_id: uuid.UUID = Field(description="The note this passage came from.")
    note_title: str = Field(description="What the learner called that note.")
    resource_id: uuid.UUID = Field(description="The material the note was written against.")
    resource_title: str = Field(description="What the learner called that material.")
    resource_type: str = Field(description="What kind of material it is.")
    topic_id: uuid.UUID = Field(description="The topic that was asked about.")
    topic_name: str = Field(description="That topic's name.")
    subject_name: str = Field(description="The subject the topic belongs to.")
    passage: str = Field(
        description=(
            "One contiguous stretch of the note, in the learner's own words, character "
            "for character. An exact substring of the stored body: nothing is generated, "
            "summarised, paraphrased, highlighted, escaped, or joined. Shorter than the "
            "note when the note is long — open it by `note_id` to read the rest."
        )
    )

    @classmethod
    def of(cls, passage: TopicNotePassage) -> NotePassageSchema:
        """Build the schema from its application DTO."""
        return cls(
            note_id=passage.note_id,
            note_title=passage.note_title,
            resource_id=passage.resource_id,
            resource_title=passage.resource_title,
            resource_type=passage.resource_type,
            topic_id=passage.topic_id,
            topic_name=passage.topic_name,
            subject_name=passage.subject_name,
            passage=passage.passage,
        )


class TopicNoteSearchSchema(BaseModel):
    """What one search answers with."""

    topic_id: uuid.UUID
    topic_name: str
    subject_name: str
    outcome: str = Field(
        description=(
            "Why this is the answer: `found`, `no_linked_material`, `no_active_notes`, or "
            "`no_matching_passage`. Three empty answers are told apart because they ask the "
            "learner to do three different things."
        )
    )
    passages: list[NotePassageSchema] = Field(
        description=(
            "The matching passages, most relevant first. Empty for every outcome except "
            "`found`. There is deliberately no total and no count."
        )
    )

    @classmethod
    def of(cls, result: TopicNoteSearchResult) -> TopicNoteSearchSchema:
        """Build the schema from its application DTO."""
        return cls(
            topic_id=result.topic_id,
            topic_name=result.topic_name,
            subject_name=result.subject_name,
            outcome=result.outcome.value,
            passages=[NotePassageSchema.of(passage) for passage in result.passages],
        )


class TopicNoteSearchResponse(BaseModel):
    """One search result, under the documented `data` envelope."""

    data: TopicNoteSearchSchema


OUTCOME_VALUES: tuple[str, ...] = tuple(outcome.value for outcome in TopicNoteSearchOutcome)
"""Every outcome this endpoint can report, for the route's documentation."""
