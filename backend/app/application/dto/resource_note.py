"""Input and output structures for the notes a learner keeps against a resource.

These carry what RES-009 to RES-012 write, read, and change. They are
framework-independent by design, as the other DTOs in this package are.

A **resource note** is text the learner typed or pasted themselves — their own
notes on a piece of study material, or a passage they transcribed from it. It
belongs to exactly one learning resource and inherits the topics that resource
covers; it carries no topic links of its own.

This is the first study material LearnFlow stores rather than points at, and it is
deliberately the *only* kind: nothing here uploads a file, fetches an address,
extracts text from a document, or reads anything from the learner's machine. The
learner types or pastes, and LearnFlow keeps what they wrote.

Nothing inbound carries a `learner_id`: the effective learner is resolved
server-side (docs/api/conventions.md). A note is reached through its resource,
and that resource's owner is the only learner who may read or change it.

The controlled values below mirror the `CHECK` constraint on `resource_notes`,
the way `RESOURCE_STATUSES` mirrors its own. A value the application forgot to
check is refused by the database rather than stored and trusted later.
"""

import uuid
from dataclasses import dataclass

RESOURCE_NOTE_STATUSES: tuple[str, ...] = ("active", "archived")
"""The statuses `resource_notes.status` accepts.

Two states, both reachable in both directions. `archived` is the learner putting
a note aside, and it is **reversible** — nothing here deletes a note, which is
the position ADR-022 took for a superseded plan, ADR-032 for a resource, and
ADR-033 for a question.

`active` rather than `registered`: *registering* is what a learner does to a
resource, and it names where material is. A note is written, not registered, so
reusing the resource word would make one term mean two things. `archived` **is**
reused deliberately — it is the resources word for putting something aside, and
docs/domain/terminology.md reserves it for exactly that.
"""

ACTIVE = "active"
ARCHIVED = "archived"

MAX_NOTE_TITLE_LENGTH = 300
"""How long a note's title may be, matching a resource's.

A title is what the learner reads in the list before opening the note, so it is
a label rather than prose.
"""

MAX_NOTE_BODY_LENGTH = 20_000
"""How much text one note may hold.

Roughly eight pages — generous for a set of notes or a transcribed passage, and
bounded. This is the **one** field in LearnFlow a form can fill without limit,
so it is the one that needs a limit: an unbounded body is a database a single
request can fill and a screen a single record can make unrenderable.

It is an application rule rather than a column width. `body` is `text`, as
docs/database/schema.md requires of learner-facing prose, so raising this bound
later is a use-case change rather than a migration — the argument ADR-020 made
for `plan_items.status`.

The refusal never echoes the rejected text, per docs/api/conventions.md. That
rule matters more here than anywhere else: the value being refused is the
learner's own study material.
"""

MAX_NOTES_PER_RESOURCE = 200
"""How many notes one resource may hold.

A bound rather than a rule about study, and the companion to the one above: a
limit on a single note is no limit at all if a caller may write unlimited notes.

**It is never shown.** docs/domain/terminology.md permits a count only where it
describes a plan's own coverage or one scheduling request; a figure beside a
learner's material would measure the learner. This is read to decide whether one
more note may be written and for nothing else — it reaches no response and no
screen.
"""


@dataclass(frozen=True, slots=True)
class ResourceNoteRecord:
    """One resource note, as stored.

    The persistence shape, used by the port. `ResourceNoteDetail` below is what a
    caller reads. They carry the same fields today and are kept apart for the
    reason `ResourceRecord` and `ResourceDetail` are: the read shape is free to
    gain what a resource note is displayed *with* without changing what is
    written.
    """

    id: uuid.UUID
    resource_id: uuid.UUID
    title: str
    body: str
    status: str


@dataclass(frozen=True, slots=True)
class ResourceNoteDetail:
    """One resource note as a learner reads it.

    `body` is returned exactly as it was stored — the learner's own text, with
    their line breaks intact. Nothing here rewrites, normalises, summarises,
    truncates, or marks up what they wrote: docs/rag/ingestion.md's normalisation
    step belongs to a pipeline that reads *files*, and this is not one.
    """

    id: uuid.UUID
    resource_id: uuid.UUID
    title: str
    body: str
    status: str


@dataclass(frozen=True, slots=True)
class ResourceNotePage:
    """One page of a resource's notes, with the total the pagination block reports."""

    notes: tuple[ResourceNoteDetail, ...]
    total: int


@dataclass(frozen=True, slots=True)
class ResourceNoteFilters:
    """What a caller may narrow a note list by.

    A note belongs to one resource and covers no topics of its own, so `status`
    is the only thing there is to filter on. **No status is assumed**: a caller
    wanting only what the learner is using asks for `active`, and one wanting
    what has been put aside asks for `archived`, which is how RES-002, PLN-002,
    and REV-001 each treat their own.
    """

    status: str | None = None


@dataclass(frozen=True, slots=True)
class NewResourceNote:
    """A note a learner is asking to keep against a resource (RES-009).

    There is no `status`: a note is written `active`, and putting it aside is a
    later statement made through RES-012. That is the shape RES-001 uses for a
    resource and PLN-004 for a plan item, where the state a record is created in
    is not a request field.

    There is no `resource_id` either — it is named by the path, so a body cannot
    disagree with the resource whose ownership was just checked.

    Attributes:
        title: What the learner calls this note, so they can find it again
            without opening it.
        body: What they wrote or pasted, at most `MAX_NOTE_BODY_LENGTH`
            characters, stored exactly as given.
    """

    title: str
    body: str


@dataclass(frozen=True, slots=True)
class ResourceNoteChanges:
    """The fields a note update asks to change (RES-012).

    A field left unset is not touched. **No field carries a `clear_` flag**,
    unlike `ResourceChanges`: a note always has a title, a body, and a status, so
    `None` can only mean "leave it alone" and there is no clearance for it to be
    confused with. That is the rule LRN-002 applies to a timezone and GOAL-004 to
    a status.

    A note is **corrected in place**, however many times the learner likes, which
    is where this differs from a practice question: ADR-035 fixes a question's
    wording once a quiz has asked it, because a stored attempt is assembled from
    the live row and rewriting the prompt would rewrite a result the learner
    already read. Nothing reads a note, so nothing can be made to disagree with
    one.
    """

    title: str | None = None
    body: str | None = None
    status: str | None = None

    @property
    def is_empty(self) -> bool:
        """Whether the update asks for nothing at all."""
        return self.title is None and self.body is None and self.status is None
