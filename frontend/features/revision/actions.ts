"use server";

/**
 * The write paths for scheduling revisions and recording what became of one.
 *
 * A server action runs on the Next.js server, so the browser still makes no
 * request to the backend: the form posts to this process, which calls the API
 * with the same server-side `API_BASE_URL` every view uses. The API therefore
 * needs no CORS allow-list and no API address reaches a client bundle, which is
 * the position ADR-015 takes and this feature inherits rather than renegotiates.
 *
 * They hold no scheduling rule. How long a topic waits, when it returns, which
 * topics are brought back, and which statuses a revision may move between are
 * all decided by the backend; these map a form onto one API call and map the
 * answer back into something a control can show.
 *
 * **This module exports async functions and nothing else.** A `"use server"`
 * file may export only async functions, and a constant exported from one fails
 * at runtime with a `500` that neither `tsc` nor `next build` reports. The state
 * shapes and their initial values therefore live in `submission.ts`.
 */

import { revalidatePath } from "next/cache";

import {
  readRevisionSubmission,
  type RevisionState,
  type ScheduleState,
} from "@/features/revision/submission";
import { ApiError, scheduleRevisions, updateRevisionStatus } from "@/lib/api-client";
import { REVISION_STATUS_CHANGE_LABELS } from "@/types/revision";

/**
 * REV-004 -- ask for revisions to be scheduled from finished work.
 *
 * The learner asks; nothing schedules on its own. Asking twice creates nothing
 * the second time, so a repeated submission is safe and the message says what
 * the run actually did rather than assuming it wrote something.
 *
 * It takes neither the previous state nor the form: REV-004 has no request body,
 * so there is nothing on the form to read. `useActionState` still calls it with
 * both and JavaScript discards them, which is why the narrower signature is
 * assignable.
 */
export async function scheduleRevisionsAction(): Promise<ScheduleState> {
  try {
    const scheduled = await scheduleRevisions();
    revalidatePath("/revisions");
    return { status: "scheduled", message: scheduled.reason };
  } catch (error) {
    if (error instanceof ApiError) {
      return { status: "error", message: error.message };
    }
    throw error;
  }
}

/**
 * REV-003 -- record what became of one revision.
 *
 * Only the named revision moves: no other revision, no plan item, and no
 * learning stage. The confirmation names what was set rather than saying
 * "saved", so a learner who mis-tapped can see which way it went.
 */
export async function saveRevisionStatus(
  _previous: RevisionState,
  form: FormData,
): Promise<RevisionState> {
  const submission = readRevisionSubmission(form);
  if (!submission) {
    return { status: "error", message: "That is not something a review can be set to." };
  }

  try {
    await updateRevisionStatus(submission.revisionId, submission.status);
    revalidatePath("/revisions");
    return {
      status: "saved",
      message: confirmationFor(submission.status),
    };
  } catch (error) {
    if (error instanceof ApiError) {
      return { status: "error", message: error.message };
    }
    throw error;
  }
}

/**
 * What a learner reads once a status is recorded.
 *
 * Each says what the record now states, and the postponement says where the
 * work goes -- a learner reading "Marked postponed" alone could reasonably
 * conclude something had re-dated it, which is exactly what does not happen.
 */
function confirmationFor(status: keyof typeof REVISION_STATUS_CHANGE_LABELS): string {
  switch (status) {
    case "completed":
      return "Marked reviewed.";
    case "skipped":
      return "Marked skipped. This review will not happen.";
    case "postponed":
      return "Marked postponed. This topic comes back when you schedule revisions again.";
    default:
      return "Put back as due.";
  }
}
