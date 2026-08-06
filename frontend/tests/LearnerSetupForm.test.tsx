import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { LearningProgram } from "@/types/curriculum";
import type { ExaminationSchedule, StudyGoal } from "@/types/study-goal";

// The form imports the server action, which pulls in `next/cache`. A component
// test exercises the markup, not the write path; the action's own logic is
// covered by tests/setup-submission.test.ts.
vi.mock("@/features/onboarding/actions", () => ({ saveLearnerSetup: vi.fn() }));

const { LearnerSetupForm } = await import("@/features/onboarding/LearnerSetupForm");

afterEach(cleanup);

const program: LearningProgram = {
  id: "program-1",
  code: "gate-cse",
  name: "GATE Computer Science",
  description: null,
  active_curriculum_version: null,
};

const schedule: ExaminationSchedule = {
  id: "schedule-1",
  learning_program_id: "program-1",
  cycle_label: "2027",
  name: "GATE 2027",
  organising_body: "IIT Madras",
  source_reference: "https://example.test/schedule",
  source_checked_on: "2026-08-01",
  schedule_status: "provisional",
  examination_window: { starts_on: "2027-02-06", ends_on: "2027-02-21" },
  periods: [],
};

const goal: StudyGoal = {
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
};

function renderForm(overrides: Partial<Parameters<typeof LearnerSetupForm>[0]> = {}) {
  return render(
    <LearnerSetupForm
      goal={null}
      profile={null}
      programs={[program]}
      schedules={[schedule]}
      {...overrides}
    />,
  );
}

describe("LearnerSetupForm", () => {
  it("offers the learning programs the API returned", () => {
    renderForm();

    expect(screen.getByRole("combobox", { name: /Learning program/i })).toBeDefined();
    expect(screen.getByRole("option", { name: "GATE Computer Science" })).toBeDefined();
  });

  it("explains an empty program collection instead of showing an unusable form", () => {
    renderForm({ programs: [] });

    expect(screen.getByRole("heading", { name: /No learning programs yet/i })).toBeDefined();
    expect(screen.queryByRole("button", { name: /Save my setup/i })).toBeNull();
  });

  it("prefills the stored profile so an update does not start from blank", () => {
    renderForm({
      profile: { id: "learner-1", display_name: "Asha", timezone: "Europe/Lisbon" },
    });

    expect(screen.getByRole("textbox", { name: /Your name/i })).toHaveProperty("value", "Asha");
    expect(screen.getByRole("textbox", { name: /Timezone/i })).toHaveProperty(
      "value",
      "Europe/Lisbon",
    );
  });

  it("describes an examination by its window, never by one date", () => {
    renderForm();

    expect(screen.getByRole("option", { name: /GATE 2027 — 2027-02-06 to 2027-02-21/ })).toBeDefined();
  });

  it("says in words that provisional dates may still change", () => {
    renderForm();

    expect(screen.getByText(/Provisional/)).toBeDefined();
  });

  it("does not call confirmed dates provisional", () => {
    renderForm({ schedules: [{ ...schedule, schedule_status: "confirmed" }] });

    expect(screen.queryByText(/Provisional/)).toBeNull();
  });

  it("starts on the target date when no examination schedule has been loaded", () => {
    renderForm({ schedules: [] });

    expect(screen.getByRole("radio", { name: /My own completion date/i })).toHaveProperty(
      "checked",
      true,
    );
  });

  it("explains the missing schedule if the learner picks the examination anyway", () => {
    renderForm({ schedules: [] });

    fireEvent.click(screen.getByRole("radio", { name: /A published examination/i }));

    expect(screen.getByText(/No examination schedule has been loaded/i)).toBeDefined();
    expect(screen.queryByRole("combobox", { name: /Examination/i })).toBeNull();
  });

  it("starts on the examination when one is available", () => {
    renderForm();

    expect(screen.getByRole("radio", { name: /A published examination/i })).toHaveProperty(
      "checked",
      true,
    );
  });

  it("carries an existing goal so a resubmission updates rather than creates", () => {
    const { container } = renderForm({ goal });

    const hidden = container.querySelector('input[name="study_goal_id"]');
    expect(hidden?.getAttribute("value")).toBe("goal-1");
    expect(screen.getByRole("button", { name: /Update my setup/i })).toBeDefined();
  });

  it("labels the button for a first-time learner as saving rather than updating", () => {
    renderForm();

    expect(screen.getByRole("button", { name: /Save my setup/i })).toBeDefined();
  });

  it("explains that the goal binds to the active curriculum version", () => {
    renderForm();

    expect(screen.getByText(/active curriculum version/i)).toBeDefined();
  });

  it("offers a control for each planning preference", () => {
    renderForm();

    expect(screen.getByRole("spinbutton", { name: /Preferred session length/i })).toBeDefined();
    expect(screen.getByRole("combobox", { name: /Topic order/i })).toBeDefined();
  });

  it("offers no preference as a real choice rather than defaulting to an order", () => {
    renderForm();

    const order = screen.getByRole("combobox", { name: /Topic order/i });

    expect(order).toHaveProperty("value", "");
    expect(screen.getByRole("option", { name: /No preference/i })).toBeDefined();
  });

  it("bounds the session length control the way the API does", () => {
    renderForm();

    const session = screen.getByRole("spinbutton", { name: /Preferred session length/i });

    expect(session.getAttribute("min")).toBe("15");
    expect(session.getAttribute("max")).toBe("480");
  });

  it("fills the preference controls from the goal already saved", () => {
    renderForm({
      goal: {
        ...goal,
        planning_preferences: {
          preferred_session_minutes: 90,
          topic_sequencing: "prerequisites_first",
        },
      },
    });

    expect(screen.getByRole("spinbutton", { name: /Preferred session length/i })).toHaveProperty(
      "value",
      "90",
    );
    expect(screen.getByRole("combobox", { name: /Topic order/i })).toHaveProperty(
      "value",
      "prerequisites_first",
    );
  });

  it("says what each topic order means, so the choice is not a guess", () => {
    renderForm();

    expect(screen.getByText(/order the syllabus lists them/i)).toBeDefined();
    expect(screen.getByText(/groundwork before the topics that build on it/i)).toBeDefined();
  });

  it("says that a session length is a duration rather than a time of day", () => {
    renderForm();

    expect(screen.getByText(/not when in the day it starts/i)).toBeDefined();
  });

  it("says that leaving a preference empty is a fine answer", () => {
    renderForm();

    expect(screen.getByText(/leaving either of these empty is a fine answer/i)).toBeDefined();
  });
});
