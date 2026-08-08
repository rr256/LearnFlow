"""Generate, read, and update a learner's study plans (PLN-001 to PLN-004).

This is the first code that *consumes* what learner setup records. Availability,
planning preferences, and recorded learning stages have all been stored and read
back without anything acting on them; a plan is what acts on them, and it is what
FR-002's last acceptance criterion asks for — a learner starting with no previous
progress still receives one.

**The plan is deterministic.** The same goal, curriculum, week, preferences, and
date produce the same plan every time, with no AI provider involved. That is what
docs/ai/learnflow-agents.md requires of the planner: core scheduling and
prioritisation are deterministic application rules, usable when Ollama is
unavailable. The two rules that decide the plan — what order, and which day — are
pure functions in `app.domain.study_planning`, so they are tested without a
database, a clock, or a request.

**The plan is explainable.** Every plan carries the reason it exists and every
item the reason it is there, written when the plan is generated and never
rewritten. FR-003 asks a learner to be able to see why an item is recommended, so
a superseded plan still explains itself in the terms that produced it.

**Two plans are generated together.** A `roadmap` orders every trackable topic
across the goal's horizon without dating anything, and a `weekly` plan places the
first of those topics onto the next seven days using the saved availability. The
roadmap answers "in what order", the week answers "what now". Monthly and daily
plans, and re-planning after missed work, are FR-003 and FR-004 work that
Milestone 3 continues.

**Completing a plan item moves that item and nothing else.** PLN-004 writes an item's
`status` and `completed_at`, and touches no plan, no other item, and no topic
progress. Completing planned work is a statement that it happened, not a claim
about how well the learner understands the topic — rule 4 of the domain model —
and re-planning around what was completed is FR-004's work, which this is not.

**Generating again supersedes rather than refuses.** The goal's active plans
become `superseded` and a new pair is written, so the learner's plan history stays
explainable, which is what docs/database/schema.md asks of plans. Nothing is
deleted, and nothing has to be confirmed twice.

**Nothing invents a preference.** A learner who set no session length gets one the
planner chose, stated in the plan as the planner's own choice, rather than a
default stored against their goal (ADR-019). A learner who saved no week gets a
roadmap and no dated work, and is told why, rather than a week the product made
up.

**Nothing here judges the learner.** A recorded learning stage is reported in an
item's reason and changes neither the order nor the time allowed. A stage guides
the next action rather than scoring a topic (FR-005), and no evidence beyond the
learner's own statement is stored to rank anything by.
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.application.dto.availability import WEEKDAYS
from app.application.dto.planning_preferences import PlanningPreferences
from app.application.dto.study_plan import (
    ACTIVE,
    COMPLETED,
    DEFAULT_SESSION_MINUTES,
    PLAN_ITEM_STATUS_CHANGES,
    PLAN_STATUSES,
    PLAN_TYPES,
    PLAN_WEEK_DAYS,
    PLANNED,
    ROADMAP,
    STUDY,
    SUPERSEDED,
    WEEKLY,
    GeneratedStudyPlans,
    PlanGenerationRequest,
    PlanItemDetail,
    PlanItemStatusChange,
    PlanItemTopic,
    StudyPlanDetail,
    StudyPlanFilters,
    StudyPlanPage,
)
from app.application.ports.clock import Clock
from app.application.ports.curriculum_repository import CurriculumRepository
from app.application.ports.curriculum_seed_repository import (
    SubjectRecord,
    TopicRecord,
    TopicRelationshipRecord,
)
from app.application.ports.examination_schedule_repository import ExaminationScheduleRepository
from app.application.ports.learner_repository import LearnerRepository
from app.application.ports.study_goal_management_repository import (
    AvailabilitySlotRecord,
    StudyGoalManagementRepository,
)
from app.application.ports.study_goal_repository import LearnerRecord, StudyGoalRecord
from app.application.ports.study_plan_repository import (
    PlanItemRecord,
    StudyPlanRecord,
    StudyPlanRepository,
)
from app.application.ports.topic_progress_repository import TopicProgressRepository
from app.application.use_cases.examination_window import derive_examination_window
from app.application.use_cases.local_learner import resolve_local_learner
from app.domain.study_planning import (
    DayCapacity,
    PlannableTopic,
    PlannedSession,
    SyllabusPosition,
    TopicOrdering,
    order_by_prerequisites,
    order_by_syllabus,
    schedule_sessions,
)

PREREQUISITE = "prerequisite"
"""The relationship type that constrains study order.

Read as **the source topic comes before the target**, matching how
`recommended_before` reads. docs/domain/terminology.md names the type without
fixing its direction, and no edge is stored in the curated GATE CSE curriculum, so
this is the first code to depend on the reading; ADR-020 records it as such.
`recommended_before` and `related` are deliberately ignored: a recommendation is
not a constraint, and a plan treating one as a constraint could not explain the
difference.
"""

PREREQUISITES_FIRST = "prerequisites_first"

SEQUENCING_LABELS: Mapping[str, str] = {
    "syllabus_order": "syllabus order",
    PREREQUISITES_FIRST: "prerequisites first",
}
"""How each topic order is named in a plan's own explanation.

The labels docs/domain/terminology.md approves, lower-cased to sit inside a
sentence. As with the stage labels below, the stored value stays `snake_case` and
this is presentation.
"""

LEARNING_STAGE_LABELS: Mapping[str, str] = {
    "not_explored": "Not explored",
    "building_foundation": "Building foundation",
    "developing_confidence": "Developing confidence",
    "practice_ready": "Practice-ready",
    "strong_understanding": "Strong understanding",
}
"""The learner-visible label for each stored learning stage.

Mirrors docs/domain/terminology.md, which stays authoritative for the wording, the
way `LEARNING_STAGES` mirrors the database `CHECK`. This is the one place the
backend writes a stage *label* rather than passing the stored value on, and it
does so because a plan item's reason is learner-facing prose fixed at generation
time rather than a controlled value a client has to interpret.
"""


class StudyPlanManagementError(Exception):
    """A study plan could not be generated or read as asked."""


class LearnerNotSetUpError(StudyPlanManagementError):
    """No learner exists yet, so there is nobody to own a plan."""


class StudyGoalNotFoundError(StudyPlanManagementError):
    """No goal with the requested identifier belongs to the local learner."""


class StudyPlanNotFoundError(StudyPlanManagementError):
    """No plan with the requested identifier belongs to the local learner."""


class PlanItemNotFoundError(StudyPlanManagementError):
    """No item with the requested identifier belongs to the local learner."""


class UnknownPlanItemStatusError(StudyPlanManagementError):
    """A learner asked to move an item to a status PLN-004 does not accept."""


class PlanItemNotOnActivePlanError(StudyPlanManagementError):
    """The item belongs to a plan that has been superseded.

    A superseded plan is kept precisely so it still reads exactly as it was
    written (ADR-020). Writing into one would change a record whose worth is that
    it does not change, so the learner is pointed at their current plan instead.
    """


class UnknownPlanFilterError(StudyPlanManagementError):
    """A listing filter names a value no plan could hold.

    ``field`` names the query parameter at fault, so the API can report which one
    rather than making a caller guess.
    """

    def __init__(self, message: str, *, field: str) -> None:
        """Record the failure and the query parameter responsible for it."""
        super().__init__(message)
        self.field = field


class StudyPlanIntegrityError(StudyPlanManagementError):
    """A stored plan or goal points at reference data that is no longer stored.

    Foreign keys make this unreachable through the API. It is raised rather than
    papered over so a hand-edited database surfaces as a reported failure instead
    of a plan with fields quietly missing.
    """


@dataclass(frozen=True, slots=True)
class Horizon:
    """When a goal's study has to be done by, and how to describe that date.

    A goal aiming at both an examination cycle and a target date is planned
    against whichever falls first: the earlier one is the binding constraint, and
    planning against the later would quietly overrun the other.

    `ends_on` is None only when the goal's examination schedule publishes no
    sitting day and no target date sits beside it. A plan says so rather than
    inventing a date.
    """

    ends_on: date | None
    examination_name: str | None
    examination_window_starts_on: date | None
    dates_may_change: bool
    target_date: date | None


class ManageStudyPlans:
    """Serves the study-plan endpoints through the ports below."""

    def __init__(
        self,
        *,
        learners: LearnerRepository,
        goals: StudyGoalManagementRepository,
        schedules: ExaminationScheduleRepository,
        curriculum: CurriculumRepository,
        progress: TopicProgressRepository,
        plans: StudyPlanRepository,
        clock: Clock,
    ) -> None:
        """Wire the use case.

        The planner reads more than any other use case because a plan is made of
        everything the learner has recorded: docs/ai/learnflow-agents.md lists the
        goal and its horizon, availability and planning preferences, the
        curriculum and its topic relationships, and topic progress as the
        planner's inputs, and each arrives through the port that already owns it.

        Args:
            learners: Where the effective learner is resolved.
            goals: Where the goal, its curriculum binding, and its saved week are
                read.
            schedules: Where the published examination schedule and its periods
                are read, so a horizon is derived from the source rather than
                copied.
            curriculum: Where the subjects, topics, and topic relationships a plan
                walks are read.
            progress: Where the learner's recorded stages are read, to explain an
                item rather than to rank one.
            plans: Where plans and their items are read and written.
            clock: Where "today" comes from, so a generated plan's dates are
                testable.
        """
        self._learners = learners
        self._goals = goals
        self._schedules = schedules
        self._curriculum = curriculum
        self._progress = progress
        self._plans = plans
        self._clock = clock

    def generate(self, request: PlanGenerationRequest) -> GeneratedStudyPlans:
        """Generate an initial study plan for one of the learner's goals.

        Supersedes the goal's existing active plans, then writes a roadmap and,
        when the learner has saved study time the coming week can use, a plan for
        that week. Repeating the call is safe: it replaces rather than duplicates,
        and nothing is deleted.

        The caller owns the transaction: this method writes through the repository
        but never commits.

        Raises:
            LearnerNotSetUpError: No learner exists to own the plan.
            StudyGoalNotFoundError: No such goal is stored, or it belongs to
                another learner.
            StudyPlanIntegrityError: The goal points at a curriculum version that
                is not stored.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        learner = resolve_local_learner(self._learners)
        if learner is None:
            raise LearnerNotSetUpError(
                "No learner profile exists yet. Complete setup before generating a plan."
            )
        goal = self._require_own_goal(request.study_goal_id, learner)
        if self._goals.find_curriculum_version(goal.curriculum_version_id) is None:
            raise StudyPlanIntegrityError(
                f"Study goal {goal.id} references curriculum version "
                f"{goal.curriculum_version_id}, which is not stored."
            )

        today = _today_for(learner, self._clock)
        horizon = self._horizon_of(goal)
        subjects = {
            subject.id: subject
            for subject in self._curriculum.list_subjects(goal.curriculum_version_id)
        }
        topics = self._curriculum.list_topics(goal.curriculum_version_id)
        ordering = _ordered_topics(
            topics,
            subjects,
            self._curriculum.list_topic_relationships(goal.curriculum_version_id),
            goal.planning_preferences,
        )
        stages = {
            record.topic_id: record.learning_stage
            for record in self._progress.list_recorded_stages(
                learner_id=learner.id, curriculum_version_id=goal.curriculum_version_id
            )
        }

        session_minutes = goal.planning_preferences.preferred_session_minutes
        week = _week_capacities(today, self._goals.list_availability_slots([goal.id]))
        sessions = schedule_sessions(
            [topic.topic_id for topic in ordering.topics],
            week,
            session_minutes=session_minutes or DEFAULT_SESSION_MINUTES,
        )

        superseded = self._supersede_active_plans(goal.id)
        reasons = _ItemReasons(
            ordering=ordering,
            subjects=subjects,
            topics={topic.id: topic for topic in topics},
            stages=stages,
            sequencing=goal.planning_preferences.topic_sequencing,
        )
        written = [
            self._write_plan(
                _NewPlan(
                    learner_id=learner.id,
                    study_goal_id=goal.id,
                    plan_type=ROADMAP,
                    period_start=today,
                    period_end=horizon.ends_on,
                    generation_reason=_roadmap_reason(
                        ordering=ordering,
                        horizon=horizon,
                        today=today,
                        session_minutes=session_minutes,
                        scheduled=len(sessions),
                        week_holds_time=any(day.available_minutes for day in week),
                    ),
                ),
                _roadmap_items(ordering, session_minutes, reasons),
                subjects=subjects,
                topics=topics,
            )
        ]
        if sessions:
            written.append(
                self._write_plan(
                    _NewPlan(
                        learner_id=learner.id,
                        study_goal_id=goal.id,
                        plan_type=WEEKLY,
                        period_start=today,
                        period_end=week[-1].on,
                        generation_reason=_weekly_reason(
                            scheduled=len(sessions),
                            planned=len(ordering.topics),
                            today=today,
                            until=week[-1].on,
                            session_minutes=session_minutes,
                        ),
                    ),
                    _weekly_items(sessions, reasons),
                    subjects=subjects,
                    topics=topics,
                )
            )
        return GeneratedStudyPlans(
            study_goal_id=goal.id,
            generated_on=today,
            plans=tuple(written),
            superseded_plan_ids=superseded,
        )

    def list_study_plans(
        self, *, filters: StudyPlanFilters, limit: int, offset: int
    ) -> StudyPlanPage:
        """One page of the local learner's plans, newest first.

        Items are deliberately not included. A page of plans each carrying every
        item would be an unbounded payload inside a paginated one; `item_count`
        says how large each plan is, and PLN-003 returns the items of the one a
        client actually opens.

        A learner who has not been created yet has no plans, which is an empty page
        rather than a failure.

        Raises:
            UnknownPlanFilterError: A filter names a plan type or status no plan
                could hold.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        _validate(filters)
        learner = resolve_local_learner(self._learners)
        if learner is None:
            return StudyPlanPage(plans=(), total=0, limit=limit, offset=offset)

        records = self._plans.list_study_plans(
            learner_id=learner.id, filters=filters, limit=limit, offset=offset
        )
        counts = self._plans.count_plan_items([record.id for record in records])
        return StudyPlanPage(
            plans=tuple(
                _plan_detail(record, item_count=counts.get(record.id, 0)) for record in records
            ),
            total=self._plans.count_study_plans(learner_id=learner.id, filters=filters),
            limit=limit,
            offset=offset,
        )

    def read(self, study_plan_id: uuid.UUID) -> StudyPlanDetail:
        """One of the local learner's plans, with its items in plan order.

        Raises:
            StudyPlanNotFoundError: No such plan is stored, or it belongs to
                another learner.
            StudyPlanIntegrityError: The plan's goal is not stored.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        learner = resolve_local_learner(self._learners)
        record = None if learner is None else self._plans.find_study_plan(study_plan_id)
        if record is None or learner is None or record.learner_id != learner.id:
            raise StudyPlanNotFoundError(
                f"No study plan is stored with identifier {study_plan_id}."
            )

        goal = self._goals.find_study_goal(record.study_goal_id)
        if goal is None:
            raise StudyPlanIntegrityError(
                f"Study plan {record.id} references study goal {record.study_goal_id}, "
                "which is not stored."
            )
        items = self._plans.list_plan_items(record.id)
        return _plan_detail(
            record,
            item_count=len(items),
            items=self._describe(items, curriculum_version_id=goal.curriculum_version_id),
        )

    def record_item_status(
        self, plan_item_id: uuid.UUID, change: PlanItemStatusChange
    ) -> PlanItemDetail:
        """Mark one of the learner's plan items completed, or return it to planned.

        The caller owns the transaction: this method writes through the
        repository but never commits.

        **Only the item moves.** Its `status` and `completed_at` are written and
        nothing else is: not the plan, not another item naming the same topic,
        and not the learner's topic progress. A completed item records that
        planned work happened, which is not a claim that the topic is understood
        (rule 4 of the domain model), and nothing re-plans around it — that is
        PLN-005 and does not exist.

        **Completing is reversible.** A learner who marked the wrong line can put
        it back to `planned`, which clears the timestamp. Nothing here treats
        completion as a verdict, and a mis-tap that could not be undone would be
        one.

        **Recording the status an item already holds is accepted and writes
        nothing**, as PRG-004 does: a repeated form submission must not fail on
        its second attempt.

        Raises:
            UnknownPlanItemStatusError: The status is not one PLN-004 accepts.
            LearnerNotSetUpError: No learner exists to own the item.
            PlanItemNotFoundError: No such item is stored, or its plan belongs to
                another learner.
            PlanItemNotOnActivePlanError: Its plan has been superseded.
            StudyPlanIntegrityError: The item's plan is not stored.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        if change.status not in PLAN_ITEM_STATUS_CHANGES:
            # The rejected value is deliberately not repeated back, which
            # docs/api/conventions.md keeps out of the error envelope. Naming
            # what is accepted is what a caller needs, and saying that skipping
            # and postponing are not built yet keeps a client from reading their
            # absence as a typo.
            raise UnknownPlanItemStatusError(
                "A plan item can be marked "
                f"{' or '.join(PLAN_ITEM_STATUS_CHANGES)}. Skipping and postponing work are "
                "not built yet."
            )

        learner = resolve_local_learner(self._learners)
        if learner is None:
            raise LearnerNotSetUpError(
                "No learner profile exists yet. Complete setup before completing a plan item."
            )

        item = self._plans.find_plan_item(plan_item_id)
        if item is None:
            raise PlanItemNotFoundError(f"No plan item is stored with identifier {plan_item_id}.")
        plan = self._plans.find_study_plan(item.study_plan_id)
        if plan is None:
            raise StudyPlanIntegrityError(
                f"Plan item {item.id} references study plan {item.study_plan_id}, "
                "which is not stored."
            )
        # An item on somebody else's plan is reported as missing rather than
        # forbidden, the rule `_require_own_goal` follows: saying "that exists
        # but is not yours" would confirm a record the caller may not read.
        if plan.learner_id != learner.id:
            raise PlanItemNotFoundError(f"No plan item is stored with identifier {plan_item_id}.")
        if plan.status != ACTIVE:
            raise PlanItemNotOnActivePlanError(
                "That item belongs to a study plan that has been replaced. It is kept as a "
                "record of what was planned, so it cannot be changed; mark the work done on "
                "your current plan instead."
            )

        if item.status != change.status:
            item = PlanItemRecord(
                id=item.id,
                study_plan_id=item.study_plan_id,
                topic_id=item.topic_id,
                action_type=item.action_type,
                scheduled_for=item.scheduled_for,
                estimated_minutes=item.estimated_minutes,
                priority=item.priority,
                status=change.status,
                recommendation_reason=item.recommendation_reason,
                # Read from the clock rather than accepted from the caller, so
                # nobody can backdate work, and cleared on the way back so a
                # `planned` item never carries a completion instant.
                completed_at=self._clock.now() if change.status == COMPLETED else None,
            )
            self._plans.update_plan_item(item)

        goal = self._goals.find_study_goal(plan.study_goal_id)
        if goal is None:
            raise StudyPlanIntegrityError(
                f"Study plan {plan.id} references study goal {plan.study_goal_id}, "
                "which is not stored."
            )
        return self._describe([item], curriculum_version_id=goal.curriculum_version_id)[0]

    def _require_own_goal(
        self, study_goal_id: uuid.UUID, learner: LearnerRecord
    ) -> StudyGoalRecord:
        """The goal, if it exists and belongs to the local learner.

        A goal owned by somebody else is reported as missing rather than
        forbidden, the rule GOAL-003 follows: docs/api/conventions.md treats "not
        visible to the caller" as a `404`, and saying "that exists but is not
        yours" would confirm a record the caller may not read.
        """
        goal = self._goals.find_study_goal(study_goal_id)
        if goal is None or goal.learner_id != learner.id:
            raise StudyGoalNotFoundError(
                f"No study goal is stored with identifier {study_goal_id}."
            )
        return goal

    def _horizon_of(self, goal: StudyGoalRecord) -> Horizon:
        """When the goal's study has to be done by, and what that date came from.

        A published schedule is read on every generation rather than copied, so a
        correction the examining body publishes reaches the next plan (ADR-013).
        """
        schedule = (
            None
            if goal.examination_schedule_id is None
            else self._schedules.find_examination_schedule(goal.examination_schedule_id)
        )
        window_starts_on = None
        if schedule is not None:
            window_starts_on, _ = derive_examination_window(
                self._schedules.list_examination_periods([schedule.id])
            )
        candidates = [
            candidate for candidate in (window_starts_on, goal.target_date) if candidate is not None
        ]
        return Horizon(
            ends_on=min(candidates) if candidates else None,
            examination_name=None if schedule is None else schedule.name,
            examination_window_starts_on=window_starts_on,
            dates_may_change=schedule is not None and schedule.schedule_status == "provisional",
            target_date=goal.target_date,
        )

    def _supersede_active_plans(self, study_goal_id: uuid.UUID) -> tuple[uuid.UUID, ...]:
        """Set the goal's active plans aside, keeping every one of them.

        Superseded rather than deleted, which is what docs/database/schema.md asks
        of plans: a learner who wants to know what they were working from last
        week can still be shown it, and asking for a new plan never silently
        destroys the old one.
        """
        superseded: list[uuid.UUID] = []
        for record in self._plans.list_active_study_plans(study_goal_id):
            self._plans.update_study_plan(
                StudyPlanRecord(
                    id=record.id,
                    learner_id=record.learner_id,
                    study_goal_id=record.study_goal_id,
                    plan_type=record.plan_type,
                    period_start=record.period_start,
                    period_end=record.period_end,
                    status=SUPERSEDED,
                    generation_reason=record.generation_reason,
                )
            )
            superseded.append(record.id)
        return tuple(superseded)

    def _write_plan(
        self,
        plan: _NewPlan,
        items: Sequence[_NewItem],
        *,
        subjects: Mapping[uuid.UUID, SubjectRecord],
        topics: Sequence[TopicRecord],
    ) -> StudyPlanDetail:
        """Store one plan and its items, and report what was written.

        The reference data is passed in rather than read back: the caller has just
        walked the whole curriculum to build these items, so re-reading it to name
        them would be a second pass over rows already in hand.

        **The plan is flushed before its items.** An item references its plan by
        foreign key, and nothing tells the store that the two writes are ordered:
        left to one flush at commit, the items can be inserted first and the
        database refuses them. Flushing is not committing, so a generation that
        fails after this point still writes nothing.
        """
        record = StudyPlanRecord(
            id=uuid.uuid4(),
            learner_id=plan.learner_id,
            study_goal_id=plan.study_goal_id,
            plan_type=plan.plan_type,
            period_start=plan.period_start,
            period_end=plan.period_end,
            status=ACTIVE,
            generation_reason=plan.generation_reason,
        )
        self._plans.add_study_plan(record)
        self._plans.flush()

        stored: list[PlanItemRecord] = []
        for item in items:
            written = PlanItemRecord(
                id=uuid.uuid4(),
                study_plan_id=record.id,
                topic_id=item.topic_id,
                action_type=STUDY,
                scheduled_for=item.scheduled_for,
                estimated_minutes=item.estimated_minutes,
                priority=item.priority,
                status=PLANNED,
                recommendation_reason=item.recommendation_reason,
            )
            self._plans.add_plan_item(written)
            stored.append(written)

        by_id = {topic.id: topic for topic in topics}
        return _plan_detail(
            record,
            item_count=len(stored),
            items=tuple(_item_detail(item, topics=by_id, subjects=subjects) for item in stored),
        )

    def _describe(
        self, items: Sequence[PlanItemRecord], *, curriculum_version_id: uuid.UUID
    ) -> tuple[PlanItemDetail, ...]:
        """Name the topic and subject behind each item, in plan order.

        `priority` is the order the plan was written in, so sorting by it
        reproduces the plan rather than the order rows happened to come back in.
        """
        topics = {
            topic.id: topic
            for topic in self._plans.list_topics(
                [item.topic_id for item in items if item.topic_id is not None]
            )
        }
        subjects = {
            subject.id: subject for subject in self._plans.list_subjects(curriculum_version_id)
        }
        return tuple(
            _item_detail(item, topics=topics, subjects=subjects)
            for item in sorted(items, key=lambda item: (item.priority, item.id))
        )


@dataclass(frozen=True, slots=True)
class _NewPlan:
    """A plan about to be written, before it has an identity."""

    learner_id: uuid.UUID
    study_goal_id: uuid.UUID
    plan_type: str
    period_start: date | None
    period_end: date | None
    generation_reason: str


@dataclass(frozen=True, slots=True)
class _NewItem:
    """An item about to be written, before its plan has an identity."""

    topic_id: uuid.UUID
    scheduled_for: date | None
    estimated_minutes: int
    priority: int
    recommendation_reason: str


class _ItemReasons:
    """Writes the sentence explaining why one item is where it is.

    Built once per generation rather than per item, because every sentence needs
    the same handful of lookups and none of the totals change between them.
    """

    def __init__(
        self,
        *,
        ordering: TopicOrdering,
        subjects: Mapping[uuid.UUID, SubjectRecord],
        topics: Mapping[uuid.UUID, TopicRecord],
        stages: Mapping[uuid.UUID, str],
        sequencing: str | None,
    ) -> None:
        """Record what every reason this generation writes has in common."""
        self._total = len(ordering.topics)
        self._subjects = subjects
        self._topics = topics
        self._stages = stages
        self._held_back = {topic.topic_id for topic in ordering.held_back_by_a_cycle}
        # A learner who chose prerequisites first but has no prerequisite links
        # stored is reading syllabus order, and the sentence says so rather than
        # naming an order the plan did not actually follow.
        self._order = SEQUENCING_LABELS[
            PREREQUISITES_FIRST
            if sequencing == PREREQUISITES_FIRST and ordering.prerequisites_applied
            else "syllabus_order"
        ]

    def for_topic(self, topic_id: uuid.UUID, position: int) -> str:
        """Why this topic sits at this point in the roadmap."""
        parts = [
            f"Topic {position} of {self._total} in {self._order}, from {self._subject(topic_id)}."
        ]
        if topic_id in self._held_back:
            parts.append(
                "Its prerequisites refer to each other in a loop, so it could not be placed by "
                "prerequisite order and follows the syllabus instead."
            )
        stage = self._stages.get(topic_id)
        if stage in LEARNING_STAGE_LABELS:
            parts.append(f"You recorded {LEARNING_STAGE_LABELS[stage]} for this topic.")
        return " ".join(parts)

    def for_session(self, topic_id: uuid.UUID, position: int, on: date) -> str:
        """Why this topic is on this day of the coming week."""
        return (
            f"Number {position} of the topics your roadmap starts with, from "
            f"{self._subject(topic_id)}, placed on {on.isoformat()} because you said you can "
            "study that day."
        )

    def _subject(self, topic_id: uuid.UUID) -> str:
        """The name of the subject the topic belongs to, for a learner to read."""
        topic = self._topics.get(topic_id)
        subject = None if topic is None else self._subjects.get(topic.subject_id)
        return "your curriculum" if subject is None else subject.name


def _roadmap_items(
    ordering: TopicOrdering, session_minutes: int | None, reasons: _ItemReasons
) -> tuple[_NewItem, ...]:
    """One undated item per trackable topic, in the order to work through them.

    A roadmap says what order, not what day, so nothing here carries a date. The
    length is the same session length the week is built from, so the two plans
    cannot disagree about how long a topic takes.
    """
    return tuple(
        _NewItem(
            topic_id=topic.topic_id,
            scheduled_for=None,
            estimated_minutes=session_minutes or DEFAULT_SESSION_MINUTES,
            priority=position,
            recommendation_reason=reasons.for_topic(topic.topic_id, position),
        )
        for position, topic in enumerate(ordering.topics, start=1)
    )


def _weekly_items(
    sessions: Sequence[PlannedSession], reasons: _ItemReasons
) -> tuple[_NewItem, ...]:
    """One dated item per session the coming week has room for."""
    return tuple(
        _NewItem(
            topic_id=session.topic_id,
            scheduled_for=session.scheduled_for,
            estimated_minutes=session.estimated_minutes,
            priority=position,
            recommendation_reason=reasons.for_session(
                session.topic_id, position, session.scheduled_for
            ),
        )
        for position, session in enumerate(sessions, start=1)
    )


def _today_for(learner: LearnerRecord, clock: Clock) -> date:
    """The learner's own date, not the server's.

    A plan generated at 23:30 in `Asia/Kolkata` must start today rather than
    yesterday, and the process may be running anywhere. An unknown stored zone
    falls back to UTC rather than failing the request: a plan a day out is a
    recoverable annoyance, and refusing to plan at all is not.
    """
    try:
        zone = ZoneInfo(learner.timezone)
    except ZoneInfoNotFoundError, ValueError:
        return clock.now().date()
    return clock.now().astimezone(zone).date()


def _ordered_topics(
    topics: Sequence[TopicRecord],
    subjects: Mapping[uuid.UUID, SubjectRecord],
    relationships: Sequence[TopicRelationshipRecord],
    preferences: PlanningPreferences,
) -> TopicOrdering:
    """Every trackable topic, in the order the learner asked to work through them.

    Only trackable topics are planned. A topic that merely groups subtopics is a
    heading rather than work, which is the rule PRG-004 applies when it refuses a
    stage against one.
    """
    plannable = _plannable(topics, subjects)
    if preferences.topic_sequencing != PREREQUISITES_FIRST:
        return order_by_syllabus(plannable)

    planned = {topic.topic_id for topic in plannable}
    prerequisites: dict[uuid.UUID, set[uuid.UUID]] = {}
    for edge in relationships:
        if edge.relationship_type != PREREQUISITE:
            continue
        if edge.target_topic_id in planned and edge.source_topic_id in planned:
            prerequisites.setdefault(edge.target_topic_id, set()).add(edge.source_topic_id)
    return order_by_prerequisites(
        plannable,
        {topic_id: frozenset(required) for topic_id, required in prerequisites.items()},
    )


def _plannable(
    topics: Sequence[TopicRecord], subjects: Mapping[uuid.UUID, SubjectRecord]
) -> tuple[PlannableTopic, ...]:
    """The trackable topics, each carrying where it sits in the syllabus."""
    by_id = {topic.id: topic for topic in topics}
    return tuple(
        PlannableTopic(
            topic_id=topic.id,
            position=SyllabusPosition(
                subject_position=subjects[topic.subject_id].position,
                path=_position_path(topic, by_id),
                topic_id=topic.id,
            ),
        )
        for topic in topics
        if topic.is_trackable and topic.subject_id in subjects
    )


def _position_path(topic: TopicRecord, by_id: Mapping[uuid.UUID, TopicRecord]) -> tuple[int, ...]:
    """The topic's stored positions from the root of its branch down to itself.

    Comparing two of these walks the syllabus the way a reader does: a parent
    sorts before its own children, and a whole branch sorts before the next one.

    A parent chain that refers back to itself is stopped rather than followed. No
    such curriculum can be seeded, but a traversal that trusts its data to be
    acyclic is one hand-written row away from hanging a request.
    """
    path: list[int] = []
    seen: set[uuid.UUID] = set()
    current: TopicRecord | None = topic
    while current is not None and current.id not in seen:
        seen.add(current.id)
        path.append(current.position)
        current = None if current.parent_topic_id is None else by_id.get(current.parent_topic_id)
    return tuple(reversed(path))


def _week_capacities(
    today: date, slots: Sequence[AvailabilitySlotRecord]
) -> tuple[DayCapacity, ...]:
    """The coming week as dated capacities, starting today.

    This is the one place a calendar date meets a stored day *name*, and the
    mapping is written out rather than assumed. `date.weekday()` numbers Monday
    zero, which is the order `WEEKDAYS` is written in — but the two agreeing is a
    fact worth pinning with a test rather than a coincidence worth relying on,
    because getting it wrong shifts a learner's whole week with no error anywhere
    (ADR-018).

    A day the learner has not set contributes zero minutes, which is the planner
    declining to invent a week nobody described. A day they deliberately kept free
    contributes zero too: the two are different statements about the learner, and
    neither is a statement that they can study.
    """
    minutes = {slot.day_of_week: slot.available_minutes for slot in slots}
    return tuple(
        DayCapacity(
            on=date.fromordinal(today.toordinal() + offset),
            available_minutes=minutes.get(
                WEEKDAYS[date.fromordinal(today.toordinal() + offset).weekday()], 0
            ),
        )
        for offset in range(PLAN_WEEK_DAYS)
    )


def _roadmap_reason(
    *,
    ordering: TopicOrdering,
    horizon: Horizon,
    today: date,
    session_minutes: int | None,
    scheduled: int,
    week_holds_time: bool,
) -> str:
    """The sentence a roadmap gives for itself.

    Everything it claims is derived from what the learner stored, and everything
    the planner chose for itself is named as the planner's choice. FR-003 asks a
    learner to be able to see why work is recommended; a plan that could not say
    where its own dates and lengths came from could not answer that.
    """
    order = SEQUENCING_LABELS[
        PREREQUISITES_FIRST if ordering.prerequisites_applied else "syllabus_order"
    ]
    parts = [f"{len(ordering.topics)} topics from your curriculum, in {order}."]
    if horizon.ends_on is None:
        parts.append(
            "This goal has no date to work toward: its examination schedule publishes no "
            "sitting day and no target date is set, so this roadmap has no end date."
        )
    else:
        parts.append(_horizon_sentence(horizon, today))
    parts.append(_session_sentence(session_minutes))
    if not week_holds_time:
        parts.append(
            "No study time is saved against this goal, so no day-by-day plan was built. "
            "Save your study week to get dated work."
        )
    elif scheduled == 0:
        parts.append(
            "None of the coming seven days holds enough time for a session, so no day-by-day "
            "plan was built."
        )
    if ordering.held_back_by_a_cycle:
        parts.append(
            f"{len(ordering.held_back_by_a_cycle)} topics could not be placed by prerequisite "
            "order, because their prerequisites refer to each other in a loop; they follow the "
            "syllabus instead."
        )
    return " ".join(parts)


def _weekly_reason(
    *, scheduled: int, planned: int, today: date, until: date, session_minutes: int | None
) -> str:
    """The sentence a weekly plan gives for itself."""
    return (
        f"The first {scheduled} of {planned} topics on your roadmap, placed on the days you said "
        f"you can study between {today.isoformat()} and {until.isoformat()}. "
        f"{_session_sentence(session_minutes)}"
    )


def _horizon_sentence(horizon: Horizon, today: date) -> str:
    """How the plan describes the date it is working toward.

    A published examination is described as a *window* opening on a date, never as
    the learner's paper date, and its provenance travels with it: a provisional
    schedule says so wherever its dates are shown (ADR-013).
    """
    if horizon.ends_on is None:
        return ""
    days = horizon.ends_on.toordinal() - today.toordinal()
    ends_on = horizon.ends_on.isoformat()
    if horizon.examination_name and horizon.ends_on == horizon.examination_window_starts_on:
        may_change = (
            " Those dates are provisional and may change." if horizon.dates_may_change else ""
        )
        if days < 0:
            return (
                f"The {horizon.examination_name} examination window opened on "
                f"{ends_on}.{may_change}"
            )
        return (
            f"{days} days until the {horizon.examination_name} examination window opens on "
            f"{ends_on}.{may_change}"
        )
    if days < 0:
        return f"Your target date of {ends_on} has passed."
    return f"{days} days until your target date of {ends_on}."


def _session_sentence(session_minutes: int | None) -> str:
    """How the plan describes the length it gave each session.

    A learner who set no session length is told the planner chose one, not that
    the value is theirs. Nothing is stored against their goal either way
    (ADR-019).
    """
    if session_minutes is None:
        return (
            f"Sessions of {DEFAULT_SESSION_MINUTES} minutes, which LearnFlow chose because you "
            "have not set a preferred session length."
        )
    return f"Sessions of {session_minutes} minutes, the length you prefer."


def _validate(filters: StudyPlanFilters) -> None:
    """Refuse a filter naming a value no plan could hold.

    An unknown plan type or status is a caller's mistake rather than an empty
    result: a client asking for `status=finished` has misread the contract, and
    returning nothing would let it keep doing so. An identifier that matches
    nothing is different, and returns an empty page.
    """
    if filters.plan_type is not None and filters.plan_type not in PLAN_TYPES:
        raise UnknownPlanFilterError(
            f"That is not a plan type. Use one of: {', '.join(PLAN_TYPES)}.",
            field="plan_type",
        )
    if filters.status is not None and filters.status not in PLAN_STATUSES:
        raise UnknownPlanFilterError(
            f"That is not a plan status. Use one of: {', '.join(PLAN_STATUSES)}.",
            field="status",
        )


def _plan_detail(
    record: StudyPlanRecord, *, item_count: int, items: tuple[PlanItemDetail, ...] = ()
) -> StudyPlanDetail:
    """Map a stored plan onto the structure the endpoints report."""
    return StudyPlanDetail(
        id=record.id,
        learner_id=record.learner_id,
        study_goal_id=record.study_goal_id,
        plan_type=record.plan_type,
        period_start=record.period_start,
        period_end=record.period_end,
        status=record.status,
        generation_reason=record.generation_reason,
        item_count=item_count,
        items=items,
    )


def _item_detail(
    record: PlanItemRecord,
    *,
    topics: Mapping[uuid.UUID, TopicRecord],
    subjects: Mapping[uuid.UUID, SubjectRecord],
) -> PlanItemDetail:
    """Map a stored item onto the structure the endpoints report.

    A topic that is not stored leaves the item's `topic` null rather than dropping
    the item. The seed never deletes a topic (ADR-012), so this cannot arise
    through the product; an item silently missing from a plan would be worse than
    one admitting it cannot name its topic.
    """
    topic = None if record.topic_id is None else topics.get(record.topic_id)
    subject = None if topic is None else subjects.get(topic.subject_id)
    return PlanItemDetail(
        id=record.id,
        topic=(
            None
            if topic is None
            else PlanItemTopic(
                id=topic.id,
                code=topic.code,
                name=topic.name,
                subject_id=topic.subject_id,
                subject_name="" if subject is None else subject.name,
            )
        ),
        action_type=record.action_type,
        scheduled_for=record.scheduled_for,
        estimated_minutes=record.estimated_minutes,
        priority=record.priority,
        status=record.status,
        recommendation_reason=record.recommendation_reason,
        completed_at=record.completed_at,
    )
