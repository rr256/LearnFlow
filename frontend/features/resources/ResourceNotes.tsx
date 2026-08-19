import styles from "@/features/resources/ResourceNotes.module.css";
import { ResourceNoteForm } from "@/features/resources/ResourceNoteForm";
import { ResourceNoteStatusControl } from "@/features/resources/ResourceNoteStatusControl";
import { isKeptNote, type ResourceNote } from "@/types/resource-note";

interface ResourceNotesProps {
  /** The material these notes were written against. */
  resourceId: string;
  /** Its notes, in the order RES-010 returned them, or empty when unreadable. */
  notes: ResourceNote[];
  /**
   * Whether the material is still in the catalogue.
   *
   * Archived material is read-only, notes included, so the forms and controls
   * are left out rather than shown and refused. The notes are still displayed:
   * putting material aside hides nothing.
   */
  writable: boolean;
}

/**
 * The learner's own notes on one piece of study material.
 *
 * **The text is rendered as text.** Every body below goes through JSX, which
 * escapes it — nothing here calls `dangerouslySetInnerHTML`, parses Markdown, or
 * interprets the content in any way, so a pasted `<script>` tag is something a
 * learner reads rather than something a browser runs. The learner's own line
 * breaks and spacing are preserved by CSS `white-space: pre-wrap`, not by
 * inserting markup.
 *
 * **Nothing is counted, ranked, or scored.** No "4 notes", no longest note, no
 * suggestion that one is more useful than another — the line
 * docs/domain/terminology.md#plan-coverage-counts-are-not-learner-scores draws,
 * applied to a learner's own writing. Notes are listed in the order the API
 * returned them, newest first, which is the backend's order rather than a
 * judgement made here.
 *
 * **Nothing is deleted**, and nothing is read by anything: no note is sent to a
 * provider, indexed, searched, or summarised.
 *
 * Each note sits in a closed disclosure, so a piece of material with several
 * long notes stays as scannable in the catalogue as one with none. That is why
 * notes are shown here and on no other screen: the curriculum view, `/revisions`,
 * `/plan`, and `/plan/today` show a topic's material to help a learner find it,
 * and pages of text under every item would bury exactly what those screens are
 * for — the reason ADR-036 kept material off `/plan/month` entirely.
 */
export function ResourceNotes({ resourceId, notes, writable }: ResourceNotesProps) {
  const kept = notes.filter(isKeptNote);
  const putAside = notes.filter((note) => !isKeptNote(note));

  return (
    <section className={styles.notes}>
      <h4 className={styles.heading}>Your notes on this</h4>

      {notes.length === 0 ? (
        <p className={styles.empty}>
          {writable
            ? "Nothing written yet. Add what you want to keep from this material below — it is stored on this computer and is not sent anywhere."
            : "No notes on this. Put the material back in your catalogue to add one."}
        </p>
      ) : (
        <ul className={styles.list}>
          {kept.map((note) => (
            <NoteLine key={note.id} note={note} writable={writable} />
          ))}
        </ul>
      )}

      {putAside.length === 0 ? null : (
        <>
          <p className={styles.asideHeading}>Notes you have put aside</p>
          <ul className={styles.list}>
            {putAside.map((note) => (
              <NoteLine key={note.id} note={note} writable={writable} />
            ))}
          </ul>
        </>
      )}

      {writable ? (
        <details className={styles.add}>
          <summary>Add a note</summary>
          <ResourceNoteForm resourceId={resourceId} />
        </details>
      ) : null}
    </section>
  );
}

/**
 * One note, closed by default.
 *
 * A native `details` rather than a toggle: it opens and closes with no
 * JavaScript at all, so the text and its correction form are reachable on a page
 * that never hydrates — which every path in this product must be.
 */
function NoteLine({ note, writable }: { note: ResourceNote; writable: boolean }) {
  return (
    <li className={styles.item}>
      <details className={styles.disclosure}>
        <summary>{note.title}</summary>

        {/*
          `pre-wrap` in CSS, not `<pre>`: the learner's line breaks and
          indentation are preserved while the text still wraps at the width of
          the page and inherits the reading font. The body is interpolated as a
          string, so React escapes it and no markup it contains can execute.
        */}
        <p className={styles.body}>{note.body}</p>

        {writable ? (
          <>
            <details className={styles.edit}>
              <summary>Correct this note</summary>
              <ResourceNoteForm note={note} resourceId={note.resource_id} />
            </details>
            <ResourceNoteStatusControl
              noteId={note.id}
              status={note.status}
              title={note.title}
            />
          </>
        ) : null}
      </details>
    </li>
  );
}
