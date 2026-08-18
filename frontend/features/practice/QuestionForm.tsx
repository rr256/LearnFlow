"use client";

import { useActionState, useId } from "react";

import styles from "@/features/practice/QuestionForm.module.css";
import { writeQuestionAction } from "@/features/practice/actions";
import {
  INITIAL_QUESTION_FORM_STATE,
  OPTION_FIELD_COUNT,
  type QuestionFormState,
} from "@/features/practice/submission";
import type { SubjectTopicOptions } from "@/features/resources/topic-options";

interface QuestionFormProps {
  /** The curriculum's topics, grouped by subject, or empty when unavailable. */
  topicGroups: SubjectTopicOptions[];
}

/**
 * The letters shown beside each option field.
 *
 * Presentation only. The keys a question is actually stored with are assigned by
 * the backend from each option's position, so these labels describe what will
 * happen rather than deciding it.
 */
const OPTION_LETTERS = ["A", "B", "C", "D", "E", "F"];

/**
 * Where a learner writes one practice question of their own.
 *
 * **Every question here is the learner's.** LearnFlow generates none, ships none,
 * and fetches none from anywhere: there is no "generate" control, because no AI
 * provider is involved and no previous-year paper is bundled with the product.
 *
 * **A question cannot be edited afterwards** — only set aside and rewritten —
 * because attempts already marked against it reference it, and rewriting a
 * prompt would silently rewrite the history of every one of them. The form says
 * so, so a learner is not surprised later.
 *
 * Four option fields are offered because that is what a GATE multiple-choice
 * question conventionally has. Leaving the last ones blank is fine: blanks are
 * dropped before the question is sent, and the backend accepts between two and
 * six.
 *
 * A client component only so it can report what the last submission did. It
 * calls no API itself: the submission goes to a server action, so the browser
 * still never reaches the backend, and the form posts natively without
 * JavaScript.
 */
export function QuestionForm({ topicGroups }: QuestionFormProps) {
  const [state, submit, pending] = useActionState<QuestionFormState, FormData>(
    writeQuestionAction,
    INITIAL_QUESTION_FORM_STATE,
  );
  const promptId = useId();
  const explanationId = useId();
  const topicsId = useId();
  const messageId = useId();

  return (
    <form action={submit} className={styles.form}>
      <h2>Write a practice question</h2>
      <p className={styles.hint}>
        Practice questions are yours. LearnFlow writes none of its own and ships none with the
        product — you write what you want to be asked, and it asks you exactly that. Once written,
        a question cannot be edited: correct one by setting it aside and writing another, so the
        results you have already seen stay true to what you answered.
      </p>

      <div className={styles.field}>
        <label htmlFor={promptId}>Question</label>
        <textarea
          className={styles.prompt}
          id={promptId}
          name="prompt"
          placeholder="How many bits are needed to address 1 KiB?"
          required
          rows={3}
        />
      </div>

      <fieldset className={styles.options}>
        <legend>Options</legend>
        <p className={styles.hint}>
          Fill in at least two. Leave the rest blank if you need fewer. Choose the one that is the
          expected answer.
        </p>
        {Array.from({ length: OPTION_FIELD_COUNT }, (_, index) => (
          <div className={styles.option} key={index}>
            <input
              aria-label={`Option ${OPTION_LETTERS[index]} is the expected answer`}
              name="correct_option"
              type="radio"
              value={String(index)}
              defaultChecked={index === 0}
            />
            <label className={styles.forScreenReaders} htmlFor={`option-${index}`}>
              Option {OPTION_LETTERS[index]}
            </label>
            <span aria-hidden="true" className={styles.letter}>
              {OPTION_LETTERS[index]}
            </span>
            <input
              id={`option-${index}`}
              name={`option_${index}`}
              placeholder={index < 2 ? "An answer a learner could choose" : "Optional"}
              type="text"
            />
          </div>
        ))}
      </fieldset>

      <div className={styles.field}>
        <label htmlFor={explanationId}>Why that is the answer (optional)</label>
        <textarea
          id={explanationId}
          name="explanation"
          placeholder="1 KiB is 2^10 bytes, so ten bits address it."
          rows={2}
        />
        <p className={styles.hint}>Shown to you after you answer, never before.</p>
      </div>

      <div className={styles.field}>
        <label htmlFor={topicsId}>Topics this covers</label>
        {topicGroups.length === 0 ? (
          <p className={styles.hint}>
            The curriculum could not be read, so there is nothing to choose from yet. Reload the
            page once the backend is reachable.
          </p>
        ) : (
          <>
            <select className={styles.topics} id={topicsId} multiple name="topic_ids" size={8}>
              {topicGroups.map((group) => (
                <optgroup key={group.subjectId} label={group.subjectName}>
                  {group.topics.map((topic) => (
                    <option key={topic.id} value={topic.id}>
                      {topic.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            <p className={styles.hint}>
              At least one. A quiz is built from the topics you pick, so a question covering none
              could never be asked.
            </p>
          </>
        )}
      </div>

      <button
        aria-describedby={state.status === "idle" ? undefined : messageId}
        disabled={pending}
        type="submit"
      >
        Add this question
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
    </form>
  );
}
