import Link from "next/link";

import styles from "@/features/progress/PriorityFocus.module.css";
import type { PriorityFocus as PriorityFocusReading } from "@/features/progress/priority-focus";

interface PriorityFocusProps {
  /** What needs attention, as `selectPriorityFocus` gathered it. */
  focus: PriorityFocusReading;
  /** True when the goal has no active weekly plan to date any work. */
  hasWeek: boolean;
}

/**
 * What currently needs the learner's attention, and why each thing is here.
 *
 * The **priority focus** [FR-011](docs/requirements/functional.md) describes,
 * built from three facts backend rules already decided: work whose day has
 * passed, reviews the backend reports as due, and a saved week PLN-006 says does
 * not reach the date. It is a **reading** of contracts `/progress` already
 * fetches, so it adds no endpoint: PRG-001 stays unimplemented, still waiting on
 * the quiz, test, and mistake evidence its purpose also promises.
 *
 * **It writes nothing.** No status control, no generate control, no adapt
 * control, no scheduling control, no `<button>`, and no `<form>` — the read-only
 * shape ADR-026 fixed and ADR-029 applied to this screen. Every group names where
 * its action lives and links to it.
 *
 * **Nothing is counted, ranked, or scored.** No entry is numbered, no group
 * outranks another, there is no "top" anything, and the panel never says how many
 * things need attention — a tally of a learner's outstanding work is a
 * measurement of a person, which
 * docs/domain/terminology.md#plan-coverage-counts-are-not-learner-scores forbids.
 *
 * **The learning stage is not a signal here**, because selecting some of the five
 * stages as priorities would rank them against each other, which ADR-017 and
 * ADR-030 both refuse. Where a stage explains an item, it is already inside the
 * item's own `recommendation_reason`, which this panel renders unchanged.
 *
 * **The wording describes records, never the learner.** An item's day has passed;
 * a review is ready; a week falls short of a date. The learner is never behind,
 * never weak, and never at risk.
 *
 * A feasibility reading that could not be taken contributes **no entry**, rather
 * than a claim in either direction. No screen reaches this today: a failed
 * PLN-006 read is an `ApiError` the page reports in full, which is ADR-029's
 * decision about an unreachable API and is unchanged here.
 */
export function PriorityFocus({ focus, hasWeek }: PriorityFocusProps) {
  return (
    <section aria-labelledby="priority-focus" className={styles.panel}>
      <h2 id="priority-focus">What could use your attention</h2>
      {focus.groups.length === 0 ? (
        <Nothing hasWeek={hasWeek} />
      ) : (
        <>
          <p className={styles.lead}>
            Things LearnFlow already has a record of, gathered in one place with the reason each one
            is here. They are not in any order of importance, and nothing on this panel changes
            anything — each group links to the screen where you act on it.
          </p>
          <ul className={styles.groups}>
            {focus.groups.map((group) => (
              <li className={styles.group} key={group.kind}>
                <h3 className={styles.groupHeading}>{group.heading}</h3>
                <ul className={styles.entries}>
                  {group.entries.map((entry) => (
                    <li className={styles.entry} key={entry.id}>
                      <p className={styles.title}>{entry.title}</p>
                      {entry.context ? <p className={styles.context}>{entry.context}</p> : null}
                      {/*
                       * Why this is here, in two sentences: the fact from the
                       * record, then the sentence whichever rule wrote the record
                       * gave for it. Neither is composed on the learner's behalf.
                       */}
                      <p className={styles.fact}>{entry.fact}</p>
                      {entry.reason ? <p className={styles.why}>{entry.reason}</p> : null}
                    </li>
                  ))}
                </ul>
                <p className={styles.action}>
                  <Link href={group.actionHref}>{group.actionLabel}</Link>
                </p>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

/**
 * Nothing is flagged.
 *
 * Said as a fact about the records rather than as praise, and it names what would
 * appear here so an empty panel does not read as a panel that is broken. Whether
 * the goal has a dated week decides which of the two sentences is honest: with no
 * weekly plan there is no day for anything to have passed on.
 */
function Nothing({ hasWeek }: { hasWeek: boolean }) {
  if (!hasWeek) {
    return (
      <p className={styles.empty}>
        Nothing is waiting on you right now. This goal has no plan for a week, so no work is dated
        and no day can have passed. <Link href="/plan">Generate or update your plan</Link> to get
        dated work.
      </p>
    );
  }
  return (
    <p className={styles.empty}>
      Nothing is waiting on you right now. Work whose day has passed, topics ready to come back, and
      a saved study week that falls short of your date would each appear here, with the reason it
      did.
    </p>
  );
}
