/**
 * Selecting what currently needs the learner's attention, out of records that
 * already exist.
 *
 * This is the **priority focus** [FR-011](docs/requirements/functional.md)
 * describes, built from three facts a backend rule has already decided: work
 * whose day has passed and which nobody has settled, reviews the backend reports
 * as due, and a saved week that PLN-006 says does not reach the goal's horizon.
 * Plain functions, so they are testable without a running server.
 *
 * **Nothing here decides that anything is a priority.** Each of the three is a
 * boolean the backend already owns — `select_overdue`'s partition, `is_due`, and
 * PLN-006's verdict — and this module filters on it and chooses words. What
 * counts as overdue, what counts as due, and whether a week reaches a date are
 * domain rules (docs/development/coding-standards.md#ui-responsibilities), and
 * this file would be the wrong place to disagree with them.
 *
 * **Nothing here ranks.** No topic is compared against another, no entry is
 * numbered, no group is "more urgent" than another, and there is no top-anything.
 * The group order below is presentation in the same sense that Monday comes first
 * in a week — it is held here rather than stored, and it ranks nothing.
 *
 * **The learning stage is deliberately not a signal.** Treating some of the five
 * stages as priorities and the rest as not would rank them against each other,
 * which ADR-017 and ADR-030 both refuse: a learner may move to any stage from any
 * stage, including backwards, so no stage is behind another. The stage still
 * reaches the learner here — it is inside the plan item's own
 * `recommendation_reason`, written when the plan was generated (ADR-020) and
 * rendered unchanged.
 *
 * **Nothing here counts.** No total, no percentage, no ratio, no streak, and no
 * tally of how many things need attention. The list lengths below decide whether
 * a group has anything to show; none of them reaches the screen.
 *
 * Dates stay ISO `YYYY-MM-DD` strings and are never parsed into a `Date`, for the
 * reason `features/home/dates.ts` records.
 */

import { selectDailyWork } from "@/features/planner/today";
import type { Revision } from "@/types/revision";
import type { PlanFeasibility, StudyPlan } from "@/types/study-plan";

/** The kinds of attention this panel distinguishes. */
export type PriorityKind = "outstanding_work" | "review_due" | "time_to_date";

/** One thing needing attention, with the record that put it there. */
export interface PriorityEntry {
  /** Stable key for rendering. It is never shown to a learner. */
  id: string;
  /** The heading a learner reads: a topic's name, or what the entry is about. */
  title: string;
  /** The subject the topic belongs to, or null when there is none to name. */
  context: string | null;
  /**
   * The neutral fact that put this entry here, in one sentence.
   *
   * It describes a **record and a date** — an item, a review, a plan, a week —
   * and never the learner. "A day has passed" is a fact about a date, where "you
   * are behind" is a verdict on a person, which docs/domain/terminology.md rules
   * out by name.
   */
  fact: string;
  /**
   * The sentence the backend wrote for this record, or null when it wrote none.
   *
   * Rendered rather than replaced: a plan item's and a revision's reasons are
   * frozen when the record is created, and PLN-006 composes its own beside the
   * figures it quotes. A screen writing its own could disagree with the record it
   * is explaining.
   */
  reason: string | null;
}

/** The entries sharing one kind of attention, under the words that describe it. */
export interface PriorityGroup {
  kind: PriorityKind;
  /** The heading a learner reads for this kind. */
  heading: string;
  /** Where the learner acts on this kind. This panel never acts itself. */
  actionHref: string;
  actionLabel: string;
  entries: PriorityEntry[];
}

/** What the priority focus panel states. */
export interface PriorityFocus {
  /** The groups holding at least one entry, in the fixed order below. */
  groups: PriorityGroup[];
}

/**
 * The order the groups appear in.
 *
 * Presentation, and **not a ranking**: outstanding work is not more important
 * than a review that is ready, and neither outranks a week that falls short.
 * The three are different kinds of fact about different records, and a learner
 * decides for themselves which to pick up. The order is fixed only so the panel
 * reads the same way twice.
 */
const GROUP_ORDER: readonly PriorityKind[] = ["outstanding_work", "review_due", "time_to_date"];

/** What a learner reads as each group's heading, and where each is acted on. */
const GROUP_HEADINGS: Record<PriorityKind, string> = {
  outstanding_work: "Work whose day has passed",
  review_due: "Topics ready to come back",
  time_to_date: "The time you have saved",
};

/**
 * Everything currently needing the learner's attention, from what is stored.
 *
 * @param week The goal's active weekly plan, or null when none was generated. A
 *   roadmap is deliberately not accepted here: its items carry no date, so
 *   nothing about them can have passed.
 * @param today The learner's own date, from `learnerToday`.
 * @param revisions Every revision the learner has, as REV-001 returned them.
 * @param feasibility PLN-006's reading. Null contributes no entry rather than a
 *   claim in either direction. **No screen reaches this with null today**: a
 *   failed PLN-006 read is an `ApiError` that the page reports in full, which is
 *   ADR-029's decision about an unreachable API and is unchanged here. The
 *   parameter tolerates it because the prop it comes from is typed that way, not
 *   because a state is being invented for it.
 */
export function selectPriorityFocus(
  week: StudyPlan | null,
  today: string,
  revisions: readonly Revision[],
  feasibility: PlanFeasibility | null,
): PriorityFocus {
  const entries: Record<PriorityKind, PriorityEntry[]> = {
    outstanding_work: outstandingWork(week, today),
    review_due: reviewsDue(revisions),
    time_to_date: timeToDate(feasibility),
  };

  return {
    groups: GROUP_ORDER.map((kind) => ({
      kind,
      heading: GROUP_HEADINGS[kind],
      actionHref: actionFor(kind, feasibility).href,
      actionLabel: actionFor(kind, feasibility).label,
      entries: entries[kind],
    })).filter((group) => group.entries.length > 0),
  };
}

/**
 * Work the plan placed on days that have passed, which nobody has settled.
 *
 * The **same partition** `/plan/today` and the overview's today panel make, from
 * the same `selectDailyWork`, so the three cannot disagree about which work is
 * still outstanding. A completed, skipped, or postponed item is settled and never
 * appears: the learner has already answered, and asking again would show their
 * own statement back to them as a demand.
 *
 * Nothing here moves anything. Placing this work again is adaptation, which the
 * learner asks for on `/plan` (ADR-022).
 */
function outstandingWork(week: StudyPlan | null, today: string): PriorityEntry[] {
  return selectDailyWork(week, today).earlier.flatMap((day) =>
    day.items.map((item) => ({
      id: item.id,
      title: item.topic ? item.topic.name : "A topic that is no longer stored",
      context: item.topic ? item.topic.subject_name : null,
      // The date is printed as the API sent it. The item, not the learner, is
      // what the day passed on.
      fact: `Your plan placed this on ${day.on}, and that day has passed with nothing said about it.`,
      reason: item.recommendation_reason,
    })),
  );
}

/**
 * The reviews the backend reports as owed now.
 *
 * `is_due` is **read, not derived**, exactly as `selectDueReviews` reads it: what
 * counts as due is a domain rule, and unlike an overdue plan item a revision
 * dated today is due. A review is a **recommendation, not a failure notice**
 * (docs/domain/terminology.md), so the wording offers it rather than demanding
 * it, and nothing here says a learner is behind on revision.
 */
function reviewsDue(revisions: readonly Revision[]): PriorityEntry[] {
  return revisions
    .filter((revision) => revision.is_due)
    .map((revision) => ({
      id: revision.id,
      title: revision.topic ? revision.topic.name : "A topic that is no longer stored",
      context: revision.topic ? revision.topic.subject_name : null,
      fact: `LearnFlow has had this ready to review since ${revision.due_on}.`,
      reason: revision.recommendation_reason,
    }));
}

/**
 * Whether the saved week is something the learner may want to look at.
 *
 * `sufficient` yields nothing: a week that reaches the date needs no attention.
 * `insufficient` and `unknown` each do, and they ask for different things — one
 * is arithmetic that came out short, the other is a question nobody has given
 * LearnFlow the inputs to answer, which ADR-027 records as an answer rather than
 * a failure.
 *
 * A verdict this build does not recognise yields **nothing**, rather than being
 * guessed at in either direction. Claiming a priority from a value that cannot be
 * interpreted would put a demand in front of a learner that no rule made, and the
 * feasibility panel below still renders the reading in full.
 *
 * Every figure stays where PLN-006 put it. Nothing here totals a week — that
 * arithmetic belongs to the domain rule alone (docs/domain/terminology.md).
 */
function timeToDate(feasibility: PlanFeasibility | null): PriorityEntry[] {
  if (!feasibility) {
    return [];
  }
  const fact = describeTimeFact(feasibility);
  if (fact === null) {
    return [];
  }

  return [
    {
      id: feasibility.study_goal_id,
      title: "The study time you saved and the date you are working toward",
      context: null,
      fact,
      reason: feasibility.reason,
    },
  ];
}

/**
 * The neutral fact behind a feasibility verdict, or null when it is not one to
 * raise.
 *
 * A statement about **the plan and the time** in every case. A week that cannot
 * reach a date is arithmetic, not a verdict on effort.
 */
function describeTimeFact(feasibility: PlanFeasibility): string | null {
  if (feasibility.verdict === "insufficient") {
    return "The study time you have saved does not cover the work left before your date.";
  }
  if (feasibility.verdict !== "unknown") {
    return null;
  }
  if (feasibility.unknown_reason === "no_horizon") {
    return "This goal aims at no examination cycle and no target date, so there is no date to work back from.";
  }
  if (feasibility.unknown_reason === "no_availability_saved") {
    return "No study week is saved for this goal, so there is no study time to work with.";
  }
  return "Whether your saved study time reaches your date cannot be worked out yet.";
}

/**
 * Where a learner acts on one kind of attention.
 *
 * Every group **names where its action lives and links to it**, which is
 * ADR-029's rule for this screen: `/progress` writes nothing, so keeping one
 * place per action is what stops a second surface acquiring its own controls.
 *
 * The time group's destination depends on what is missing. A shortfall is
 * something to see in full and re-plan around, which is `/plan`; an unanswerable
 * question needs a date or a week, which is `/setup`.
 */
function actionFor(
  kind: PriorityKind,
  feasibility: PlanFeasibility | null,
): { href: string; label: string } {
  if (kind === "outstanding_work") {
    return { href: "/plan/today", label: "Say what became of it on today's screen" };
  }
  if (kind === "review_due") {
    return { href: "/revisions", label: "Mark these on your reviews screen" };
  }
  if (feasibility?.verdict === "unknown") {
    return { href: "/setup", label: "Complete your study setup" };
  }
  return { href: "/plan", label: "See the figures and update your plan" };
}
