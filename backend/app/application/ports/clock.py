"""The port an application use case reads the current time through.

Reading the clock directly would make a use case untestable in the one way that
matters here: a plan is built around "today", so a test that cannot choose today
can only assert that the code agrees with itself. Every date in a generated plan
— the roadmap's start, the week's seven days, the days left before the
examination — comes from this port, so a test fixes one instant and asserts exact
dates.

It is a port rather than a passed-in date because the value is read once per
generation and belongs to the use case's own reasoning, not to its caller's. The
composition root chooses the implementation, as it does for every other port
(docs/architecture/dependency-rules.md).
"""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Reports the current instant."""

    def now(self) -> datetime:
        """The current instant, timezone-aware and in UTC.

        Aware rather than naive, and UTC rather than local, for the reason
        `learners.timezone` exists: a naive timestamp is wrong by a day at the
        boundary, and the boundary is exactly where a study plan's dates land. A
        caller wanting a calendar date converts this into the learner's own zone
        rather than assuming the process's.
        """
        ...
