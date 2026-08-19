"""An in-memory stand-in for the topic-note search port.

It mirrors the eligibility rules the SQL applies — a note must be **active**, on
a resource that is **registered** and owned by the asking learner, and linked to
the topic — so a use-case test that forgot one of them fails here rather than
passing against a fake that was more generous than the database.

**The matching is deliberately cruder than PostgreSQL's.** It lowercases and
splits on word characters, with no stemming and no ranking beyond "more matched
terms first". Real full-text behaviour — stemming, the GIN index — is not
simulated, because a fake that pretended to stem would prove something about the
fake. Those belong to tests/integration/test_note_search_api.py, which runs
against a real database.

It returns **whole bodies**, as the real adapter does. Cutting a passage out of
one is the use case's rule, covered by its own tests.

**There is no write method**, because the port has none: a search stores nothing.
"""

import re
import uuid
from collections.abc import Sequence

from app.application.dto.note_retrieval import NoteMatch
from app.application.dto.resource import ResourceRecord, ResourceTopic
from app.application.dto.resource_note import ResourceNoteRecord

ACTIVE = "active"
REGISTERED = "registered"


class FakeNoteSearchRepository:
    """Searches notes held in lists, applying the same eligibility rules as the SQL."""

    def __init__(
        self,
        *,
        resources: Sequence[ResourceRecord] = (),
        notes: Sequence[ResourceNoteRecord] = (),
        topics: Sequence[ResourceTopic] = (),
        links: dict[uuid.UUID, Sequence[uuid.UUID]] | None = None,
    ) -> None:
        """Start from stored material, its notes, the topics, and the links between."""
        self.resources = list(resources)
        self.notes = list(notes)
        self.topics = list(topics)
        self.links = {resource_id: tuple(ids) for resource_id, ids in (links or {}).items()}
        # Every call made, so a test can assert a search was not run at all.
        self.searches: list[tuple[uuid.UUID, str]] = []

    def has_linked_material(self, *, learner_id: uuid.UUID, topic_id: uuid.UUID) -> bool:
        return any(self._eligible_resources(learner_id, topic_id))

    def has_active_notes(self, *, learner_id: uuid.UUID, topic_id: uuid.UUID) -> bool:
        return any(self._eligible_notes(learner_id, topic_id))

    def search_matches(
        self,
        *,
        learner_id: uuid.UUID,
        topic_id: uuid.UUID,
        query_terms: str,
        limit: int,
    ) -> tuple[NoteMatch, ...]:
        self.searches.append((topic_id, query_terms))
        terms = {term for term in _words(query_terms) if term != "or"}
        if not terms:
            return ()

        topic = next((candidate for candidate in self.topics if candidate.id == topic_id), None)
        if topic is None:
            return ()

        scored: list[tuple[int, ResourceNoteRecord, ResourceRecord]] = []
        for note, resource in self._eligible_notes(learner_id, topic_id):
            matched = len(terms & set(_words(f"{note.title} {note.body}")))
            if matched:
                scored.append((matched, note, resource))

        # More matched terms first, then newest, matching the SQL's intent.
        scored.sort(key=lambda entry: (-entry[0], -self.notes.index(entry[1])))
        return tuple(
            NoteMatch(
                note_id=note.id,
                note_title=note.title,
                # The whole body, exactly as the real adapter returns it: cutting
                # the passage is the use case's job, and its own tests cover it.
                body=note.body,
                resource_id=resource.id,
                resource_title=resource.title,
                resource_type=resource.resource_type,
                topic_id=topic.id,
                topic_name=topic.name,
                subject_name=topic.subject_name,
            )
            for _, note, resource in scored[:limit]
        )

    def _eligible_resources(
        self, learner_id: uuid.UUID, topic_id: uuid.UUID
    ) -> list[ResourceRecord]:
        return [
            resource
            for resource in self.resources
            if resource.owner_learner_id == learner_id
            and resource.status == REGISTERED
            and topic_id in self.links.get(resource.id, ())
        ]

    def _eligible_notes(
        self, learner_id: uuid.UUID, topic_id: uuid.UUID
    ) -> list[tuple[ResourceNoteRecord, ResourceRecord]]:
        eligible = {
            resource.id: resource for resource in self._eligible_resources(learner_id, topic_id)
        }
        return [
            (note, eligible[note.resource_id])
            for note in self.notes
            if note.status == ACTIVE and note.resource_id in eligible
        ]


def _words(text: str) -> list[str]:
    """Lowercased word characters, with no stemming. See the module docstring."""
    return re.findall(r"[\w]+", text.lower(), flags=re.UNICODE)
