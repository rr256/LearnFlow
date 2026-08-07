import { describe, expect, it } from "vitest";

import { INITIAL_PLAN_STATE, readPlanSubmission } from "@/features/planner/submission";

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
