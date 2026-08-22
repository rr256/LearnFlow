"use server";

/**
 * The write paths for adding a PDF to a resource, and for setting one aside.
 *
 * A server action runs on the Next.js server, so **the browser never reaches the
 * backend**: the form posts a `multipart/form-data` body to this process, which
 * forwards the file to the API with the same server-side `API_BASE_URL` every
 * view uses. No API address reaches a client bundle, and no CORS configuration
 * exists — the position ADR-015 takes, which this feature inherits rather than
 * renegotiates.
 *
 * It holds no rule about what may be stored. Which files are acceptable, how
 * large they may be, how many pages they may have, and how many one resource may
 * hold are all decided by the backend; these map a form onto one API call and
 * map the answer back into something a control can show.
 *
 * **One action here destroys data.** `removeResourceFileAction` deletes a stored
 * file and its bytes permanently (RES-018), for a learner who chose the wrong
 * document. Setting a file aside stays the reversible option and is what the
 * screen offers first.
 *
 * **This module exports async functions and nothing else.** A `"use server"`
 * file may export only async functions; the state shapes and their initial
 * values live in `file-submission.ts`.
 */

import { revalidatePath } from "next/cache";

import type { RemoveState } from "@/features/resources/RemoveControl";

import {
  readResourceFileStatusSubmission,
  readResourceFileSubmission,
  type ResourceFileFormState,
  type ResourceFileStatusState,
} from "@/features/resources/file-submission";
import {
  ApiError,
  deleteResourceFile,
  updateResourceFile,
  uploadResourceFile,
} from "@/lib/api-client";

/**
 * Everywhere a change to a resource's files is visible.
 *
 * Only `/resources`: files are shown there and nowhere else. The curriculum
 * view, `/revisions`, `/plan`, and `/plan/today` show a topic's material
 * unchanged and gain no file list, so revalidating them would say something had
 * changed when nothing there had.
 */
function revalidateWhereFilesAppear(): void {
  revalidatePath("/resources");
}

/**
 * RES-014 — store one PDF against a resource.
 *
 * The file arrives as part of the form and is forwarded straight to the API; it
 * is never written to the Next.js server's own filesystem, and its bytes are not
 * held beyond the request.
 */
export async function uploadResourceFileAction(
  _previous: ResourceFileFormState,
  form: FormData,
): Promise<ResourceFileFormState> {
  const submitted = readResourceFileSubmission(form);
  if ("error" in submitted) {
    return { stored: null, error: submitted.error };
  }

  try {
    const stored = await uploadResourceFile(submitted.resourceId, submitted.file);
    revalidateWhereFilesAppear();
    return { stored, error: null };
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    return { stored: null, error: messageFor(error) };
  }
}

/**
 * RES-017 — set a stored PDF aside, or bring it back.
 *
 * Reversible, and it removes nothing.
 */
export async function setResourceFileStatusAction(
  _previous: ResourceFileStatusState,
  form: FormData,
): Promise<ResourceFileStatusState> {
  const submitted = readResourceFileStatusSubmission(form);
  if ("error" in submitted) {
    return { error: submitted.error };
  }

  try {
    await updateResourceFile(submitted.fileId, submitted.status);
    revalidateWhereFilesAppear();
    return { error: null };
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    return { error: messageFor(error) };
  }
}

/**
 * What to tell the learner about a refused request.
 *
 * The API's own message is used where it has one, because it names the rule that
 * was broken — the size limit, the page limit, the encryption, the ceiling.
 * **No such message repeats the filename or any byte of the file**, which the
 * backend guarantees and its tests assert.
 */
function messageFor(error: ApiError): string {
  if (error.isUnreachable) {
    return "LearnFlow could not reach its own backend, so nothing was stored.";
  }
  if (error.isConflict) {
    return error.message;
  }
  if (error.isNotFound) {
    return "That material is no longer in your catalogue. Reload the page and try again.";
  }
  return error.message;
}

/**
 * RES-018 — remove a stored PDF permanently.
 *
 * **Irreversible.** The screen puts this behind a disclosure the learner has to
 * open first, so it takes two deliberate actions and cannot be reached by one
 * stray click on a list of files.
 */
export async function removeResourceFileAction(
  _previous: RemoveState,
  form: FormData,
): Promise<RemoveState> {
  const fileId = form.get("file_id");
  if (typeof fileId !== "string" || !fileId.trim()) {
    return { message: "That file could not be identified. Reload the page and try again." };
  }

  try {
    await deleteResourceFile(fileId.trim());
    revalidateWhereFilesAppear();
    return { message: null };
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    return { message: messageFor(error) };
  }
}
