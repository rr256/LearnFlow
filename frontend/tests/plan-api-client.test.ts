import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  generateStudyPlan,
  listStudyPlans,
  readStudyPlan,
  updatePlanItemStatus,
} from "@/lib/api-client";

function respondWith(body: unknown, status = 200): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), { status })),
  );
}

function requestUrl(): string {
  return vi.mocked(fetch).mock.calls[0]?.[0] as string;
}

function requestInit(): RequestInit {
  return vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit;
}

const roadmap = {
  id: "11111111-1111-4111-8111-111111111111",
  learner_id: "22222222-2222-4222-8222-222222222222",
  study_goal_id: "33333333-3333-4333-8333-333333333333",
  plan_type: "roadmap",
  period_start: "2026-08-06",
  period_end: "2027-02-06",
  status: "active",
  generation_reason: "60 topics from your curriculum, in syllabus order.",
  item_count: 1,
  items: [
    {
      id: "44444444-4444-4444-8444-444444444444",
      topic: {
        id: "55555555-5555-4555-8555-555555555555",
        code: null,
        name: "CPU scheduling",
        subject_id: "66666666-6666-4666-8666-666666666666",
        subject_name: "Operating Systems",
      },
      action_type: "study",
      scheduled_for: null,
      estimated_minutes: 60,
      priority: 1,
      status: "planned",
      recommendation_reason: "Topic 1 of 60 in syllabus order, from Operating Systems.",
      completed_at: null,
    },
  ],
};

const planItem = roadmap.items[0]!;

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("generateStudyPlan (PLN-001)", () => {
  it("posts the goal and returns the plans that were written", async () => {
    respondWith({
      data: {
        study_goal_id: roadmap.study_goal_id,
        generated_on: "2026-08-06",
        plans: [roadmap],
        superseded_plan_ids: [],
      },
    });

    const generated = await generateStudyPlan(roadmap.study_goal_id);

    expect(requestUrl()).toMatch(/\/api\/v1\/study-plans\/generate$/);
    expect(requestInit().method).toBe("POST");
    expect(JSON.parse(requestInit().body as string)).toEqual({
      study_goal_id: roadmap.study_goal_id,
    });
    expect(generated.plans).toHaveLength(1);
    expect(generated.generated_on).toBe("2026-08-06");
  });

  it("sends no learner identifier, because the backend resolves the learner", async () => {
    respondWith({
      data: {
        study_goal_id: roadmap.study_goal_id,
        generated_on: "2026-08-06",
        plans: [],
        superseded_plan_ids: [],
      },
    });

    await generateStudyPlan(roadmap.study_goal_id);

    expect(requestInit().body as string).not.toContain("learner_id");
  });

  it("reports what a regeneration set aside", async () => {
    respondWith({
      data: {
        study_goal_id: roadmap.study_goal_id,
        generated_on: "2026-08-06",
        plans: [roadmap],
        superseded_plan_ids: ["77777777-7777-4777-8777-777777777777"],
      },
    });

    const generated = await generateStudyPlan(roadmap.study_goal_id);

    expect(generated.superseded_plan_ids).toHaveLength(1);
  });

  it("raises the API's own code when the goal is not stored", async () => {
    respondWith(
      { error: { code: "not_found", message: "No study goal is stored.", details: [] } },
      404,
    );

    await expect(generateStudyPlan(roadmap.study_goal_id)).rejects.toMatchObject({
      code: "not_found",
    });
  });

  it("raises a conflict when setup has not created a learner", async () => {
    respondWith(
      { error: { code: "conflict", message: "No learner profile exists yet.", details: [] } },
      409,
    );

    await expect(generateStudyPlan(roadmap.study_goal_id)).rejects.toMatchObject({
      code: "conflict",
    });
  });

  it("rejects a success body that carries no plans", async () => {
    respondWith({ data: { study_goal_id: roadmap.study_goal_id, generated_on: "2026-08-06" } });

    await expect(generateStudyPlan(roadmap.study_goal_id)).rejects.toBeInstanceOf(ApiError);
  });
});

describe("listStudyPlans (PLN-002)", () => {
  it("returns the plans under the collection envelope", async () => {
    respondWith({ data: [roadmap], pagination: { limit: 25, offset: 0, total: 1 } });

    const plans = await listStudyPlans();

    expect(plans).toHaveLength(1);
    expect(plans[0]?.plan_type).toBe("roadmap");
  });

  it("passes the goal and status filters as query parameters", async () => {
    respondWith({ data: [], pagination: { limit: 25, offset: 0, total: 0 } });

    await listStudyPlans({ studyGoalId: roadmap.study_goal_id, status: "active" });

    expect(requestUrl()).toContain(`study_goal_id=${roadmap.study_goal_id}`);
    expect(requestUrl()).toContain("status=active");
  });

  it("resolves to an empty list before any plan has been generated", async () => {
    respondWith({ data: [], pagination: { limit: 25, offset: 0, total: 0 } });

    await expect(listStudyPlans()).resolves.toEqual([]);
  });

  it("rejects a body without the pagination block", async () => {
    respondWith({ data: [roadmap] });

    await expect(listStudyPlans()).rejects.toBeInstanceOf(ApiError);
  });
});

describe("readStudyPlan (PLN-003)", () => {
  it("returns one plan with its items", async () => {
    respondWith({ data: roadmap });

    const plan = await readStudyPlan(roadmap.id);

    expect(requestUrl()).toContain(`/api/v1/study-plans/${roadmap.id}`);
    expect(plan.items).toHaveLength(1);
    expect(plan.items[0]?.recommendation_reason).toContain("syllabus order");
  });

  it("raises the API's own code when the plan is not stored", async () => {
    respondWith(
      { error: { code: "not_found", message: "No study plan is stored.", details: [] } },
      404,
    );

    await expect(readStudyPlan(roadmap.id)).rejects.toMatchObject({ code: "not_found" });
  });

  it("rejects a success body that carries no items list", async () => {
    respondWith({ data: { ...roadmap, items: undefined } });

    await expect(readStudyPlan(roadmap.id)).rejects.toBeInstanceOf(ApiError);
  });

  it("reports an unreachable backend distinctly from a backend that answered", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed");
      }),
    );

    await expect(readStudyPlan(roadmap.id)).rejects.toMatchObject({ code: "api_unreachable" });
  });
});

describe("updatePlanItemStatus (PLN-004)", () => {
  it("patches the item and returns it with its new status", async () => {
    respondWith({
      data: { ...planItem, status: "completed", completed_at: "2026-08-06T09:00:00Z" },
    });

    const item = await updatePlanItemStatus(planItem.id, "completed");

    expect(requestUrl()).toMatch(new RegExp(`/api/v1/plan-items/${planItem.id}$`));
    expect(requestInit().method).toBe("PATCH");
    expect(JSON.parse(requestInit().body as string)).toEqual({ status: "completed" });
    expect(item.status).toBe("completed");
    expect(item.completed_at).toBe("2026-08-06T09:00:00Z");
  });

  it("sends only the status, so no caller can backdate work", async () => {
    respondWith({ data: { ...planItem, status: "completed" } });

    await updatePlanItemStatus(planItem.id, "completed");

    expect(Object.keys(JSON.parse(requestInit().body as string))).toEqual(["status"]);
  });

  it("puts an item back and reads the cleared timestamp", async () => {
    respondWith({ data: { ...planItem, status: "planned", completed_at: null } });

    const item = await updatePlanItemStatus(planItem.id, "planned");

    expect(JSON.parse(requestInit().body as string)).toEqual({ status: "planned" });
    expect(item.completed_at).toBeNull();
  });

  it("raises a conflict when the item's plan has been superseded", async () => {
    respondWith(
      {
        error: {
          code: "conflict",
          message: "That item belongs to a study plan that has been replaced.",
          details: [],
        },
      },
      409,
    );

    await expect(updatePlanItemStatus(planItem.id, "completed")).rejects.toMatchObject({
      code: "conflict",
      status: 409,
    });
  });

  it("raises the API's own code when the item is not stored", async () => {
    respondWith(
      { error: { code: "not_found", message: "No plan item is stored.", details: [] } },
      404,
    );

    await expect(updatePlanItemStatus(planItem.id, "completed")).rejects.toMatchObject({
      code: "not_found",
    });
  });

  it("rejects a success body without the data envelope", async () => {
    respondWith({ status: "completed" });

    await expect(updatePlanItemStatus(planItem.id, "completed")).rejects.toBeInstanceOf(ApiError);
  });

  it("reports an unreachable backend distinctly from a backend that answered", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed");
      }),
    );

    await expect(updatePlanItemStatus(planItem.id, "completed")).rejects.toMatchObject({
      code: "api_unreachable",
    });
  });
});
