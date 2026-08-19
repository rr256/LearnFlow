"""Input and output structures for retrieving passages from a learner's own notes.

These carry what RES-013 returns. They are framework-independent by design, as
the other DTOs in this package are.

**This is retrieval, and retrieval alone.** Nothing here asks a model anything,
generates an answer, summarises, embeds, or indexes into a vector store. A
passage is the learner's own words, **verbatim**, with enough context to say
where it came from — which is what
[rag/retrieval.md](../../../../docs/rag/retrieval.md) requires of a source
reference and no more.

**Nothing here is a measurement of the learner.** A passage's relevance decides
only the order results arrive in; it is deliberately **not carried on this
structure**, so no screen can render it as a figure beside a learner's own
writing. See `TopicNotePassage`.
"""

import uuid
from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True, slots=True)
class NoteMatch:
    """One note the search matched, with its **whole** body.

    What the repository returns. The body travels intact because **deciding what
    a passage is belongs to the application**, not to SQL: the extract has to be
    an exact substring, and the only way to guarantee that is to cut it from the
    stored text rather than ask the database to render something.

    That is a deliberate trade. PostgreSQL could return a shorter string with
    `ts_headline`, but its parser drops text it reads as an HTML tag, so
    `vector<int>` came back mangled. A whole body costs a little more to
    transfer — bounded by `MAX_NOTE_BODY_LENGTH` per note and `MAX_PASSAGES`
    notes — and keeps every character the learner typed.
    """

    note_id: uuid.UUID
    note_title: str
    body: str
    resource_id: uuid.UUID
    resource_title: str
    resource_type: str
    topic_id: uuid.UUID
    topic_name: str
    subject_name: str


@dataclass(frozen=True, slots=True)
class TopicNotePassage:
    """One passage from one of the learner's notes, with where it came from.

    **There is no relevance field, deliberately.** The repository orders by
    relevance and then discards the figure: a number beside a learner's own
    writing would be read as a mark on it, which is the line
    docs/domain/terminology.md draws for a plan coverage count and which applies
    with more force here. The order is the only thing relevance decides.

    Attributes:
        note_id: The note this passage came from, so a learner can open it.
        note_title: What the learner called that note.
        resource_id: The material the note was written against.
        resource_title: What the learner called that material.
        resource_type: Its kind, so a passage from a PYQ set reads differently
            from one out of their own notes.
        topic_id: The topic asked about, echoed so a caller can join without
            holding the request.
        topic_name: That topic's name, and the `subject_name` beside it below,
            are the *topic context* a passage is shown with.
        subject_name: The subject the topic belongs to.
        passage: One contiguous stretch of the note, **character for
            character**. It is an exact substring of the stored body: nothing is
            highlighted, marked up, escaped, re-encoded, joined, or elided, so
            `vector<int>`, `a < b`, and every other literal survives exactly as
            the learner typed it. Shorter than the note when the note is long;
            `note_id` leads to the rest.
    """

    note_id: uuid.UUID
    note_title: str
    resource_id: uuid.UUID
    resource_title: str
    resource_type: str
    topic_id: uuid.UUID
    topic_name: str
    subject_name: str
    passage: str


class TopicNoteSearchOutcome(Enum):
    """Why a search returned what it did.

    Three empty answers are told apart rather than collapsed into one, because
    they ask the learner to do three different things — link some material, write
    a note, or try another topic. Reporting "nothing found" for all three would
    hide which.
    """

    FOUND = "found"
    """At least one passage matched."""

    NO_LINKED_MATERIAL = "no_linked_material"
    """The learner has linked no material to this topic at all."""

    NO_ACTIVE_NOTES = "no_active_notes"
    """Material is linked, but it carries no note that is currently active."""

    NO_MATCHING_PASSAGE = "no_matching_passage"
    """Active notes exist on the linked material, and none mentions the topic."""


@dataclass(frozen=True, slots=True)
class TopicNoteSearchResult:
    """What RES-013 answers with.

    `passages` is empty for every outcome except `FOUND`, and `outcome` is what
    says why — see `TopicNoteSearchOutcome`.

    There is **no total and no count**: the passages are the answer, and a figure
    saying how many notes a learner has written would measure them rather than
    describe the search.
    """

    topic_id: uuid.UUID
    topic_name: str
    subject_name: str
    outcome: TopicNoteSearchOutcome
    passages: tuple[TopicNotePassage, ...] = ()


MAX_PASSAGES = 20
"""How many passages one search returns.

A bound on the answer, not a judgement about which few matter: results arrive in
relevance order, so this cuts the tail rather than choosing between passages the
learner would weigh differently. It exists because a learner with two hundred
notes on one topic would otherwise render every one of them on a single screen.

It is **never reported**. A learner is told what they can see, not how much was
left out, because a count of their own writing is a measurement of them.
"""

MAX_PASSAGE_WORDS = 60
"""How many words of a note one passage shows.

Enough for a passage to be understandable on its own, which
docs/rag/retrieval.md's context-budget rules ask for, and short enough that a
20,000-character note cannot fill the screen.

**One contiguous window, not several joined fragments.** Joining fragments would
mean inserting a separator, and a passage carrying anything the learner did not
write is no longer their text. A note that mentions the topic in three places
shows the first; `note_id` leads to the rest.
"""

LEAD_IN_WORDS = MAX_PASSAGE_WORDS // 3
"""How many words of run-up a passage keeps before the word that matched.

A match with nothing in front of it reads as though it began mid-thought. A third
of the window is enough to see what the sentence was doing.
"""
