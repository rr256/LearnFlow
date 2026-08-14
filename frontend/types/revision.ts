/**
 * Revision types, derived from the REV-001 to REV-004 response contract in
 * docs/api/endpoints.md#revision-endpoints.
 *
 * Nothing here schedules anything. How long a topic waits, when it comes back,
 * and whether it is due are decided by the backend and stored; this file only
 * describes what comes back
 * (docs/development/coding-standards.md#ui-responsibilities).
 *
 * Every revision carries the reason it exists, written when it was created and
 * never rewritten. The frontend renders that sentence rather than composing its
 * own, so what a learner reads is what actually decided the date.
 */

import type { CollectionEnvelope, DataEnvelope } from "@/types/api";

/** The states a revision can be in. */
export type RevisionStatus = "due" | "scheduled" | "completed" | "skipped" | "postponed";

/**
 * The statuses REV-003 accepts as a target.
 *
 * Four of the five the column holds. `scheduled` is deliberately absent: it
 * needs a date nothing collects, so the endpoint refuses it.
 *
 * A learner may move a revision to any of these from any of them. Nothing is
 * one-way, which is why the control offers the other three rather than a single
 * next step — the shape PLN-004 uses for a plan item.
 */
export const REVISION_STATUS_CHANGES = ["completed", "due", "skipped", "postponed"] as const;

export type RevisionStatusChange = (typeof REVISION_STATUS_CHANGES)[number];

/**
 * What each button says, naming the state it moves the revision *to*.
 *
 * A learner returning a week later reads what the button will do rather than an
 * "undo" whose subject has been forgotten. The wording describes the review and
 * never the learner (docs/domain/terminology.md).
 */
export const REVISION_STATUS_CHANGE_LABELS: Record<RevisionStatusChange, string> = {
  completed: "Mark reviewed",
  due: "Put back as due",
  skipped: "Skip this review",
  postponed: "Postpone this review",
};

/**
 * The statuses in which nothing offers a revision again on its own.
 *
 * The frontend's mirror of `SETTLED_REVISION_STATUSES` in
 * `backend/app/application/dto/revision.py`. It decides which items are marked
 * and which the screen groups as still owed; it decides nothing that is stored,
 * and the backend's `is_due` stays authoritative for whether a revision is
 * actually due.
 */
export const SETTLED_REVISION_STATUSES: readonly RevisionStatus[] = [
  "completed",
  "skipped",
  "postponed",
];

/** True when nothing should offer this revision again on its own. */
export function isSettledRevision(status: string): boolean {
  return (SETTLED_REVISION_STATUSES as readonly string[]).includes(status);
}

/**
 * What a learner reads beside a revision the API sent in a settled status.
 *
 * `due` and `scheduled` have no label: a review nobody has answered about needs
 * no announcement.
 */
export const REVISION_SETTLED_LABELS: Partial<Record<RevisionStatus, string>> = {
  completed: "Marked reviewed",
  skipped: "Marked skipped",
  postponed: "Marked postponed",
};

/** Why a revision exists. */
export type RevisionTrigger = "completed_plan_item" | "completed_revision";

/** What a learner reads for each trigger. */
export const REVISION_TRIGGER_LABELS: Record<RevisionTrigger, string> = {
  completed_plan_item: "After finished study",
  completed_revision: "After your last review",
};

/** The topic a revision recommends reviewing. */
export interface RevisionTopic {
  id: string;
  code: string | null;
  name: string;
  subject_id: string;
  subject_name: string;
}

/** One topic coming back for review. */
export interface Revision {
  id: string;
  /** Null only when the topic is no longer stored. */
  topic: RevisionTopic | null;
  due_on: string;
  /** Always null: naming a day for a revision is not built. */
  scheduled_for: string | null;
  status: RevisionStatus | string;
  trigger_type: RevisionTrigger | string;
  recommendation_reason: string | null;
  /** Null unless `status` is `completed`, and cleared by any move off it. */
  completed_at: string | null;
  /**
   * Whether this review is owed today, decided by the backend.
   *
   * Read rather than derived: what counts as due is a domain rule, and a screen
   * computing its own could disagree with the backend that owns it.
   */
  is_due: boolean;
}

/** What one scheduling run produced (REV-004). */
export interface ScheduledRevisions {
  /** The date the run was made for, in the learner's own timezone. */
  scheduled_on: string;
  revisions: Revision[];
  /** Finished topics left alone because they already had a revision. */
  already_scheduled_topic_count: number;
  reason: string;
}

export type RevisionCollectionResponse = CollectionEnvelope<Revision>;
export type RevisionResponse = DataEnvelope<Revision>;
export type ScheduleRevisionsResponse = DataEnvelope<{
  scheduled_on: string;
  created: Revision[];
  already_scheduled_topic_count: number;
  reason: string;
}>;
