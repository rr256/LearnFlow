"""Input and output structures for recording a learner's topic progress.

These carry what PRG-002 and PRG-004 read and write. They are
framework-independent by design: the API schemas that serialise them are a
separate representation, so a change to the HTTP contract does not reach back
into the use case.

Unlike the curriculum DTOs, everything here is learner-owned and carries a
`learner_id`.

A stage is reported with the topic it belongs to, because an identifier alone
tells a learner nothing. `subject_id` and `curriculum_version_id` travel with it
so a client can place the record in the hierarchy it is already showing without
a second lookup.
"""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TopicProgressRecord:
    """One learner's recorded stage for one topic, as stored.

    `stage_source` says whether the learner chose this stage themselves or it
    was derived from evidence. Every record written today says `learner`;
    nothing derives a stage yet.
    """

    id: uuid.UUID
    learner_id: uuid.UUID
    topic_id: uuid.UUID
    learning_stage: str
    stage_source: str


@dataclass(frozen=True, slots=True)
class TopicProgressTopic:
    """The topic a progress record belongs to, named well enough to display.

    `is_trackable` is reported rather than assumed. A record can only exist for
    a trackable topic, but a topic can in principle stop being trackable when a
    curriculum is re-seeded, and a client that has to guess would show a stage
    against a heading that no longer accepts one.
    """

    id: uuid.UUID
    code: str | None
    name: str
    is_trackable: bool
    subject_id: uuid.UUID
    curriculum_version_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class TopicProgressDetail:
    """A recorded stage together with the topic it describes.

    No timestamp is reported. `learner_topic_progress` carries `created_at` and
    `updated_at` as every durable table does, but nothing in this flow reads
    them, and adding an optional response field later is compatible under
    docs/api/versioning.md.
    """

    id: uuid.UUID
    learner_id: uuid.UUID
    learning_stage: str
    stage_source: str
    topic: TopicProgressTopic


@dataclass(frozen=True, slots=True)
class TopicProgressPage:
    """One requested window over the learner's stored progress records.

    `total` counts every record matching the filter, not the window, so a client
    can tell a complete list from a truncated one.
    """

    records: tuple[TopicProgressDetail, ...]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class TopicStageChange:
    """A learner's request to record a stage against one topic.

    There is deliberately no way to express "clear this". A learner who has
    changed their mind sets `not_explored`, which stores a record saying they
    did so on purpose -- distinguishable from a topic never touched, and not a
    deletion of learner-owned data through a field update.
    """

    learning_stage: str
