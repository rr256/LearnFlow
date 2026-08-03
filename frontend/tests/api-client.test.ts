import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  listLearningPrograms,
  readCurriculumTree,
  readLearningProgram,
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

const program = {
  id: "3f1c0b6e-5f5a-4a7f-9d3e-1f2a3b4c5d6e",
  code: "gate-cse",
  name: "GATE Computer Science",
  description: null,
  active_curriculum_version: null,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("listLearningPrograms", () => {
  it("returns the data array and the pagination block", async () => {
    respondWith({ data: [program], pagination: { limit: 25, offset: 0, total: 1 } });

    const collection = await listLearningPrograms();

    expect(collection.data).toHaveLength(1);
    expect(collection.data[0]?.code).toBe("gate-cse");
    expect(collection.pagination.total).toBe(1);
  });

  it("sends the requested window as query parameters", async () => {
    respondWith({ data: [], pagination: { limit: 5, offset: 10, total: 0 } });

    await listLearningPrograms({ limit: 5, offset: 10 });

    const requestedUrl = vi.mocked(fetch).mock.calls[0]?.[0];
    expect(String(requestedUrl)).toContain("limit=5");
    expect(String(requestedUrl)).toContain("offset=10");
  });

  it("rejects a collection missing its pagination block", async () => {
    respondWith({ data: [] });

    await expect(listLearningPrograms()).rejects.toThrow(ApiError);
  });

  it("reports an unreachable api distinctly from an api that answered", async () => {
    failToConnect();

    const error = await listLearningPrograms().catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).isUnreachable).toBe(true);
    expect((error as ApiError).isNotFound).toBe(false);
  });
});

describe("readLearningProgram", () => {
  it("unwraps the data envelope", async () => {
    respondWith({ data: program });

    await expect(readLearningProgram(program.id)).resolves.toMatchObject({ code: "gate-cse" });
  });

  it("carries the documented error code and status off a failure envelope", async () => {
    respondWith(
      { error: { code: "not_found", message: "No such learning program.", details: [] } },
      404,
    );

    const error = await readLearningProgram(program.id).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("not_found");
    expect((error as ApiError).isNotFound).toBe(true);
  });

  it("still raises an ApiError when a failure carries no error envelope", async () => {
    respondWith("<html>gateway error</html>", 502);

    const error = await readLearningProgram(program.id).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("request_failed");
    expect((error as ApiError).status).toBe(502);
  });

  it("rejects a success response without the data envelope", async () => {
    respondWith(program);

    await expect(readLearningProgram(program.id)).rejects.toThrow(ApiError);
  });
});

describe("readCurriculumTree", () => {
  it("returns the version, its subjects, and its relationships", async () => {
    respondWith({
      data: {
        curriculum_version: {
          id: "9a8b7c6d-5e4f-4a3b-8c1d-2e3f4a5b6c7d",
          learning_program_id: program.id,
          version_label: "2027",
          status: "active",
          source_reference: "Official syllabus",
          published_at: null,
        },
        subjects: [],
        topic_relationships: [],
      },
    });

    const tree = await readCurriculumTree("9a8b7c6d-5e4f-4a3b-8c1d-2e3f4a5b6c7d");

    expect(tree.curriculum_version.version_label).toBe("2027");
    expect(tree.subjects).toEqual([]);
  });

  it("rejects a tree without a subjects list", async () => {
    respondWith({ data: { curriculum_version: {}, topic_relationships: [] } });

    await expect(readCurriculumTree("9a8b7c6d-5e4f-4a3b-8c1d-2e3f4a5b6c7d")).rejects.toThrow(
      ApiError,
    );
  });
});
