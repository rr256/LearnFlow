"""Input and output structures for a learner's revisions.

These carry what REV-001 to REV-004 read, schedule, and move. They are
framework-independent by design, as the other DTOs in this package are: the API
schemas that serialise them are a separate representation, so a change to the
HTTP contract does not reach back into the use case.

A revision is learner-owned and names one topic. Nothing inbound carries a
`learner_id`: the effective learner is resolved server-side
(docs/api/conventions.md).

The controlled values below mirror the `CHECK` constraints on `revision_records`,
the way `LEARNING_STAGES`, `WEEKDAYS`, and the plan vocabularies mirror theirs. A
value the application forgot to check is refused by the database rather than
stored and trusted later.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime

REVISION_STATUSES: tuple[str, ...] = ("due", "scheduled", "completed", "skipped", "postponed")
"""The statuses `revision_records.status` accepts.

Every revision is written `due`. **REV-003 moves one to `completed`, `skipped`,
or `postponed`, and back**, which is PLN-004's shape for a plan item.

`scheduled` is approved and **unwritten**, as `scheduled_for` is. Naming a day
for a revision is a second capability, and the constraint carries the value so it
arrives as a use-case change rather than a migration.
"""

REVISION_STATUS_CHANGES: tuple[str, ...] = ("due", "completed", "skipped", "postponed")
"""The statuses REV-003 accepts as a target.

Four of the five the column holds. `scheduled` is deliberately absent: a caller
asking for it would be asking for a date nothing collects, so the endpoint
refuses it rather than storing a status whose companion column stays null.

The two tuples are named separately, as PLN-004's are, because they answer
different questions — what a learner may *ask for*, and what the column may
*hold* — and only the second is mirrored by the `CHECK`.
"""

REVISION_TRIGGERS: tuple[str, ...] = ("completed_plan_item", "completed_revision")
"""Why a revision was created.

`completed_plan_item` is a topic the learner finished planned work on;
`completed_revision` is that topic returning after a review they completed, which
is the *prior revision history* FR-006's fourth criterion names.
"""

DUE = "due"
SCHEDULED = "scheduled"
COMPLETED = "completed"
SKIPPED = "skipped"
POSTPONED = "postponed"
COMPLETED_PLAN_ITEM = "completed_plan_item"
COMPLETED_REVISION = "completed_revision"

SETTLED_REVISION_STATUSES: frozenset[str] = frozenset({COMPLETED, SKIPPED, POSTPONED})
"""The statuses in which a revision is not offered as due again.

The mirror of the plan item's `SETTLED_STATUSES`, meaning the same thing:
something has already been said about this, so nothing should put it in front of
the learner again on its own. `due` and `scheduled` are outside it.
"""


@dataclass(frozen=True, slots=True)
class RevisionTopic:
    """The topic a revision recommends reviewing, named well enough to display."""

    id: uuid.UUID
    code: str | None
    name: str
    subject_id: uuid.UUID
    subject_name: str


@dataclass(frozen=True, slots=True)
class RevisionRecord:
    """One topic coming back for review, as stored.

    The persistence shape, used by the port. `RevisionDetail` below is what a
    caller reads.
    """

    id: uuid.UUID
    learner_id: uuid.UUID
    topic_id: uuid.UUID
    plan_item_id: uuid.UUID | None
    due_on: date
    scheduled_for: date | None
    status: str
    trigger_type: str
    recommendation_reason: str | None
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class RevisionDetail:
    """One revision as a learner reads it.

    `is_due` is reported rather than left to the client, because what counts as
    due is a domain rule (`select_due`) and a screen deriving it could disagree
    with the backend that owns it.

    `recommendation_reason` is the sentence written when the revision was
    created and never rewritten, so a record explains itself in the terms that
    produced its date — the guarantee a plan item's reason carries.
    """

    id: uuid.UUID
    topic: RevisionTopic | None
    due_on: date
    scheduled_for: date | None
    status: str
    trigger_type: str
    recommendation_reason: str | None
    completed_at: datetime | None
    is_due: bool


@dataclass(frozen=True, slots=True)
class RevisionPage:
    """One page of revisions, with the total the pagination block reports."""

    revisions: tuple[RevisionDetail, ...]
    total: int


@dataclass(frozen=True, slots=True)
class RevisionFilters:
    """What a caller may narrow a revision list by."""

    status: str | None = None
    due_only: bool = False


@dataclass(frozen=True, slots=True)
class RevisionStatusChange:
    """What REV-003 asks of one revision.

    Only a status. There is deliberately no date and no reason: naming a day is
    the unwritten `scheduled` capability, and asking why a learner skipped would
    invite the product to form a view about the answer — the judgement FR-005
    refuses and terminology names as wording to avoid.
    """

    status: str


@dataclass(frozen=True, slots=True)
class ScheduledRevisions:
    """What one scheduling run produced (REV-004).

    `created` names what was written. `already_scheduled_topic_count` says how
    many topics were passed over because they already have a revision waiting,
    which is what makes a run that writes nothing legible rather than mysterious.

    Both are **descriptions of the schedule, not measurements of the learner** —
    the line ADR-020 drew when it let a plan state "60 topics" while refusing to
    total a day or a week.
    """

    scheduled_on: date
    created: tuple[RevisionDetail, ...]
    already_scheduled_topic_count: int = 0
    reason: str = ""
