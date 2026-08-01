"""Input and output structures for seeding a published examination schedule.

An examination schedule is the dated calendar a learning program's examining body
publishes for one cycle -- for GATE CSE, one GATE year. It is reference data with
provenance, like the curriculum: it describes the world rather than the learner,
and every learner planning against that cycle sees the same dates.

The examination itself is modelled as one or more dated *periods*, never as a
single day. An examining body commonly publishes a range of sitting days and
announces the specific paper's day much later; recording one guessed date would
present that guess as fact. A period with the same start and end day is a
single-day event, which is how a results announcement is stored.

`schedule_status` carries the honesty that matters most here: a published
schedule stays `provisional` while its source says the dates are liable to
change, and becomes `confirmed` only when the examining body confirms them.
"""

from dataclasses import dataclass, field
from datetime import date

from app.application.dto.seed_outcome import SeedOutcome

EXAMINATION_SCHEDULE_STATUSES: tuple[str, ...] = ("provisional", "confirmed")
"""Statuses `examination_schedules.schedule_status` accepts.

`provisional` means the source states the dates may still change. It is the
honest default for a schedule published ahead of the examination.
"""

EXAMINATION_PERIOD_TYPES: tuple[str, ...] = (
    "registration",
    "late_registration",
    "examination",
    "results",
)
"""Period types `examination_periods.period_type` accepts."""

EXAMINATION_PERIOD_TYPE: str = "examination"
"""The period type that defines the examination window itself.

The other types are the deadlines around it. Only these periods answer "when is
the examination", so the window a study goal plans toward is derived from them
alone.
"""


@dataclass(frozen=True, slots=True)
class ExaminationPeriodSeed:
    """One dated period of a schedule, from a single day to a range of days."""

    period_type: str
    starts_on: date
    ends_on: date


@dataclass(frozen=True, slots=True)
class ExaminationScheduleSeed:
    """A complete published schedule for one examination cycle."""

    program_code: str
    cycle_label: str
    name: str
    source_reference: str
    source_checked_on: date
    schedule_status: str
    organising_body: str | None = None
    periods: tuple[ExaminationPeriodSeed, ...] = ()


@dataclass(frozen=True, slots=True)
class ExaminationScheduleSeedResult:
    """What applying a schedule seed did, one outcome per kind of record."""

    examination_schedule: SeedOutcome = field(default_factory=SeedOutcome)
    examination_periods: SeedOutcome = field(default_factory=SeedOutcome)

    @property
    def changed(self) -> bool:
        """Whether the run wrote anything at all."""
        return self.examination_schedule.changed or self.examination_periods.changed
