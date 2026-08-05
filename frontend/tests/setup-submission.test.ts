import { describe, expect, it } from "vitest";

import {
  readSetupSubmission,
  toNewStudyGoal,
  toStudyGoalUpdate,
} from "@/features/onboarding/submission";

const PROGRAM_ID = "3f1c0b6e-5f5a-4a7f-9d3e-1f2a3b4c5d6e";
const SCHEDULE_ID = "1c2d3e4f-5a6b-4c7d-8e9f-0a1b2c3d4e5f";

function form(fields: Record<string, string>): FormData {
  const data = new FormData();
  for (const [name, value] of Object.entries(fields)) {
    data.set(name, value);
  }
  return data;
}

function submissionOf(fields: Record<string, string>) {
  const read = readSetupSubmission(form(fields));
  if ("problem" in read) {
    throw new Error(`expected a submission, got a problem on ${read.problem.field}`);
  }
  return read.submission;
}

describe("readSetupSubmission", () => {
  it("reads a goal aiming at a published examination", () => {
    const submission = submissionOf({
      learning_program_id: PROGRAM_ID,
      goal_target: "examination",
      examination_schedule_id: SCHEDULE_ID,
    });

    expect(submission.examinationScheduleId).toBe(SCHEDULE_ID);
    expect(submission.targetDate).toBeNull();
  });

  it("reads a goal aiming at the learner's own date", () => {
    const submission = submissionOf({
      learning_program_id: PROGRAM_ID,
      goal_target: "target_date",
      target_date: "2027-01-31",
    });

    expect(submission.targetDate).toBe("2027-01-31");
    expect(submission.examinationScheduleId).toBeNull();
  });

  it("clears the horizon the learner did not choose", () => {
    // The unselected control is still in the DOM on a re-render, so a stale
    // value must not survive a switch from one kind of horizon to the other.
    const submission = submissionOf({
      learning_program_id: PROGRAM_ID,
      goal_target: "target_date",
      target_date: "2027-01-31",
      examination_schedule_id: SCHEDULE_ID,
    });

    expect(submission.examinationScheduleId).toBeNull();
  });

  it("sends an empty name as null so a cleared name is removed", () => {
    const submission = submissionOf({
      learning_program_id: PROGRAM_ID,
      goal_target: "target_date",
      target_date: "2027-01-31",
      display_name: "   ",
    });

    expect(submission.profile.display_name).toBeNull();
  });

  it("omits the timezone entirely when the learner left it empty", () => {
    // Absent leaves the stored value alone; the API rejects an explicit null.
    const submission = submissionOf({
      learning_program_id: PROGRAM_ID,
      goal_target: "target_date",
      target_date: "2027-01-31",
      timezone: "",
    });

    expect("timezone" in submission.profile).toBe(false);
  });

  it("keeps a timezone the learner supplied", () => {
    const submission = submissionOf({
      learning_program_id: PROGRAM_ID,
      goal_target: "target_date",
      target_date: "2027-01-31",
      timezone: " Europe/Lisbon ",
    });

    expect(submission.profile.timezone).toBe("Europe/Lisbon");
  });

  it("carries an existing goal identifier so a resubmission updates rather than creates", () => {
    const submission = submissionOf({
      learning_program_id: PROGRAM_ID,
      goal_target: "target_date",
      target_date: "2027-01-31",
      study_goal_id: "9f8e7d6c-5b4a-4392-8172-6a5b4c3d2e1f",
    });

    expect(submission.studyGoalId).toBe("9f8e7d6c-5b4a-4392-8172-6a5b4c3d2e1f");
  });

  it("reports a missing learning program against its own field", () => {
    const read = readSetupSubmission(form({ goal_target: "target_date", target_date: "2027-01-31" }));

    expect(read).toEqual({
      problem: {
        field: "learning_program_id",
        message: "Choose the learning program you are studying.",
      },
    });
  });

  it("reports a missing examination against its own field", () => {
    const read = readSetupSubmission(
      form({ learning_program_id: PROGRAM_ID, goal_target: "examination" }),
    );

    expect("problem" in read && read.problem.field).toBe("examination_schedule_id");
  });

  it("reports a missing target date against its own field", () => {
    const read = readSetupSubmission(
      form({ learning_program_id: PROGRAM_ID, goal_target: "target_date" }),
    );

    expect("problem" in read && read.problem.field).toBe("target_date");
  });
});

describe("request bodies", () => {
  it("builds a GOAL-001 body carrying no learner or curriculum-version identifier", () => {
    const body = toNewStudyGoal(
      submissionOf({
        learning_program_id: PROGRAM_ID,
        goal_target: "examination",
        examination_schedule_id: SCHEDULE_ID,
      }),
    );

    expect(Object.keys(body).sort()).toEqual([
      "examination_schedule_id",
      "learning_program_id",
      "target_date",
    ]);
  });

  it("builds a GOAL-004 body that replaces both halves of the horizon", () => {
    const body = toStudyGoalUpdate(
      submissionOf({
        learning_program_id: PROGRAM_ID,
        goal_target: "target_date",
        target_date: "2027-01-31",
      }),
    );

    expect(body).toEqual({ examination_schedule_id: null, target_date: "2027-01-31" });
  });
});
