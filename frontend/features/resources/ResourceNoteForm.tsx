"use client";

import { useActionState, useId } from "react";

import styles from "@/features/resources/ResourceNoteForm.module.css";
import { saveResourceNoteEdit, writeResourceNoteAction } from "@/features/resources/actions";
import {
  INITIAL_RESOURCE_NOTE_FORM_STATE,
  type ResourceNoteFormState,
} from "@/features/resources/note-submission";
import { MAX_NOTE_BODY_LENGTH, type ResourceNote } from "@/types/resource-note";

interface ResourceNoteFormProps {
  /** The material this note belongs to. Required when writing a new one. */
  resourceId: string;
  /**
   * The note being corrected, or undefined to write a new one.
   *
   * Writing and correcting are one form because they ask for the same two
   * things. What differs is where the answers go — RES-009 or RES-012 — and
   * whether the fields start empty or filled.
   */
  note?: ResourceNote;
}

/**
 * Where a learner writes or pastes their own notes on a piece of material.
 *
 * **This is the one place in LearnFlow that stores content rather than a
 * pointer to it**, and the boundary around it is narrow: the learner types or
 * pastes, and that is all. There is no file input, no address to fetch, and no
 * import — nothing here reads anything from their machine, which is the same
 * reason `ResourceForm` has no file input either.
 *
 * **What is written stays on this machine.** Nothing sends a note anywhere or
 * reads it with an AI model. One thing does read it: the topic search at
 * `/resources/search`, which runs locally and only when the learner asks. The
 * form says exactly that, because NFR-001 asks for the data-sharing position to
 * be clear before it matters rather than after — and a promise that quietly
 * stopped being true would be worse than none. See ADR-038.
 *
 * A client component only so it can report what the last submission did. It
 * calls no API itself: the submission goes to a server action, so the browser
 * still never reaches the backend, and the form posts natively without
 * JavaScript.
 *
 * The `maxLength` on the text area is a courtesy, not the rule. The backend
 * refuses an over-long note whatever a browser allowed, which is where the limit
 * is actually enforced.
 */
export function ResourceNoteForm({ resourceId, note }: ResourceNoteFormProps) {
  const editing = note !== undefined;
  const [state, submit, pending] = useActionState<ResourceNoteFormState, FormData>(
    editing ? saveResourceNoteEdit : writeResourceNoteAction,
    INITIAL_RESOURCE_NOTE_FORM_STATE,
  );
  const titleId = useId();
  const bodyId = useId();
  const messageId = useId();

  return (
    <form action={submit} className={styles.form}>
      {editing ? (
        <input type="hidden" name="note_id" value={note.id} />
      ) : (
        <input type="hidden" name="resource_id" value={resourceId} />
      )}

      <p className={styles.hint}>
        {editing
          ? "Correct the note and save. Your text replaces what is stored."
          : "Write or paste what you want to keep from this material — your own notes, or a passage you have copied out. It is stored on this computer and never sent anywhere. Nothing reads your notes except the topic search on this machine, which runs only when you ask for it, and no AI model ever sees them."}
      </p>

      <div className={styles.field}>
        <label htmlFor={titleId}>Note title</label>
        <input
          defaultValue={note?.title ?? ""}
          id={titleId}
          maxLength={300}
          name="title"
          required
          type="text"
        />
        <p className={styles.fieldHint}>
          What to call it, so you can find it again without opening it.
        </p>
      </div>

      <div className={styles.field}>
        <label htmlFor={bodyId}>Your text</label>
        <textarea
          defaultValue={note?.body ?? ""}
          id={bodyId}
          maxLength={MAX_NOTE_BODY_LENGTH}
          name="body"
          required
          rows={editing ? 12 : 8}
        />
        <p className={styles.fieldHint}>
          Plain text. Your line breaks and spacing are kept exactly as you type them, and
          nothing is formatted, shortened, or rewritten.
        </p>
      </div>

      <div className={styles.actions}>
        <button disabled={pending} type="submit">
          {editing ? "Save this note" : "Keep this note"}
        </button>
        {state.status === "idle" ? null : (
          <p
            className={state.status === "error" ? styles.failed : styles.saved}
            id={messageId}
            role={state.status === "error" ? "alert" : "status"}
          >
            {state.message}
          </p>
        )}
      </div>
    </form>
  );
}
