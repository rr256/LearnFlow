"use client";

import { useActionState, useId } from "react";

import styles from "@/features/practice/StartQuizForm.module.css";
import { startQuizAction } from "@/features/practice/actions";
import { INITIAL_START_QUIZ_STATE, type StartQuizState } from "@/features/practice/submission";
import type { SubjectTopicOptions } from "@/features/resources/topic-options";

interface StartQuizFormProps {
  /** The curriculum's topics, grouped by subject, or empty when unavailable. */
  topicGroups: SubjectTopicOptions[];
}

/**
 * Where a learner asks for a checkpoint quiz on the topics they choose.
 *
 * **The quiz asks every question you wrote for those topics**, in the order you
 * wrote them. LearnFlow picks none and leaves none out — choosing which few to
 * ask would be a ranking, and nothing in LearnFlow ranks. The length of a quiz
 * is therefore the learner's own decision, and the form says so.
 *
 * **Nothing is generated.** Despite the API path, assembling is a deterministic
 * selection of stored questions: no AI provider is reached, and asking twice for
 * the same topics produces the same questions in the same order.
 *
 * A client component only so it can report a refusal — most often that no
 * question has been written for the topics chosen. On success the action
 * redirects to the quiz, which works with no JavaScript because the form posts
 * natively and the browser follows a normal redirect.
 */
export function StartQuizForm({ topicGroups }: StartQuizFormProps) {
  const [state, submit, pending] = useActionState<StartQuizState, FormData>(
    startQuizAction,
    INITIAL_START_QUIZ_STATE,
  );
  const topicsId = useId();
  const messageId = useId();

  return (
    <form action={submit} className={styles.form}>
      <h2>Practise a topic</h2>
      <p className={styles.hint}>
        Choose what to practise. The quiz asks every question you have written for those topics, in
        the order you wrote them — LearnFlow picks none of them for you and leaves none out.
      </p>

      <div className={styles.field}>
        <label htmlFor={topicsId}>Topics</label>
        {topicGroups.length === 0 ? (
          <p className={styles.hint}>
            The curriculum could not be read, so there is nothing to choose from yet.
          </p>
        ) : (
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
        )}
      </div>

      <button
        aria-describedby={state.status === "idle" ? undefined : messageId}
        disabled={pending}
        type="submit"
      >
        Start a practice quiz
      </button>

      {state.status === "idle" ? null : (
        <p className={styles.failed} id={messageId} role="alert">
          {state.message}
        </p>
      )}
    </form>
  );
}
