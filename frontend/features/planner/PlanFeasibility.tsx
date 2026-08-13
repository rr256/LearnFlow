import Link from "next/link";

import styles from "@/features/planner/PlanFeasibility.module.css";
import type { PlanFeasibility as PlanFeasibilityReading } from "@/types/study-plan";

interface PlanFeasibilityProps {
  /** The reading PLN-006 returned, or null when it could not be taken. */
  reading: PlanFeasibilityReading | null;
}

/**
 * Whether the learner's saved week reaches their goal's horizon.
 *
 * This is FR-004's third acceptance criterion — the plan highlighting a
 * meaningful trade-off when time is insufficient — and it is a **reading**.
 * Nothing here writes: no plan, no availability, no preference, and no item
 * status moves because this is on screen, and nothing adapts.
 *
 * **The sentence is the backend's.** `reason` is composed beside the numbers it
 * quotes, so the screen renders it rather than assembling its own — the same
 * rule the roadmap and the week follow for `generation_reason`. A screen that
 * wrote its own could disagree with the figures beside it.
 *
 * **Nothing is derived here.** No percentage, no ratio, no proportion: the
 * backend refuses to compute one and this must not either
 * (docs/domain/terminology.md). Where two counts are shown they are shown as two
 * counts, never as one over the other.
 *
 * The wording describes **the plan and the time**, never the learner. A week
 * that cannot reach a date is arithmetic, not a verdict on effort.
 */
export function PlanFeasibility({ reading }: PlanFeasibilityProps) {
  if (!reading) {
    return null;
  }

  return (
    <section aria-labelledby="plan-feasibility" className={panelClassName(reading.verdict)}>
      <h2 id="plan-feasibility">Time to your date</h2>
      <p className={styles.verdict}>{describeVerdict(reading.verdict)}</p>
      <p className={styles.reason}>{reading.reason}</p>
      {reading.verdict === "unknown" ? (
        <Unanswered reason={reading.unknown_reason} />
      ) : (
        <Figures reading={reading} />
      )}
    </section>
  );
}

/**
 * The heading a learner reads for each verdict.
 *
 * A statement about the plan in every case. "You are behind" and its relatives
 * are the wording terminology.md rules out, and there is no verdict here that
 * describes a person.
 */
function describeVerdict(verdict: string): string {
  if (verdict === "sufficient") {
    return "Your saved study time covers the work that is left.";
  }
  if (verdict === "insufficient") {
    return "Your saved study time does not cover the work that is left.";
  }
  return "This cannot be worked out yet.";
}

/**
 * The panel's classes, marked by verdict.
 *
 * `styles` is a CSS Module, whose generated type is an index signature rather
 * than a named shape, so each class is read by key and falls back to nothing —
 * the same handling `itemClassName` uses. The mark never carries the meaning on
 * its own: the verdict is stated in words directly above it.
 */
function panelClassName(verdict: string): string {
  const base = styles.panel ?? "";
  return `${base} ${styles[verdict] ?? ""}`.trim();
}

/**
 * What is missing, and what would settle it.
 *
 * Two different gaps ask the learner for two different things, so each names its
 * own next step rather than sharing a vague one.
 */
function Unanswered({ reason }: { reason: string | null }) {
  if (reason === "no_horizon") {
    return (
      <p className={styles.next}>
        <Link href="/setup">Set an examination cycle or a target date</Link> and this can be
        worked out.
      </p>
    );
  }
  if (reason === "no_availability_saved") {
    return (
      <p className={styles.next}>
        <Link href="/setup">Save the days you can study</Link> and this can be worked out.
      </p>
    );
  }
  return null;
}

/**
 * The figures behind the verdict, as counts and durations.
 *
 * Each is labelled and stated on its own. `coverable_topic_count` sits beside
 * `remaining_topic_count` as two separate figures rather than as a fraction,
 * because a denominator invites a comparison this product does not make.
 */
function Figures({ reading }: { reading: PlanFeasibilityReading }) {
  return (
    <dl className={styles.figures}>
      <div className={styles.figure}>
        <dt>Study time you saved</dt>
        <dd>{describeDuration(reading.available_minutes)}</dd>
      </div>
      <div className={styles.figure}>
        <dt>Time the remaining work needs</dt>
        <dd>{describeDuration(reading.required_minutes)}</dd>
      </div>
      {reading.shortfall_minutes > 0 ? (
        <div className={styles.figure}>
          <dt>Short by</dt>
          <dd>{describeDuration(reading.shortfall_minutes)}</dd>
        </div>
      ) : null}
      <div className={styles.figure}>
        <dt>Topics still to work through</dt>
        <dd>{reading.remaining_topic_count}</dd>
      </div>
      {reading.verdict === "insufficient" ? (
        <div className={styles.figure}>
          <dt>Topics that time covers</dt>
          <dd>{reading.coverable_topic_count}</dd>
        </div>
      ) : null}
      <div className={styles.figure}>
        <dt>Days to {reading.horizon_ends_on}</dt>
        <dd>{reading.study_days}</dd>
      </div>
    </dl>
  );
}

/**
 * A duration a learner reads, in hours and minutes.
 *
 * Printed from what the API sent, which is already a number of minutes over a
 * span the backend decided. Nothing is totalled here — this only chooses the
 * words for a figure that arrived.
 */
function describeDuration(minutes: number): string {
  if (minutes < 60) {
    return `${minutes} min`;
  }
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  const hourPart = `${hours} hr`;
  return remainder === 0 ? hourPart : `${hourPart} ${remainder} min`;
}
