/**
 * Reading an uploaded PDF off a form, and the state an upload comes back in.
 *
 * Separate from `file-actions.ts` because a `"use server"` module may export
 * **only** async functions: a constant exported from one fails at runtime with a
 * `500` that neither `tsc` nor `next build` reports.
 *
 * **The checks here are a courtesy that saves a round trip, never the rule.**
 * The backend refuses a file that is not a PDF, is too large, has too many
 * pages, or is encrypted, whatever a browser allowed — and it is the only place
 * those are decided. What this catches is the empty submit and the obviously
 * wrong pick, with a clearer message than a server round trip would give.
 */

import { MAX_FILE_BYTES, type ResourceFile, readableSize } from "@/types/resource-file";

/** What the upload form knows after a submission. */
export interface ResourceFileFormState {
  /** The file that was stored, or null when nothing was. */
  stored: ResourceFile | null;
  /** Why the upload did not happen, in words a learner can act on. */
  error: string | null;
}

export const INITIAL_RESOURCE_FILE_FORM_STATE: ResourceFileFormState = {
  stored: null,
  error: null,
};

/** What setting a file aside, or bringing it back, reports. */
export interface ResourceFileStatusState {
  error: string | null;
}

export const INITIAL_RESOURCE_FILE_STATUS_STATE: ResourceFileStatusState = { error: null };

/** One submitted upload, or the reason it cannot be sent. */
export interface ResourceFileSubmission {
  resourceId: string;
  file: File;
}

/**
 * Read the chosen file and the resource it belongs to off the form.
 *
 * A browser that submits an empty file input still sends a part — a zero-byte
 * `File` with an empty name — so "nothing chosen" is checked by size and name
 * rather than by the field's absence.
 */
export function readResourceFileSubmission(
  form: FormData,
): ResourceFileSubmission | { error: string } {
  const resourceId = readText(form, "resource_id");
  if (!resourceId) {
    return { error: "That material could not be identified. Reload the page and try again." };
  }

  const chosen = form.get("file");
  if (!(chosen instanceof File) || chosen.size === 0 || !chosen.name) {
    return { error: "Choose a PDF to add." };
  }
  if (!chosen.name.toLowerCase().endsWith(".pdf")) {
    return { error: "Only PDF files can be added here." };
  }
  if (chosen.size > MAX_FILE_BYTES) {
    return {
      error: `That file is ${readableSize(chosen.size)}. The limit is ${readableSize(
        MAX_FILE_BYTES,
      )}.`,
    };
  }
  return { resourceId, file: chosen };
}

/** One submitted status change. */
export interface ResourceFileStatusSubmission {
  fileId: string;
  status: string;
}

/** Read a file's identifier and the status it should move to. */
export function readResourceFileStatusSubmission(
  form: FormData,
): ResourceFileStatusSubmission | { error: string } {
  const fileId = readText(form, "file_id");
  const status = readText(form, "status");

  if (!fileId || !status) {
    return { error: "That file could not be identified. Reload the page and try again." };
  }
  return { fileId, status };
}

/** One trimmed text field, or an empty string when absent or not text. */
function readText(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
}
