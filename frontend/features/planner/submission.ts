/**
 * Reading the planner's forms into the requests they make.
 *
 * Kept apart from the server actions so they can be tested as ordinary
 * functions. They hold no planning rule: what a plan contains, what order it
 * goes in, which day each item falls on, and which statuses an item may move
 * between are all decided by the backend, which is the only place they can be
 * enforced (docs/development/coding-standards.md). What is checked here is that
 * a form produced something worth sending at all.
 */

import { PLAN_ITEM_STATUS_CHANGES, type PlanItemStatusChange } from "@/types/study-plan";

/** What the button shows after a submission. */
export interface PlanState {
  status: "idle" | "generated" | "error";
  message: string;
}

/**
 * The state before anything has been submitted.
 *
 * It lives here rather than beside the action because a `"use server"` module may
 * export only async functions -- a constant exported from one fails at runtime,
 * which neither the type checker nor the production build reports.
 */
export const INITIAL_PLAN_STATE: PlanState = { status: "idle", message: "" };

function trimmed(value: FormDataEntryValue | null): string {
  return typeof value === "string" ? value.trim() : "";
}

/**
 * Read one submission of the generate-plan form.
 *
 * @returns The goal to plan for, or the reason it could not be read.
 */
export function readPlanSubmission(
  form: FormData,
): { studyGoalId: string } | { problem: string } {
  const studyGoalId = trimmed(form.get("study_goal_id"));
  if (!studyGoalId) {
    return { problem: "That form did not say which study goal to plan for." };
  }
  return { studyGoalId };
}

/** What one submission of a plan-item form asks for. */
export interface PlanItemSubmission {
  planItemId: string;
  status: PlanItemStatusChange;
}

/** What the control on one plan item shows after a submission. */
export interface PlanItemState {
  status: "idle" | "saved" | "error";
  message: string;
}

/** The state before anything has been submitted, for the reason above. */
export const INITIAL_PLAN_ITEM_STATE: PlanItemState = { status: "idle", message: "" };

/** True when a string is a status this build may ask the API for. */
export function isPlanItemStatusChange(value: string): value is PlanItemStatusChange {
  return (PLAN_ITEM_STATUS_CHANGES as readonly string[]).includes(value);
}

/**
 * Read one submission of a plan-item form.
 *
 * @returns The submission, or the reason it could not be built.
 */
export function readPlanItemSubmission(
  form: FormData,
): { submission: PlanItemSubmission } | { problem: string } {
  const planItemId = trimmed(form.get("plan_item_id"));
  if (!planItemId) {
    return { problem: "That form did not say which plan item it was for." };
  }

  const status = trimmed(form.get("status"));
  if (!isPlanItemStatusChange(status)) {
    return {
      problem: "A plan item can only be marked completed or skipped, or returned to planned.",
    };
  }

  return { submission: { planItemId, status } };
}

/** What the adapt control shows after a submission. */
export interface AdaptState {
  status: "idle" | "adapted" | "error";
  message: string;
}

/** The state before anything has been submitted, for the reason above. */
export const INITIAL_ADAPT_STATE: AdaptState = { status: "idle", message: "" };

/**
 * Read one submission of the adapt form.
 *
 * It carries only the goal. Everything adaptation acts on is already stored, so
 * there is nothing else a form could truthfully send.
 *
 * @returns The goal to adapt, or the reason it could not be read.
 */
export function readAdaptSubmission(
  form: FormData,
): { studyGoalId: string } | { problem: string } {
  const studyGoalId = trimmed(form.get("study_goal_id"));
  if (!studyGoalId) {
    return { problem: "That form did not say which study goal to adapt." };
  }
  return { studyGoalId };
}
