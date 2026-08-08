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

/** The states a plan item can be in. Generation writes `planned`. */
export type PlanItemStatus = "planned" | "completed" | "skipped" | "postponed";

/**
 * The statuses PLN-004 accepts as a target.
 *
 * A subset of the statuses the column holds: `skipped` and `postponed` are
 * approved and the API does not yet accept them, so offering either would be a
 * control that always fails.
 */
export const PLAN_ITEM_STATUS_CHANGES = ["planned", "completed"] as const;

export type PlanItemStatusChange = (typeof PLAN_ITEM_STATUS_CHANGES)[number];

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
