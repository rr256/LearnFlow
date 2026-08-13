/**
 * Deciding which of a goal's active plans belong to the learner's own month.
 *
 * Plain functions, so they are testable at a fixed instant without a running
 * server, and presentation only. Nothing here plans, re-plans, or writes: the
 * monthly study view is a way of reading the `roadmap` and `weekly` plans the
 * backend already generated
 * (docs/development/coding-standards.md#ui-responsibilities).
 *
 * **This is not the `monthly` plan type.** `monthly` is an approved `plan_type`
 * that nothing generates, and ADR-020 left it that way deliberately. Nothing here
 * writes a plan record of any kind — it selects from ones that exist.
 *
 * **The frontend does not decide how much of a roadmap a month holds.** A weekly
 * plan dates seven days, so a calendar month contains at most one week of dated
 * work; the rest of the roadmap stays undated here rather than being spread across
 * the month's remaining days. Spreading it would be placing sessions, which is
 * planning arithmetic the backend owns and which no stored record would back.
 *
 * Dates stay ISO `YYYY-MM-DD` strings throughout and are compared as strings,
 * which orders them correctly and avoids the `new Date("2026-08-09")` trap
 * `features/home/dates.ts` records: a date-only string parses as UTC midnight,
 * which west of Greenwich would show a learner the previous month's boundary.
 */

import { groupByDay, type PlannedDay } from "@/features/planner/plan";
import { learnerToday } from "@/features/planner/today";
import type { PlanItem, StudyPlan } from "@/types/study-plan";

/** The month names a learner reads, as the rest of the UI hardcodes its copy. */
const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
] as const;

/** How many days each month holds, February excepted. */
const DAYS_IN_MONTH = [31, 0, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31] as const;

/** The first and last calendar dates of a month, as ISO `YYYY-MM-DD`. */
export interface MonthBounds {
  startsOn: string;
  endsOn: string;
}

/** What the monthly view shows, split into what is dated and what is not. */
export interface MonthlyWork {
  /**
   * The days inside the month that the active weekly plan placed work on, in
   * date order.
   *
   * Settled items are included and keep their place, as they do on every other
   * panel: the plan is the record of what the month held, so hiding finished work
   * would leave the month looking undone and hiding a skip or a postponement
   * would hide a decision the learner may want to take back.
   */
  days: PlannedDay[];
  /**
   * The roadmap's topics that the weekly plan has not dated, in roadmap order.
   *
   * Deliberately undated. These are what the plan works through after the dated
   * days above, and the plan itself has not said when — so neither does this.
   */
  ahead: PlanItem[];
}

/**
 * The learner's own calendar month at a given instant, as `YYYY-MM`.
 *
 * The learner's month, never the server's, for the reason `learnerToday` gives
 * about their date: a container running in UTC must not show a learner in
 * `Pacific/Kiritimati` last month on the first of theirs. Derived from
 * `learnerToday` rather than resolved again, so there is one conversion to keep
 * correct and one fallback to keep in step with the backend's.
 *
 * @param instant The moment to resolve. Passed in rather than read here, so a
 *   test can choose it.
 * @param timezone An IANA zone name, as `learners.timezone` stores it.
 */
export function learnerMonth(instant: Date, timezone: string): string {
  return learnerToday(instant, timezone).slice(0, 7);
}

/**
 * The first and last dates of a month.
 *
 * Computed from the month's own numbers rather than through a `Date`, so no
 * parsing rule or host timezone can move a boundary. The leap-year rule is the
 * full Gregorian one — divisible by four, except centuries that are not divisible
 * by four hundred — because a February boundary that is wrong once a century is
 * still wrong.
 *
 * @param month The learner's month, as `YYYY-MM`.
 */
export function monthBounds(month: string): MonthBounds {
  const year = Number(month.slice(0, 4));
  const ordinal = Number(month.slice(5, 7));
  const isLeapYear = (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
  // A month this build cannot count falls back to 31 days, which makes the
  // bounds too wide rather than too narrow: a view is better showing a day it
  // should not than hiding one the plan placed work on.
  const days = ordinal === 2 ? (isLeapYear ? 29 : 28) : (DAYS_IN_MONTH[ordinal - 1] ?? 31);

  return { startsOn: `${month}-01`, endsOn: `${month}-${String(days).padStart(2, "0")}` };
}

/**
 * The month as a learner reads it — `August 2026`.
 *
 * A month this function cannot name is returned as the string it was given rather
 * than rendered as `undefined`, which is the same fallback `describeAction`
 * applies to an action this build does not recognise.
 */
export function monthLabel(month: string): string {
  const name = MONTH_NAMES[Number(month.slice(5, 7)) - 1];
  return name ? `${name} ${month.slice(0, 4)}` : month;
}

/** Whether an ISO date falls inside the month, inclusive of both boundaries. */
export function isWithinMonth(on: string | null, month: string): boolean {
  if (on === null) {
    return false;
  }
  const { startsOn, endsOn } = monthBounds(month);
  return on >= startsOn && on <= endsOn;
}

/**
 * Split a goal's active plans into the month's dated work and the roadmap ahead
 * of it.
 *
 * A topic the weekly plan has dated is left out of `ahead` wherever that date
 * falls, including in a following month: it is work the plan has placed, and
 * listing it again as undated would say the plan had not decided when. A topic
 * dated beyond this month is simply not shown here, which is the honest reading
 * for a view about one month.
 *
 * A roadmap item naming no topic cannot be matched against a dated one, so it
 * stays in `ahead` rather than being dropped — the plan holds it, and a view that
 * silently omitted a line would misdescribe the plan it is rendering.
 *
 * @param week The goal's active weekly plan, or null when none was generated.
 * @param roadmap The goal's active roadmap, or null when none was generated.
 * @param month The learner's own month, from `learnerMonth`.
 */
export function selectMonthlyWork(
  week: StudyPlan | null,
  roadmap: StudyPlan | null,
  month: string,
): MonthlyWork {
  const datedTopicIds = new Set<string>();
  for (const item of week?.items ?? []) {
    if (item.scheduled_for !== null && item.topic !== null) {
      datedTopicIds.add(item.topic.id);
    }
  }

  return {
    days: groupByDay(week).filter((day) => isWithinMonth(day.on, month)),
    ahead: (roadmap?.items ?? []).filter(
      (item) => item.topic === null || !datedTopicIds.has(item.topic.id),
    ),
  };
}

/**
 * Whether the plan's dated work runs out before the month does.
 *
 * A weekly plan covers the seven days from the day it was generated, so a month
 * almost always outlasts it (ADR-020, ADR-022). A learner looking at a month
 * mostly free of dated work is owed that reason, rather than being left to infer
 * that the plan expects nothing of them.
 */
export function datedWorkEndsInsideMonth(week: StudyPlan | null, month: string): boolean {
  const endsOn = week?.period_end ?? null;
  return endsOn !== null && endsOn < monthBounds(month).endsOn;
}
