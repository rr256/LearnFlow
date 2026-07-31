"""Read a published examination schedule from a JSON file into application DTOs.

The file format is the seed's authoring surface, so every failure here names the
field that is wrong rather than raising a bare `KeyError` three frames deep. A
key beginning with ``$`` is ignored, which is what lets the data file carry its
own ``$comment`` block recording the source, the transcription rules, and the
one inference it makes.

Unlike the curriculum file, order carries no meaning: a period is identified by
its type and its start date, and the seed reads them in whatever order the file
lists them.
"""

import json
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from app.application.dto.examination_schedule_seed import (
    ExaminationPeriodSeed,
    ExaminationScheduleSeed,
)

GATE_CSE_EXAMINATION_SCHEDULE_FILE = (
    Path(__file__).resolve().parent / "gate_cse_examination_schedule.json"
)
"""The published GATE 2027 schedule shipped with the repository."""


class ExaminationScheduleFileError(Exception):
    """The schedule file is missing, malformed, or has a field of the wrong type."""


def load_examination_schedule(path: Path) -> ExaminationScheduleSeed:
    """Read and convert the schedule file at `path`.

    Raises:
        ExaminationScheduleFileError: The file is unreadable, is not valid JSON,
            or does not match the documented shape.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ExaminationScheduleFileError(
            f"Cannot read examination schedule file {path}: {error}"
        ) from error

    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise ExaminationScheduleFileError(f"{path} is not valid JSON: {error}") from error

    if not isinstance(document, dict):
        raise ExaminationScheduleFileError(f"{path} must contain a JSON object at the top level.")

    return build_examination_schedule(document)


def build_examination_schedule(document: Mapping[str, Any]) -> ExaminationScheduleSeed:
    """Convert an already-parsed schedule document into an `ExaminationScheduleSeed`."""
    return ExaminationScheduleSeed(
        program_code=_text(document, "program_code"),
        cycle_label=_text(document, "cycle_label"),
        name=_text(document, "name"),
        organising_body=_optional_text(document, "organising_body"),
        source_reference=_text(document, "source_reference"),
        source_checked_on=_date(document, "source_checked_on"),
        schedule_status=_text(document, "schedule_status"),
        periods=tuple(
            _period(entry, f"periods[{index}]") for index, entry in enumerate(_periods(document))
        ),
    )


def _periods(document: Mapping[str, Any]) -> Sequence[Any]:
    value = document.get("periods")
    if value is None:
        raise ExaminationScheduleFileError("periods is required.")
    if not isinstance(value, list):
        raise ExaminationScheduleFileError("periods must be a JSON array.")
    return value


def _period(entry: object, where: str) -> ExaminationPeriodSeed:
    if not isinstance(entry, dict):
        raise ExaminationScheduleFileError(f"{where} must be a JSON object.")
    return ExaminationPeriodSeed(
        period_type=_text(entry, "period_type", where),
        starts_on=_date(entry, "starts_on", where),
        ends_on=_date(entry, "ends_on", where),
    )


def _text(mapping: Mapping[str, Any], key: str, where: str = "") -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ExaminationScheduleFileError(f"{_at(where, key)} must be a non-empty string.")
    return value


def _optional_text(mapping: Mapping[str, Any], key: str, where: str = "") -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ExaminationScheduleFileError(
            f"{_at(where, key)} must be a non-empty string when present."
        )
    return value


def _date(mapping: Mapping[str, Any], key: str, where: str = "") -> date:
    """Read a date-only value.

    ISO 8601 ``YYYY-MM-DD``, matching the API convention for date-only values.
    A timestamp is rejected rather than truncated: which day a moment falls on
    depends on the timezone reading it, and a published calendar date has none.
    """
    value = mapping.get(key)
    if not isinstance(value, str):
        raise ExaminationScheduleFileError(f"{_at(where, key)} must be a YYYY-MM-DD string.")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ExaminationScheduleFileError(
            f"{_at(where, key)} is not a valid YYYY-MM-DD date: {error}"
        ) from error


def _at(where: str, key: str) -> str:
    return f"{where}.{key}" if where else key
