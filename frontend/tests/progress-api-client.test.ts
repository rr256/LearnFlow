import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, listTopicProgress, recordTopicStage } from "@/lib/api-client";

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

const record = {
  id: "11111111-1111-4111-8111-111111111111",
  learner_id: "22222222-2222-4222-8222-222222222222",
  learning_stage: "building_foundation",
  stage_source: "learner",
  topic: {
    id: "33333333-3333-4333-8333-333333333333",
    code: null,
    name: "CPU scheduling",
    is_trackable: true,
    subject_id: "44444444-4444-4444-8444-444444444444",
    curriculum_version_id: "55555555-5555-4555-8555-555555555555",
  },
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("listTopicProgress (PRG-002)", () => {
  it("returns the recorded stages under the data envelope", async () => {
    respondWith({ data: [record], pagination: { limit: 100, offset: 0, total: 1 } });

    const records = await listTopicProgress();

    expect(records).toHaveLength(1);
    expect(records[0]?.topic.name).toBe("CPU scheduling");
  });

  it("resolves to an empty list before a learner has recorded anything", async () => {
    respondWith({ data: [], pagination: { limit: 100, offset: 0, total: 0 } });

    await expect(listTopicProgress()).resolves.toEqual([]);
  });

  it("passes the curriculum version as a query parameter", async () => {
    respondWith({ data: [], pagination: { limit: 100, offset: 0, total: 0 } });

    await listTopicProgress({ curriculumVersionId: record.topic.curriculum_version_id });

    expect(requestUrl()).toContain(
      `curriculum_version_id=${record.topic.curriculum_version_id}`,
    );
  });

  it("rejects a success body that carries no pagination block", async () => {
    respondWith({ data: [record] });

    await expect(listTopicProgress()).rejects.toMatchObject({ code: "malformed_response" });
  });

  it("reports a backend failure with the API's own code", async () => {
    respondWith({ error: { code: "conflict", message: "Two learners are stored.", details: [] } }, 409);

    const failure = await listTopicProgress().catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).code).toBe("conflict");
    expect((failure as ApiError).isConflict).toBe(true);
  });
});

describe("recordTopicStage (PRG-004)", () => {
  it("sends the stage as a PATCH and returns the saved record", async () => {
    respondWith({ data: record });

    const saved = await recordTopicStage(record.topic.id, "building_foundation");

    const init = requestInit();
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ learning_stage: "building_foundation" });
    expect(requestUrl()).toContain(`/api/v1/progress/topics/${record.topic.id}`);
    expect(saved.learning_stage).toBe("building_foundation");
  });

  it("sends no learner identifier: the backend resolves the effective learner", async () => {
    respondWith({ data: record });

    await recordTopicStage(record.topic.id, "practice_ready");

    expect(requestInit().body as string).not.toContain("learner_id");
  });

  it("reports a rejected grouping topic with the field the API named", async () => {
    respondWith(
      {
        error: {
          code: "validation_error",
          message: "Topic 'Operating Systems' groups subtopics.",
          details: [
            {
              field: "path.topic_id",
              message: "Topic 'Operating Systems' groups subtopics.",
              type: "topic_not_trackable",
            },
          ],
        },
      },
      422,
    );

    const failure = (await recordTopicStage(record.topic.id, "practice_ready").catch(
      (error: unknown) => error,
    )) as ApiError;

    expect(failure.code).toBe("validation_error");
    expect(failure.details[0]?.type).toBe("topic_not_trackable");
  });

  it("reports an unreachable backend rather than a malformed response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed");
      }),
    );

    const failure = (await recordTopicStage(record.topic.id, "practice_ready").catch(
      (error: unknown) => error,
    )) as ApiError;

    expect(failure.code).toBe("api_unreachable");
    expect(failure.isUnreachable).toBe(true);
  });

  it("rejects a success body with no data envelope", async () => {
    respondWith({ learning_stage: "practice_ready" });

    await expect(recordTopicStage(record.topic.id, "practice_ready")).rejects.toMatchObject({
      code: "malformed_response",
    });
  });
});
