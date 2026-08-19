import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, searchTopicNotes } from "@/lib/api-client";

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

const TOPIC_ID = "11111111-1111-4111-8111-111111111111";

const found = {
  topic_id: TOPIC_ID,
  topic_name: "CPU scheduling",
  subject_name: "Operating Systems",
  outcome: "found",
  passages: [
    {
      note_id: "22222222-2222-4222-8222-222222222222",
      note_title: "Round robin",
      resource_id: "33333333-3333-4333-8333-333333333333",
      resource_title: "Operating Systems notes",
      resource_type: "note",
      topic_id: TOPIC_ID,
      topic_name: "CPU scheduling",
      subject_name: "Operating Systems",
      passage: "Round robin scheduling gives each process a quantum.",
    },
  ],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("searchTopicNotes", () => {
  it("reads the data envelope", async () => {
    respondWith({ data: found });

    const result = await searchTopicNotes(TOPIC_ID);

    expect(result.outcome).toBe("found");
    expect(result.passages[0]?.passage).toContain("Round robin scheduling");
  });

  it("asks for the documented path with the topic as the query", async () => {
    respondWith({ data: found });

    await searchTopicNotes(TOPIC_ID);

    expect(requestUrl()).toContain("/api/v1/resource-notes/search?");
    expect(requestUrl()).toContain(`topic_id=${TOPIC_ID}`);
    expect(requestInit()?.method ?? "GET").toBe("GET");
  });

  it("sends no free-text query and no learner identifier", async () => {
    respondWith({ data: found });

    await searchTopicNotes(TOPIC_ID);
    const url = requestUrl();

    expect(url).not.toContain("q=");
    expect(url).not.toContain("query=");
    expect(url).not.toContain("learner_id");
  });

  it("carries an empty outcome through rather than treating it as a failure", async () => {
    respondWith({ data: { ...found, outcome: "no_linked_material", passages: [] } });

    const result = await searchTopicNotes(TOPIC_ID);

    expect(result.outcome).toBe("no_linked_material");
    expect(result.passages).toEqual([]);
  });

  it("reports an unknown topic as missing", async () => {
    respondWith({ error: { code: "not_found", message: "No such topic.", details: [] } }, 404);

    await expect(searchTopicNotes(TOPIC_ID)).rejects.toMatchObject({ isNotFound: true });
  });

  it("reports a conflict before setup has run", async () => {
    respondWith({ error: { code: "conflict", message: "No learner.", details: [] } }, 409);

    await expect(searchTopicNotes(TOPIC_ID)).rejects.toMatchObject({ isConflict: true });
  });

  it("reports a malformed answer rather than returning one", async () => {
    respondWith({ data: "not a search result" });

    await expect(searchTopicNotes(TOPIC_ID)).rejects.toBeInstanceOf(ApiError);
  });
});
