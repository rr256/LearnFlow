"use server";

/**
 * The write path for generating a study plan.
 *
 * A server action runs on the Next.js server, so the browser still makes no
 * request to the backend: the form posts to this process, which calls the API
 * with the same server-side `API_BASE_URL` every view uses. The API therefore
 * needs no CORS allow-list and no API address reaches a client bundle, which is
 * the position ADR-015 takes and this feature inherits rather than renegotiates.
 *
 * It holds no planning rule. What a plan contains, what order it goes in, how
 * long a session runs, and what happens to the plan it replaces are all decided
 * by the backend; this maps a form onto one API call and maps the answer back
 * into something the button can show.
 *
 * **This module exports one async function and nothing else.** A `"use server"`
 * file may export only async functions, and a constant exported from one fails
 * at runtime with a `500` that neither `tsc` nor `next build` reports. The state
 * shape and its initial value therefore live in `submission.ts`.
 */

import { revalidatePath } from "next/cache";

import { readPlanSubmission, type PlanState } from "@/features/planner/submission";
import { ApiError, generateStudyPlan } from "@/lib/api-client";

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
