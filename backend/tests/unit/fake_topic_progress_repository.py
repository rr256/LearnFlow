"""An in-memory stand-in for the topic-progress repository port.

Progress records are held in insertion order so a page reads back newest first,
the way the SQLAlchemy adapter orders them. Topics are held separately, because
they are curriculum reference data this port only reads.
"""

import uuid
from collections.abc import Sequence

from app.application.dto.topic_progress import TopicProgressRecord, TopicProgressTopic


class FakeTopicProgressRepository:
    """Stores progress records in a list and topics in a dictionary."""

    def __init__(
        self,
        topics: tuple[TopicProgressTopic, ...] = (),
        records: tuple[TopicProgressRecord, ...] = (),
    ) -> None:
        self.topics: dict[uuid.UUID, TopicProgressTopic] = {topic.id: topic for topic in topics}
        self.records: list[TopicProgressRecord] = list(records)

    def find_topic(self, topic_id: uuid.UUID) -> TopicProgressTopic | None:
        return self.topics.get(topic_id)

    def list_topics(self, topic_ids: Sequence[uuid.UUID]) -> tuple[TopicProgressTopic, ...]:
        return tuple(self.topics[topic_id] for topic_id in topic_ids if topic_id in self.topics)

    def count_topic_progress(
        self, *, learner_id: uuid.UUID, curriculum_version_id: uuid.UUID | None
    ) -> int:
        return len(self._matching(learner_id, curriculum_version_id))

    def list_topic_progress(
        self,
        *,
        learner_id: uuid.UUID,
        curriculum_version_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[TopicProgressRecord, ...]:
        matching = list(reversed(self._matching(learner_id, curriculum_version_id)))
        return tuple(matching[offset : offset + limit])

    def list_recorded_stages(
        self, *, learner_id: uuid.UUID, curriculum_version_id: uuid.UUID
    ) -> tuple[TopicProgressRecord, ...]:
        return tuple(self._matching(learner_id, curriculum_version_id))

    def find_topic_progress(
        self, *, learner_id: uuid.UUID, topic_id: uuid.UUID
    ) -> TopicProgressRecord | None:
        for record in self.records:
            if record.learner_id == learner_id and record.topic_id == topic_id:
                return record
        return None

    def add_topic_progress(self, record: TopicProgressRecord) -> None:
        self.records.append(record)

    def update_topic_progress(self, record: TopicProgressRecord) -> None:
        for index, stored in enumerate(self.records):
            if stored.id == record.id:
                self.records[index] = record
                return
        raise AssertionError(f"topic progress {record.id} is not stored")

    def _matching(
        self, learner_id: uuid.UUID, curriculum_version_id: uuid.UUID | None
    ) -> list[TopicProgressRecord]:
        matching = [record for record in self.records if record.learner_id == learner_id]
        if curriculum_version_id is None:
            return matching
        return [
            record
            for record in matching
            if record.topic_id in self.topics
            and self.topics[record.topic_id].curriculum_version_id == curriculum_version_id
        ]


def topic(
    *,
    name: str = "CPU scheduling",
    code: str | None = None,
    is_trackable: bool = True,
    subject_id: uuid.UUID | None = None,
    curriculum_version_id: uuid.UUID | None = None,
) -> TopicProgressTopic:
    """A stored topic, for a test that does not care about the identifiers."""
    return TopicProgressTopic(
        id=uuid.uuid4(),
        code=code,
        name=name,
        is_trackable=is_trackable,
        subject_id=subject_id or uuid.uuid4(),
        curriculum_version_id=curriculum_version_id or uuid.uuid4(),
    )


def progress(
    *,
    learner_id: uuid.UUID,
    topic_id: uuid.UUID,
    learning_stage: str = "building_foundation",
    stage_source: str = "learner",
) -> TopicProgressRecord:
    """A stored progress record."""
    return TopicProgressRecord(
        id=uuid.uuid4(),
        learner_id=learner_id,
        topic_id=topic_id,
        learning_stage=learning_stage,
        stage_source=stage_source,
    )
