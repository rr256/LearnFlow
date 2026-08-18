import Link from "next/link";

import styles from "@/features/practice/AttemptHistory.module.css";
import {
  attemptMoment,
  attemptStateLabel,
  coveredTopics,
} from "@/features/practice/history";
import type { QuizAttempt } from "@/types/practice";

interface AttemptHistoryProps {
  attempts: QuizAttempt[];
  /**
   * Whether the learner has taken quizzes older than the ones given here.
   *
   * Decided by the page from what QZ-006 returned, never from a count: it changes
   * the wording beside the link and nothing else, and no figure comes with it.
   */
  hasMore: boolean;
}

/**
 * The most recent quizzes a learner has taken, newest first.
 *
 * This is the practice screen's own view of the history. The **whole** history,
 * a page at a time and with what became of each question, is
 * `PracticeHistory` at `/practice/history`, which the link at the foot leads to
 * — so nothing is out of reach from here, and this panel stays short enough that
 * the screen's own work of writing questions and starting a quiz still reads.
 *
 * **Nothing is counted, totalled, or compared.** No attempt carries a score, a
 * mark, or a figure of any kind, and no attempt is set against another — a
 * history that ranked its own entries would be a progress score under a
 * different name (docs/domain/terminology.md). The panel never states how many
 * quizzes the learner has taken, including when there are older ones.
 *
 * The date each attempt was submitted is shown as the API sent it, formatted for
 * the learner's locale by the browser through `<time>` rather than by a
 * conversion this component performs.
 *
 * A server component. It renders what it was given and derives nothing.
 */
export function AttemptHistory({ attempts, hasMore }: AttemptHistoryProps) {
  return (
    <section aria-labelledby="what-you-have-taken" className={styles.panel}>
      <h2 id="what-you-have-taken">Quizzes you have taken</h2>

      {attempts.length === 0 ? (
        <p className={styles.empty}>
          None yet. Choose some topics above and answer a quiz to see what you made of them.
        </p>
      ) : (
        <>
          <ul className={styles.items}>
            {attempts.map((attempt) => {
              const moment = attemptMoment(attempt);
              const topics = coveredTopics(attempt.topics);
              return (
                <li className={styles.item} key={attempt.id}>
                  <p className={styles.title}>
                    <Link href={`/practice/attempts/${attempt.id}`}>{attempt.quiz_title}</Link>
                  </p>
                  <p className={styles.state}>
                    {attemptStateLabel(attempt.status)}
                    {moment ? (
                      <>
                        {moment.kind === "submitted" ? " on " : ", started on "}
                        <time dateTime={moment.iso}>{moment.day}</time>
                      </>
                    ) : null}
                  </p>
                  {topics ? <p className={styles.topics}>Covers: {topics}</p> : null}
                </li>
              );
            })}
          </ul>

          <p className={styles.more}>
            {hasMore ? "These are your most recent. " : null}
            <Link href="/practice/history">
              See every quiz you have taken, and what became of each question
            </Link>
          </p>
        </>
      )}
    </section>
  );
}
