import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  listRevisions,
  scheduleRevisions,
  updateRevisionStatus,
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

const revision = {
  id: "11111111-1111-4111-8111-111111111111",
  topic: {
    id: "22222222-2222-4222-8222-222222222222",
    code: null,
    name: "CPU scheduling",
    subject_id: "33333333-3333-4333-8333-333333333333",
    subject_name: "Operating Systems",
  },
  due_on: "2026-08-20",
  scheduled_for: null,
  status: "due",
  trigger_type: "completed_plan_item",
  recommendation_reason: "You completed planned work on this on 2026-08-13.",
  completed_at: null,
  is_due: true,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("listRevisions", () => {
  it("reads the collection envelope", async () => {
    respondWith({ data: [revision], pagination: { limit: 100, offset: 0, total: 1 } });

    const revisions = await listRevisions();

    expect(revisions).toHaveLength(1);
    expect(revisions[0]?.topic?.name).toBe("CPU scheduling");
  });

  it("asks for the documented path", async () => {
    respondWith({ data: [], pagination: { limit: 100, offset: 0, total: 0 } });

    await listRevisions();

    expect(requestUrl()).toContain("/api/v1/revisions?");
  });

  it("passes the due-only filter when asked", async () => {
    respondWith({ data: [], pagination: { limit: 100, offset: 0, total: 0 } });

    await listRevisions({ dueOnly: true });

    expect(requestUrl()).toContain("due_only=true");
  });

  it("leaves the filter off by default, so nothing is hidden unasked", async () => {
    respondWith({ data: [], pagination: { limit: 100, offset: 0, total: 0 } });

    await listRevisions();

    expect(requestUrl()).not.toContain("due_only");
  });

  it("reads with no body and no write method", async () => {
    respondWith({ data: [], pagination: { limit: 100, offset: 0, total: 0 } });

    await listRevisions();

    expect(requestInit().method).toBe("GET");
    expect(requestInit().body).toBeUndefined();
  });

  it("rejects a response without the documented envelope", async () => {
    respondWith([revision]);

    await expect(listRevisions()).rejects.toBeInstanceOf(ApiError);
  });

  it("reports a backend that cannot be reached", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed");
      }),
    );

    await expect(listRevisions()).rejects.toMatchObject({ isUnreachable: true });
  });
});

describe("updateRevisionStatus", () => {
  it("sends only the status, in the documented shape", async () => {
    respondWith({ data: { ...revision, status: "completed" } });

    await updateRevisionStatus(revision.id, "completed");

    expect(requestInit().method).toBe("PATCH");
    expect(JSON.parse(requestInit().body as string)).toEqual({ status: "completed" });
  });

  it("sends no learner identifier", async () => {
    respondWith({ data: revision });

    await updateRevisionStatus(revision.id, "skipped");

    expect(requestInit().body as string).not.toContain("learner_id");
  });

  it("sends no date, because a review names none", async () => {
    respondWith({ data: revision });

    await updateRevisionStatus(revision.id, "postponed");

    const body = JSON.parse(requestInit().body as string);
    expect(body).not.toHaveProperty("due_on");
    expect(body).not.toHaveProperty("scheduled_for");
  });

  it("addresses the revision by its own identifier", async () => {
    respondWith({ data: revision });

    await updateRevisionStatus(revision.id, "completed");

    expect(requestUrl()).toContain(`/api/v1/revisions/${revision.id}`);
  });

  it("reports a revision that is not stored", async () => {
    respondWith({ error: { code: "not_found", message: "No such revision.", details: [] } }, 404);

    await expect(updateRevisionStatus(revision.id, "completed")).rejects.toMatchObject({
      isNotFound: true,
    });
  });
});

describe("scheduleRevisions", () => {
  it("posts to the documented path with no meaningful body", async () => {
    respondWith(
      {
        data: {
          scheduled_on: "2026-08-20",
          created: [revision],
          already_scheduled_topic_count: 0,
          reason: "1 topics you have finished are ready to come back.",
        },
      },
      201,
    );

    await scheduleRevisions();

    expect(requestUrl()).toContain("/api/v1/revisions/schedule");
    expect(requestInit().method).toBe("POST");
    expect(JSON.parse(requestInit().body as string)).toEqual({});
  });

  it("returns what the run wrote and what it left alone", async () => {
    respondWith(
      {
        data: {
          scheduled_on: "2026-08-20",
          created: [revision],
          already_scheduled_topic_count: 2,
          reason: "1 topics are ready to come back.",
        },
      },
      201,
    );

    const scheduled = await scheduleRevisions();

    expect(scheduled.revisions).toHaveLength(1);
    expect(scheduled.already_scheduled_topic_count).toBe(2);
    expect(scheduled.scheduled_on).toBe("2026-08-20");
    expect(scheduled.reason).toContain("ready to come back");
  });

  it("accepts a run that wrote nothing", async () => {
    respondWith(
      {
        data: {
          scheduled_on: "2026-08-20",
          created: [],
          already_scheduled_topic_count: 3,
          reason: "Every topic you have finished already has a revision waiting.",
        },
      },
      201,
    );

    const scheduled = await scheduleRevisions();

    expect(scheduled.revisions).toEqual([]);
  });

  it("rejects a response without a created list", async () => {
    respondWith({ data: { scheduled_on: "2026-08-20" } }, 201);

    await expect(scheduleRevisions()).rejects.toBeInstanceOf(ApiError);
  });

  it("reports a conflict when no learner exists yet", async () => {
    respondWith(
      { error: { code: "conflict", message: "No learner is stored.", details: [] } },
      409,
    );

    await expect(scheduleRevisions()).rejects.toMatchObject({ isConflict: true });
  });
});
