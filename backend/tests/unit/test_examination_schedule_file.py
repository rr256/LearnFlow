"""Reading an examination schedule file, including the bundled GATE 2027 one.

The file is the authoring surface for published dates, so a malformed entry must
name the field at fault rather than surfacing three frames deep. The bundled file
is also asserted against the dates its `$comment` block cites, so a careless edit
to either fails here.
"""

from datetime import date

import pytest

from scripts.examination_schedule_file import (
    GATE_CSE_EXAMINATION_SCHEDULE_FILE,
    ExaminationScheduleFileError,
    build_examination_schedule,
    load_examination_schedule,
)

VALID_DOCUMENT = {
    "$comment": ["ignored"],
    "program_code": "gate-cse",
    "cycle_label": "2027",
    "name": "GATE 2027",
    "organising_body": "IIT Madras",
    "source_reference": "https://gate2027.iitm.ac.in/",
    "source_checked_on": "2026-08-01",
    "schedule_status": "provisional",
    "periods": [
        {"period_type": "examination", "starts_on": "2027-02-06", "ends_on": "2027-02-07"},
    ],
}


def document(**overrides) -> dict:
    return {**VALID_DOCUMENT, **overrides}


def test_a_valid_document_becomes_a_seed():
    seed = build_examination_schedule(VALID_DOCUMENT)

    assert seed.program_code == "gate-cse"
    assert seed.cycle_label == "2027"
    assert seed.source_checked_on == date(2026, 8, 1)
    assert seed.periods[0].starts_on == date(2027, 2, 6)


def test_a_comment_key_is_ignored():
    """It is how the data file records its source and transcription rules."""
    seed = build_examination_schedule(VALID_DOCUMENT)

    assert seed.name == "GATE 2027"


def test_an_absent_organising_body_is_allowed():
    seed = build_examination_schedule(document(organising_body=None))

    assert seed.organising_body is None


@pytest.mark.parametrize(
    "field", ["program_code", "cycle_label", "name", "source_reference", "schedule_status"]
)
def test_a_missing_required_string_names_the_field(field):
    with pytest.raises(ExaminationScheduleFileError) as excinfo:
        build_examination_schedule(document(**{field: None}))

    assert field in str(excinfo.value)


def test_an_empty_string_is_rejected_like_a_missing_one():
    with pytest.raises(ExaminationScheduleFileError):
        build_examination_schedule(document(name=""))


def test_missing_periods_are_reported():
    with pytest.raises(ExaminationScheduleFileError) as excinfo:
        build_examination_schedule(document(periods=None))

    assert "periods" in str(excinfo.value)


def test_periods_must_be_an_array():
    with pytest.raises(ExaminationScheduleFileError) as excinfo:
        build_examination_schedule(document(periods={"period_type": "examination"}))

    assert "array" in str(excinfo.value)


def test_a_period_must_be_an_object():
    with pytest.raises(ExaminationScheduleFileError) as excinfo:
        build_examination_schedule(document(periods=["2027-02-06"]))

    assert "periods[0]" in str(excinfo.value)


def test_a_malformed_date_names_the_period_and_the_field():
    with pytest.raises(ExaminationScheduleFileError) as excinfo:
        build_examination_schedule(
            document(
                periods=[
                    {
                        "period_type": "examination",
                        "starts_on": "06-02-2027",
                        "ends_on": "2027-02-07",
                    }
                ]
            )
        )

    assert "periods[0].starts_on" in str(excinfo.value)


def test_a_timestamp_is_rejected_rather_than_truncated():
    """Which day a moment falls on depends on the zone reading it; a published
    calendar date has none."""
    with pytest.raises(ExaminationScheduleFileError):
        build_examination_schedule(document(source_checked_on="2026-08-01T00:00:00+00:00"))


def test_a_missing_file_is_reported_with_its_path(tmp_path):
    missing = tmp_path / "absent.json"

    with pytest.raises(ExaminationScheduleFileError) as excinfo:
        load_examination_schedule(missing)

    assert "absent.json" in str(excinfo.value)


def test_invalid_json_is_reported(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")

    with pytest.raises(ExaminationScheduleFileError) as excinfo:
        load_examination_schedule(broken)

    assert "not valid JSON" in str(excinfo.value)


def test_a_top_level_array_is_rejected(tmp_path):
    listed = tmp_path / "listed.json"
    listed.write_text("[]", encoding="utf-8")

    with pytest.raises(ExaminationScheduleFileError) as excinfo:
        load_examination_schedule(listed)

    assert "JSON object" in str(excinfo.value)


def test_the_bundled_schedule_names_the_official_source():
    seed = load_examination_schedule(GATE_CSE_EXAMINATION_SCHEDULE_FILE)

    assert seed.program_code == "gate-cse"
    assert seed.cycle_label == "2027"
    assert seed.organising_body == "IIT Madras"
    assert seed.source_reference == "https://gate2027.iitm.ac.in/"


def test_the_bundled_schedule_is_provisional():
    """Its source states the dates are liable to change, and it must say so."""
    seed = load_examination_schedule(GATE_CSE_EXAMINATION_SCHEDULE_FILE)

    assert seed.schedule_status == "provisional"


def test_the_bundled_schedule_records_every_published_date():
    seed = load_examination_schedule(GATE_CSE_EXAMINATION_SCHEDULE_FILE)

    published = sorted(
        (period.period_type, period.starts_on, period.ends_on) for period in seed.periods
    )

    assert published == [
        ("examination", date(2027, 2, 6), date(2027, 2, 7)),
        ("examination", date(2027, 2, 13), date(2027, 2, 14)),
        ("examination", date(2027, 2, 20), date(2027, 2, 21)),
        ("late_registration", date(2026, 9, 22), date(2026, 9, 30)),
        ("registration", date(2026, 8, 14), date(2026, 9, 21)),
        ("results", date(2027, 3, 19), date(2027, 3, 19)),
    ]


def test_the_bundled_schedule_names_no_single_examination_day():
    """The Computer Science paper's day is not published; three weekends are."""
    seed = load_examination_schedule(GATE_CSE_EXAMINATION_SCHEDULE_FILE)

    sittings = [period for period in seed.periods if period.period_type == "examination"]

    assert len(sittings) == 3
    assert all(period.ends_on > period.starts_on for period in sittings)
