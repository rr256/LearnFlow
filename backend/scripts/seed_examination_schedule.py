"""Load a published examination schedule into the database. Safe to run repeatedly.

Run from ``backend/`` so the ``app`` package resolves:

    python -m scripts.seed_examination_schedule                  # bundled GATE 2027
    python -m scripts.seed_examination_schedule --file other.json
    python -m scripts.seed_examination_schedule --dry-run        # report, then roll back

Apply the migrations and load the curriculum first: a schedule belongs to a
learning program the curriculum seed creates, and this writes rows rather than
creating tables (docs/database/migrations.md).

This module does the composition-root work for the seed: it is the only part
that reads configuration, opens a database, or decides which implementation
fulfils the repository port. The reconcile rules live in the use case it calls.
"""

import argparse
import sys
from pathlib import Path

from app.application.dto.examination_schedule_seed import (
    ExaminationScheduleSeed,
    ExaminationScheduleSeedResult,
)
from app.application.dto.seed_outcome import SeedOutcome
from app.application.use_cases.seed_examination_schedule import (
    ExaminationScheduleSeedError,
    SeedExaminationSchedule,
)
from app.composition.config import load_settings
from app.infrastructure.persistence.engine import create_database_engine, create_session_factory
from app.infrastructure.persistence.examination_schedule_seed_repository import (
    SqlAlchemyExaminationScheduleSeedRepository,
)
from scripts.examination_schedule_file import (
    GATE_CSE_EXAMINATION_SCHEDULE_FILE,
    ExaminationScheduleFileError,
    load_examination_schedule,
)


def main(argv: list[str] | None = None) -> int:
    """Apply the schedule and report what changed.

    Returns:
        ``0`` when the stored schedule matches the file, ``1`` when it could not
        be applied.
    """
    arguments = _parse_arguments(argv)

    try:
        seed = load_examination_schedule(arguments.file)
    except ExaminationScheduleFileError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    settings = load_settings()
    engine = create_database_engine(str(settings.database_url))
    session_factory = create_session_factory(engine)

    try:
        with session_factory() as session:
            use_case = SeedExaminationSchedule(SqlAlchemyExaminationScheduleSeedRepository(session))
            try:
                result = use_case(seed)
            except ExaminationScheduleSeedError as error:
                session.rollback()
                print(f"error: {error}", file=sys.stderr)
                return 1

            if arguments.dry_run:
                session.rollback()
            else:
                session.commit()
    finally:
        engine.dispose()

    _report(seed, result, dry_run=arguments.dry_run)
    return 0


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.seed_examination_schedule",
        description=(
            "Load a published examination schedule into the configured database, idempotently."
        ),
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=GATE_CSE_EXAMINATION_SCHEDULE_FILE,
        help="Examination schedule JSON file (default: the bundled GATE 2027 schedule).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what the run would change, then roll back instead of committing.",
    )
    return parser.parse_args(argv)


def _report(
    seed: ExaminationScheduleSeed,
    result: ExaminationScheduleSeedResult,
    *,
    dry_run: bool,
) -> None:
    print(f"Examination schedule {seed.program_code} {seed.cycle_label} ({seed.name})")
    print(f"  source               {seed.source_reference}")
    print(f"  read on              {seed.source_checked_on.isoformat()}")
    print(f"  status               {seed.schedule_status}")
    rows = (
        ("examination schedule", result.examination_schedule),
        ("examination periods", result.examination_periods),
    )
    for label, outcome in rows:
        print(f"  {label:<20} {_summarise(outcome)}")

    if seed.schedule_status == "provisional":
        print("These dates are liable to change until the organising body confirms them.")
    if not result.changed:
        print("Already up to date; nothing was written.")
    elif dry_run:
        print("Dry run: the changes above were rolled back.")


def _summarise(outcome: SeedOutcome) -> str:
    return f"created {outcome.created}, updated {outcome.updated}, unchanged {outcome.unchanged}"


if __name__ == "__main__":
    raise SystemExit(main())
