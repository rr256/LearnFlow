"use server";

/**
 * The write paths for cataloguing study material, correcting it, and putting it
 * aside.
 *
 * A server action runs on the Next.js server, so the browser still makes no
 * request to the backend: the form posts to this process, which calls the API
 * with the same server-side `API_BASE_URL` every view uses. The API therefore
 * needs no CORS allow-list and no API address reaches a client bundle, which is
 * the position ADR-015 takes and this feature inherits rather than renegotiates.
 *
 * They hold no catalogue rule. Which kinds of material may be registered, what
 * counts as a usable link, which topics exist, and what a learner may change are
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
  readEditSubmission,
  readRegisterSubmission,
  readResourceStatusSubmission,
  type ResourceFormState,
  type ResourceStatusState,
} from "@/features/resources/submission";
import { ApiError, registerResource, updateResource } from "@/lib/api-client";

/**
 * Everywhere a change to the catalogue is visible.
 *
 * Material linked to a topic changes what the curriculum view and the revision
 * list show as well as the catalogue itself, so all three are revalidated
 * whichever write happened.
 */
function revalidateEverywhereMaterialAppears(): void {
  revalidatePath("/resources");
  revalidatePath("/revisions");
  revalidatePath("/curriculum", "layout");
}

/** What a learner reads when a form asked for something that cannot be sent. */
const UNUSABLE_FORM =
  "Give the material a title, a kind, and either a link or a note of where it is.";

/**
 * RES-001 — record where one piece of study material is.
 *
 * The confirmation names what was catalogued rather than saying "saved", so a
 * learner adding several in a row can see which one landed.
 */
export async function registerResourceAction(
  _previous: ResourceFormState,
  form: FormData,
): Promise<ResourceFormState> {
  const submission = readRegisterSubmission(form);
  if (!submission) {
    return { status: "error", message: UNUSABLE_FORM };
  }

  try {
    const resource = await registerResource(submission);
    revalidateEverywhereMaterialAppears();
    return { status: "saved", message: `Added ${resource.title} to your material.` };
  } catch (error) {
    if (error instanceof ApiError) {
      return { status: "error", message: error.message };
    }
    throw error;
  }
}

/**
 * RES-004 — correct what one piece of material says, and which topics it covers.
 *
 * Every field the form carries is sent, including `topic_ids`: RES-004 replaces
 * the whole link set when one is supplied, so what the learner sees selected is
 * what is stored. A field they cleared is sent as null, which is how RES-004
 * spells a clearance — and the backend refuses a change that would leave the
 * material saying where it is neither in words nor by a link, which is reported
 * here rather than swallowed.
 *
 * **This cannot archive.** `status` is not among the fields, so a correction and
 * a decision to stop using something stay separate actions.
 *
 * Only the named resource moves: no other resource, no learning stage, no plan,
 * no plan item, and no revision.
 */
export async function saveResourceEdit(
  _previous: ResourceFormState,
  form: FormData,
): Promise<ResourceFormState> {
  const submission = readEditSubmission(form);
  if (!submission) {
    return { status: "error", message: UNUSABLE_FORM };
  }

  try {
    const resource = await updateResource(submission.resourceId, submission.changes);
    revalidateEverywhereMaterialAppears();
    return { status: "saved", message: `Saved your changes to ${resource.title}.` };
  } catch (error) {
    if (error instanceof ApiError) {
      return { status: "error", message: error.message };
    }
    throw error;
  }
}

/**
 * RES-004 — put one piece of material aside, or bring it back.
 *
 * **Nothing is deleted.** Archiving is a statement that the learner is not using
 * something now, and it is reversible from the same screen — which is why the
 * catalogue still lists what has been put aside.
 *
 * Only the named resource moves: no other resource, no learning stage, no plan,
 * no plan item, and no revision.
 */
export async function saveResourceStatus(
  _previous: ResourceStatusState,
  form: FormData,
): Promise<ResourceStatusState> {
  const submission = readResourceStatusSubmission(form);
  if (!submission) {
    return { status: "error", message: "That is not something material can be set to." };
  }

  try {
    await updateResource(submission.resourceId, { status: submission.status });
    revalidateEverywhereMaterialAppears();
    return {
      status: "saved",
      message:
        submission.status === "archived"
          ? "Put aside. It stays in your catalogue and you can put it back."
          : "Put back in your catalogue.",
    };
  } catch (error) {
    if (error instanceof ApiError) {
      return { status: "error", message: error.message };
    }
    throw error;
  }
}
