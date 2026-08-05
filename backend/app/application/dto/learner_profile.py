"""Input and output structures for reading and updating the learner's profile.

The profile is the learner's own identity and local preferences: a display name
they chose, and the timezone their study dates are interpreted in. It carries no
credentials, because LearnFlow has no authentication (ADR-015), and no learner
identifier is ever accepted from a client -- the effective learner is resolved
server-side, per docs/api/conventions.md.

`LearnerProfileChanges` describes a *partial* update. A field left unset is not
touched, which is why removing a display name needs `clear_display_name` rather
than a `None`: nullable alone cannot distinguish "leave it alone" from "remove
it", and silently doing one when the caller meant the other loses data the
learner typed.
"""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LearnerProfile:
    """The stored learner and their local preferences."""

    id: uuid.UUID
    display_name: str | None
    timezone: str


@dataclass(frozen=True, slots=True)
class LearnerProfileChanges:
    """The fields a profile update asks to change.

    Attributes:
        display_name: A new name, or ``None`` to leave the stored one alone.
        timezone: A new IANA timezone, or ``None`` to leave the stored one
            alone. Its format is validated at the API boundary; nothing here
            re-checks it.
        clear_display_name: Remove the stored display name. Takes precedence
            over ``display_name`` only in the sense that the two are never sent
            together; the API boundary rejects that combination.
    """

    display_name: str | None = None
    timezone: str | None = None
    clear_display_name: bool = False

    @property
    def is_empty(self) -> bool:
        """Whether the update asks for nothing at all."""
        return self.display_name is None and self.timezone is None and not self.clear_display_name
