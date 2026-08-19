"""SQLAlchemy implementation of the topic-note search port.

Serves RES-013. It is **PostgreSQL's own full-text search and nothing else**: no
embedding provider, no vector store, no AI provider, no external call. A search
is one `SELECT`, and it writes nothing.

It decides nothing about study. Which notes are eligible, what an empty answer
means, and how many passages come back are all settled by the use case
(docs/architecture/dependency-rules.md); this renders the query those rules
describe.

**Relevance leaves this module as an order and never as a number.** `ts_rank`
appears in the `ORDER BY` and is deliberately absent from the projection, so no
figure that could be read as a mark on a learner's own writing reaches the
application layer at all.

**`ts_headline` is deliberately not used.** It would return a shorter string,
and its parser drops text it reads as an HTML tag: a note containing
`vector<int>` came back with the tag-like part removed. Nothing here renders,
truncates, or re-encodes a learner's text — the stored body is returned as it is,
and the application cuts an exact substring from it.

The session's transaction is owned by the caller. Nothing here commits.
"""

import uuid

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session

from app.application.dto.note_retrieval import NoteMatch
from app.infrastructure.persistence.curriculum import Subject, Topic
from app.infrastructure.persistence.resources import (
    SEARCH_CONFIGURATION,
    Resource,
    ResourceNote,
    ResourceTopicLink,
)

ACTIVE_NOTE = "active"
"""The one note status this search considers.

A note the learner put aside is left out, exactly as archived material is left
out of every screen that shows a topic's resources.
"""

REGISTERED_RESOURCE = "registered"
"""The one resource status whose notes are searched."""


class SqlAlchemyNoteSearchRepository:
    """Searches a learner's own notes through a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one unit of work."""
        self._session = session

    def has_linked_material(self, *, learner_id: uuid.UUID, topic_id: uuid.UUID) -> bool:
        """Whether any registered resource of this learner is linked to the topic."""
        return bool(
            self._session.scalar(
                select(
                    select(Resource.id)
                    .join(ResourceTopicLink, ResourceTopicLink.resource_id == Resource.id)
                    .where(
                        *_owned_and_registered(learner_id), ResourceTopicLink.topic_id == topic_id
                    )
                    .exists()
                )
            )
        )

    def has_active_notes(self, *, learner_id: uuid.UUID, topic_id: uuid.UUID) -> bool:
        """Whether any active note sits on that linked, registered material."""
        return bool(
            self._session.scalar(
                select(
                    select(ResourceNote.id)
                    .join(Resource, Resource.id == ResourceNote.resource_id)
                    .join(ResourceTopicLink, ResourceTopicLink.resource_id == Resource.id)
                    .where(
                        *_owned_and_registered(learner_id),
                        ResourceTopicLink.topic_id == topic_id,
                        ResourceNote.status == ACTIVE_NOTE,
                    )
                    .exists()
                )
            )
        )

    def search_matches(
        self,
        *,
        learner_id: uuid.UUID,
        topic_id: uuid.UUID,
        query_terms: str,
        limit: int,
    ) -> tuple[NoteMatch, ...]:
        """The matching notes, most relevant first, bodies intact.

        `websearch_to_tsquery` is used rather than `to_tsquery` because it never
        raises on odd input: a topic name is data, and a parser that could fail
        on it would turn a curriculum row into an error the learner cannot act
        on. The use case has already reduced the name to words joined by `or`.

        Ownership, status, and topic linkage are all conditions of the query, so
        a row belonging to another learner is never read into memory.

        The **whole body** is selected. `ts_headline` would send less, and would
        mangle the learner's text doing it; the transfer is bounded by
        `MAX_NOTE_BODY_LENGTH` per note and by `limit` notes.
        """
        if not query_terms.strip():
            return ()

        query = func.websearch_to_tsquery(SEARCH_CONFIGURATION, query_terms)
        document = _searchable_document()
        # Ordered by relevance, then by a stable tiebreak so two equally relevant
        # passages cannot swap places between identical requests.
        statement: Select = (
            select(
                ResourceNote.id,
                ResourceNote.title,
                Resource.id,
                Resource.title,
                Resource.resource_type,
                Topic.id,
                Topic.name,
                Subject.name,
                ResourceNote.body,
            )
            .join(Resource, Resource.id == ResourceNote.resource_id)
            .join(ResourceTopicLink, ResourceTopicLink.resource_id == Resource.id)
            .join(Topic, Topic.id == ResourceTopicLink.topic_id)
            .join(Subject, Subject.id == Topic.subject_id)
            .where(
                *_owned_and_registered(learner_id),
                ResourceTopicLink.topic_id == topic_id,
                ResourceNote.status == ACTIVE_NOTE,
                document.op("@@")(query),
            )
            .order_by(
                func.ts_rank(document, query).desc(),
                ResourceNote.created_at.desc(),
                ResourceNote.id,
            )
            .limit(limit)
        )

        return tuple(
            NoteMatch(
                note_id=row[0],
                note_title=row[1],
                resource_id=row[2],
                resource_title=row[3],
                resource_type=row[4],
                topic_id=row[5],
                topic_name=row[6],
                subject_name=row[7],
                body=row[8],
            )
            for row in self._session.execute(statement).all()
        )


def _owned_and_registered(learner_id: uuid.UUID) -> tuple[ColumnElement[bool], ...]:
    """The two conditions every read here applies to the resource.

    Ownership **and** status together: the material must be this learner's, and
    it must still be in their catalogue. Written once so no query can be added
    later that quietly checks only one of them.
    """
    return (
        Resource.owner_learner_id == learner_id,
        Resource.status == REGISTERED_RESOURCE,
    )


def _searchable_document() -> ColumnElement:
    """The text a note is matched against: its title and its body.

    **This expression is the index.** Migration `20260820_01` creates a GIN index
    over exactly this, with the same configuration and the same column order, so
    any change here without a matching migration turns an indexed search into a
    sequential scan rather than into a wrong answer.

    The two-argument `to_tsvector` with a literal configuration is required: the
    one-argument form depends on `default_text_search_config` at runtime, which
    makes it `STABLE` rather than `IMMUTABLE`, and PostgreSQL refuses to index a
    non-immutable expression.

    A note's title is searched beside its body because a learner who titles a
    note *Deadlock conditions* has said something about what it covers.
    """
    return func.to_tsvector(
        SEARCH_CONFIGURATION,
        ResourceNote.title.concat(" ").concat(ResourceNote.body),
    )
