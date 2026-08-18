import Link from "next/link";

import styles from "@/features/practice/AttemptHistory.module.css";
import type { QuizAttempt } from "@/types/practice";

interface AttemptHistoryProps {
  attempts: QuizAttempt[];
}

/** How an attempt's state reads, falling back to the stored word. */
function stateLabel(status: string): string {
  if (status === "evaluated") {
    return "Answered";
  }
  if (status === "in_progress") {
    return "Not submitted";
  }
  return status;
}

/**
 * The quizzes a learner has taken, newest first.
 *
 * **Nothing is counted, totalled, or compared.** No attempt carries a score, a
 * mark, or a figure of any kind, and no attempt is set against another — a
 * history that ranked its own entries would be a progress score under a
 * different name (docs/domain/terminology.md).
 *
 * The date each attempt was submitted is shown as the API sent it, formatted for
 * the learner's locale by the browser through `<time>` rather than by a
 * conversion this component performs.
 *
 * A server component. It renders what it was given and derives nothing.
 */
export function AttemptHistory({ attempts }: AttemptHistoryProps) {
  return (
    <section aria-labelledby="what-you-have-taken" className={styles.panel}>
      <h2 id="what-you-have-taken">Quizzes you have taken</h2>

      {attempts.length === 0 ? (
        <p className={styles.empty}>
          None yet. Choose some topics above and answer a quiz to see what you made of them.
        </p>
      ) : (
        <ul className={styles.items}>
          {attempts.map((attempt) => (
            <li className={styles.item} key={attempt.id}>
              <p className={styles.title}>
                <Link href={`/practice/attempts/${attempt.id}`}>{attempt.quiz_title}</Link>
              </p>
              <p className={styles.state}>
                {stateLabel(attempt.status)}
                {attempt.submitted_at ? (
                  <>
                    {" on "}
                    <time dateTime={attempt.submitted_at}>
                      {attempt.submitted_at.slice(0, 10)}
                    </time>
                  </>
                ) : null}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
