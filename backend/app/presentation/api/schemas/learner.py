"""Request and response schemas for the learner profile endpoints (LRN-001, LRN-002).

No schema here accepts a learner identifier. The effective learner is resolved
server-side, so a client cannot name whose profile it is reading or writing
(docs/api/conventions.md).

`extra="forbid"` is deliberate on the update request. A field the contract does
not define is a client mistake worth reporting -- and it is what keeps a
hopeful `learner_id` from being sent and silently ignored.
"""

import uuid
import zoneinfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.application.dto.learner_profile import LearnerProfile, LearnerProfileChanges

MAX_DISPLAY_NAME_LENGTH = 200
"""A typo guard, not a storage limit: `learners.display_name` is unbounded `text`."""


class LearnerProfileSchema(BaseModel):
    """The local learner's identity and preferences."""

    id: uuid.UUID
    display_name: str | None = Field(description="Optional learner-facing name.")
    timezone: str = Field(description="IANA timezone name, such as `Asia/Kolkata`.")

    @classmethod
    def of(cls, profile: LearnerProfile) -> LearnerProfileSchema:
        """Build the schema from its application DTO."""
        return cls(id=profile.id, display_name=profile.display_name, timezone=profile.timezone)


class LearnerProfileResponse(BaseModel):
    """The learner profile, under the documented `data` envelope.

    `data` is null before setup has created a learner. That is a real state of a
    fresh installation rather than a failure, so it is reported as an empty
    profile with `200` rather than as a `404` a client would have to special-case.
    """

    data: LearnerProfileSchema | None


class LearnerProfileUpdateRequest(BaseModel):
    """A partial update to the local learner's profile.

    A field that is absent is left alone. `display_name: null` removes the stored
    name, which absence deliberately cannot express -- a form that omitted a
    field must not erase it.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_DISPLAY_NAME_LENGTH,
        description="New name, or null to remove the stored one.",
    )
    timezone: str | None = Field(
        default=None,
        description="New IANA timezone name. Null is rejected: a learner must have one.",
    )

    @field_validator("timezone")
    @classmethod
    def _require_a_known_timezone(cls, value: str | None) -> str | None:
        """Reject anything the standard library cannot resolve to a real zone.

        A typo would otherwise surface much later as a study plan whose days land
        in the wrong place, which is the same reason `APP_DEFAULT_TIMEZONE` is
        validated at startup (ADR-013).
        """
        if value is None:
            return None
        try:
            zoneinfo.ZoneInfo(value)
        except (zoneinfo.ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(
                f"{value!r} is not a known IANA timezone, for example 'Asia/Kolkata'."
            ) from error
        return value

    @model_validator(mode="after")
    def _reject_a_null_timezone(self) -> LearnerProfileUpdateRequest:
        """A learner always has a timezone, so null cannot mean "remove it"."""
        if "timezone" in self.model_fields_set and self.timezone is None:
            raise ValueError("timezone cannot be null. Omit it to leave the stored value alone.")
        return self

    def to_changes(self) -> LearnerProfileChanges:
        """Map the request onto the application's partial-update structure.

        `model_fields_set` is what distinguishes "absent" from "explicitly null";
        a default alone cannot, because both arrive as `None`.
        """
        supplied = self.model_fields_set
        return LearnerProfileChanges(
            display_name=self.display_name if "display_name" in supplied else None,
            timezone=self.timezone if "timezone" in supplied else None,
            clear_display_name="display_name" in supplied and self.display_name is None,
        )
