/**
 * Study plan types, derived from the PLN-001 to PLN-003 response contract in
 * docs/api/endpoints.md#planning-endpoints.
 *
 * Nothing here plans anything. What order topics go in, which day each falls on,
 * and how long a session runs are decided by the backend and stored; this file
 * only describes what comes back
 * (docs/development/coding-standards.md#ui-responsibilities).
 *
 * A plan carries the reason it exists and every item the reason it is there,
 * written when the plan was generated. The frontend renders those sentences
 * rather than composing its own, so what a learner reads is what was actually
 * decided.
 */

import type { CollectionEnvelope, DataEnvelope } from "@/types/api";

/** The kinds of plan the API can hold. Two are generated today. */
export const PLAN_TYPES = ["roadmap", "monthly", "weekly", "daily"] as const;

export type PlanType = (typeof PLAN_TYPES)[number];

/**
 * The heading a learner reads for each plan type.
 *
 * The wire value and the label are separate representations, as they are for a
 * learning stage: rewording one of these is a copy change, not a migration.
 */
export const PLAN_TYPE_LABELS: Record<PlanType, string> = {
  roadmap: "Your roadmap",
  monthly: "This month",
  weekly: "Your week",
  daily: "Today",
};

/** The states a plan can be in. Generation writes `active` and `superseded`. */
export type PlanStatus = "draft" | "active" | "superseded" | "archived";

/** The actions a plan item can recommend. Everything generated today is `study`. */
export type PlanItemAction = "study" | "practice" | "revise" | "review_mistakes";

/** What a learner reads for each action. */
export const PLAN_ITEM_ACTION_LABELS: Record<PlanItemAction, string> = {
  study: "Study",
  practice: "Practise",
  revise: "Revise",
  review_mistakes: "Review mistakes",
};

/** The states a plan item can be in. Generation writes `planned`; PLN-004 and PLN-005 write the rest. */
export type PlanItemStatus = "planned" | "completed" | "skipped" | "postponed";

/**
 * The statuses PLN-004 accepts as a target.
 *
 * Every status the column holds, where this was once a strict subset:
 * `postponed` is now something a learner asks for as well as something
 * adaptation writes for work whose day passed with nothing said about it.
 *
 * A learner may move an item to any of these four from any of them. Nothing
 * here is one-way, which is why the control offers the other three rather than a
 * single next step.
 */
export const PLAN_ITEM_STATUS_CHANGES = [
  "completed",
  "planned",
  "skipped",
  "postponed",
] as const;

export type PlanItemStatusChange = (typeof PLAN_ITEM_STATUS_CHANGES)[number];

/**
 * What each button says, naming the state it moves the item *to*.
 *
 * A learner returning to the page a week later reads what the button will do,
 * rather than an "undo" whose subject has been forgotten. The wording describes
 * the item and never the learner (docs/domain/terminology.md).
 */
export const PLAN_ITEM_STATUS_CHANGE_LABELS: Record<PlanItemStatusChange, string> = {
  completed: "Mark completed",
  planned: "Return to planned",
  skipped: "Skip this item",
  postponed: "Postpone this item",
};

/**
 * The statuses in which nothing carries an item forward on its own.
 *
 * The frontend's one mirror of `SETTLED_STATUSES` in
 * `backend/app/application/dto/study_plan.py`, which is what the domain rule
 * `select_overdue` reads. It decides which heading an item appears under and
 * which items are marked; it decides nothing that is stored, so a drift between
 * the two shows a learner the wrong heading rather than writing a wrong status.
 * The backend rule stays authoritative (ADR-023).
 *
 * `planned` is the only status not here: it is the one about which nothing has
 * been said.
 */
export const PLAN_ITEM_SETTLED_STATUSES: readonly PlanItemStatus[] = [
  "completed",
  "skipped",
  "postponed",
];

/** True when nothing should carry this item forward on its own. */
export function isSettledStatus(status: string): boolean {
  return (PLAN_ITEM_SETTLED_STATUSES as readonly string[]).includes(status);
}

/**
 * What a learner reads beside an item the API sent in a settled status.
 *
 * `planned` has no label: an item nobody has said anything about needs no
 * announcement. The other three do, including `postponed` — which a learner now
 * writes on an active plan, where before it appeared only on a superseded one
 * that no screen renders.
 */
export const PLAN_ITEM_SETTLED_LABELS: Partial<Record<PlanItemStatus, string>> = {
  completed: "Marked completed",
  skipped: "Marked skipped",
  postponed: "Marked postponed",
};

/** True when a string is one of the plan types this build knows. */
export function isPlanType(value: string): value is PlanType {
  return (PLAN_TYPES as readonly string[]).includes(value);
}

/** The topic a plan item recommends work on. */
export interface PlanItemTopic {
  id: string;
  code: string | null;
  name: string;
  subject_id: string;
  subject_name: string;
}

/** One recommended action within a plan. */
export interface PlanItem {
  id: string;
  /** Null only for an item recommending work belonging to no single topic. */
  topic: PlanItemTopic | null;
  action_type: PlanItemAction | string;
  /** Null on a roadmap item, which says what order to work in, not which day. */
  scheduled_for: string | null;
  estimated_minutes: number | null;
  /** Where the item falls in its plan, counting from 1. An order, not a score. */
  priority: number;
  status: PlanItemStatus | string;
  recommendation_reason: string | null;
  /**
   * When the learner marked this work done. Null unless `status` is
   * `completed`, and cleared when an item is put back to `planned`.
   */
  completed_at: string | null;
}

/** One study plan. `items` is empty on a listed plan and filled on one read. */
export interface StudyPlan {
  id: string;
  learner_id: string;
  study_goal_id: string;
  plan_type: PlanType | string;
  period_start: string | null;
  period_end: string | null;
  status: PlanStatus | string;
  generation_reason: string | null;
  item_count: number;
  items: PlanItem[];
}

/** What one generation produced. */
export interface GeneratedStudyPlans {
  study_goal_id: string;
  /** The date the plan was built around, in the learner's own timezone. */
  generated_on: string;
  plans: StudyPlan[];
  /** Plans this generation set aside. They are kept, not deleted. */
  superseded_plan_ids: string[];
}

export type StudyPlanCollectionResponse = CollectionEnvelope<StudyPlan>;
export type StudyPlanResponse = DataEnvelope<StudyPlan>;
export type GenerateStudyPlanResponse = DataEnvelope<GeneratedStudyPlans>;
export type PlanItemResponse = DataEnvelope<PlanItem>;

/** What one adaptation produced (PLN-005). */
export interface AdaptedStudyPlans {
  study_goal_id: string;
  /** The date the adapted plan was built around, in the learner's own timezone. */
  adapted_on: string;
  plans: StudyPlan[];
  /** Plans this adaptation set aside. They are kept, not deleted. */
  superseded_plan_ids: string[];
  /** Items whose day had passed with the work undone, now marked `postponed`. */
  postponed_plan_item_ids: string[];
  /** Topics with a completed session, which are not planned again. */
  completed_topic_count: number;
  /** How many topics the adapted plan still covers. */
  remaining_topic_count: number;
}

export type AdaptStudyPlanResponse = DataEnvelope<AdaptedStudyPlans>;

/** What PLN-006 can conclude about a saved week reaching a goal's horizon. */
export const FEASIBILITY_VERDICTS = ["sufficient", "insufficient", "unknown"] as const;

export type FeasibilityVerdict = (typeof FEASIBILITY_VERDICTS)[number];

/**
 * Why a feasibility question could not be answered.
 *
 * Two different gaps, kept apart because they ask the learner for different
 * things: a goal aiming at nothing needs a date, and a goal with no saved week
 * needs a week. A week saved and deliberately kept free is neither -- that is
 * zero minutes, which is an answer.
 */
export type FeasibilityUnknownReason = "no_horizon" | "no_availability_saved";

/**
 * Whether the learner's saved week reaches their goal's horizon (PLN-006).
 *
 * A reading: asking for it writes nothing. Every number is a count or a
 * duration, and there is deliberately no percentage or ratio -- the backend
 * refuses to compute one, and this screen must not derive one either
 * (docs/domain/terminology.md).
 *
 * `reason` is the sentence the backend composed beside the numbers it quotes.
 * The frontend renders it rather than writing its own, as it does for a plan's
 * `generation_reason`, so what a learner reads is what was actually decided.
 */
export interface PlanFeasibility {
  study_goal_id: string;
  /** The learner's own date this was assessed for, from their stored timezone. */
  assessed_on: string;
  verdict: FeasibilityVerdict | string;
  reason: string;
  /** Null unless the verdict is `unknown`. */
  unknown_reason: FeasibilityUnknownReason | string | null;
  /** Null when the goal aims at no examination cycle and no target date. */
  horizon_ends_on: string | null;
  /** Topics on the active roadmap that still have work. */
  remaining_topic_count: number;
  session_minutes: number;
  /** True when the learner set no session length and LearnFlow chose one. */
  session_minutes_chosen_by_planner: boolean;
  /** Calendar days to the horizon, both ends included. */
  study_days: number;
  available_minutes: number;
  required_minutes: number;
  /** Zero when the week is enough, and never negative. */
  shortfall_minutes: number;
  /** How many remaining topics the available time holds a whole session for. */
  coverable_topic_count: number;
}

export type PlanFeasibilityResponse = DataEnvelope<PlanFeasibility>;
