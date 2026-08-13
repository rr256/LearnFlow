import Link from "next/link";

import styles from "@/features/planner/MonthlyPlanView.module.css";
import {
  datedWorkEndsInsideMonth,
  isWithinMonth,
  monthLabel,
  selectMonthlyWork,
} from "@/features/planner/month";
import {
  describeAction,
  describeEstimate,
  describeSettledStatus,
  itemClassName,
} from "@/features/planner/plan";
import type { PlanItem, StudyPlan } from "@/types/study-plan";

interface MonthlyPlanViewProps {
  /** The goal's active roadmap, or null when none was generated. */
  roadmap: StudyPlan | null;
  /** The goal's active weekly plan, or null when none was generated. */
  week: StudyPlan | null;
  /** The learner's own calendar month, from `learnerMonth`. */
  month: string;
}

/**
 * The monthly study view: the work this month already has dates for, and the
 * roadmap that follows it.
 *
 * It is a **reading of the roadmap and the weekly plan**, not a plan of its own.
 * Nothing here generates, adapts, or stores anything, and no `monthly` plan record
 * exists — that plan type stays constrained and unwritten, as ADR-020 left it.
 *
 * Every item shows the reason the plan gave for it, which is FR-003's fourth
 * acceptance criterion, and an item the learner has settled keeps its place,
 * marked in words, as it does on every other panel.
 *
 * **This screen is read-only**, which is where it departs from the daily study
 * view. A month is where a learner looks ahead rather than where they work
 * through a day, so completing, skipping, and postponing stay on `/plan/today` and
 * `/plan`, and generating and adapting stay on `/plan`. Nothing here writes a
 * status, a date, or a plan.
 *
 * **The month is not filled in.** A weekly plan dates seven days, so the rest of
 * the month has no dated work and this view says so rather than spreading the
 * roadmap across the days that are left — placing sessions is planning arithmetic
 * the backend owns (docs/development/coding-standards.md#ui-responsibilities).
 *
 * The wording describes **the plan and its items**, never the learner, and nothing
 * is counted, totalled, ranked, or scored (docs/domain/terminology.md).
 */
export function MonthlyPlanView({ roadmap, week, month }: MonthlyPlanViewProps) {
  const work = selectMonthlyWork(week, roadmap, month);
  const horizon = roadmap?.period_end ?? null;

  return (
    <>
      <section aria-labelledby="dated-this-month" className={styles.panel}>
        <h2 id="dated-this-month">{monthLabel(month)}</h2>

        {work.days.length === 0 ? (
          <p className={styles.empty}>
            Your plan has placed no work on a day in {monthLabel(month)}. A plan dates the week
            ahead of when it was built, so a month you are early or late in holds none of it —{" "}
            <Link href="/plan">update your plan</Link> to get dated work for the week ahead.
          </p>
        ) : (
          <>
            <p className={styles.lead}>
              The days this month your plan has already placed work on. Mark work as you do it on{" "}
              <Link href="/plan/today">today&apos;s study view</Link>.
            </p>
            <ol className={styles.days}>
              {work.days.map((day) => (
                <li key={day.on}>
                  <h3 className={styles.date}>{day.on}</h3>
                  <ul className={styles.items}>
                    {day.items.map((item) => (
                      <PlanItemLine item={item} key={item.id} />
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          </>
        )}

        {datedWorkEndsInsideMonth(week, month) ? (
          <p className={styles.note}>
            Your plan dates work as far as {week?.period_end}. The rest of {monthLabel(month)} has
            no dates yet — the topics below are the order it works through next, and{" "}
            <Link href="/plan">updating your plan</Link> is what gives them days.
          </p>
        ) : null}

        {horizon ? (
          <p className={styles.note}>
            {isWithinMonth(horizon, month)
              ? `This is the month you are working toward: your plan runs to ${horizon}.`
              : `You are working toward ${horizon}.`}
          </p>
        ) : null}
      </section>

      <section aria-labelledby="roadmap-ahead" className={styles.panel}>
        <h2 id="roadmap-ahead">Next in your roadmap</h2>
        {work.ahead.length === 0 ? (
          <EmptyRoadmap roadmap={roadmap} />
        ) : (
          <>
            <p className={styles.lead}>
              The topics your roadmap works through after the dated days above, in the order it
              chose. These have no dates yet, and nothing here has moved them.
            </p>
            <ul className={styles.items}>
              {work.ahead.map((item) => (
                <PlanItemLine item={item} key={item.id} />
              ))}
            </ul>
          </>
        )}
      </section>
    </>
  );
}

/**
 * One item of the plan, as both lists on this screen show it.
 *
 * The same fields the week's panel and the daily view show, in the same order, so
 * an item reads the same wherever a learner meets it — without the status control,
 * which this screen deliberately does not carry.
 */
function PlanItemLine({ item }: { item: PlanItem }) {
  return (
    <li className={itemClassName(item, styles)}>
      <p className={styles.topic}>
        <span className={styles.action}>{describeAction(item.action_type)}</span>{" "}
        {item.topic ? item.topic.name : "A topic that is no longer stored"}
      </p>
      <p className={styles.meta}>
        {item.topic ? `${item.topic.subject_name} · ` : ""}
        {describeEstimate(item.estimated_minutes)}
      </p>
      {describeSettledStatus(item.status) ? (
        <p className={styles.settledLabel}>{describeSettledStatus(item.status)}</p>
      ) : null}
      {item.recommendation_reason ? <p className={styles.why}>{item.recommendation_reason}</p> : null}
    </li>
  );
}

/**
 * Why nothing follows the dated days, said plainly rather than left to be
 * inferred.
 *
 * Two different situations reach this, and they mean opposite things: a goal with
 * no roadmap has had nothing built for it, while a roadmap whose every topic the
 * week has dated is a plan that fits inside one week.
 */
function EmptyRoadmap({ roadmap }: { roadmap: StudyPlan | null }) {
  if (!roadmap) {
    return (
      <p className={styles.empty}>
        This goal has no roadmap, so there is no order to work through yet.{" "}
        <Link href="/plan">Generate a plan</Link> to get one.
      </p>
    );
  }

  return (
    <p className={styles.empty}>
      Your roadmap has no topics beyond the dated days above — the week your plan covers reaches
      all of them.
    </p>
  );
}
