/**
 * Resource-note types, derived from the RES-009 to RES-012 response contract in
 * docs/api/endpoints.md#resource-and-ingestion-endpoints.
 *
 * A **resource note** is text the learner typed or pasted themselves, kept
 * against one piece of their study material. It is the first content LearnFlow
 * stores rather than points at, and deliberately the only kind: nothing here
 * uploads a file, fetches an address, or reads anything from the learner's
 * machine.
 *
 * `body` is **plain text and is rendered as plain text**. Nothing in this
 * frontend parses it as HTML or Markdown, and nothing passes it to
 * `dangerouslySetInnerHTML` — React escapes it, and CSS `white-space: pre-wrap`
 * is what preserves the learner's own line breaks. A pasted tag is therefore
 * something a learner reads, never something a browser runs.
 *
 * Nothing here recommends, ranks, scores, or counts anything. A resource's notes
 * are the ones the learner wrote, in the order the API returned them
 * (docs/development/coding-standards.md#ui-responsibilities).
 */

import type { CollectionEnvelope, DataEnvelope } from "@/types/api";

/**
 * How much text one note may hold, mirroring the backend's own bound.
 *
 * Used only to set `maxLength` on the text area, as a courtesy to a learner
 * pasting something long. **The backend is the authority**: it refuses an
 * over-long note whatever a browser allowed, so this number being wrong would
 * cost a helpful hint rather than the rule
 * (docs/development/coding-standards.md#ui-responsibilities).
 */
export const MAX_NOTE_BODY_LENGTH = 20_000;

/** The statuses a note can be in. */
export const RESOURCE_NOTE_STATUSES = ["active", "archived"] as const;

export type ResourceNoteStatus = (typeof RESOURCE_NOTE_STATUSES)[number];

/**
 * What each status control says, naming the state it moves the note *to*.
 *
 * Nothing deletes: putting a note aside is reversible, so both directions are
 * offered and neither is final.
 */
export const RESOURCE_NOTE_STATUS_LABELS: Record<ResourceNoteStatus, string> = {
  active: "Put this note back",
  archived: "Put this note aside",
};

/** True when the API sent a status this build offers a control for. */
export function isOfferedNoteStatus(value: string): value is ResourceNoteStatus {
  return (RESOURCE_NOTE_STATUSES as readonly string[]).includes(value);
}

/** True when a note is one the learner is currently using. */
export function isKeptNote(note: ResourceNote): boolean {
  return note.status === "active";
}

/** One note a learner keeps against a piece of their study material. */
export interface ResourceNote {
  id: string;
  /** The material this note was written against. */
  resource_id: string;
  title: string;
  /** The learner's own text, exactly as they stored it. Never markup. */
  body: string;
  status: ResourceNoteStatus | string;
}

/** What RES-009 is asked to keep. */
export interface NewResourceNote {
  title: string;
  body: string;
}

/**
 * What RES-012 is asked to change.
 *
 * A field left out is not touched. No field may be null: a note always has a
 * title, a body, and a status.
 */
export interface ResourceNoteUpdate {
  title?: string;
  body?: string;
  status?: string;
}

export type ResourceNoteCollectionResponse = CollectionEnvelope<ResourceNote>;
export type ResourceNoteResponse = DataEnvelope<ResourceNote>;
