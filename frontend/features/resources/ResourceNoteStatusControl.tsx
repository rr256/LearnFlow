"use client";

import { useActionState, useId } from "react";

import styles from "@/features/resources/ResourceNoteStatusControl.module.css";
import { saveResourceNoteStatus } from "@/features/resources/actions";
import {
  INITIAL_RESOURCE_NOTE_STATUS_STATE,
  type ResourceNoteStatusState,
} from "@/features/resources/note-submission";
import {
  RESOURCE_NOTE_STATUS_LABELS,
  isOfferedNoteStatus,
  type ResourceNoteStatus,
} from "@/types/resource-note";

interface ResourceNoteStatusControlProps {
  noteId: string;
  /** Named in the button's accessible label, so several stay distinguishable. */
  title: string;
  /** The note's stored status, as the API sent it. */
  status: string;
}

/**
 * Where a learner puts one note aside, or brings it back.
 *
 * **Nothing here deletes.** Putting a note aside says the learner is not using
 * it now, and it is reversible from this same control — which is why the
 * material goes on listing it. That is ADR-032's position for a resource applied
 * to the text kept against one.
 *
 * A client component only so it can show the result of the last submission
 * beside the note it acted on. It calls no API itself: the submission goes to a
 * server action, so the browser still never reaches the backend.
 *
 * `useActionState` degrades without JavaScript — the form posts natively and the
 * page re-renders — so putting a note aside does not depend on a hydrated
 * bundle. The status travels in a hidden field rather than on the button, so a
 * scriptless submission carries it exactly as a hydrated one does.
 */
export function ResourceNoteStatusControl({
  noteId,
  title,
  status,
}: ResourceNoteStatusControlProps) {
  const [state, submit, pending] = useActionState<ResourceNoteStatusState, FormData>(
    saveResourceNoteStatus,
    INITIAL_RESOURCE_NOTE_STATUS_STATE,
  );
  const messageId = useId();

  if (!isOfferedNoteStatus(status)) {
    return <p className={styles.unmovable}>Status: {status}</p>;
  }

  const target: ResourceNoteStatus = status === "archived" ? "active" : "archived";

  return (
    <div className={styles.control}>
      <form action={submit}>
        <input type="hidden" name="note_id" value={noteId} />
        <input type="hidden" name="status" value={target} />

        <button
          aria-describedby={state.status === "idle" ? undefined : messageId}
          className={styles[target] ?? ""}
          disabled={pending}
          type="submit"
        >
          {/*
            The visible words stay part of the accessible name rather than being
            replaced by an `aria-label`, so speaking the label a learner can see
            still activates the button. The title is appended for a screen
            reader, because a list holding several would otherwise present the
            same name on every one of them.
          */}
          {RESOURCE_NOTE_STATUS_LABELS[target]}
          <span className={styles.forScreenReaders}> — {title}</span>
        </button>
      </form>

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
  );
}
