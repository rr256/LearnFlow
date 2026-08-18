import Link from "next/link";

import styles from "@/features/practice/PracticeHistory.module.css";
import {
  attemptMoment,
  attemptStateLabel,
  coveredTopics,
  historyHref,
  type HistoryPage,
} from "@/features/practice/history";
import { outcomeLabel, type QuizAttempt } from "@/types/practice";

interface PracticeHistoryProps {
  page: HistoryPage;
}

/**
 * What became of each question in one attempt, behind a disclosure.
 *
 * `<details>` is used rather than a scripted panel because every practice screen
 * works with JavaScript disabled, and a browser opens and closes this one on its
 * own. It is closed to begin with so that a page of attempts stays a list of
 * attempts, and opening one is the learner's choice rather than the screen's.
 *
 * **Only the outcome is stated here, in words.** The expected answer and the
 * explanation stay on the result view, which is what the link at the foot of the
 * disclosure is for — a history that repeated the whole result would leave
 * nothing to open.
 *
 * An attempt that was never submitted has nothing to read back. Rendering its
 * questions as unanswered would state something the learner never did.
 */
function AttemptOutcomes({ attempt }: { attempt: QuizAttempt }) {
  if (attempt.status !== "evaluated") {
    return (
      <p className={styles.unsubmitted}>
        This one was never submitted, so there is nothing to read back. Starting the quiz again
        from Practice picks up the attempt you left open.
      </p>
    );
  }

  return (
    <details className={styles.outcomes}>
      <summary>What became of each question</summary>
      <ol className={styles.outcomeItems}>
        {attempt.outcomes.map((outcome) => (
          <li className={styles.outcomeItem} key={outcome.question_id}>
            <p className={styles.outcomePrompt}>{outcome.prompt}</p>
            <p className={styles.outcomeState}>{outcomeLabel(outcome)}</p>
          </li>
        ))}
      </ol>
      <p className={styles.outcomeFooter}>
        <Link href={`/practice/attempts/${attempt.id}`}>
          Open the full result for the expected answers and explanations
        </Link>
      </p>
    </details>
  );
}

/**
 * Every checkpoint quiz a learner has taken, newest first, a page at a time.
 *
 * **Nothing is counted, totalled, or compared.** No attempt carries a score, a
 * mark, or a figure of any kind; no attempt is set against another; and the
 * screen never says how many quizzes the learner has taken, which
 * docs/domain/terminology.md forbids by name. There is no percentage, no
 * streak, and no summary of how the learner is doing.
 *
 * **Nothing is ranked and nothing is left out.** The order is QZ-006's own —
 * newest first, which is chronological rather than a judgement — every attempt
 * is styled identically, and walking back through the pages reaches all of them.
 *
 * **Read-only.** There is no control here at all: a record of what happened is
 * not edited afterwards, and nothing on this screen records a learning stage,
 * moves a plan, or schedules a review. Practising again means a new quiz, from
 * Practice.
 *
 * A server component. It renders what it was given and derives nothing.
 */
export function PracticeHistory({ page }: PracticeHistoryProps) {
  return (
    <section aria-labelledby="every-quiz-you-have-taken" className={styles.panel}>
      <h2 id="every-quiz-you-have-taken">Every quiz you have taken</h2>

      {page.attempts.length === 0 ? (
        <p className={styles.empty}>
          {page.newerOffset === null
            ? "None yet. Write some questions on Practice, then ask for a quiz on the topics they cover."
            : "There is nothing further back than this."}
        </p>
      ) : (
        <ul className={styles.items}>
          {page.attempts.map((attempt) => {
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

                <AttemptOutcomes attempt={attempt} />
              </li>
            );
          })}
        </ul>
      )}

      {page.olderOffset === null && page.newerOffset === null ? null : (
        <nav aria-label="History pages" className={styles.pages}>
          <ul>
            {page.newerOffset === null ? null : (
              <li>
                <Link href={historyHref(page.newerOffset)} rel="prev">
                  More recent quizzes
                </Link>
              </li>
            )}
            {page.olderOffset === null ? null : (
              <li className={styles.older}>
                <Link href={historyHref(page.olderOffset)} rel="next">
                  Earlier quizzes
                </Link>
              </li>
            )}
          </ul>
        </nav>
      )}
    </section>
  );
}
