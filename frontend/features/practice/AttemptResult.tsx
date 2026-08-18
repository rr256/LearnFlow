import styles from "@/features/practice/AttemptResult.module.css";
import { optionText, outcomeLabel, type QuizAttempt } from "@/types/practice";

interface AttemptResultProps {
  attempt: QuizAttempt;
}

/**
 * What became of one attempt, question by question.
 *
 * **There is no score anywhere on this screen.** No total, no mark, no "3 of 5",
 * no percentage, and no comparison with an earlier attempt: the learner reads
 * what happened to each question and draws their own conclusion. That is what
 * docs/domain/terminology.md requires — a number that rates the learner is
 * forbidden by name — and what ADR-033 records. **This component counts nothing
 * of its own**, and there is nothing here for it to count.
 *
 * **An unanswered question is not a wrong one**, and it says so in words rather
 * than being folded in with the answers that missed.
 *
 * **Nothing is coloured by outcome.** Every question is styled the same way, so
 * the result reads as a record of work rather than as a verdict, and nothing
 * depends on the styling being seen.
 *
 * **Nothing here claims a topic is understood.** One checkpoint is one
 * checkpoint; the learning stage stays the learner's own statement, recorded on
 * the curriculum screen, which is where this links.
 *
 * A server component. It renders what it was given and derives nothing.
 */
export function AttemptResult({ attempt }: AttemptResultProps) {
  return (
    <section aria-labelledby="what-happened" className={styles.panel}>
      <h2 id="what-happened">What you answered</h2>
      <p className={styles.lead}>
        Each question, what you chose, and what the question expected. Nothing here is added up:
        one practice quiz is one practice quiz, and it says nothing on its own about how well you
        know a topic.
      </p>

      <ol className={styles.items}>
        {attempt.outcomes.map((outcome) => {
          const chosen = optionText(outcome.options, outcome.chosen_option_key);
          const expected = optionText(outcome.options, outcome.expected_option_key);
          return (
            <li className={styles.item} key={outcome.question_id}>
              <p className={styles.prompt}>
                <span className={styles.position}>{outcome.position}.</span> {outcome.prompt}
              </p>
              <p className={styles.outcome}>{outcomeLabel(outcome)}</p>

              {chosen === null ? null : <p className={styles.line}>You chose: {chosen}</p>}
              {expected === null ? (
                <p className={styles.line}>
                  This attempt has not been submitted yet, so the expected answer is not shown.
                </p>
              ) : (
                <p className={styles.line}>Expected: {expected}</p>
              )}

              {outcome.explanation ? (
                <p className={styles.explanation}>{outcome.explanation}</p>
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
