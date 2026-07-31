"""Read a curated curriculum from a JSON file into application DTOs.

The file format is the seed's authoring surface, so every failure here names the
field that is wrong rather than raising a bare `KeyError` three frames deep. A
key beginning with ``$`` is ignored, which is what lets the data file carry its
own ``$comment`` block recording the source and the transcription rules.

Ordering in the file is meaningful: subjects and topics take their `position`
from their index, so moving an entry moves it in the curriculum.
"""

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from app.application.dto.curriculum_seed import (
    CurriculumSeed,
    SubjectSeed,
    TopicPath,
    TopicRelationshipSeed,
    TopicSeed,
)

GATE_CSE_CURRICULUM_FILE = Path(__file__).resolve().parent / "gate_cse_curriculum.json"
"""The curated GATE CSE curriculum shipped with the repository."""


class CurriculumSeedFileError(Exception):
    """The seed file is missing, malformed, or has a field of the wrong type."""


def load_curriculum_seed(path: Path) -> CurriculumSeed:
    """Read and convert the seed file at `path`.

    Raises:
        CurriculumSeedFileError: The file is unreadable, is not valid JSON, or
            does not match the documented shape.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise CurriculumSeedFileError(
            f"Cannot read curriculum seed file {path}: {error}"
        ) from error

    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise CurriculumSeedFileError(f"{path} is not valid JSON: {error}") from error

    if not isinstance(document, dict):
        raise CurriculumSeedFileError(f"{path} must contain a JSON object at the top level.")

    return build_curriculum_seed(document)


def build_curriculum_seed(document: Mapping[str, Any]) -> CurriculumSeed:
    """Convert an already-parsed seed document into a `CurriculumSeed`."""
    return CurriculumSeed(
        program_code=_text(document, "program_code"),
        program_name=_text(document, "program_name"),
        program_description=_optional_text(document, "program_description"),
        version_label=_text(document, "version_label"),
        version_status=_text(document, "version_status"),
        source_reference=_optional_text(document, "source_reference"),
        published_at=_optional_timestamp(document, "published_at"),
        subjects=tuple(
            _subject(entry, f"subjects[{index}]")
            for index, entry in enumerate(_sequence(document, "subjects", required=True))
        ),
        topic_relationships=tuple(
            _relationship(entry, f"topic_relationships[{index}]")
            for index, entry in enumerate(_sequence(document, "topic_relationships"))
        ),
    )


def _subject(entry: object, where: str) -> SubjectSeed:
    mapping = _mapping(entry, where)
    return SubjectSeed(
        code=_text(mapping, "code", where),
        name=_text(mapping, "name", where),
        description=_optional_text(mapping, "description", where),
        topics=_topics(mapping, where),
    )


def _topics(mapping: Mapping[str, Any], where: str) -> tuple[TopicSeed, ...]:
    return tuple(
        _topic(entry, f"{where}.topics[{index}]")
        for index, entry in enumerate(_sequence(mapping, "topics", where=where))
    )


def _topic(entry: object, where: str) -> TopicSeed:
    mapping = _mapping(entry, where)
    trackable = mapping.get("is_trackable", True)
    if not isinstance(trackable, bool):
        raise CurriculumSeedFileError(f"{where}.is_trackable must be true or false.")
    return TopicSeed(
        name=_text(mapping, "name", where),
        code=_optional_text(mapping, "code", where),
        description=_optional_text(mapping, "description", where),
        is_trackable=trackable,
        topics=_topics(mapping, where),
    )


def _relationship(entry: object, where: str) -> TopicRelationshipSeed:
    mapping = _mapping(entry, where)
    return TopicRelationshipSeed(
        source=_topic_path(mapping.get("source"), f"{where}.source"),
        target=_topic_path(mapping.get("target"), f"{where}.target"),
        relationship_type=_text(mapping, "relationship_type", where),
    )


def _topic_path(entry: object, where: str) -> TopicPath:
    mapping = _mapping(entry, where)
    names = _sequence(mapping, "names", where=where, required=True)
    if not names:
        raise CurriculumSeedFileError(f"{where}.names must name at least one topic.")
    for index, name in enumerate(names):
        if not isinstance(name, str) or not name:
            raise CurriculumSeedFileError(f"{where}.names[{index}] must be a non-empty string.")
    return TopicPath(
        subject_code=_text(mapping, "subject_code", where),
        names=tuple(names),
    )


def _mapping(entry: object, where: str) -> Mapping[str, Any]:
    if not isinstance(entry, dict):
        raise CurriculumSeedFileError(f"{where} must be a JSON object.")
    return entry


def _sequence(
    mapping: Mapping[str, Any],
    key: str,
    *,
    where: str = "",
    required: bool = False,
) -> Sequence[Any]:
    value = mapping.get(key)
    if value is None:
        if required:
            raise CurriculumSeedFileError(f"{_at(where, key)} is required.")
        return ()
    if not isinstance(value, list):
        raise CurriculumSeedFileError(f"{_at(where, key)} must be a JSON array.")
    return value


def _text(mapping: Mapping[str, Any], key: str, where: str = "") -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise CurriculumSeedFileError(f"{_at(where, key)} must be a non-empty string.")
    return value


def _optional_text(mapping: Mapping[str, Any], key: str, where: str = "") -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise CurriculumSeedFileError(f"{_at(where, key)} must be a non-empty string when present.")
    return value


def _optional_timestamp(mapping: Mapping[str, Any], key: str, where: str = "") -> datetime | None:
    value = mapping.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise CurriculumSeedFileError(f"{_at(where, key)} must be an ISO 8601 string when present.")
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as error:
        raise CurriculumSeedFileError(
            f"{_at(where, key)} is not a valid ISO 8601 timestamp: {error}"
        ) from error
    if moment.tzinfo is None:
        # Every timestamp column is `timestamptz`; a naive value would be stored
        # as though it were in whatever timezone the writer happened to use.
        raise CurriculumSeedFileError(
            f"{_at(where, key)} must state a UTC offset, for example 2026-02-01T00:00:00+00:00."
        )
    return moment


def _at(where: str, key: str) -> str:
    return f"{where}.{key}" if where else key
