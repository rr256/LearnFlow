"use client";

import { useActionState } from "react";

import styles from "@/features/resources/RemoveControl.module.css";

/** One state shape both removal actions can report through. */
export interface RemoveState {
  message: string | null;
}

export const INITIAL_REMOVE_STATE: RemoveState = { message: null };

interface RemoveControlProps {
  /** The server action that performs the removal. */
  action: (previous: RemoveState, form: FormData) => Promise<RemoveState>;
  /** The hidden field the action reads the identifier from. */
  fieldName: string;
  /** The identifier itself. */
  fieldValue: string;
  /** What is being removed, in the learner's own words — a filename, a title. */
  label: string;
  /** "PDF" or "note", so the copy names the thing rather than saying "item". */
  kind: string;
  /** What is lost, said plainly. Differs between a file, a note and a resource. */
  consequence: string;
  /**
   * The confirm button's words, when "Yes, remove this {kind} permanently" is
   * not what the learner should read. RES-005 removes more than the thing it
   * names, and the button says so.
   */
  confirmLabel?: string;
  /**
   * The reversible alternative, when "set it aside" is the wrong verb. A
   * *resource* is **put** aside -- terminology reserves that phrasing for
   * material -- while a file is **set** aside.
   */
  instead?: string;
}

/**
 * The one control in LearnFlow that destroys something.
 *
 * **Two deliberate actions, not one.** The button sits inside a closed
 * disclosure, so removing something takes opening it and then confirming. That
 * is the confirmation step — deliberately not a `window.confirm`, which does not
 * exist without JavaScript and cannot be styled or read consistently.
 *
 * **It is server-rendered and posts natively.** A `<details>` element opens
 * without script and the form carries its own action fields, so a native post
 * reaches the endpoint with no client bundle involved; the pending state below is
 * the only part of this component that needs hydration.
 *
 * **With JavaScript enabled — the ordinary case — this control works.**
 *
 * **What it is not is proof that the screen works with scripting disabled.**
 * React streams most of `/resources`'s forms — this one and the older controls
 * beside it — into a hidden segment that an inline script moves into place, so
 * with JavaScript fully off those buttons are not reachable. It predates this
 * control and affects the whole screen; see ADR-041, which records it rather
 * than claiming otherwise.
 *
 * **The copy names what will be lost**, and says what to do instead. Removing is
 * offered because a learner should be able to take back a mistake — not because
 * it is the ordinary way to tidy up, which is what setting something aside is
 * for.
 */
export function RemoveControl({
  action,
  fieldName,
  fieldValue,
  label,
  kind,
  consequence,
  confirmLabel,
  instead,
}: RemoveControlProps) {
  const [state, removeAction, removing] = useActionState<RemoveState, FormData>(
    action,
    INITIAL_REMOVE_STATE,
  );

  return (
    <details className={styles.disclosure}>
      <summary>Remove this {kind}</summary>
      <div className={styles.body}>
        <p className={styles.warning}>
          Removing <strong>{label}</strong> is permanent. {consequence} LearnFlow keeps no copy,
          and this cannot be undone.
        </p>
        <p className={styles.instead}>
          {instead ?? "To keep it but stop using it, set it aside instead — that is reversible."}
        </p>
        <form action={removeAction}>
          <input name={fieldName} type="hidden" value={fieldValue} />
          <button className={styles.confirm} disabled={removing} type="submit">
            {removing ? "Removing…" : (confirmLabel ?? `Yes, remove this ${kind} permanently`)}
          </button>
        </form>
        {state.message !== null ? (
          <p className={styles.error} role="alert">
            {state.message}
          </p>
        ) : null}
      </div>
    </details>
  );
}
