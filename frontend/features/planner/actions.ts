"use server";

/**
 * The write paths for generating a study plan, completing its items, and
 * adapting it around what happened.
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
  readAdaptSubmission,
  readPlanItemSubmission,
  readPlanSubmission,
  type AdaptState,
  type PlanItemState,
  type PlanState,
} from "@/features/planner/submission";
import {
  ApiError,
  adaptStudyPlan,
  generateStudyPlan,
  updatePlanItemStatus,
} from "@/lib/api-client";

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
 * Mark one plan item completed, skipped, or postponed, or return it to planned.
 *
 * Safe to repeat: sending the status an item already holds changes nothing. The
 * rest of the plan is untouched, and nothing is re-planned around what the
 * learner said — rebuilding the plan is `adaptPlan` below, which they ask for.
 * Postponing in particular moves nothing on its own: the work is carried onto
 * the plan the learner's next adaptation writes.
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

  return { status: "saved", message: SAVED_MESSAGES[item.status] ?? "Saved." };
}

/**
 * What the control says once the API has confirmed the move.
 *
 * Keyed by the status the API sent back rather than the one the form asked for,
 * so the message reports what was stored. A status this build does not recognise
 * falls back to a plain acknowledgement rather than claiming something untrue.
 *
 * The skip message says the topic comes back, because a learner who reads
 * "skipped" without it could reasonably think they have dropped the topic for
 * good — which is not what PLN-004 does. The postpone message says where the
 * work goes and who moves it, because postponing is the one status that names a
 * later plan and nothing here writes that plan on its own.
 */
const SAVED_MESSAGES: Readonly<Record<string, string>> = {
  completed: "Marked completed.",
  planned: "Returned to your plan.",
  skipped: "Marked skipped. This topic is planned again when you update your plan.",
  postponed: "Marked postponed. This work is placed again when you update your plan.",
};


/**
 * Adapt the learner's active plan around what has and has not happened.
 *
 * The learner asks for this; nothing adapts on its own. Topics they have
 * completed are not planned again, and work whose day passed is carried forward.
 *
 * A conflict means the goal has no active plan yet, so the message points at
 * generating one rather than repeating the backend's wording.
 */
export async function adaptPlan(_previous: AdaptState, form: FormData): Promise<AdaptState> {
  const read = readAdaptSubmission(form);
  if ("problem" in read) {
    return { status: "error", message: read.problem };
  }

  let adapted;
  try {
    adapted = await adaptStudyPlan(read.studyGoalId);
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    if (error.isUnreachable) {
      return {
        status: "error",
        message:
          "The LearnFlow API could not be reached, so nothing was adapted. Check that the backend is running, then try again.",
      };
    }
    if (error.isConflict) {
      return {
        status: "error",
        message: "There is no plan to adapt yet. Generate one first, then come back to this.",
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

  // The panels are rendered from the plan, so the page has to be re-read for the
  // adapted one to appear rather than the one it replaced.
  revalidatePath("/plan");

  const carried =
    adapted.postponed_plan_item_ids.length > 0
      ? ` ${adapted.postponed_plan_item_ids.length} items whose day had passed were carried forward.`
      : "";
  const done =
    adapted.completed_topic_count > 0
      ? ` ${adapted.completed_topic_count} topics you have completed are not planned again.`
      : "";
  return {
    status: "adapted",
    message: `Your plan has been rebuilt around where you are.${done}${carried} The previous one is kept, not deleted.`,
  };
}
