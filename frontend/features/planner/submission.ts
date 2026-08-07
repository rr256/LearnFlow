/**
 * Reading the generate-plan form into the request it makes.
 *
 * Kept apart from the server action so it can be tested as an ordinary function.
 * It holds no planning rule: what a plan contains, what order it goes in, and
 * which day each item falls on are all decided by the backend, which is the only
 * place they can be enforced (docs/development/coding-standards.md). What it
 * checks here is that the form produced something worth sending at all.
 */

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
