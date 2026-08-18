import Link from "next/link";

import styles from "@/features/planner/DailyStudyView.module.css";
import { PlanItemStatusControl } from "@/features/planner/PlanItemStatusControl";
import {
  describeAction,
  describeEstimate,
  describeSettledStatus,
  itemClassName,
} from "@/features/planner/plan";
import { selectDailyWork, weekHasPassed } from "@/features/planner/today";
import { TopicResources } from "@/features/resources/TopicResources";
import { resourcesFor } from "@/features/resources/by-topic";
import type { LearningResource } from "@/types/resource";
import type { PlanItem, StudyPlan } from "@/types/study-plan";

interface DailyStudyViewProps {
  /** The goal's active weekly plan, or null when none was generated. */
  plan: StudyPlan | null;
  /** The learner's own calendar date, from `learnerToday`. */
  today: string;
  /**
   * The learner's catalogued material, keyed by the topics it covers, or null
   * when it could not be read. Null renders the day without it, which costs the
   * reader the material rather than the work they came for.
   */
  resources?: Map<string, LearningResource[]> | null;
}

/**
 * The daily study view: the work the active weekly plan placed on today, and the
 * work whose day has passed.
 *
 * It is a **reading of the weekly plan**, not a plan of its own. Nothing here
 * generates, adapts, or stores anything, and no `daily` plan record exists —
 * that plan type stays constrained and unwritten, as ADR-020 left it.
 *
 * Every item shows the reason the plan gave for it, which is FR-003's fourth
 * acceptance criterion, and carries the same PLN-004 control the week and the
 * roadmap carry — completed, skipped, postponed, or back to planned. A plan item
 * is a plan item whichever screen shows it, and moving one still moves that item
 * alone.
 *
 * **Work whose day has passed is shown, and nothing moves it.** It sits under its
 * own heading rather than mixed into today, because the plan did not ask for it
 * today and this screen must not say it did. Carrying it forward is adaptation,
 * which the learner asks for on the plan screen — a list that rearranged itself
 * under a hand ticking it would be the surprise ADR-022 refused. **Postponing an
 * item here does not move it either**: it records what the learner wants, and the
 * work is placed again when they next update their plan.
 *
 * Work the learner has **settled** does not appear under that heading: a skipped
 * or postponed item is not outstanding, so showing it back to them as work still
 * owed would ask a question they have already answered.
 *
 * The wording describes **items**, never the learner: an item is overdue, and a
 * day that passed is a fact about a date rather than a verdict on a person
 * (docs/domain/terminology.md). Nothing is counted, totalled, or scored.
 *
 * **The material beside an item is the learner's own, and nothing suggests any.**
 * It is what they linked to that topic in their catalogue, listed read-only in the
 * API's order; material they have put aside is left out, and a topic with nothing
 * linked shows nothing rather than an invented suggestion. It is here because this
 * is the screen a learner reads before they sit down to study — registering,
 * correcting, and putting material aside stay on the catalogue screen, exactly as
 * generating and adapting stay on the plan screen.
 */
export function DailyStudyView({ plan, today, resources = null }: DailyStudyViewProps) {
  const work = selectDailyWork(plan, today);

  return (
    <>
      <section aria-labelledby="todays-work" className={styles.panel}>
        <h2 id="todays-work">Today</h2>
        {/*
         * Printed as the API prints a date. Parsing a date-only string into a
         * `Date` reads it as UTC midnight, which west of Greenwich would head the
         * day's work with the previous day.
         */}
        <p className={styles.date}>{today}</p>

        {work.today.length === 0 ? (
          <EmptyDay plan={plan} today={today} />
        ) : (
          <ul className={styles.items}>
            {work.today.map((item) => (
              <PlanItemLine item={item} key={item.id} resources={resources} />
            ))}
          </ul>
        )}
      </section>

      {work.earlier.length === 0 ? null : (
        <section aria-labelledby="earlier-work" className={styles.panel}>
          <h2 id="earlier-work">From earlier days</h2>
          <p className={styles.lead}>
            Your plan placed these on days that have now passed. Nothing has moved them, and
            nothing here is a mark against you. When you are ready,{" "}
            <Link href="/plan">update your plan</Link> and this work is carried forward onto the
            plan that replaces it.
          </p>
          <ol className={styles.days}>
            {work.earlier.map((day) => (
              <li key={day.on}>
                <h3 className={styles.date}>{day.on}</h3>
                <ul className={styles.items}>
                  {day.items.map((item) => (
                    <PlanItemLine item={item} key={item.id} resources={resources} />
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </section>
      )}
    </>
  );
}

/**
 * One item of the plan, as both lists on this screen show it.
 *
 * The same fields the week's panel shows, in the same order, so an item reads
 * the same wherever a learner meets it — the learner's own material for its topic
 * included, which is why the panel on the plan screen renders it in the same
 * place.
 */
function PlanItemLine({
  item,
  resources,
}: {
  item: PlanItem;
  resources: Map<string, LearningResource[]> | null;
}) {
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
      {/*
        The learner's own material for this item's topic, read-only: adding it
        and putting it aside live on the catalogue screen. Nothing is suggested --
        this is what they linked, and a topic with nothing linked renders nothing.
      */}
      {resources && item.topic ? (
        <TopicResources
          resources={resourcesFor(resources, item.topic.id)}
          topicName={item.topic.name}
        />
      ) : null}
      <PlanItemStatusControl
        planItemId={item.id}
        status={item.status}
        topicName={item.topic ? item.topic.name : "this item"}
      />
    </li>
  );
}

/**
 * Why today holds no work, said plainly rather than left to be inferred.
 *
 * A weekly plan covers the seven days from the day it was generated, so a learner
 * returning after that span has an empty day for a reason the screen can state.
 * A day inside the span holds nothing because the plan placed nothing on it —
 * which the learner's saved week decides, and this screen does not second-guess.
 */
function EmptyDay({ plan, today }: { plan: StudyPlan | null; today: string }) {
  if (weekHasPassed(plan, today)) {
    return (
      <p className={styles.empty}>
        The week this plan covers ran to {plan?.period_end} and has passed, so it places no work on
        today. <Link href="/plan">Update your plan</Link> to get dated work for the week ahead.
      </p>
    );
  }

  return (
    <p className={styles.empty}>
      Nothing is planned for today. Your plan places work only on the days you told LearnFlow you
      can study — you can change that in <Link href="/setup">your setup</Link>, or see the rest of
      the week on <Link href="/plan">your study plan</Link>.
    </p>
  );
}
