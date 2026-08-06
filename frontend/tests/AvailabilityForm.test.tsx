import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { StudyGoal } from "@/types/study-goal";

// The form imports the server action, which pulls in `next/cache`. A component
// test exercises the markup, not the write path; the action's parsing is covered
// by tests/availability-submission.test.ts.
vi.mock("@/features/onboarding/actions", () => ({ saveAvailability: vi.fn() }));

const { AvailabilityForm } = await import("@/features/onboarding/AvailabilityForm");

afterEach(cleanup);

function goal(overrides: Partial<StudyGoal> = {}): StudyGoal {
  return {
    id: "goal-1",
    learner_id: "learner-1",
    status: "active",
    target_date: "2027-01-31",
    learning_program: { id: "program-1", code: "gate-cse", name: "GATE Computer Science" },
    curriculum_version: { id: "version-1", version_label: "2027", status: "active" },
    examination: null,
    availability: { slots: [] },
    ...overrides,
  };
}

function box(day: string): HTMLInputElement {
  return screen.getByRole("spinbutton", { name: day }) as HTMLInputElement;
}

describe("AvailabilityForm", () => {
  it("offers a box for every day of the week", () => {
    render(<AvailabilityForm goal={goal()} />);

    for (const day of [
      "Monday",
      "Tuesday",
      "Wednesday",
      "Thursday",
      "Friday",
      "Saturday",
      "Sunday",
    ]) {
      expect(box(day)).toBeDefined();
    }
  });

  it("fills each box from the saved week", () => {
    render(
      <AvailabilityForm
        goal={goal({
          availability: {
            slots: [
              { day_of_week: "monday", available_minutes: 120 },
              { day_of_week: "saturday", available_minutes: 240 },
            ],
          },
        })}
      />,
    );

    expect(box("Monday").value).toBe("120");
    expect(box("Saturday").value).toBe("240");
  });

  it("leaves a day the learner has not set empty rather than showing zero", () => {
    render(<AvailabilityForm goal={goal()} />);

    expect(box("Tuesday").value).toBe("");
  });

  it("shows a deliberately free day as zero, which is not the same as unset", () => {
    render(
      <AvailabilityForm
        goal={goal({
          availability: { slots: [{ day_of_week: "sunday", available_minutes: 0 }] },
        })}
      />,
    );

    expect(box("Sunday").value).toBe("0");
    expect(box("Monday").value).toBe("");
  });

  it("carries the goal the week belongs to, so no client chooses it", () => {
    const { container } = render(<AvailabilityForm goal={goal()} />);

    const hidden = container.querySelector('input[name="study_goal_id"]');
    expect(hidden?.getAttribute("value")).toBe("goal-1");
    expect(container.querySelector('input[name="learner_id"]')).toBeNull();
  });

  it("names each control by its day, never by an index", () => {
    const { container } = render(<AvailabilityForm goal={goal()} />);

    expect(container.querySelector('input[name="minutes_monday"]')).not.toBeNull();
    expect(container.querySelector('input[name="minutes_0"]')).toBeNull();
  });

  it("bounds each box to the length of a day", () => {
    render(<AvailabilityForm goal={goal()} />);

    expect(box("Monday").getAttribute("min")).toBe("0");
    expect(box("Monday").getAttribute("max")).toBe("1440");
  });

  it("shows no weekly total, because summing a week is planning work", () => {
    render(
      <AvailabilityForm
        goal={goal({
          availability: {
            slots: [
              { day_of_week: "monday", available_minutes: 120 },
              { day_of_week: "tuesday", available_minutes: 60 },
            ],
          },
        })}
      />,
    );

    expect(screen.queryByText(/total/i)).toBeNull();
    expect(screen.queryByText("180")).toBeNull();
  });

  it("explains that a blank day is unset and a zero day is kept free", () => {
    render(<AvailabilityForm goal={goal()} />);

    expect(screen.getByText(/Leave a day empty/i)).toBeDefined();
    expect(screen.getByText(/keep it free/i)).toBeDefined();
  });

  it("asks a learner with no goal to set one first, and offers no boxes", () => {
    render(<AvailabilityForm goal={null} />);

    expect(screen.getByRole("heading", { name: /Set your study goal first/i })).toBeDefined();
    expect(screen.queryByRole("spinbutton", { name: "Monday" })).toBeNull();
  });
});
