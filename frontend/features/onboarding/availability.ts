/**
 * Reading the weekly-availability form into the request it makes, and writing a
 * saved week the way a learner reads it.
 *
 * Kept apart from the server action so both halves can be tested as ordinary
 * functions. They hold no business rule: which days exist, what minutes a day may
 * hold, and whose goal a week belongs to are all decided by the backend, which is
 * the only place they can be enforced
 * (docs/development/coding-standards.md).
 *
 * What this module does own is the difference between "the learner left this day
 * blank" and "the learner said this day is free". An HTML form sends an empty
 * string for the first and `0` for the second, and GOAL-005 distinguishes them: a
 * blank day is left out of the week entirely, a zero is sent as a day kept free.
 *
 * Nothing here totals a week. Availability is a planning input, and turning one
 * into an hours figure is planning work the product does not do yet.
 */

import {
  WEEKDAYS,
  WEEKDAY_LABELS,
  isWeekday,
  type AvailabilitySlot,
  type Weekday,
  type WeeklyAvailability,
} from "@/types/study-goal";

/** The upper bound the API enforces on one day; a larger value is a 422. */
export const MINUTES_IN_A_DAY = 1440;

/** What one submission of the availability form asks for. */
export interface AvailabilitySubmission {
  studyGoalId: string;
  /** The complete week. Every day left out of it is removed. */
  slots: AvailabilitySlot[];
}

/** A reason the submission could not be built, tied to the day at fault. */
export interface AvailabilityProblem {
  /** The day whose entry was wrong, or null when the form itself was. */
  day: Weekday | null;
  message: string;
}

/** What the form shows after a submission. */
export interface AvailabilityState {
  status: "idle" | "saved" | "error";
  message: string;
  /** The day to mark, when the failure belongs to one. */
  day: Weekday | null;
}

/**
 * The state before anything has been submitted.
 *
 * It lives here rather than beside the action because a `"use server"` module
 * may export only async functions -- a constant exported from one fails at
 * runtime, which neither the type checker nor the production build reports.
 */
export const INITIAL_AVAILABILITY_STATE: AvailabilityState = {
  status: "idle",
  message: "",
  day: null,
};

/** The form control name carrying one day's minutes. */
export function minutesFieldName(day: Weekday): string {
  return `minutes_${day}`;
}

/**
 * The minutes stored against each day, or null for a day the learner has not set.
 *
 * The form fills its inputs from this, so a blank box means "not set" on the way
 * in as well as on the way out. A day the API sent that this build does not
 * recognise is skipped rather than shown raw.
 */
export function minutesByDay(
  availability: WeeklyAvailability | null,
): Record<Weekday, number | null> {
  const byDay = Object.fromEntries(WEEKDAYS.map((day) => [day, null])) as Record<
    Weekday,
    number | null
  >;
  for (const slot of availability?.slots ?? []) {
    if (isWeekday(slot.day_of_week)) {
      byDay[slot.day_of_week] = slot.available_minutes;
    }
  }
  return byDay;
}

/**
 * Read one submission of the availability form.
 *
 * A day left blank is absent from the resulting week, which GOAL-005 treats as a
 * removal. That is what makes clearing a box the way to take a day back.
 *
 * @returns The submission, or the first problem that stops it being built.
 */
export function readAvailabilitySubmission(
  form: FormData,
): { submission: AvailabilitySubmission } | { problem: AvailabilityProblem } {
  const studyGoalId = trimmed(form.get("study_goal_id"));
  if (!studyGoalId) {
    return {
      problem: {
        day: null,
        message: "That form did not say which study goal it was for.",
      },
    };
  }

  const slots: AvailabilitySlot[] = [];
  for (const day of WEEKDAYS) {
    const entered = trimmed(form.get(minutesFieldName(day)));
    if (!entered) {
      continue;
    }
    const minutes = Number(entered);
    if (!Number.isInteger(minutes)) {
      return {
        problem: {
          day,
          message: `Enter ${WEEKDAY_LABELS[day]} as a whole number of minutes, or leave it empty.`,
        },
      };
    }
    if (minutes < 0 || minutes > MINUTES_IN_A_DAY) {
      return {
        problem: {
          day,
          message: `${WEEKDAY_LABELS[day]} must be between 0 and ${MINUTES_IN_A_DAY} minutes, the length of a day.`,
        },
      };
    }
    slots.push({ day_of_week: day, available_minutes: minutes });
  }

  return { submission: { studyGoalId, slots } };
}

/**
 * One day's availability, written the way a learner reads it.
 *
 * Minutes are reported as minutes. Converting them to hours would be arithmetic
 * over a planning input, which belongs to the planner rather than to a label.
 */
export function describeMinutes(minutes: number): string {
  if (minutes === 0) {
    return "Kept free";
  }
  return minutes === 1 ? "1 minute" : `${minutes} minutes`;
}

/**
 * The saved week in week order, Monday first, skipping days this build does not
 * recognise.
 *
 * The API already answers in week order. Sorting again here means a view does not
 * depend on that, and a day added to the contract later is left out rather than
 * rendered as a raw value.
 */
export function weekInOrder(availability: WeeklyAvailability | null): AvailabilitySlot[] {
  const byDay = minutesByDay(availability);
  return WEEKDAYS.filter((day) => byDay[day] !== null).map((day) => ({
    day_of_week: day,
    available_minutes: byDay[day] as number,
  }));
}

function trimmed(value: FormDataEntryValue | null): string {
  return typeof value === "string" ? value.trim() : "";
}
