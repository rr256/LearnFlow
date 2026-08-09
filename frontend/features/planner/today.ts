/**
 * Deciding which of a weekly plan's items belong to the learner's own today.
 *
 * Plain functions, so they are testable at a fixed instant without a running
 * server, and presentation only. Nothing here plans, re-plans, or writes: the
 * daily view is a way of reading the `weekly` plan the backend already generated
 * (docs/development/coding-standards.md#ui-responsibilities).
 *
 * **This is not the `daily` plan type.** `daily` is an approved `plan_type` that
 * nothing generates, and ADR-020 left it that way deliberately. Nothing here
 * writes a plan record of any kind — it selects from one that exists.
 *
 * **What counts as overdue is mirrored, not owned.** `select_overdue` in
 * `backend/app/domain/study_planning.py` is the authoritative rule, and it is
 * what *adaptation* acts on. The partition below groups the same items for
 * display and acts on nothing, so the two agree on the boundaries: an item dated
 * today is not overdue, an undated roadmap item never is, and completed work
 * never is however late it was done.
 *
 * Dates stay ISO `YYYY-MM-DD` strings throughout and are compared as strings,
 * which orders them correctly and avoids the `new Date("2026-08-09")` trap
 * `features/home/dates.ts` records: a date-only string parses as UTC midnight,
 * which west of Greenwich would show a learner the previous day's work.
 */

import { groupByDay, type PlannedDay } from "@/features/planner/plan";
import type { PlanItem, StudyPlan } from "@/types/study-plan";

/** The zone a learner's date falls back to when their stored one cannot be read. */
const FALLBACK_TIMEZONE = "UTC";

/** What the daily view shows, split into what is due today and what is not. */
export interface DailyWork {
  /**
   * The items the plan placed on the learner's own date, in plan order.
   *
   * Completed items are included and keep their place: the plan is the record of
   * what the day held, and hiding finished work would leave the day looking
   * undone (ADR-021).
   */
  today: PlanItem[];
  /**
   * Work the plan placed on days that have passed and which has not happened,
   * grouped by the day it was placed on, earliest first.
   *
   * Nothing here moves it. Carrying work forward is adaptation, which the learner
   * asks for on the plan screen (ADR-022).
   */
  earlier: PlannedDay[];
}

/**
 * The learner's own calendar date at a given instant, as `YYYY-MM-DD`.
 *
 * The learner's date, never the server's. A plan read at 23:30 in `Asia/Kolkata`
 * from a container running in UTC must show today's work rather than tomorrow's,
 * which is the reason `learners.timezone` is stored at all (ADR-013, ADR-016).
 * This is the same conversion `_today_for` performs in the backend, including its
 * fallback: a zone that cannot be read falls back to UTC rather than failing the
 * page, because a date a day out is recoverable and a blank screen is not.
 *
 * @param instant The moment to resolve. Passed in rather than read here, so a
 *   test can choose it.
 * @param timezone An IANA zone name, as `learners.timezone` stores it.
 */
export function learnerToday(instant: Date, timezone: string): string {
  let parts: Intl.DateTimeFormatPart[];
  try {
    parts = dateParts(instant, timezone);
  } catch {
    parts = dateParts(instant, FALLBACK_TIMEZONE);
  }

  const value = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? "";
  return `${value("year")}-${value("month")}-${value("day")}`;
}

/**
 * The calendar parts of an instant in one zone.
 *
 * Assembled from `formatToParts` rather than read out of a formatted string, so
 * the result does not depend on how a locale happens to order or separate them.
 */
function dateParts(instant: Date, timeZone: string): Intl.DateTimeFormatPart[] {
  return new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(instant);
}

/**
 * Split a weekly plan into the work due today and the work whose day has passed.
 *
 * Undated items are left out by `groupByDay`, so a roadmap passed here yields
 * nothing rather than claiming a day the plan never named.
 *
 * A past day with nothing outstanding disappears entirely rather than appearing
 * empty: the learner did that day's work, and a heading with nothing under it
 * would read as a reproach.
 *
 * @param plan The goal's active weekly plan, or null when none was generated.
 * @param today The learner's own date, from `learnerToday`.
 */
export function selectDailyWork(plan: StudyPlan | null, today: string): DailyWork {
  const days = groupByDay(plan);

  return {
    today: days.find((day) => day.on === today)?.items ?? [],
    earlier: days
      .filter((day) => day.on < today)
      .map((day) => ({ on: day.on, items: day.items.filter(isOutstanding) }))
      .filter((day) => day.items.length > 0),
  };
}

/**
 * Whether a plan item's work is still outstanding.
 *
 * Anything but `completed`, which mirrors `select_overdue`'s `is_done`: the
 * question is whether the work happened, not which of the other statuses it
 * holds. Today only `planned` can appear on an active plan, and an item in some
 * other state is shown as it is rather than hidden.
 */
function isOutstanding(item: PlanItem): boolean {
  return item.status !== "completed";
}

/**
 * Whether the plan's week still covers the learner's today.
 *
 * A weekly plan covers the seven days from the day it was generated, and nothing
 * re-plans it on its own (ADR-020, ADR-022). A learner returning after that span
 * is owed the reason their day is empty, rather than being left to infer that
 * they have no work.
 */
export function weekHasPassed(plan: StudyPlan | null, today: string): boolean {
  const endsOn = plan?.period_end ?? null;
  return endsOn !== null && endsOn < today;
}
