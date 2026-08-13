import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PlanFeasibility } from "@/features/planner/PlanFeasibility";
import type { PlanFeasibility as PlanFeasibilityReading } from "@/types/study-plan";

afterEach(cleanup);

function reading(overrides: Partial<PlanFeasibilityReading> = {}): PlanFeasibilityReading {
  return {
    study_goal_id: "goal-1",
    assessed_on: "2026-08-14",
    verdict: "sufficient",
    reason: "Across the 177 days to 2027-02-06, the week you saved offers 60 hours.",
    unknown_reason: null,
    horizon_ends_on: "2027-02-06",
    remaining_topic_count: 60,
    session_minutes: 60,
    session_minutes_chosen_by_planner: true,
    study_days: 177,
    available_minutes: 3600,
    required_minutes: 3600,
    shortfall_minutes: 0,
    coverable_topic_count: 60,
    ...overrides,
  };
}

describe("PlanFeasibility", () => {
  it("says plainly when the saved time covers the work", () => {
    render(<PlanFeasibility reading={reading()} />);

    expect(screen.getByText(/covers the work that is left/)).toBeDefined();
  });

  it("says plainly when it does not", () => {
    render(
      <PlanFeasibility
        reading={reading({ verdict: "insufficient", shortfall_minutes: 600 })}
      />,
    );

    expect(screen.getByText(/does not cover the work that is left/)).toBeDefined();
  });

  it("renders the reason the backend composed rather than writing its own", () => {
    render(<PlanFeasibility reading={reading()} />);

    expect(screen.getByText(/Across the 177 days to 2027-02-06/)).toBeDefined();
  });

  it("shows the saved time and the time the work needs, as durations", () => {
    render(<PlanFeasibility reading={reading()} />);

    expect(screen.getByText("Study time you saved")).toBeDefined();
    expect(screen.getAllByText("60 hr").length).toBeGreaterThan(0);
  });

  it("shows the shortfall only when there is one", () => {
    render(<PlanFeasibility reading={reading()} />);

    expect(screen.queryByText("Short by")).toBeNull();
  });

  it("shows the shortfall as a duration when the time falls short", () => {
    render(
      <PlanFeasibility
        reading={reading({
          verdict: "insufficient",
          required_minutes: 4200,
          shortfall_minutes: 600,
          coverable_topic_count: 51,
        })}
      />,
    );

    expect(screen.getByText("Short by")).toBeDefined();
    expect(screen.getByText("10 hr")).toBeDefined();
  });

  it("states the two topic counts separately, never as a fraction", () => {
    /* docs/domain/terminology.md: a denominator invites the comparison this
     * product does not make, so the counts are two labelled figures. */
    render(
      <PlanFeasibility
        reading={reading({
          verdict: "insufficient",
          shortfall_minutes: 600,
          remaining_topic_count: 60,
          coverable_topic_count: 51,
        })}
      />,
    );

    expect(screen.getByText("Topics still to work through")).toBeDefined();
    expect(screen.getByText("Topics that time covers")).toBeDefined();
    expect(screen.queryByText("51 of 60")).toBeNull();
    expect(screen.queryByText("51/60")).toBeNull();
  });

  it("renders no percentage anywhere", () => {
    render(
      <PlanFeasibility
        reading={reading({ verdict: "insufficient", shortfall_minutes: 600 })}
      />,
    );

    expect(document.body.textContent).not.toMatch(/\d+\s?%/);
  });

  it("explains a goal that aims at no date, and names the next step", () => {
    render(
      <PlanFeasibility
        reading={reading({
          verdict: "unknown",
          unknown_reason: "no_horizon",
          horizon_ends_on: null,
          reason: "This goal aims at no examination cycle and no target date.",
        })}
      />,
    );

    expect(screen.getByText(/cannot be worked out yet/)).toBeDefined();
    expect(
      screen.getByRole("link", { name: "Set an examination cycle or a target date" }),
    ).toBeDefined();
  });

  it("explains a goal with no saved week, and names a different next step", () => {
    render(
      <PlanFeasibility
        reading={reading({
          verdict: "unknown",
          unknown_reason: "no_availability_saved",
          reason: "No study week is saved for this goal.",
        })}
      />,
    );

    expect(screen.getByRole("link", { name: "Save the days you can study" })).toBeDefined();
  });

  it("shows no figures when the question could not be answered", () => {
    render(
      <PlanFeasibility
        reading={reading({ verdict: "unknown", unknown_reason: "no_horizon" })}
      />,
    );

    expect(screen.queryByText("Study time you saved")).toBeNull();
  });

  it("renders nothing at all when no reading is available", () => {
    const { container } = render(<PlanFeasibility reading={null} />);

    expect(container.firstChild).toBeNull();
  });

  it("offers no control that would change anything", () => {
    /* A reading. Rebuilding the plan stays with the adapt control, and editing
     * the week stays in setup. */
    render(<PlanFeasibility reading={reading()} />);

    expect(screen.queryByRole("button")).toBeNull();
  });

  it("describes the plan and the time, never the learner", () => {
    render(
      <PlanFeasibility
        reading={reading({ verdict: "insufficient", shortfall_minutes: 600 })}
      />,
    );

    const page = (document.body.textContent ?? "").toLowerCase();
    for (const wording of [
      "you are behind",
      "you fell behind",
      "you failed",
      "not enough effort",
      "too slow",
      "unrealistic",
    ]) {
      expect(page).not.toContain(wording);
    }
  });

  it("renders an unrecognised verdict without inventing a claim", () => {
    /* A later backend could add one; the panel must not assert something untrue
     * about it, and the reason it sent still reads. */
    render(<PlanFeasibility reading={reading({ verdict: "invented" })} />);

    expect(screen.getByText(/cannot be worked out yet/)).toBeDefined();
    expect(screen.getByText(/Across the 177 days/)).toBeDefined();
  });
});
