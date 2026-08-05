"""The examination window a study goal aims at.

The window spans the first published sitting day to the last. It is derived from
the stored periods on every read rather than held in a column, so a schedule the
examining body corrects reaches every goal pointing at it without a learner-data
migration (ADR-013).

The rule lives here, above the repository and below the routes, because two
workflows need exactly the same answer: the `scripts.set_study_goal` command and
the study-goal endpoints. Duplicating it would let the command and the API
disagree about when the examination is.
"""

from collections.abc import Iterable
from datetime import date

from app.application.dto.examination_schedule_seed import EXAMINATION_PERIOD_TYPE
from app.application.ports.examination_schedule_repository import ExaminationPeriodRecord


def derive_examination_window(
    periods: Iterable[ExaminationPeriodRecord],
) -> tuple[date | None, date | None]:
    """The first and last day the examination is sat.

    Registration and results periods are excluded: they bracket the examination
    rather than being it, and including them would widen the window a plan is
    built against by months.

    Returns:
        ``(starts_on, ends_on)``, or ``(None, None)`` when a stored schedule
        holds no examination period. The seed refuses to create that shape, but a
        hand-edited database could hold it, and reporting no window is honest
        where inventing one is not.
    """
    sittings = [period for period in periods if period.period_type == EXAMINATION_PERIOD_TYPE]
    if not sittings:
        return None, None
    return (
        min(period.starts_on for period in sittings),
        max(period.ends_on for period in sittings),
    )
