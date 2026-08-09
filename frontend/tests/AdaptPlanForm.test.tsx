import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// The control imports the server action, which pulls in `next/cache`. A
// component test exercises the markup, not the write path; the action's own
// parsing is covered by tests/plan-submission.test.ts.
vi.mock("@/features/planner/actions", () => ({ adaptPlan: vi.fn() }));

const { AdaptPlanForm } = await import("@/features/planner/AdaptPlanForm");

afterEach(cleanup);

describe("AdaptPlanForm", () => {
  it("offers to update the plan", () => {
    render(<AdaptPlanForm studyGoalId="goal-1" />);

    expect(screen.getByRole("button", { name: /Update my plan/ })).toBeDefined();
  });

  it("carries the goal so the action knows what to adapt", () => {
    const { container } = render(<AdaptPlanForm studyGoalId="goal-1" />);

    const field = container.querySelector('input[name="study_goal_id"]') as HTMLInputElement;
    expect(field.value).toBe("goal-1");
  });

  it("sends nothing but the goal", () => {
    /*
     * Everything adaptation acts on is already stored. A form that sent a
     * preference would let a client adapt toward one the learner never set,
     * which is the distinction PLN-001 also keeps.
     */
    const { container } = render(<AdaptPlanForm studyGoalId="goal-1" />);

    const names = [...container.querySelectorAll("input")].map((input) => input.name);
    expect(names).toEqual(["study_goal_id"]);
  });

  it("says what adapting will do before it is pressed", () => {
    /* A learner working from a plan needs to know what a rebuild costs them. */
    render(<AdaptPlanForm studyGoalId="goal-1" />);

    const hint = screen.getByText(/topics you have completed are not planned again/);
    expect(hint.textContent).toMatch(/carried forward/);
    expect(hint.textContent).toMatch(/kept, not deleted/);
  });

  it("reports no result before the learner has acted", () => {
    render(<AdaptPlanForm studyGoalId="goal-1" />);

    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
