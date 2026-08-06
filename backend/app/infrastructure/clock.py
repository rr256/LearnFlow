"""The system clock, as an adapter behind the `Clock` port.

It sits in `infrastructure/` rather than in a subfolder because the operating
system's clock is not persistence, an AI or storage provider, or RAG. The
folder-creation rule in docs/development/folder-structure.md says a folder is
created when its first file needs one, and a single four-line adapter does not
need one of its own.

It is an adapter at all because reading the clock is exactly the kind of ambient
dependency that makes a use case untestable: every date in a generated plan
derives from "now", so the application asks a port and the composition root
decides what answers.
"""

from datetime import UTC, datetime


class SystemClock:
    """Reports the current instant from the operating system."""

    def now(self) -> datetime:
        """The current instant, timezone-aware and in UTC.

        UTC rather than local time, so the process's own timezone never reaches a
        learner's dates. A caller wanting a calendar date converts this into the
        learner's stored zone.
        """
        return datetime.now(UTC)
