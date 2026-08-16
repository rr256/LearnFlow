/**
 * Reading the learning-resource forms into the requests they make.
 *
 * Kept apart from the server actions so they can be tested as ordinary
 * functions. They hold no catalogue rule: which kinds of material may be
 * registered, what counts as a usable link, whether a topic exists, and what a
 * learner may change are all decided by the backend, which is the only place
 * they can be enforced (docs/development/coding-standards.md). What is checked
 * here is that a form produced something worth sending at all.
 */

import { RESOURCE_STATUSES, RESOURCE_TYPES, type ResourceStatus } from "@/types/resource";

/**
 * What the add or edit form shows after a submission.
 *
 * One shape for both, because both answer the same question — did the change
 * reach the API, and what does the learner now know? The message says which
 * happened; the status only decides how it is announced.
 */
export interface ResourceFormState {
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
export const INITIAL_RESOURCE_FORM_STATE: ResourceFormState = { status: "idle", message: "" };

/** What the control beside one resource shows after a submission. */
export interface ResourceStatusState {
  status: "idle" | "saved" | "error";
  message: string;
}

export const INITIAL_RESOURCE_STATUS_STATE: ResourceStatusState = {
  status: "idle",
  message: "",
};

function trimmed(value: FormDataEntryValue | null): string {
  return typeof value === "string" ? value.trim() : "";
}

/** The six things both resource forms ask for. */
export interface ResourceFields {
  resource_type: string;
  title: string;
  source_label: string | null;
  external_reference: string | null;
  topic_ids: string[];
}

/**
 * Read the fields both forms carry, or null when the form asks for nothing
 * usable.
 *
 * A blank label or link is read as null rather than as an empty string, so the
 * record says the learner left it out rather than storing whitespace — and, on
 * an edit, so clearing a field actually clears it.
 *
 * Three things are refused here rather than sent: a form with no title, one
 * naming a kind of material this build does not offer, and one naming neither a
 * label nor a link. All three are refused by the backend too, and it is the only
 * authority — but a request that cannot succeed is not worth making, and the
 * message can name what is missing while the form is still on screen.
 *
 * Everything else — whether the link is a usable web address, whether each topic
 * exists — is the backend's to judge.
 */
function readFields(form: FormData): ResourceFields | null {
  const title = trimmed(form.get("title"));
  const resourceType = trimmed(form.get("resource_type"));
  const sourceLabel = trimmed(form.get("source_label"));
  const externalReference = trimmed(form.get("external_reference"));

  if (!title || !resourceType) {
    return null;
  }
  if (!(RESOURCE_TYPES as readonly string[]).includes(resourceType)) {
    return null;
  }
  if (!sourceLabel && !externalReference) {
    return null;
  }

  return {
    resource_type: resourceType,
    title,
    source_label: sourceLabel || null,
    external_reference: externalReference || null,
    // `getAll` is what carries a multiple-selection list, and it is empty when
    // the learner chose no topic -- which is allowed: material may be
    // catalogued before it is placed, and an edit may unlink every topic.
    topic_ids: form
      .getAll("topic_ids")
      .map((value) => trimmed(value))
      .filter(Boolean),
  };
}

/** What the register form asks for, or null when it asks for nothing usable. */
export type RegisterResourceSubmission = ResourceFields;

/** Read one registration form into the request it makes (RES-001). */
export function readRegisterSubmission(form: FormData): RegisterResourceSubmission | null {
  return readFields(form);
}

/** What one edit form asks for: the resource, and its six fields. */
export interface EditResourceSubmission {
  resourceId: string;
  changes: ResourceFields;
}

/**
 * Read one edit form into the request it makes (RES-004).
 *
 * Every field is sent, including `topic_ids`, because RES-004 replaces the whole
 * link set when one is supplied and the picker always carries the learner's
 * current selection — so what they see on the form is what is stored. A field
 * they cleared is sent as null, which is how RES-004 spells a clearance.
 *
 * `status` is deliberately **not** among them: putting material aside is its own
 * control, and an edit form that could archive by accident would make a
 * correction indistinguishable from a decision to stop using something.
 */
export function readEditSubmission(form: FormData): EditResourceSubmission | null {
  const resourceId = trimmed(form.get("resource_id"));
  const changes = readFields(form);

  if (!resourceId || !changes) {
    return null;
  }
  return { resourceId, changes };
}

/** What one status form asks for, or null when it asks for nothing usable. */
export interface ResourceStatusSubmission {
  resourceId: string;
  status: ResourceStatus;
}

/**
 * Read the resource identifier and the status a form carries.
 *
 * The status travels in a hidden field rather than on the button, so a
 * submission without JavaScript carries it exactly as a hydrated one does — the
 * shape the plan-item and revision controls both use.
 */
export function readResourceStatusSubmission(form: FormData): ResourceStatusSubmission | null {
  const resourceId = trimmed(form.get("resource_id"));
  const status = trimmed(form.get("status"));

  if (!resourceId || !status) {
    return null;
  }
  if (!(RESOURCE_STATUSES as readonly string[]).includes(status)) {
    return null;
  }
  return { resourceId, status: status as ResourceStatus };
}
