"""The persistence port topic-note retrieval works through.

It answers one question: which passages of this learner's own active notes, on
material they linked to this topic, mention that topic — and in what order.

**The ordering is fixed here**, for the reason `curriculum_repository` records:
a result set cannot be ordered after it has been sliced. Notes come back in
relevance order, and the relevance figure itself is **discarded by the adapter**
rather than carried out of it, so nothing downstream can render a number beside
a learner's own writing.

**Nothing here renders text.** The database matches and orders; it returns the
stored body untouched, and the application cuts the passage from it. That is what
keeps a passage an exact substring.

**No provider sits behind this port.** It is a database read and nothing else:
no embedding provider, no vector store, no AI provider, and no outbound call of
any kind. That is what keeps a learner's note text on their own machine, and it
is asserted by a test.

The two counting methods exist to tell three empty answers apart, not to report
a figure. See `TopicNoteSearchOutcome`.
"""

import uuid
from typing import Protocol

from app.application.dto.note_retrieval import NoteMatch


class NoteSearchRepository(Protocol):
    """Reads passages from a learner's notes for one topic."""

    def has_linked_material(self, *, learner_id: uuid.UUID, topic_id: uuid.UUID) -> bool:
        """Whether the learner has any registered resource linked to this topic.

        A **boolean, never a count** — the rule ADR-035 set for `has_been_asked`.
        It distinguishes "you have linked nothing here" from "nothing matched",
        and a figure would answer a question nobody asked.
        """
        ...

    def has_active_notes(self, *, learner_id: uuid.UUID, topic_id: uuid.UUID) -> bool:
        """Whether any active note exists on the material linked to this topic.

        A boolean, for the reason above. It separates "no notes yet" from "no
        passage mentions this topic", which ask the learner to do different
        things.
        """
        ...

    def search_matches(
        self,
        *,
        learner_id: uuid.UUID,
        topic_id: uuid.UUID,
        query_terms: str,
        limit: int,
    ) -> tuple[NoteMatch, ...]:
        """The matching notes, most relevant first, with their bodies intact.

        **This returns notes, not passages.** Which stretch of a note to show is
        an application rule, decided after this returns, because a passage must
        be an exact substring and only the stored text can guarantee that.

        Only notes that are **active**, on resources that are **registered** and
        owned by this learner, and linked to this topic are considered. Ownership
        is enforced in the query rather than filtered afterwards, so a row
        belonging to another learner is never read into memory at all.

        Args:
            learner_id: The effective learner, resolved server-side.
            topic_id: The topic being asked about.
            query_terms: The search terms the use case derived from that topic.
            limit: At most this many notes.
        """
        ...
