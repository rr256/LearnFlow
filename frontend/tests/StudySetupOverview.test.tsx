import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { StudySetupOverview } from "@/features/home/StudySetupOverview";
import type { LearnerProfile } from "@/types/learner";
import type { ExaminationSchedule, StudyGoal } from "@/types/study-goal";

afterEach(cleanup);

function profile(overrides: Partial<LearnerProfile> = {}): LearnerProfile {
  return { id: "learner-1", display_name: "Rishabh", timezone: "Asia/Kolkata", ...overrides };
}

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

function schedule(): ExaminationSchedule {
  return {
    id: "schedule-1",
    learning_program_id: "program-1",
    cycle_label: "2027",
    name: "GATE 2027",
    organising_body: "IIT Madras",
    source_reference: "https://example.test/schedule",
    source_checked_on: "2026-08-01",
    schedule_status: "provisional",
    examination_window: { starts_on: "2027-02-06", ends_on: "2027-02-21" },
    periods: [{ period_type: "registration", starts_on: "2026-08-28", ends_on: "2026-10-05" }],
  };
}

describe("StudySetupOverview", () => {
  it("points a learner with nothing saved at setup", () => {
    render(<StudySetupOverview goal={null} profile={null} schedule={null} />);

    expect(screen.getByRole("heading", { name: /Nothing is set up yet/i })).toBeDefined();
    const link = screen.getByRole("link", { name: /Set up your study goal/i });
    expect(link.getAttribute("href")).toBe("/setup");
  });

  it("shows the saved profile", () => {
    render(<StudySetupOverview goal={goal()} profile={profile()} schedule={null} />);

    expect(screen.getByText("Rishabh")).toBeDefined();
    expect(screen.getByText("Asia/Kolkata")).toBeDefined();
  });

  it("says a name is unset rather than rendering an empty value", () => {
    render(
      <StudySetupOverview goal={goal()} profile={profile({ display_name: null })} schedule={null} />,
    );

    expect(screen.getByText("Not set")).toBeDefined();
  });

  it("invites a learner with a goal but no profile to add one", () => {
    render(<StudySetupOverview goal={goal()} profile={null} schedule={null} />);

    expect(screen.getByRole("link", { name: /Add your name and timezone/i })).toBeDefined();
  });

  it("shows the goal's program, curriculum version, and status", () => {
    render(<StudySetupOverview goal={goal()} profile={profile()} schedule={null} />);

    expect(screen.getByText("GATE Computer Science")).toBeDefined();
    expect(screen.getByText("2027")).toBeDefined();
    expect(screen.getByText("active")).toBeDefined();
  });

  it("names the cycle the goal is working toward", () => {
    render(<StudySetupOverview goal={goal()} profile={profile()} schedule={schedule()} />);

    expect(screen.getByText("Working toward")).toBeDefined();
    expect(screen.getByRole("heading", { name: "GATE 2027" })).toBeDefined();
  });

  it("shows the examination's window and published dates", () => {
    render(<StudySetupOverview goal={goal()} profile={profile()} schedule={schedule()} />);

    expect(screen.getByText(/2027-02-06 to 2027-02-21/)).toBeDefined();
    expect(screen.getByRole("heading", { name: "Important dates" })).toBeDefined();
    expect(screen.getByText("2026-08-28 to 2026-10-05")).toBeDefined();
  });

  it("shows the window even when the goal's cycle was not among the published schedules", () => {
    render(<StudySetupOverview goal={goal()} profile={profile()} schedule={null} />);

    expect(screen.getByText(/2027-02-06 to 2027-02-21/)).toBeDefined();
    expect(screen.getByText(/could not be read/)).toBeDefined();
  });

  it("shows a target date for a goal that follows no examination", () => {
    render(
      <StudySetupOverview
        goal={goal({ examination: null, target_date: "2027-01-31" })}
        profile={profile()}
        schedule={null}
      />,
    );

    expect(screen.getByText("2027-01-31")).toBeDefined();
    expect(screen.queryByText(/Examination window/)).toBeNull();
    expect(screen.queryByText(/Working toward/)).toBeNull();
  });

  it("invites a learner with a profile but no goal to choose one", () => {
    render(<StudySetupOverview goal={null} profile={profile()} schedule={null} />);

    expect(screen.getByRole("link", { name: /Choose what you are working toward/i })).toBeDefined();
    expect(screen.queryByRole("heading", { name: "Important dates" })).toBeNull();
  });
});
