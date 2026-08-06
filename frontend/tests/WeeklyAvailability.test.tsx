import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { WeeklyAvailability } from "@/features/home/WeeklyAvailability";
import type { StudyGoal } from "@/types/study-goal";

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
    planning_preferences: { preferred_session_minutes: null, topic_sequencing: null },
    ...overrides,
  };
}

describe("WeeklyAvailability", () => {
  it("shows the saved days with their study time", () => {
    render(
      <WeeklyAvailability
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

    expect(screen.getByText("Monday")).toBeDefined();
    expect(screen.getByText("120 minutes")).toBeDefined();
    expect(screen.getByText("Saturday")).toBeDefined();
    expect(screen.getByText("240 minutes")).toBeDefined();
  });

  it("shows the week Monday first", () => {
    render(
      <WeeklyAvailability
        goal={goal({
          availability: {
            slots: [
              { day_of_week: "sunday", available_minutes: 30 },
              { day_of_week: "tuesday", available_minutes: 60 },
            ],
          },
        })}
      />,
    );

    const days = screen.getAllByRole("term").map((term) => term.textContent);
    expect(days).toEqual(["Tuesday", "Sunday"]);
  });

  it("omits a day the learner has not set rather than showing it as zero", () => {
    render(
      <WeeklyAvailability
        goal={goal({
          availability: { slots: [{ day_of_week: "monday", available_minutes: 120 }] },
        })}
      />,
    );

    expect(screen.queryByText("Tuesday")).toBeNull();
  });

  it("says a zero day is kept free, which is not the same as unset", () => {
    render(
      <WeeklyAvailability
        goal={goal({
          availability: { slots: [{ day_of_week: "sunday", available_minutes: 0 }] },
        })}
      />,
    );

    expect(screen.getByText("Sunday")).toBeDefined();
    expect(screen.getByText("Kept free")).toBeDefined();
  });

  it("shows no weekly total, because summing a week is planning work", () => {
    render(
      <WeeklyAvailability
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
    expect(screen.queryByText(/180/)).toBeNull();
  });

  it("invites a learner with a goal but no week to set one", () => {
    render(<WeeklyAvailability goal={goal()} />);

    const link = screen.getByRole("link", { name: /Tell LearnFlow when you can study/i });
    expect(link.getAttribute("href")).toBe("/setup");
  });

  it("explains that availability needs a goal when the learner has none", () => {
    render(<WeeklyAvailability goal={null} />);

    expect(screen.getByRole("link", { name: /Choose what you are working toward/i })).toBeDefined();
  });

  it("skips a day this build does not recognise rather than showing it raw", () => {
    render(
      <WeeklyAvailability
        goal={goal({
          availability: {
            slots: [
              { day_of_week: "monday", available_minutes: 120 },
              { day_of_week: "someday", available_minutes: 60 },
            ],
          },
        })}
      />,
    );

    expect(screen.getByText("Monday")).toBeDefined();
    expect(screen.queryByText("someday")).toBeNull();
  });

  it("writes nothing: it is a read-only view with no form", () => {
    const { container } = render(
      <WeeklyAvailability
        goal={goal({
          availability: { slots: [{ day_of_week: "monday", available_minutes: 120 }] },
        })}
      />,
    );

    expect(container.querySelector("form")).toBeNull();
    expect(container.querySelector("input")).toBeNull();
  });
});
