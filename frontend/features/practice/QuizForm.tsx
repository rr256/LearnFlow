"use client";

import { useActionState, useId } from "react";

import styles from "@/features/practice/QuizForm.module.css";
import { submitAnswersAction } from "@/features/practice/actions";
import { INITIAL_ANSWER_FORM_STATE, type AnswerFormState } from "@/features/practice/submission";
import type { CheckpointQuiz } from "@/types/practice";

interface QuizFormProps {
  quiz: CheckpointQuiz;
}

/**
 * Where a learner answers a checkpoint quiz.
 *
 * **The whole quiz is submitted at once.** There is no save-as-you-go: one form
 * post carries every answer, which is what lets this work with no JavaScript and
 * is why QZ-004 is not implemented.
 *
 * **A question can be left unanswered.** No radio is pre-selected and nothing is
 * required, because guessing to satisfy a form is not practice. An unanswered
 * question is recorded as unanswered, never as wrong, and the form says so.
 *
 * **No answer is shown here.** The quiz the server sent carries no expected
 * option and no explanation, so there is nothing to hide: they arrive with the
 * result, after the learner has answered.
 *
 * **Nothing is timed and nothing is counted.** There is no clock, no progress
 * bar, and no running tally — those measure the learner rather than describe the
 * work.
 *
 * A client component only so it can report a refusal. On success the action
 * redirects to the result.
 */
export function QuizForm({ quiz }: QuizFormProps) {
  const [state, submit, pending] = useActionState<AnswerFormState, FormData>(
    submitAnswersAction,
    INITIAL_ANSWER_FORM_STATE,
  );
  const messageId = useId();

  return (
    <form action={submit} className={styles.form}>
      <input type="hidden" name="quiz_id" value={quiz.id} />

      <p className={styles.hint}>
        Answer what you can. Leaving a question alone is fine — it is recorded as unanswered, not
        as wrong. Nothing is timed, and nothing is scored.
      </p>

      <ol className={styles.questions}>
        {quiz.questions.map((question) => (
          <li className={styles.question} key={question.question_id}>
            <fieldset className={styles.choices}>
              <legend className={styles.prompt}>
                <span className={styles.position}>{question.position}.</span> {question.prompt}
              </legend>
              {question.options.map((option) => (
                <label className={styles.choice} key={option.key}>
                  <input
                    name={`answer_${question.question_id}`}
                    type="radio"
                    value={option.key}
                  />
                  <span className={styles.key}>{option.key}</span>
                  <span>{option.text}</span>
                </label>
              ))}
            </fieldset>
          </li>
        ))}
      </ol>

      <button
        aria-describedby={state.status === "idle" ? undefined : messageId}
        disabled={pending}
        type="submit"
      >
        Submit these answers
      </button>

      {state.status === "idle" ? null : (
        <p className={styles.failed} id={messageId} role="alert">
          {state.message}
        </p>
      )}
    </form>
  );
}
