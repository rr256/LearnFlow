import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  createStudyGoal,
  listExaminationSchedules,
  listStudyGoals,
  readLearnerProfile,
  updateLearnerProfile,
  updateStudyGoal,
} from "@/lib/api-client";

function respondWith(body: unknown, status = 200): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), { status })),
  );
}

function failToConnect(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      throw new TypeError("fetch failed");
    }),
  );
}

function lastRequest(): RequestInit {
  return vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit;
}

const schedule = {
  id: "1c2d3e4f-5a6b-4c7d-8e9f-0a1b2c3d4e5f",
  learning_program_id: "3f1c0b6e-5f5a-4a7f-9d3e-1f2a3b4c5d6e",
  cycle_label: "2027",
  name: "GATE 2027",
  organising_body: "IIT Madras",
  source_reference: "https://example.test/schedule",
  source_checked_on: "2026-08-01",
  schedule_status: "provisional",
  examination_window: { starts_on: "2027-02-06", ends_on: "2027-02-21" },
  periods: [{ period_type: "examination", starts_on: "2027-02-06", ends_on: "2027-02-07" }],
};

const goal = {
  id: "9f8e7d6c-5b4a-4392-8172-6a5b4c3d2e1f",
  learner_id: "0a1b2c3d-4e5f-4061-8273-8495a6b7c8d9",
  status: "active",
  target_date: null,
  learning_program: { id: schedule.learning_program_id, code: "gate-cse", name: "GATE CSE" },
  curriculum_version: { id: "aabbccdd-1122-4334-8556-778899aabbcc", version_label: "2027", status: "active" },
  examination: {
    id: schedule.id,
    cycle_label: "2027",
    name: "GATE 2027",
    organising_body: "IIT Madras",
    source_reference: "https://example.test/schedule",
    source_checked_on: "2026-08-01",
    schedule_status: "provisional",
    examination_window: { starts_on: "2027-02-06", ends_on: "2027-02-21" },
  },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("readLearnerProfile", () => {
  it("returns null before setup has created a learner", async () => {
    respondWith({ data: null });

    await expect(readLearnerProfile()).resolves.toBeNull();
  });

  it("returns the stored profile", async () => {
    respondWith({
      data: { id: "0a1b2c3d-4e5f-4061-8273-8495a6b7c8d9", display_name: "Asha", timezone: "Asia/Kolkata" },
    });

    const profile = await readLearnerProfile();

    expect(profile?.display_name).toBe("Asha");
  });

  it("reports an unreachable api distinctly from an api that answered", async () => {
    failToConnect();

    const error = await readLearnerProfile().catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).isUnreachable).toBe(true);
  });
});

describe("updateLearnerProfile", () => {
  it("sends a PATCH carrying only the fields it was given", async () => {
    respondWith({ data: { id: "x", display_name: "Asha", timezone: "Asia/Kolkata" } });

    await updateLearnerProfile({ display_name: "Asha" });

    const request = lastRequest();
    expect(request.method).toBe("PATCH");
    expect(JSON.parse(String(request.body))).toEqual({ display_name: "Asha" });
  });

  it("sends an explicit null so a cleared name is removed rather than kept", async () => {
    respondWith({ data: { id: "x", display_name: null, timezone: "Asia/Kolkata" } });

    await updateLearnerProfile({ display_name: null });

    expect(JSON.parse(String(lastRequest().body))).toEqual({ display_name: null });
  });

  it("carries the field-level details of a rejected write", async () => {
    respondWith(
      {
        error: {
          code: "validation_error",
          message: "The request failed validation.",
          details: [{ field: "body.timezone", message: "not a zone", type: "value_error" }],
        },
      },
      422,
    );

    const error = (await updateLearnerProfile({ timezone: "Mars/Olympus_Mons" }).catch(
      (caught: unknown) => caught,
    )) as ApiError;

    expect(error.code).toBe("validation_error");
    expect(error.details[0]?.field).toBe("body.timezone");
  });
});

describe("listExaminationSchedules", () => {
  it("returns the schedules with their windows", async () => {
    respondWith({ data: [schedule], pagination: { limit: 25, offset: 0, total: 1 } });

    const schedules = await listExaminationSchedules();

    expect(schedules[0]?.examination_window).toEqual({
      starts_on: "2027-02-06",
      ends_on: "2027-02-21",
    });
  });

  it("filters by learning program when one is given", async () => {
    respondWith({ data: [], pagination: { limit: 25, offset: 0, total: 0 } });

    await listExaminationSchedules({ learningProgramId: schedule.learning_program_id });

    expect(String(vi.mocked(fetch).mock.calls[0]?.[0])).toContain(
      `learning_program_id=${schedule.learning_program_id}`,
    );
  });

  it("rejects a collection missing its pagination block", async () => {
    respondWith({ data: [schedule] });

    await expect(listExaminationSchedules()).rejects.toThrow(ApiError);
  });
});

describe("createStudyGoal", () => {
  it("sends a POST with the goal body", async () => {
    respondWith({ data: goal }, 201);

    await createStudyGoal({
      learning_program_id: schedule.learning_program_id,
      examination_schedule_id: schedule.id,
      target_date: null,
    });

    const request = lastRequest();
    expect(request.method).toBe("POST");
    expect(JSON.parse(String(request.body))).toEqual({
      learning_program_id: schedule.learning_program_id,
      examination_schedule_id: schedule.id,
      target_date: null,
    });
  });

  it("reports a conflict distinctly, so a repeated submit can be explained", async () => {
    respondWith(
      { error: { code: "conflict", message: "An active study goal already exists.", details: [] } },
      409,
    );

    const error = (await createStudyGoal({
      learning_program_id: schedule.learning_program_id,
      target_date: "2027-01-31",
    }).catch((caught: unknown) => caught)) as ApiError;

    expect(error.isConflict).toBe(true);
    expect(error.code).toBe("conflict");
  });
});

describe("listStudyGoals", () => {
  it("returns an empty list before setup has run", async () => {
    respondWith({ data: [], pagination: { limit: 25, offset: 0, total: 0 } });

    await expect(listStudyGoals()).resolves.toEqual([]);
  });

  it("returns the learner's goals", async () => {
    respondWith({ data: [goal], pagination: { limit: 25, offset: 0, total: 1 } });

    const goals = await listStudyGoals();

    expect(goals[0]?.examination?.cycle_label).toBe("2027");
  });
});

describe("updateStudyGoal", () => {
  it("sends a PATCH to the addressed goal", async () => {
    respondWith({ data: goal });

    await updateStudyGoal(goal.id, { target_date: "2027-01-31" });

    expect(String(vi.mocked(fetch).mock.calls[0]?.[0])).toContain(`/study-goals/${goal.id}`);
    expect(lastRequest().method).toBe("PATCH");
  });

  it("reports a missing goal as not found", async () => {
    respondWith(
      { error: { code: "not_found", message: "No study goal is stored.", details: [] } },
      404,
    );

    const error = (await updateStudyGoal(goal.id, { status: "paused" }).catch(
      (caught: unknown) => caught,
    )) as ApiError;

    expect(error.isNotFound).toBe(true);
  });
});
