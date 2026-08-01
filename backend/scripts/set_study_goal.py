"""Set the local learner's curriculum and examination goal. Safe to run repeatedly.

Run from ``backend/`` so the ``app`` package resolves:

    python -m scripts.set_study_goal                        # GATE CSE, GATE 2027
    python -m scripts.set_study_goal --display-name "Asha"
    python -m scripts.set_study_goal --target-date 2027-02-06
    python -m scripts.set_study_goal --dry-run              # report, then roll back

Apply the migrations, load the curriculum, and load the examination schedule
first. This binds a goal to records those steps create.

It creates the local learner on first run and leaves an existing one untouched:
renaming a learner or moving their timezone is a profile change with its own
workflow, and doing it here would overwrite a deliberate edit with a
command-line default.

This module does the composition-root work: it is the only part that reads
configuration, opens a database, or decides which implementation fulfils the
repository port. The rules live in the use case it calls.
"""

import argparse
import sys
from datetime import date

from app.application.dto.study_goal import StudyGoalRequest, StudyGoalSummary
from app.application.use_cases.set_study_goal import SetStudyGoal, StudyGoalError
from app.composition.config import load_settings
from app.infrastructure.persistence.engine import create_database_engine, create_session_factory
from app.infrastructure.persistence.study_goal_repository import SqlAlchemyStudyGoalRepository

DEFAULT_PROGRAM_CODE = "gate-cse"
DEFAULT_EXAMINATION_CYCLE = "2027"
"""The cycle in ``scripts/gate_cse_examination_schedule.json``, the bundled schedule."""


def main(argv: list[str] | None = None) -> int:
    """Set the goal and report what changed.

    Returns:
        ``0`` when the goal is in place, ``1`` when it could not be set.
    """
    arguments = _parse_arguments(argv)

    settings = load_settings()
    engine = create_database_engine(str(settings.database_url))
    session_factory = create_session_factory(engine)

    request = StudyGoalRequest(
        program_code=arguments.program,
        learner_timezone=settings.app_default_timezone,
        examination_cycle_label=None if arguments.no_examination else arguments.examination_cycle,
        target_date=arguments.target_date,
        learner_display_name=arguments.display_name,
    )

    try:
        with session_factory() as session:
            use_case = SetStudyGoal(SqlAlchemyStudyGoalRepository(session))
            try:
                summary = use_case(request)
            except StudyGoalError as error:
                session.rollback()
                print(f"error: {error}", file=sys.stderr)
                return 1

            if arguments.dry_run:
                session.rollback()
            else:
                session.commit()
    finally:
        engine.dispose()

    _report(summary, dry_run=arguments.dry_run)
    return 0


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.set_study_goal",
        description="Set the local learner's curriculum and examination goal, idempotently.",
    )
    parser.add_argument(
        "--program",
        default=DEFAULT_PROGRAM_CODE,
        help=f"Learning program code to study (default: {DEFAULT_PROGRAM_CODE}).",
    )
    parser.add_argument(
        "--examination-cycle",
        default=DEFAULT_EXAMINATION_CYCLE,
        help=f"Published examination cycle to aim at (default: {DEFAULT_EXAMINATION_CYCLE}).",
    )
    parser.add_argument(
        "--no-examination",
        action="store_true",
        help="Aim at a target date only, with no examination cycle. Requires --target-date.",
    )
    parser.add_argument(
        "--target-date",
        type=_iso_date,
        default=None,
        help=(
            "Target completion date, YYYY-MM-DD. Optional alongside an examination "
            "cycle, required without one."
        ),
    )
    parser.add_argument(
        "--display-name",
        default=None,
        help="Name for the learner record, used only when this run creates it.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what the run would change, then roll back instead of committing.",
    )
    return parser.parse_args(argv)


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"{value!r} is not a valid YYYY-MM-DD date: {error}"
        ) from error


def _report(summary: StudyGoalSummary, *, dry_run: bool) -> None:
    print(f"Study goal {summary.study_goal_id} ({summary.study_goal_change})")
    print(f"  learner              {summary.learner_id} ({summary.learner_change})")
    print(f"  learning program     {summary.learning_program_code}")
    print(f"  curriculum version   {summary.curriculum_version_label}")
    print(f"  status               {summary.status}")

    examination = summary.examination
    if examination is None:
        print("  examination          none")
    else:
        window = _window(examination.window_starts_on, examination.window_ends_on)
        print(f"  examination          {examination.name} (cycle {examination.cycle_label})")
        print(f"  examination window   {window}")
        print(f"  source               {examination.source_reference}")
        print(f"  read on              {examination.source_checked_on.isoformat()}")

    if summary.target_date is not None:
        print(f"  target date          {summary.target_date.isoformat()}")

    if examination is not None and examination.dates_may_change:
        print(
            "These dates are liable to change until "
            f"{examination.organising_body or 'the organising body'} confirms them."
        )
    if not summary.changed:
        print("Already up to date; nothing was written.")
    elif dry_run:
        print("Dry run: the changes above were rolled back.")


def _window(starts_on: date | None, ends_on: date | None) -> str:
    if starts_on is None or ends_on is None:
        return "not published"
    return f"{starts_on.isoformat()} to {ends_on.isoformat()}"


if __name__ == "__main__":
    raise SystemExit(main())
