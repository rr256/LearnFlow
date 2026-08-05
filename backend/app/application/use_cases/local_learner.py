"""Resolving the effective learner of a single-learner installation.

Every learner-owned endpoint needs the same answer, and none of them may take it
from the client: `docs/api/conventions.md` requires the backend to determine the
effective learner itself, so no request can name another learner's records. That
rule survives the arrival of authentication unchanged -- only the source of the
answer moves, from "the one stored learner" to "the authenticated one".

Three states exist, and each is reported rather than smoothed over:

- **None stored.** A fresh installation, before setup has run. Not an error;
  the profile endpoint says so and the setup screen offers to create one.
- **Exactly one.** The expected state.
- **More than one.** LearnFlow is single-learner by design, so "the local
  learner" is undefined. Picking one would attach a learner's goal to somebody
  else's record, so this raises instead.
"""

from app.application.ports.learner_repository import LearnerRepository
from app.application.ports.study_goal_repository import LearnerRecord


class AmbiguousLocalLearnerError(Exception):
    """More than one learner is stored, so "the local learner" is undefined."""


def resolve_local_learner(repository: LearnerRepository) -> LearnerRecord | None:
    """The single stored learner, or None when setup has not created one.

    Raises:
        AmbiguousLocalLearnerError: More than one learner is stored.
    """
    learners = repository.list_learners()
    if len(learners) > 1:
        raise AmbiguousLocalLearnerError(
            f"{len(learners)} learners are stored, so the local learner is undefined. "
            "LearnFlow is single-learner until accounts exist."
        )
    return learners[0] if learners else None
