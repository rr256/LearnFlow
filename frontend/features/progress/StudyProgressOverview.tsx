import Link from "next/link";

import { PlanFeasibility } from "@/features/planner/PlanFeasibility";
import {
  describeAction,
  describeEstimate,
  describeSettledStatus,
  itemClassName,
} from "@/features/planner/plan";
import { selectDailyWork, weekHasPassed } from "@/features/planner/today";
import { LearningStagesBySubject } from "@/features/progress/LearningStagesBySubject";
import { PriorityFocus } from "@/features/progress/PriorityFocus";
import styles from "@/features/progress/StudyProgressOverview.module.css";
import { describePlanType, selectDueReviews, selectMarkedWork } from "@/features/progress/overview";
import { selectPriorityFocus } from "@/features/progress/priority-focus";
import { selectStagesBySubject } from "@/features/progress/subject-stages";
import type { MarkedGroup } from "@/features/progress/overview";
import type { RecordedStages } from "@/features/progress/subject-stages";
import type { Revision } from "@/types/revision";
import type { DailyWork } from "@/features/planner/today";
import type { PlanItem, PlanFeasibility as PlanFeasibilityReading, StudyPlan } from "@/types/study-plan";

interface StudyProgressOverviewProps {
  /** The goal's active roadmap, or null when nothing has been generated. */
  roadmap: StudyPlan | null;
  /** The goal's active weekly plan, or null when the week had no room. */
  week: StudyPlan | null;
  /** The learner's own calendar date, resolved from their stored timezone. */
  today: string;
  /** Whether the saved week reaches the horizon, or null when unavailable. */
  feasibility: PlanFeasibilityReading | null;
  /** Every revision the learner has, in the order the backend returned them. */
  revisions: Revision[];
  /**
   * The learner's recorded stages and the curriculum that places them, or null
   * when either read failed. Null is not an empty study history, and the panel
   * says which of the two it is looking at.
   */
  stages: RecordedStages | null;
  /** The curriculum screen where a learning stage is recorded and changed. */
  curriculumHref: string;
}

/**
 * Where the learner's study stands, gathered from records that already exist.
 *
 * This is the **progress overview** [FR-011](docs/requirements/functional.md)
 * describes, and it is a **reading**: it consumes LRN-001, GOAL-002, PLN-002,
 * PLN-003, PLN-006, REV-001, PRG-002, and CUR-003 unchanged and adds no endpoint
 * of its own. PRG-001 stays unimplemented: the priority focus panel below is
 * drawn from facts these eight reads already carry, and the quiz, test, and
 * mistake evidence PRG-001's purpose also promises is still stored nowhere.
 *
 * **It writes nothing at all.** No status control, no generate control, no adapt
 * control, and no scheduling control — the read-only shape ADR-026 fixed for the
 * monthly study view, for the reason it gave: marking work belongs where a
 * learner works. Every panel names where its action lives and links to it.
 *
 * **Nothing is counted, totalled, ranked, or scored.** The only figures on the
 * screen are ones the API reported — a plan's `item_count`, and the counts and
 * durations PLN-006 returned — which
 * docs/domain/terminology.md#plan-coverage-counts-are-not-learner-scores permits
 * as facts about a plan. There is no completion count, no revision count, no
 * skip or postponement tally, no percentage, and no streak.
 *
 * **The wording describes work and plans, never the learner.** An item is
 * overdue; a learner is never behind.
 */
export function StudyProgressOverview({
  roadmap,
  week,
  today,
  feasibility,
  revisions,
  stages,
  curriculumHref,
}: StudyProgressOverviewProps) {
  return (
    <>
      {/*
       * What needs attention comes before where things stand: a learner opening
       * this screen is asking what to pick up, and the panels below answer where
       * they are. Everything it names is drawn from the same reads the panels
       * below render, so the two cannot disagree.
       */}
      <PriorityFocus
        focus={selectPriorityFocus(week, today, revisions, feasibility)}
        hasWeek={week !== null}
      />
      <PlanStanding roadmap={roadmap} week={week} />
      <TodaysWork today={today} week={week} work={selectDailyWork(week, today)} />
      {/*
       * Rendered exactly as `/plan` renders it, from the same reading. The
       * sentence and every figure are the backend's; this screen composes none
       * of them and carries no control beside them.
       */}
      <PlanFeasibility reading={feasibility} />
      <MarkedWork groups={selectMarkedWork([week, roadmap])} />
      {/*
       * What the learner said about the *topics*, beside what they said about
       * the plan. Both are their own statements, so the two sit together; the
       * plan item records whether work happened and the stage records how far
       * along they judge themselves to be, and nothing derives either from the
       * other.
       */}
      <LearningStagesBySubject
        curriculumHref={curriculumHref}
        groups={stages ? selectStagesBySubject(stages.records, stages.subjects) : null}
      />
      <ReadyToReview due={selectDueReviews(revisions)} hasAny={revisions.length > 0} />
    </>
  );
}

/**
 * The plans the learner is working from, and how much each covers.
 *
 * `item_count` is the API's own figure and is a *plan coverage count*: it
 * describes the plan rather than the learner, and would be just as true of a plan
 * nobody had touched. It is stated on its own and never against a second number.
 */
function PlanStanding({ roadmap, week }: { roadmap: StudyPlan | null; week: StudyPlan | null }) {
  const plans = [roadmap, week].filter((plan): plan is StudyPlan => plan !== null);

  return (
    <section aria-labelledby="plan-standing" className={styles.panel}>
      <h2 id="plan-standing">Where your plan stands</h2>
      {plans.length === 0 ? (
        <p className={styles.empty}>
          Nothing has been generated for this goal yet.{" "}
          <Link href="/plan">Generate a plan</Link>, and what it covers appears here.
        </p>
      ) : (
        <ul className={styles.plans}>
          {plans.map((plan) => (
            <li className={styles.plan} key={plan.id}>
              <p className={styles.planName}>{describePlanType(plan.plan_type)}</p>
              {/*
               * Dates are printed as the API sent them. Parsing a date-only
               * string into a `Date` reads it as UTC midnight, which west of
               * Greenwich would move a plan's span by a day.
               */}
              <p className={styles.meta}>
                {plan.item_count} topics
                {plan.period_start && plan.period_end
                  ? `, from ${plan.period_start} to ${plan.period_end}`
                  : ""}
                .
              </p>
              {plan.generation_reason ? (
                <p className={styles.why}>{plan.generation_reason}</p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * The work the plan placed on the learner's own date.
 *
 * The same selection `/plan/today` makes, from the same function, so the two
 * screens cannot disagree about which day a learner is on. This one carries no
 * control: marking work stays on the daily screen, which this panel links to.
 *
 * Work whose day has passed is reported as **outstanding**, without being counted
 * and without moving. Carrying work forward is adaptation, which the learner asks
 * for on `/plan`.
 */
function TodaysWork({
  work,
  week,
  today,
}: {
  work: DailyWork;
  week: StudyPlan | null;
  today: string;
}) {
  return (
    <section aria-labelledby="todays-work" className={styles.panel}>
      <h2 id="todays-work">Today</h2>
      <p className={styles.date}>{today}</p>
      {work.today.length === 0 ? (
        <NothingToday today={today} week={week} />
      ) : (
        <>
          <p className={styles.lead}>
            What your plan asks of you today.{" "}
            <Link href="/plan/today">Mark it on today&apos;s screen</Link>.
          </p>
          <ul className={styles.items}>
            {work.today.map((item) => (
              <OverviewItem item={item} key={item.id} />
            ))}
          </ul>
        </>
      )}
      {work.earlier.length > 0 ? (
        <p className={styles.note}>
          Work from earlier days is still outstanding.{" "}
          <Link href="/plan/today">See it on today&apos;s screen</Link>, where you can say what
          became of it, or <Link href="/plan">update your plan</Link> to place it again.
        </p>
      ) : null}
    </section>
  );
}

/**
 * Why today holds nothing, said plainly rather than left to be inferred.
 *
 * Three situations reach this and they mean different things: no dated plan
 * exists at all, the plan's week ended before today, or the plan simply placed no
 * work on this day — which is what a day the learner kept free looks like.
 */
function NothingToday({ week, today }: { week: StudyPlan | null; today: string }) {
  if (!week) {
    return (
      <p className={styles.empty}>
        This goal has no plan for a week, so nothing is placed on a day.{" "}
        <Link href="/plan">Generate or update your plan</Link> to get dated work.
      </p>
    );
  }
  if (weekHasPassed(week, today)) {
    return (
      <p className={styles.empty}>
        Your plan dates work to {week.period_end}, which has passed, so today holds nothing.{" "}
        <Link href="/plan">Update your plan</Link> to date the days ahead.
      </p>
    );
  }
  return (
    <p className={styles.empty}>
      Your plan places no work on today. That is a day you have no study time saved for, or one you
      kept free.
    </p>
  );
}

/**
 * What the learner has said about the plans they are working from now.
 *
 * A statement about **planned sessions**, never about the learner: every mark is
 * reversible, a skipped or postponed topic is planned again, and nothing here
 * records or asks why. The three groups are listed, never tallied — terminology
 * forbids counting skips and postponements by name.
 *
 * Marks made on a plan that has since been superseded are not shown, because only
 * the goal's active plans are read. That is deliberate: a superseded plan is
 * history a learner can no longer write into.
 */
function MarkedWork({ groups }: { groups: MarkedGroup[] }) {
  return (
    <section aria-labelledby="marked-work" className={styles.panel}>
      <h2 id="marked-work">What you have said about your plan</h2>
      {groups.length === 0 ? (
        <p className={styles.empty}>
          You have not marked anything on your current plan yet. Marking work completed, skipped,
          or postponed happens on <Link href="/plan/today">today&apos;s screen</Link> or on{" "}
          <Link href="/plan">your study plan</Link>.
        </p>
      ) : (
        <>
          <p className={styles.lead}>
            What you have marked on the plans you are working from now. Each one describes a
            planned session, and every one of them can be changed.
          </p>
          {groups.map((group) => (
            <div className={styles.group} key={group.status}>
              <h3 className={styles.groupLabel}>{group.label}</h3>
              <ul className={styles.items}>
                {group.items.map(({ item, planLabel }) => (
                  <li className={itemClassName(item, styles)} key={item.id}>
                    <p className={styles.topic}>
                      {item.topic ? item.topic.name : "A topic that is no longer stored"}
                    </p>
                    <p className={styles.meta}>
                      {item.topic ? `${item.topic.subject_name} · ` : ""}
                      {planLabel}
                      {item.scheduled_for ? ` · ${item.scheduled_for}` : ""}
                    </p>
                    {item.recommendation_reason ? (
                      <p className={styles.why}>{item.recommendation_reason}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </>
      )}
    </section>
  );
}

/**
 * The topics ready to come back, as the backend decided.
 *
 * A revision is a **recommendation, not a failure notice**
 * (docs/domain/terminology.md). Nothing here says a learner is behind on
 * revision, and **nothing counts reviews** — that count is forbidden in the
 * interface outright, so this panel lists what is ready and states no total.
 */
function ReadyToReview({ due, hasAny }: { due: Revision[]; hasAny: boolean }) {
  return (
    <section aria-labelledby="ready-to-review" className={styles.panel}>
      <h2 id="ready-to-review">Ready to review</h2>
      {due.length === 0 ? (
        <p className={styles.empty}>
          {hasAny
            ? "Nothing is ready to review today. Your reviews have days still to come, or you have already dealt with them."
            : "No reviews are scheduled yet. Reviews come from work you have finished, and you ask for them."}{" "}
          <Link href="/revisions">Your reviews</Link>
        </p>
      ) : (
        <>
          <p className={styles.lead}>
            Topics you have finished, coming back so they stay familiar.{" "}
            <Link href="/revisions">Mark them on your reviews screen</Link>.
          </p>
          <ul className={styles.items}>
            {due.map((revision) => (
              <li className={styles.item} key={revision.id}>
                <p className={styles.topic}>
                  {revision.topic ? revision.topic.name : "A topic that is no longer stored"}
                </p>
                <p className={styles.meta}>
                  {revision.topic ? `${revision.topic.subject_name} · ` : ""}
                  Due {revision.due_on}
                </p>
                {revision.recommendation_reason ? (
                  <p className={styles.why}>{revision.recommendation_reason}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

/**
 * One item of today's work, read-only.
 *
 * The same fields the week and the daily view show — action, topic, subject,
 * estimate, and the reason the plan gave — without the control they carry. A
 * settled item keeps its place, marked in words rather than by its border alone.
 */
function OverviewItem({ item }: { item: PlanItem }) {
  const settled = describeSettledStatus(item.status);

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
      {settled ? <p className={styles.settledLabel}>{settled}</p> : null}
      {item.recommendation_reason ? <p className={styles.why}>{item.recommendation_reason}</p> : null}
    </li>
  );
}
