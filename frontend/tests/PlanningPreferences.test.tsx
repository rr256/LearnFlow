import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PlanningPreferences } from "@/features/home/PlanningPreferences";
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

describe("PlanningPreferences", () => {
  it("shows both saved preferences with their labels", () => {
    render(
      <PlanningPreferences
        goal={goal({
          planning_preferences: {
            preferred_session_minutes: 90,
            topic_sequencing: "prerequisites_first",
          },
        })}
      />,
    );

    expect(screen.getByText("Session length")).toBeDefined();
    expect(screen.getByText("90 minutes")).toBeDefined();
    expect(screen.getByText("Topic order")).toBeDefined();
    expect(screen.getByText("Prerequisites first")).toBeDefined();
  });

  it("leaves out a preference the learner has not set rather than showing a default", () => {
    render(
      <PlanningPreferences
        goal={goal({
          planning_preferences: {
            preferred_session_minutes: null,
            topic_sequencing: "syllabus_order",
          },
        })}
      />,
    );

    expect(screen.getByText("Syllabus order")).toBeDefined();
    expect(screen.queryByText("Session length")).toBeNull();
  });

  it("says nothing is saved when the learner has set no preference", () => {
    render(<PlanningPreferences goal={goal()} />);

    expect(screen.getByText(/No planning preferences are saved yet/)).toBeDefined();
    expect(screen.getByRole("link", { name: /how you like to study/i })).toBeDefined();
  });

  it("points a learner with no goal at choosing one first", () => {
    render(<PlanningPreferences goal={null} />);

    expect(screen.getByText(/belong to a study goal/)).toBeDefined();
    expect(screen.getByRole("link", { name: /what you are working toward/i })).toBeDefined();
  });

  it("says plainly what a plan does with a saved preference", () => {
    render(
      <PlanningPreferences
        goal={goal({
          planning_preferences: { preferred_session_minutes: 60, topic_sequencing: null },
        })}
      />,
    );

    expect(screen.getByText(/Your study plan is built with these/)).toBeDefined();
  });

  it("skips a topic order this build does not recognise rather than showing it raw", () => {
    render(
      <PlanningPreferences
        goal={goal({
          planning_preferences: {
            preferred_session_minutes: null,
            topic_sequencing: "alphabetical_order",
          },
        })}
      />,
    );

    expect(screen.queryByText("alphabetical_order")).toBeNull();
    expect(screen.getByText(/No planning preferences are saved yet/)).toBeDefined();
  });

  it("reports no total and no score, because a preference is a planning input", () => {
    const { container } = render(
      <PlanningPreferences
        goal={goal({
          planning_preferences: {
            preferred_session_minutes: 60,
            topic_sequencing: "syllabus_order",
          },
        })}
      />,
    );

    expect(container.textContent).not.toMatch(/total/i);
    expect(container.textContent).not.toMatch(/score/i);
  });
});
