"""How one kind of record fared when reference data was applied.

Every seed reports the same three numbers per kind of record: how many were
created, how many were updated, and how many already matched. The counter knows
nothing about what a record is, so the curriculum seed and the examination
schedule seed report through this one type rather than each inventing its own.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SeedOutcome:
    """How one kind of record fared: how many were written, and how many already matched."""

    created: int = 0
    updated: int = 0
    unchanged: int = 0

    @property
    def changed(self) -> bool:
        """Whether applying the seed wrote anything for this kind of record."""
        return bool(self.created or self.updated)

    def with_created(self) -> SeedOutcome:
        """This outcome plus one created record."""
        return SeedOutcome(self.created + 1, self.updated, self.unchanged)

    def with_updated(self) -> SeedOutcome:
        """This outcome plus one updated record."""
        return SeedOutcome(self.created, self.updated + 1, self.unchanged)

    def with_unchanged(self) -> SeedOutcome:
        """This outcome plus one record that already matched the seed."""
        return SeedOutcome(self.created, self.updated, self.unchanged + 1)
