import { describe, expect, it } from "vitest";

import { learnerToday, selectDailyWork, weekHasPassed } from "@/features/planner/today";
import type { PlanItem, StudyPlan } from "@/types/study-plan";

function item(overrides: Partial<PlanItem> = {}): PlanItem {
  return {
    id: `item-${Math.random()}`,
    topic: {
      id: "topic-1",
      code: null,
      name: "CPU scheduling",
      subject_id: "subject-1",
      subject_name: "Operating Systems",
    },
    action_type: "study",
    scheduled_for: null,
    estimated_minutes: 60,
    priority: 1,
    status: "planned",
    recommendation_reason: "Topic 1 of 60 in syllabus order, from Operating Systems.",
    completed_at: null,
    ...overrides,
  };
}

function plan(overrides: Partial<StudyPlan> = {}): StudyPlan {
  return {
    id: "plan-1",
    learner_id: "learner-1",
    study_goal_id: "goal-1",
    plan_type: "weekly",
    period_start: "2026-08-09",
    period_end: "2026-08-15",
    status: "active",
    generation_reason: "The first 3 of 60 topics on your roadmap.",
    item_count: 0,
    items: [],
    ...overrides,
  };
}

describe("learnerToday", () => {
  /*
   * The instant is passed in rather than read from the clock, so these assert
   * exact dates rather than that the code agrees with itself -- the same reason
   * the backend reads its clock through a port.
   */
  const lateEvening = new Date("2026-08-09T18:30:00Z");

  it("gives the learner's own date, not the server's", () => {
    // 18:30 UTC is already past midnight in Asia/Kolkata, so the learner's day
    // has turned over while the process's has not.
    expect(learnerToday(lateEvening, "Asia/Kolkata")).toBe("2026-08-10");
    expect(learnerToday(lateEvening, "UTC")).toBe("2026-08-09");
  });

  it("gives yesterday's date for a learner west of the server", () => {
    const earlyMorning = new Date("2026-08-09T02:00:00Z");

    expect(learnerToday(earlyMorning, "America/New_York")).toBe("2026-08-08");
    expect(learnerToday(earlyMorning, "Asia/Kolkata")).toBe("2026-08-09");
  });

  it("pads a single-digit month and day, so the result sorts as an ISO date", () => {
    expect(learnerToday(new Date("2026-01-05T00:30:00Z"), "UTC")).toBe("2026-01-05");
  });

  it("falls back to UTC for a zone that cannot be read, rather than failing", () => {
    // The same fallback the backend's `_today_for` applies: a date a day out is
    // recoverable, and a screen that refuses to render is not.
    expect(learnerToday(lateEvening, "Not/AZone")).toBe("2026-08-09");
    expect(learnerToday(lateEvening, "")).toBe("2026-08-09");
  });
});

describe("selectDailyWork", () => {
  const today = "2026-08-09";

  it("takes the items the plan placed on the learner's date, in plan order", () => {
    const work = selectDailyWork(
      plan({
        items: [
          item({ id: "first", priority: 1, scheduled_for: today }),
          item({ id: "second", priority: 2, scheduled_for: today }),
          item({ id: "tomorrow", priority: 3, scheduled_for: "2026-08-10" }),
        ],
      }),
      today,
    );

    expect(work.today.map((entry) => entry.id)).toEqual(["first", "second"]);
  });

  it("keeps a skipped item on today rather than hiding it", () => {
    /* A learner who set today's work aside must still be able to take it back
     * without leaving the screen they are working on. */
    const work = selectDailyWork(
      plan({ items: [item({ id: "set-aside", scheduled_for: today, status: "skipped" })] }),
      today,
    );

    expect(work.today.map((entry) => entry.id)).toEqual(["set-aside"]);
  });

  it("keeps a postponed item on today rather than hiding it", () => {
    /* Postponing names no new day, so the item stays where the plan put it,
     * with the control that takes the postponement back. */
    const work = selectDailyWork(
      plan({ items: [item({ id: "deferred", scheduled_for: today, status: "postponed" })] }),
      today,
    );

    expect(work.today.map((entry) => entry.id)).toEqual(["deferred"]);
  });

  it("keeps a completed item on today rather than hiding it", () => {
    /* The plan is the record of what the day held; hiding finished work would
     * leave the day looking undone (ADR-021). */
    const work = selectDailyWork(
      plan({ items: [item({ id: "done", scheduled_for: today, status: "completed" })] }),
      today,
    );

    expect(work.today.map((entry) => entry.id)).toEqual(["done"]);
  });

  it("groups outstanding work from days that have passed, earliest first", () => {
    const work = selectDailyWork(
      plan({
        items: [
          item({ id: "friday", scheduled_for: "2026-08-07" }),
          item({ id: "saturday", scheduled_for: "2026-08-08" }),
          item({ id: "today", scheduled_for: today }),
        ],
      }),
      today,
    );

    expect(work.earlier.map((day) => day.on)).toEqual(["2026-08-07", "2026-08-08"]);
    expect(work.earlier[0]?.items.map((entry) => entry.id)).toEqual(["friday"]);
  });

  it.each(["completed", "skipped", "postponed"])(
    "leaves %s work out of the days that have passed",
    (status) => {
      /* Mirrors the backend rule: a settled item is never behind, whether the
       * work happened, the learner said it would not, or they said not yet. */
      const work = selectDailyWork(
        plan({
          items: [
            item({ id: "settled", scheduled_for: "2026-08-07", status }),
            item({ id: "undone", priority: 2, scheduled_for: "2026-08-07" }),
          ],
        }),
        today,
      );

      expect(work.earlier[0]?.items.map((entry) => entry.id)).toEqual(["undone"]);
    },
  );

  it.each(["completed", "skipped", "postponed"])(
    "drops a passed day entirely once its only item is %s",
    (status) => {
      const work = selectDailyWork(
        plan({ items: [item({ scheduled_for: "2026-08-07", status })] }),
        today,
      );

      expect(work.earlier).toEqual([]);
    },
  );

  it("still shows work in a status this build does not recognise as outstanding", () => {
    /* The mirror is of `SETTLED_STATUSES`, not of "anything but planned": a
     * backend that grows a fifth status must not have it silently dropped. */
    const work = selectDailyWork(
      plan({ items: [item({ id: "unknown", scheduled_for: "2026-08-07", status: "invented" })] }),
      today,
    );

    expect(work.earlier[0]?.items.map((entry) => entry.id)).toEqual(["unknown"]);
  });

  it("treats an item dated today as due rather than as behind", () => {
    /* The day has not finished, so opening this screen in the morning must not
     * declare it lost. */
    const work = selectDailyWork(plan({ items: [item({ scheduled_for: today })] }), today);

    expect(work.today).toHaveLength(1);
    expect(work.earlier).toEqual([]);
  });

  it("never treats an undated item as behind", () => {
    /* A roadmap item says what order to work in, not which day; it cannot be
     * late for a day it never named. */
    const work = selectDailyWork(plan({ plan_type: "roadmap", items: [item()] }), today);

    expect(work).toEqual({ today: [], earlier: [] });
  });

  it("leaves work still to come out of both lists", () => {
    const work = selectDailyWork(plan({ items: [item({ scheduled_for: "2026-08-12" })] }), today);

    expect(work).toEqual({ today: [], earlier: [] });
  });

  it("returns nothing when no plan exists", () => {
    expect(selectDailyWork(null, today)).toEqual({ today: [], earlier: [] });
  });
});

describe("weekHasPassed", () => {
  it("is true once the plan's last day is behind the learner", () => {
    expect(weekHasPassed(plan({ period_end: "2026-08-08" }), "2026-08-09")).toBe(true);
  });

  it("is false on the plan's last day, which has not finished", () => {
    expect(weekHasPassed(plan({ period_end: "2026-08-09" }), "2026-08-09")).toBe(false);
  });

  it("is false while the week is still running", () => {
    expect(weekHasPassed(plan({ period_end: "2026-08-15" }), "2026-08-09")).toBe(false);
  });

  it("is false for a plan with no end date, which cannot have run out", () => {
    expect(weekHasPassed(plan({ period_end: null }), "2026-08-09")).toBe(false);
  });

  it("is false when there is no plan at all", () => {
    expect(weekHasPassed(null, "2026-08-09")).toBe(false);
  });
});
