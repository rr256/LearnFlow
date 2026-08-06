import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { StudyGoalSummary } from "@/features/onboarding/StudyGoalSummary";
import type { StudyGoal } from "@/types/study-goal";

afterEach(cleanup);

function goal(overrides: Partial<StudyGoal> = {}): StudyGoal {
  return {
    id: "goal-1",
    learner_id: "learner-1",
    status: "active",
    target_date: null,
    learning_program: { id: "program-1", code: "gate-cse", name: "GATE Computer Science" },
    curriculum_version: { id: "version-1", version_label: "2027", status: "active" },
    examination: {
      id: "schedule-1",
      cycle_label: "2027",
      name: "GATE 2027",
      organising_body: "IIT Madras",
      source_reference: "https://example.test/schedule",
      source_checked_on: "2026-08-01",
      schedule_status: "provisional",
      examination_window: { starts_on: "2027-02-06", ends_on: "2027-02-21" },
    },
    availability: { slots: [] },
    planning_preferences: { preferred_session_minutes: null, topic_sequencing: null },
    ...overrides,
  };
}

describe("StudyGoalSummary", () => {
  it("invites the learner to set a goal when they have none", () => {
    render(<StudyGoalSummary goal={null} />);

    expect(screen.getByRole("heading", { name: /No study goal yet/i })).toBeDefined();
  });

  it("reports the examination as a window rather than a single date", () => {
    render(<StudyGoalSummary goal={goal()} />);

    expect(screen.getByText(/2027-02-06 to 2027-02-21/)).toBeDefined();
  });

  it("says in words that provisional dates may still change", () => {
    // Terminology requires the status wherever the dates are shown, and colour
    // alone would not carry it.
    render(<StudyGoalSummary goal={goal()} />);

    expect(screen.getByText(/Provisional/)).toBeDefined();
    expect(screen.getByText(/IIT Madras may still\s+change these dates/)).toBeDefined();
  });

  it("does not call confirmed dates provisional", () => {
    render(
      <StudyGoalSummary
        goal={goal({
          examination: { ...goal().examination!, schedule_status: "confirmed" },
        })}
      />,
    );

    expect(screen.queryByText(/Provisional/)).toBeNull();
  });

  it("names the source the dates came from and the day it was read", () => {
    render(<StudyGoalSummary goal={goal()} />);

    const link = screen.getByRole("link", { name: "IIT Madras" });
    expect(link.getAttribute("href")).toBe("https://example.test/schedule");
    expect(screen.getByText(/read on 2026-08-01/)).toBeDefined();
  });

  it("reports a schedule that has published no sitting day rather than inventing one", () => {
    render(
      <StudyGoalSummary
        goal={goal({ examination: { ...goal().examination!, examination_window: null } })}
      />,
    );

    expect(screen.getByText(/Sitting days not published/)).toBeDefined();
  });

  it("shows a target date for a goal that follows no examination", () => {
    render(<StudyGoalSummary goal={goal({ examination: null, target_date: "2027-01-31" })} />);

    expect(screen.getByText("2027-01-31")).toBeDefined();
    expect(screen.queryByText(/Examination window/)).toBeNull();
  });
});
