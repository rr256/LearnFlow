/**
 * Reading the resource-note forms into the requests they make.
 *
 * Kept apart from the server actions so they can be tested as ordinary
 * functions. They hold no rule of their own: how long a note may be, how many
 * one resource may hold, whether its material is still in the catalogue, and
 * what a learner may change are all decided by the backend, which is the only
 * place they can be enforced (docs/development/coding-standards.md). What is
 * checked here is that a form produced something worth sending at all.
 *
 * **A note's text is never trimmed inside.** Only surrounding whitespace is
 * removed, exactly as the backend does, so a learner's line breaks, blank lines,
 * and indentation reach the API as they typed them. Every other form field in
 * this product is trimmed whole; a pasted passage is the one place that would
 * lose something.
 */

import { RESOURCE_NOTE_STATUSES, type ResourceNoteStatus } from "@/types/resource-note";

/**
 * What the note form shows after a submission.
 *
 * One shape for writing and correcting, because both answer the same question —
 * did the change reach the API, and what does the learner now know?
 */
export interface ResourceNoteFormState {
  status: "idle" | "saved" | "error";
  message: string;
}

/**
 * The state before anything has been submitted.
 *
 * It lives here rather than beside the action because a `"use server"` module
 * may export only async functions -- a constant exported from one fails at
 * runtime, which neither the type checker nor the production build reports.
 */
export const INITIAL_RESOURCE_NOTE_FORM_STATE: ResourceNoteFormState = {
  status: "idle",
  message: "",
};

/** What the control beside one note shows after a submission. */
export interface ResourceNoteStatusState {
  status: "idle" | "saved" | "error";
  message: string;
}

export const INITIAL_RESOURCE_NOTE_STATUS_STATE: ResourceNoteStatusState = {
  status: "idle",
  message: "",
};

function trimmed(value: FormDataEntryValue | null): string {
  return typeof value === "string" ? value.trim() : "";
}

/** The two things a note form asks for. */
export interface ResourceNoteFields {
  title: string;
  body: string;
}

/**
 * Read the fields a note form carries, or null when it asks for nothing usable.
 *
 * Two things are refused here rather than sent: a form with no title, and one
 * with no text in it. Both are refused by the backend too, and it is the only
 * authority — but a request that cannot succeed is not worth making, and the
 * message can name what is missing while the form is still on screen.
 *
 * Everything else — how long a note may be, how many one resource may hold,
 * whether its material is still in the catalogue — is the backend's to judge.
 */
function readFields(form: FormData): ResourceNoteFields | null {
  const title = trimmed(form.get("title"));
  const raw = form.get("body");
  // Surrounding whitespace only. What is inside is the learner's own text.
  const body = typeof raw === "string" ? raw.trim() : "";

  if (!title || !body) {
    return null;
  }
  return { title, body };
}

/** What one write form asks for: the material, and the note's two fields. */
export interface WriteResourceNoteSubmission {
  resourceId: string;
  note: ResourceNoteFields;
}

/** Read one write form into the request it makes (RES-009). */
export function readWriteNoteSubmission(form: FormData): WriteResourceNoteSubmission | null {
  const resourceId = trimmed(form.get("resource_id"));
  const note = readFields(form);

  if (!resourceId || !note) {
    return null;
  }
  return { resourceId, note };
}

/** What one correction form asks for: the note, and its two fields. */
export interface EditResourceNoteSubmission {
  noteId: string;
  changes: ResourceNoteFields;
}

/**
 * Read one correction form into the request it makes (RES-012).
 *
 * Both fields are sent, because the form always carries what is currently
 * stored, so what the learner sees is what is saved.
 *
 * `status` is deliberately **not** among them: putting a note aside is its own
 * control, and a correction form that could archive by accident would make
 * correcting a note indistinguishable from deciding to set it down — the
 * separation RES-004's two controls already keep for a resource.
 */
export function readEditNoteSubmission(form: FormData): EditResourceNoteSubmission | null {
  const noteId = trimmed(form.get("note_id"));
  const changes = readFields(form);

  if (!noteId || !changes) {
    return null;
  }
  return { noteId, changes };
}

/** What one note status form asks for, or null when it asks for nothing usable. */
export interface ResourceNoteStatusSubmission {
  noteId: string;
  status: ResourceNoteStatus;
}

/**
 * Read the note identifier and the status a form carries.
 *
 * The status travels in a hidden field rather than on the button, so a
 * submission without JavaScript carries it exactly as a hydrated one does — the
 * shape the resource, plan-item, and revision controls all use.
 */
export function readNoteStatusSubmission(form: FormData): ResourceNoteStatusSubmission | null {
  const noteId = trimmed(form.get("note_id"));
  const status = trimmed(form.get("status"));

  if (!noteId || !status) {
    return null;
  }
  if (!(RESOURCE_NOTE_STATUSES as readonly string[]).includes(status)) {
    return null;
  }
  return { noteId, status: status as ResourceNoteStatus };
}
