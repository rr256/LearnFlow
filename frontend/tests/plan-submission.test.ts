import { describe, expect, it } from "vitest";

import {
  INITIAL_ADAPT_STATE,
  INITIAL_PLAN_ITEM_STATE,
  INITIAL_PLAN_STATE,
  readAdaptSubmission,
  readPlanItemSubmission,
  readPlanSubmission,
} from "@/features/planner/submission";

function form(entries: Record<string, string>): FormData {
  const data = new FormData();
  for (const [name, value] of Object.entries(entries)) {
    data.set(name, value);
  }
  return data;
}

describe("readPlanSubmission", () => {
  it("reads the goal the form names", () => {
    const read = readPlanSubmission(form({ study_goal_id: "goal-1" }));

    expect(read).toEqual({ studyGoalId: "goal-1" });
  });

  it("trims a padded identifier", () => {
    const read = readPlanSubmission(form({ study_goal_id: "  goal-1  " }));

    expect(read).toEqual({ studyGoalId: "goal-1" });
  });

  it("reports a form that names no goal", () => {
    const read = readPlanSubmission(form({}));

    expect(read).toHaveProperty("problem");
  });

  it("reports a form whose goal is blank", () => {
    const read = readPlanSubmission(form({ study_goal_id: "   " }));

    expect(read).toHaveProperty("problem");
  });

  it("sends no preference of its own", () => {
    /*
     * A plan is built from what the learner stored. If this ever read a session
     * length or a topic order out of the form, a client could plan with a
     * preference the learner never set -- which is the distinction ADR-019
     * exists to keep.
     */
    const read = readPlanSubmission(
      form({ study_goal_id: "goal-1", preferred_session_minutes: "45" }),
    );

    expect(read).toEqual({ studyGoalId: "goal-1" });
  });
});

describe("INITIAL_PLAN_STATE", () => {
  it("starts idle with nothing to report", () => {
    expect(INITIAL_PLAN_STATE).toEqual({ status: "idle", message: "" });
  });
});

describe("readPlanItemSubmission", () => {
  it("reads the item and the status the form names", () => {
    const read = readPlanItemSubmission(form({ plan_item_id: "item-1", status: "completed" }));

    expect(read).toEqual({ submission: { planItemId: "item-1", status: "completed" } });
  });

  it("reads a request to put an item back", () => {
    const read = readPlanItemSubmission(form({ plan_item_id: "item-1", status: "planned" }));

    expect(read).toEqual({ submission: { planItemId: "item-1", status: "planned" } });
  });

  it("trims a padded identifier", () => {
    const read = readPlanItemSubmission(
      form({ plan_item_id: "  item-1  ", status: "completed" }),
    );

    expect(read).toEqual({ submission: { planItemId: "item-1", status: "completed" } });
  });

  it("reports a form that names no item", () => {
    const read = readPlanItemSubmission(form({ status: "completed" }));

    expect(read).toHaveProperty("problem");
  });

  it("reads a skip", () => {
    const read = readPlanItemSubmission(form({ plan_item_id: "item-1", status: "skipped" }));

    expect(read).toEqual({ submission: { planItemId: "item-1", status: "skipped" } });
  });

  it("reads a postponement", () => {
    const read = readPlanItemSubmission(form({ plan_item_id: "item-1", status: "postponed" }));

    expect(read).toEqual({ submission: { planItemId: "item-1", status: "postponed" } });
  });

  it.each(["finished", "abandoned"])("refuses %s, which the API does not accept", (status) => {
    /*
     * Every status the column holds is now askable, so a refusal here is a value
     * the API would answer 422 to as well; it is caught before the round trip.
     */
    const read = readPlanItemSubmission(form({ plan_item_id: "item-1", status }));

    expect(read).toHaveProperty("problem");
  });

  it("refuses a status that is not a status at all", () => {
    const read = readPlanItemSubmission(form({ plan_item_id: "item-1", status: "done-ish" }));

    expect(read).toHaveProperty("problem");
  });

  it("sends no completion time of its own", () => {
    /*
     * When the learner said so is the server's record. If this ever read one out
     * of the form, a client could backdate work.
     */
    const read = readPlanItemSubmission(
      form({
        plan_item_id: "item-1",
        status: "completed",
        completed_at: "2020-01-01T00:00:00Z",
      }),
    );

    expect(read).toEqual({ submission: { planItemId: "item-1", status: "completed" } });
  });
});

describe("INITIAL_PLAN_ITEM_STATE", () => {
  it("starts idle with nothing to report", () => {
    expect(INITIAL_PLAN_ITEM_STATE).toEqual({ status: "idle", message: "" });
  });
});

describe("readAdaptSubmission", () => {
  it("reads the goal the form names", () => {
    expect(readAdaptSubmission(form({ study_goal_id: "goal-1" }))).toEqual({
      studyGoalId: "goal-1",
    });
  });

  it("trims a padded identifier", () => {
    expect(readAdaptSubmission(form({ study_goal_id: "  goal-1  " }))).toEqual({
      studyGoalId: "goal-1",
    });
  });

  it("reports a form that names no goal", () => {
    expect(readAdaptSubmission(form({}))).toHaveProperty("problem");
  });

  it("sends nothing but the goal", () => {
    /*
     * Everything adaptation acts on is already stored. Reading a preference out
     * of the form would let a client adapt toward one the learner never set.
     */
    const read = readAdaptSubmission(
      form({ study_goal_id: "goal-1", preferred_session_minutes: "45" }),
    );

    expect(read).toEqual({ studyGoalId: "goal-1" });
  });
});

describe("INITIAL_ADAPT_STATE", () => {
  it("starts idle with nothing to report", () => {
    expect(INITIAL_ADAPT_STATE).toEqual({ status: "idle", message: "" });
  });
});
