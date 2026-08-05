import styles from "@/features/home/ExaminationDates.module.css";
import { describeDateSpan, describePeriodType } from "@/features/home/dates";
import {
  datesMayChange,
  type ExaminationGoal,
  type ExaminationPeriod,
} from "@/types/study-goal";

interface ExaminationDatesProps {
  /** The cycle the goal aims at, which carries the window and the provenance. */
  examination: ExaminationGoal;
  /**
   * The cycle's dated periods, from EXM-001.
   *
   * Null when the goal's cycle was not among the schedules published for its
   * program, which is said rather than papered over.
   */
  periods: ExaminationPeriod[] | null;
}

/**
 * The examination the goal aims at: its window, and every dated period the
 * examining body publishes.
 *
 * Every date on this screen is gathered here, so the provisional status and the
 * source are stated once beside all of them rather than repeated panel by panel.
 * A date shown without its status reads as settled fact, and one shown without
 * its source cannot be checked when the examining body revises it
 * (docs/domain/terminology.md).
 *
 * The window is a derived span -- first published sitting day to last -- and is
 * kept apart from the published periods rather than listed among them, because
 * it is not itself something the examining body published
 * (docs/adr/ADR-013-examination-schedule-and-study-goal.md).
 *
 * The registration deadlines are the nearest actionable dates a learner has,
 * which is why ADR-013 persists them alongside the sitting days. They appear in
 * the order the API returns them; ordering published dates is the backend's
 * business, not this component's.
 */
export function ExaminationDates({ examination, periods }: ExaminationDatesProps) {
  const window = examination.examination_window;

  return (
    <section aria-labelledby="your-examination" className={styles.panel}>
      <h2 id="your-examination">{examination.name}</h2>
      <p className={styles.window}>
        <span className={styles.windowLabel}>Examination window</span>{" "}
        {window ? describeDateSpan(window.starts_on, window.ends_on) : "Sitting days not published"}
      </p>

      {periods === null ? (
        <p className={styles.empty}>
          The dates published for this cycle could not be read, so only the window is shown.
        </p>
      ) : periods.length === 0 ? (
        <p className={styles.empty}>No dated periods are published for this cycle.</p>
      ) : (
        <>
          <h3 className={styles.subheading}>Important dates</h3>
          <dl className={styles.dates}>
            {periods.map((period) => (
              <div key={`${period.period_type}-${period.starts_on}`}>
                <dt>{describePeriodType(period.period_type)}</dt>
                <dd>{describeDateSpan(period.starts_on, period.ends_on)}</dd>
              </div>
            ))}
          </dl>
        </>
      )}

      {datesMayChange(examination) ? (
        <p className={styles.provisional}>
          Provisional — {examination.organising_body ?? "the organising body"} may still change
          these dates.
        </p>
      ) : null}
      <p className={styles.source}>
        Dates from{" "}
        <a href={examination.source_reference} rel="noreferrer noopener" target="_blank">
          {examination.organising_body ?? examination.name}
        </a>
        , read on {examination.source_checked_on}.
      </p>
    </section>
  );
}
