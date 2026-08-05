"""Read and update the local learner's profile (LRN-001, LRN-002).

The profile is the first thing onboarding touches and the smallest learner-owned
write in LearnFlow: a display name the learner chose, and the timezone their
study dates are interpreted in.

Three rules shape it.

**A read never writes.** LRN-001 reports that no learner exists yet rather than
creating one, so a page load cannot leave a record behind. Creating the learner
is what LRN-002 does, deliberately and on the learner's action.

**The timezone has no invented default.** A learner record needs one -- a
timestamp read in the wrong zone is wrong by a day at the boundary, which is
exactly where a study plan's dates land -- so the composition root supplies
`APP_DEFAULT_TIMEZONE` for the record this use case creates. Application code
must never read configuration itself, so the value arrives as an argument.

**An update leaves unmentioned fields alone.** A partial update that silently
reset the timezone because a form did not include it would move every future
plan by hours.
"""

import uuid

from app.application.dto.learner_profile import LearnerProfile, LearnerProfileChanges
from app.application.ports.learner_repository import LearnerRepository
from app.application.ports.study_goal_repository import LearnerRecord
from app.application.use_cases.local_learner import resolve_local_learner


class LearnerProfileError(Exception):
    """The learner profile could not be read or updated as asked."""


class EmptyProfileUpdateError(LearnerProfileError):
    """The update names no field to change."""


class ManageLearnerProfile:
    """Serves the learner profile endpoints through a `LearnerRepository`."""

    def __init__(self, repository: LearnerRepository, *, default_timezone: str) -> None:
        """Wire the use case.

        Args:
            repository: Where the learner is read and written.
            default_timezone: IANA zone stored on a learner record this use case
                creates, when the request names none. Supplied by the
                composition root, the only layer permitted to read
                configuration.
        """
        self._repository = repository
        self._default_timezone = default_timezone

    def read(self) -> LearnerProfile | None:
        """The local learner's profile, or None when none is stored yet.

        Raises:
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        learner = resolve_local_learner(self._repository)
        return None if learner is None else _profile(learner)

    def update(self, changes: LearnerProfileChanges) -> LearnerProfile:
        """Apply `changes`, creating the local learner if none exists yet.

        The caller owns the transaction: this method writes through the
        repository but never commits.

        Raises:
            EmptyProfileUpdateError: The update names no field to change.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        if changes.is_empty:
            raise EmptyProfileUpdateError(
                "A profile update must name at least one field to change."
            )

        existing = resolve_local_learner(self._repository)
        if existing is None:
            created = LearnerRecord(
                id=uuid.uuid4(),
                display_name=None if changes.clear_display_name else changes.display_name,
                timezone=changes.timezone or self._default_timezone,
            )
            self._repository.add_learner(created)
            return _profile(created)

        updated = LearnerRecord(
            id=existing.id,
            display_name=_new_display_name(existing.display_name, changes),
            timezone=changes.timezone or existing.timezone,
        )
        if updated != existing:
            self._repository.update_learner(updated)
        return _profile(updated)


def _new_display_name(stored: str | None, changes: LearnerProfileChanges) -> str | None:
    if changes.clear_display_name:
        return None
    return stored if changes.display_name is None else changes.display_name


def _profile(record: LearnerRecord) -> LearnerProfile:
    return LearnerProfile(id=record.id, display_name=record.display_name, timezone=record.timezone)
