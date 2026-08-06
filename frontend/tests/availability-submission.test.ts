import { describe, expect, it } from "vitest";

import {
  describeMinutes,
  minutesByDay,
  minutesFieldName,
  readAvailabilitySubmission,
  weekInOrder,
} from "@/features/onboarding/availability";

/**
 * The availability form's parsing and presentation, as plain functions.
 *
 * The rules these do *not* enforce matter as much as the ones they do: which days
 * exist and what minutes a day may hold are the backend's to refuse. What is
 * checked here is the one distinction the form owns — a day left blank means
 * "not set", and `0` means "kept free" — because an HTML form sends an empty
 * string for the first and the API contract treats the two differently.
 */

function form(entries: Record<string, string>): FormData {
  const data = new FormData();
  for (const [name, value] of Object.entries(entries)) {
    data.set(name, value);
  }
  return data;
}

function week(entries: Record<string, string>): FormData {
  return form({ study_goal_id: "goal-1", ...entries });
}

describe("readAvailabilitySubmission", () => {
  it("names the days the learner entered", () => {
    const read = readAvailabilitySubmission(
      week({ minutes_monday: "120", minutes_thursday: "90" }),
    );

    expect(read).toEqual({
      submission: {
        studyGoalId: "goal-1",
        slots: [
          { day_of_week: "monday", available_minutes: 120 },
          { day_of_week: "thursday", available_minutes: 90 },
        ],
      },
    });
  });

  it("orders the week Monday first, whatever order the form was read in", () => {
    const read = readAvailabilitySubmission(
      week({ minutes_sunday: "30", minutes_tuesday: "60", minutes_saturday: "240" }),
    );

    expect("submission" in read && read.submission.slots.map((slot) => slot.day_of_week)).toEqual([
      "tuesday",
      "saturday",
      "sunday",
    ]);
  });

  it("leaves a blank day out of the week, so saving removes it", () => {
    const read = readAvailabilitySubmission(week({ minutes_monday: "120", minutes_tuesday: "" }));

    expect("submission" in read && read.submission.slots).toEqual([
      { day_of_week: "monday", available_minutes: 120 },
    ]);
  });

  it("sends a zero day rather than dropping it", () => {
    const read = readAvailabilitySubmission(week({ minutes_sunday: "0" }));

    expect("submission" in read && read.submission.slots).toEqual([
      { day_of_week: "sunday", available_minutes: 0 },
    ]);
  });

  it("treats a whitespace-only entry as blank", () => {
    const read = readAvailabilitySubmission(week({ minutes_monday: "   " }));

    expect("submission" in read && read.submission.slots).toEqual([]);
  });

  it("builds an empty week when every day is blank, which clears the goal", () => {
    const read = readAvailabilitySubmission(week({}));

    expect("submission" in read && read.submission.slots).toEqual([]);
  });

  it("refuses a form that does not say which goal it is for", () => {
    const read = readAvailabilitySubmission(form({ minutes_monday: "120" }));

    expect("problem" in read && read.problem.day).toBeNull();
  });

  it("names the day whose entry is not a whole number", () => {
    const read = readAvailabilitySubmission(week({ minutes_wednesday: "an hour" }));

    expect("problem" in read && read.problem.day).toBe("wednesday");
  });

  it("refuses a fractional number of minutes", () => {
    const read = readAvailabilitySubmission(week({ minutes_friday: "90.5" }));

    expect("problem" in read && read.problem.day).toBe("friday");
  });

  it("names the day claiming more minutes than a day holds", () => {
    const read = readAvailabilitySubmission(week({ minutes_monday: "1441" }));

    expect("problem" in read && read.problem.day).toBe("monday");
    expect("problem" in read && read.problem.message).toContain("1440");
  });

  it("refuses a negative number of minutes", () => {
    const read = readAvailabilitySubmission(week({ minutes_monday: "-1" }));

    expect("problem" in read && read.problem.day).toBe("monday");
  });

  it("accepts a whole day of study time", () => {
    const read = readAvailabilitySubmission(week({ minutes_saturday: "1440" }));

    expect("submission" in read && read.submission.slots).toEqual([
      { day_of_week: "saturday", available_minutes: 1440 },
    ]);
  });
});

describe("minutesFieldName", () => {
  it("names a control per day, so the form carries the whole week", () => {
    expect(minutesFieldName("monday")).toBe("minutes_monday");
    expect(minutesFieldName("sunday")).toBe("minutes_sunday");
  });
});

describe("minutesByDay", () => {
  it("reports null for a day the learner has not set", () => {
    const byDay = minutesByDay({ slots: [{ day_of_week: "monday", available_minutes: 120 }] });

    expect(byDay.monday).toBe(120);
    expect(byDay.tuesday).toBeNull();
  });

  it("keeps a zero day distinct from an unset one", () => {
    const byDay = minutesByDay({ slots: [{ day_of_week: "sunday", available_minutes: 0 }] });

    expect(byDay.sunday).toBe(0);
    expect(byDay.monday).toBeNull();
  });

  it("reports every day as unset for a goal with no availability", () => {
    const byDay = minutesByDay({ slots: [] });

    expect(Object.values(byDay).every((minutes) => minutes === null)).toBe(true);
  });

  it("treats a missing week as no availability rather than failing", () => {
    expect(minutesByDay(null).monday).toBeNull();
  });

  it("skips a day this build does not recognise", () => {
    const byDay = minutesByDay({
      slots: [
        { day_of_week: "monday", available_minutes: 120 },
        { day_of_week: "someday", available_minutes: 60 },
      ],
    });

    expect(byDay.monday).toBe(120);
    expect(Object.keys(byDay)).not.toContain("someday");
  });
});

describe("weekInOrder", () => {
  it("returns only the days that are set, Monday first", () => {
    const ordered = weekInOrder({
      slots: [
        { day_of_week: "saturday", available_minutes: 240 },
        { day_of_week: "monday", available_minutes: 120 },
      ],
    });

    expect(ordered).toEqual([
      { day_of_week: "monday", available_minutes: 120 },
      { day_of_week: "saturday", available_minutes: 240 },
    ]);
  });

  it("is empty for a goal with no availability", () => {
    expect(weekInOrder({ slots: [] })).toEqual([]);
    expect(weekInOrder(null)).toEqual([]);
  });
});

describe("describeMinutes", () => {
  it("says a zero day is kept free rather than showing 0 minutes", () => {
    expect(describeMinutes(0)).toBe("Kept free");
  });

  it("reports minutes as minutes, without converting them to hours", () => {
    expect(describeMinutes(120)).toBe("120 minutes");
    expect(describeMinutes(90)).toBe("90 minutes");
  });

  it("agrees with itself for a single minute", () => {
    expect(describeMinutes(1)).toBe("1 minute");
  });
});
