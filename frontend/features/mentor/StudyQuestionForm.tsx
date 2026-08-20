"use client";

import { useActionState, useId } from "react";

import styles from "@/features/mentor/StudyQuestionForm.module.css";
import { askStudyQuestionAction } from "@/features/mentor/actions";
import { StudyAnswerView } from "@/features/mentor/StudyAnswerView";
import {
  INITIAL_STUDY_QUESTION_STATE,
  type StudyQuestionState,
} from "@/features/mentor/submission";
import type { SubjectTopicOptions } from "@/features/resources/topic-options";
import { MAX_QUESTION_LENGTH } from "@/types/study-answer";

interface StudyQuestionFormProps {
  /** The curriculum's topics, grouped by subject, or empty when unavailable. */
  topicGroups: SubjectTopicOptions[];
}

/**
 * Where a learner asks a question about one topic and reads the answer.
 *
 * The **Ask your notes** screen (docs/domain/terminology.md). The word *mentor*
 * survives only in the route and the endpoint family, which name the service.
 *
 * **The model is asked because the learner submitted, and never otherwise.**
 * Nothing here runs on a page load: rendering this screen asks nothing, reads no
 * note, and makes no outbound request. That is what keeps the privacy statement
 * a description of what LearnFlow does rather than of what it might do.
 *
 * **A server action, not a `GET` form** — which departs from the search screen
 * next door. A search carries a topic identifier; this carries the learner's own
 * question, and a question in the address would land in server logs and browser
 * history. It still posts natively without JavaScript: the action runs on the
 * Next.js server and the page re-renders with the answer.
 *
 * A client component only so it can show the last answer. It calls no API
 * itself — the submission goes to a server action, so the browser never reaches
 * the backend.
 *
 * The picker reuses the same `topic-options` grouping the resource, search, and
 * practice screens use, rather than a fourth copy of the same walk. The
 * `maxLength` on the text area is a courtesy, not the rule: the backend refuses
 * an over-long question whatever a browser allowed.
 */
export function StudyQuestionForm({ topicGroups }: StudyQuestionFormProps) {
  const [state, formAction] = useActionState<StudyQuestionState, FormData>(
    askStudyQuestionAction,
    INITIAL_STUDY_QUESTION_STATE,
  );
  const topicField = useId();
  const questionField = useId();

  if (topicGroups.length === 0) {
    return (
      <p className={styles.unavailable}>
        The curriculum could not be read, so there are no topics to choose from. Reload the page,
        or come back once the backend is reachable.
      </p>
    );
  }

  return (
    <>
      <form action={formAction} className={styles.form}>
        <div className={styles.field}>
          <label htmlFor={topicField}>Topic</label>
          <select
            defaultValue={state.topicId ?? ""}
            id={topicField}
            name="topic_id"
            required
          >
            <option disabled value="">
              Choose a topic…
            </option>
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
        </div>

        <div className={styles.field}>
          <label htmlFor={questionField}>Your question</label>
          <textarea
            defaultValue={state.question}
            id={questionField}
            maxLength={MAX_QUESTION_LENGTH}
            name="question"
            placeholder="What do you want explained about this topic?"
            required
            rows={3}
          />
          <p className={styles.hint}>
            Your question and the matching passages from your notes are sent to an AI model
            running on this computer, only when you ask. Nothing leaves the machine, nothing is
            stored, and no other part of your study — your plan, progress, or practice — is sent.
          </p>
        </div>

        <button type="submit">Ask your notes</button>
      </form>

      {state.error !== null ? (
        <p className={styles.error} role="alert">
          {state.error}
        </p>
      ) : null}

      {state.answer !== null ? <StudyAnswerView answer={state.answer} /> : null}
    </>
  );
}
