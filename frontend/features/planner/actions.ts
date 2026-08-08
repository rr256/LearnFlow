"use server";

/**
 * The write paths for generating a study plan and completing its items.
 *
 * A server action runs on the Next.js server, so the browser still makes no
 * request to the backend: the form posts to this process, which calls the API
 * with the same server-side `API_BASE_URL` every view uses. The API therefore
 * needs no CORS allow-list and no API address reaches a client bundle, which is
 * the position ADR-015 takes and this feature inherits rather than renegotiates.
 *
 * They hold no planning rule. What a plan contains, what order it goes in, how
 * long a session runs, what happens to the plan it replaces, and which statuses
 * an item may move between are all decided by the backend; these map a form onto
 * one API call and map the answer back into something a control can show.
 *
 * **This module exports async functions and nothing else.** A `"use server"`
 * file may export only async functions, and a constant exported from one fails
 * at runtime with a `500` that neither `tsc` nor `next build` reports. The state
 * shapes and their initial values therefore live in `submission.ts`.
 */

import { revalidatePath } from "next/cache";

import {
  readPlanItemSubmission,
  readPlanSubmission,
  type PlanItemState,
  type PlanState,
} from "@/features/planner/submission";
import { ApiError, generateStudyPlan, updatePlanItemStatus } from "@/lib/api-client";

/**
 * Generate a study plan for the learner's goal.
 *
 * Safe to repeat: generating again supersedes the goal's existing active plans
 * rather than duplicating them, and nothing is deleted. A conflict means setup
 * has not created a learner yet, so the message says what to do about it rather
 * than repeating the backend's wording.
 */
export async function createStudyPlan(_previous: PlanState, form: FormData): Promise<PlanState> {
  const read = readPlanSubmission(form);
  if ("problem" in read) {
    return { status: "error", message: read.problem };
  }

  let generated;
  try {
    generated = await generateStudyPlan(read.studyGoalId);
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    if (error.isUnreachable) {
      return {
        status: "error",
        message:
          "The LearnFlow API could not be reached, so no plan was generated. Check that the backend is running, then try again.",
      };
    }
    if (error.isConflict) {
      return {
        status: "error",
        message: "Complete your learner setup first, then generate a plan here.",
      };
    }
    if (error.isNotFound) {
      return {
        status: "error",
        message: "That study goal is no longer stored. Set your goal again, then generate a plan.",
      };
    }
    return { status: "error", message: error.message };
  }

  // The plan page reads what was generated, so it has to be re-rendered for the
  // new plan to appear rather than the one it replaced.
  revalidatePath("/plan");

  const replaced = generated.superseded_plan_ids.length > 0;
  return {
    status: "generated",
    message: replaced
      ? "Your plan has been rebuilt. The previous one is kept, not deleted."
      : "Your plan is ready.",
  };
}

/**
 * Mark one plan item completed, or return it to planned.
 *
 * Safe to repeat: sending the status an item already holds changes nothing. The
 * rest of the plan is untouched, and nothing is re-planned around what was
 * completed — that is FR-004's work and does not exist yet.
 *
 * A conflict means the item's plan has been superseded, which happens to a
 * learner who rebuilt their plan in another tab. The message says to use the
 * current plan rather than repeating the backend's wording.
 */
export async function savePlanItemStatus(
  _previous: PlanItemState,
  form: FormData,
): Promise<PlanItemState> {
  const read = readPlanItemSubmission(form);
  if ("problem" in read) {
    return { status: "error", message: read.problem };
  }

  let item;
  try {
    item = await updatePlanItemStatus(read.submission.planItemId, read.submission.status);
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    if (error.isUnreachable) {
      return {
        status: "error",
        message:
          "The LearnFlow API could not be reached, so nothing was saved. Check that the backend is running, then try again.",
      };
    }
    if (error.isConflict) {
      return {
        status: "error",
        message:
          "That item belongs to a plan that has been replaced. Reload this page and complete the item on your current plan.",
      };
    }
    if (error.isNotFound) {
      return {
        status: "error",
        message: "That plan item is no longer stored. Reload this page to see your current plan.",
      };
    }
    return { status: "error", message: error.message };
  }

  // The panels are rendered from the plan, so the page has to be re-read for the
  // item to show its new status rather than the one it had.
  revalidatePath("/plan");

  return {
    status: "saved",
    message:
      item.status === "completed" ? "Marked completed." : "Returned to your plan.",
  };
}
