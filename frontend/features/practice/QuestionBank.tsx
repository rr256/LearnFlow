import styles from "@/features/practice/QuestionBank.module.css";
import { QuestionStatusControl } from "@/features/practice/QuestionStatusControl";
import {
  QUESTION_STATE_LABELS,
  type PracticeQuestion,
  type QuestionStatus,
} from "@/types/practice";

interface QuestionBankProps {
  questions: PracticeQuestion[];
}

/** How a question's state reads, falling back to the stored word. */
function stateLabel(status: string): string {
  return QUESTION_STATE_LABELS[status as QuestionStatus] ?? status;
}

/**
 * The practice questions a learner has written, newest first.
 *
 * **Nothing here is counted, ranked, or recommended.** The list is what the
 * learner wrote, in the order the API returned; no question is marked easier,
 * more important, or more worth answering than another, and no figure appears
 * beside a topic or a subject.
 *
 * A question that has been set aside is **still listed**, marked in words, so
 * bringing it back is possible from the same place. Nothing is hidden and
 * nothing is deleted.
 *
 * The expected answer is shown here, unlike on a quiz being taken: this is the
 * author reading back what they wrote.
 *
 * A server component. It renders what it was given and derives nothing.
 */
export function QuestionBank({ questions }: QuestionBankProps) {
  return (
    <section aria-labelledby="your-questions" className={styles.panel}>
      <h2 id="your-questions">Your practice questions</h2>

      {questions.length === 0 ? (
        <p className={styles.empty}>
          You have not written any yet. Add one above, then ask for a quiz on the topics it covers.
        </p>
      ) : (
        <ul className={styles.items}>
          {questions.map((question) => (
            <li className={styles.item} key={question.id}>
              <p className={styles.prompt}>{question.prompt}</p>
              <p className={styles.state}>{stateLabel(question.status)}</p>

              <ol className={styles.options}>
                {question.options.map((option) => (
                  <li
                    className={
                      option.key === question.expected_option_key ? styles.expected : styles.option
                    }
                    key={option.key}
                  >
                    <span className={styles.key}>{option.key}</span> {option.text}
                    {option.key === question.expected_option_key ? (
                      <span className={styles.note}> — the expected answer</span>
                    ) : null}
                  </li>
                ))}
              </ol>

              {question.explanation ? (
                <p className={styles.explanation}>{question.explanation}</p>
              ) : null}

              {question.topics.length > 0 ? (
                <p className={styles.topics}>
                  Covers:{" "}
                  {question.topics
                    .map((topic) => `${topic.subject_name} — ${topic.name}`)
                    .join("; ")}
                </p>
              ) : null}

              <QuestionStatusControl
                prompt={question.prompt}
                questionId={question.id}
                status={question.status}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
