/**
 * Reading the revision forms into the requests they make.
 *
 * Kept apart from the server actions so they can be tested as ordinary
 * functions. They hold no scheduling rule: how long a topic waits, when it comes
 * back, whether it is due, and which statuses a revision may move between are
 * all decided by the backend, which is the only place they can be enforced
 * (docs/development/coding-standards.md). What is checked here is that a form
 * produced something worth sending at all.
 */

import { REVISION_STATUS_CHANGES, type RevisionStatusChange } from "@/types/revision";

/** What the schedule button shows after a submission. */
export interface ScheduleState {
  status: "idle" | "scheduled" | "error";
  message: string;
}

/**
 * The state before anything has been submitted.
 *
 * It lives here rather than beside the action because a `"use server"` module
 * may export only async functions -- a constant exported from one fails at
 * runtime, which neither the type checker nor the production build reports.
 */
export const INITIAL_SCHEDULE_STATE: ScheduleState = { status: "idle", message: "" };

/** What the control beside one revision shows after a submission. */
export interface RevisionState {
  status: "idle" | "saved" | "error";
  message: string;
}

export const INITIAL_REVISION_STATE: RevisionState = { status: "idle", message: "" };

function trimmed(value: FormDataEntryValue | null): string {
  return typeof value === "string" ? value.trim() : "";
}

/** What one revision status form asks for, or null when it asks for nothing usable. */
export interface RevisionSubmission {
  revisionId: string;
  status: RevisionStatusChange;
}

/**
 * Read the revision identifier and the status a form carries.
 *
 * The status travels in a hidden field rather than on the button, so a
 * submission without JavaScript carries it exactly as a hydrated one does.
 *
 * A status this build does not offer is refused here rather than sent: the
 * backend refuses it too, and it is the only authority, but a request that
 * cannot succeed is not worth making.
 */
export function readRevisionSubmission(form: FormData): RevisionSubmission | null {
  const revisionId = trimmed(form.get("revision_id"));
  const status = trimmed(form.get("status"));

  if (!revisionId || !status) {
    return null;
  }
  if (!(REVISION_STATUS_CHANGES as readonly string[]).includes(status)) {
    return null;
  }
  return { revisionId, status: status as RevisionStatusChange };
}
