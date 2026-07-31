"""Load a curated curriculum into the database. Safe to run repeatedly.

Run from ``backend/`` so the ``app`` package resolves:

    python -m scripts.seed_curriculum                  # the bundled GATE CSE curriculum
    python -m scripts.seed_curriculum --file other.json
    python -m scripts.seed_curriculum --dry-run        # report, then roll back

The target database is ``DATABASE_URL``, read through the application's
validated settings, so the seed cannot reach a database the backend was never
configured for. Apply the migrations first: this writes rows, it does not create
tables (docs/database/migrations.md).

This module does the composition-root work for the seed: it is the only part
that reads configuration, opens a database, or decides which implementation
fulfils the repository port. The reconcile rules live in the use case it calls.
"""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.application.dto.curriculum_seed import CurriculumSeedResult, SeedOutcome
from app.application.use_cases.seed_curriculum import CurriculumSeedError, SeedCurriculum
from app.composition.config import load_settings
from app.infrastructure.persistence.curriculum_seed_repository import (
    SqlAlchemyCurriculumSeedRepository,
)
from app.infrastructure.persistence.engine import create_database_engine, create_session_factory
from scripts.curriculum_seed_file import (
    GATE_CSE_CURRICULUM_FILE,
    CurriculumSeedFileError,
    load_curriculum_seed,
)


def main(argv: list[str] | None = None) -> int:
    """Apply the seed and report what changed.

    Returns:
        ``0`` when the curriculum matches the seed file, ``1`` when the seed
        could not be applied.
    """
    arguments = _parse_arguments(argv)

    try:
        seed = load_curriculum_seed(arguments.file)
    except CurriculumSeedFileError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    settings = load_settings()
    engine = create_database_engine(str(settings.database_url))
    session_factory = create_session_factory(engine)

    try:
        with session_factory() as session:
            use_case = SeedCurriculum(
                SqlAlchemyCurriculumSeedRepository(session),
                clock=lambda: datetime.now(UTC),
            )
            try:
                result = use_case(seed)
            except CurriculumSeedError as error:
                session.rollback()
                print(f"error: {error}", file=sys.stderr)
                return 1

            if arguments.dry_run:
                session.rollback()
            else:
                session.commit()
    finally:
        engine.dispose()

    _report(seed.program_code, seed.version_label, result, dry_run=arguments.dry_run)
    return 0


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.seed_curriculum",
        description="Load a curated curriculum into the configured database, idempotently.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=GATE_CSE_CURRICULUM_FILE,
        help="Curriculum seed JSON file (default: the bundled GATE CSE curriculum).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what the run would change, then roll back instead of committing.",
    )
    return parser.parse_args(argv)


def _report(
    program_code: str,
    version_label: str,
    result: CurriculumSeedResult,
    *,
    dry_run: bool,
) -> None:
    print(f"Curriculum {program_code} {version_label}")
    rows = (
        ("learning program", result.learning_program),
        ("curriculum version", result.curriculum_version),
        ("subjects", result.subjects),
        ("topics", result.topics),
        ("topic relationships", result.topic_relationships),
    )
    for label, outcome in rows:
        print(f"  {label:<20} {_summarise(outcome)}")

    if not result.changed:
        print("Already up to date; nothing was written.")
    elif dry_run:
        print("Dry run: the changes above were rolled back.")


def _summarise(outcome: SeedOutcome) -> str:
    return f"created {outcome.created}, updated {outcome.updated}, unchanged {outcome.unchanged}"


if __name__ == "__main__":
    raise SystemExit(main())
