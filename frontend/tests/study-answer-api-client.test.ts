import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, askStudyQuestion } from "@/lib/api-client";

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
const QUESTION = "How does round robin choose the next process?";

const answered = {
  topic_id: TOPIC_ID,
  topic_name: "CPU scheduling",
  subject_name: "Operating Systems",
  question: QUESTION,
  outcome: "answered",
  answer: "Each process runs for one quantum, then goes to the back of the queue.",
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

describe("askStudyQuestion", () => {
  it("reads the data envelope", async () => {
    respondWith({ data: answered });

    const result = await askStudyQuestion(TOPIC_ID, QUESTION);

    expect(result.outcome).toBe("answered");
    expect(result.answer).toContain("one quantum");
    expect(result.passages[0]?.passage).toContain("Round robin scheduling");
  });

  it("posts to the documented mentor path", async () => {
    respondWith({ data: answered });

    await askStudyQuestion(TOPIC_ID, QUESTION);

    expect(requestUrl()).toContain("/api/v1/mentor/questions");
    expect(requestInit()?.method).toBe("POST");
  });

  it("sends the question in the body, never in the address", async () => {
    // A learner's own words in a URL would land in server logs and history.
    respondWith({ data: answered });

    await askStudyQuestion(TOPIC_ID, QUESTION);

    expect(requestUrl()).not.toContain("?");
    expect(requestUrl()).not.toContain(encodeURIComponent(QUESTION));
    expect(requestUrl()).not.toContain("round robin");
    expect(JSON.parse(requestInit()?.body as string)).toEqual({
      topic_id: TOPIC_ID,
      question: QUESTION,
    });
  });

  it("sends no learner identifier, model, or provider selection", async () => {
    respondWith({ data: answered });

    await askStudyQuestion(TOPIC_ID, QUESTION);

    const body = JSON.parse(requestInit()?.body as string);
    expect(Object.keys(body).sort()).toEqual(["question", "topic_id"]);
  });

  it("carries an ungrounded outcome through rather than treating it as a failure", async () => {
    // No passage found means no model was asked. That is an answer, not an error.
    respondWith({
      data: { ...answered, outcome: "no_matching_passage", answer: null, passages: [] },
    });

    const result = await askStudyQuestion(TOPIC_ID, QUESTION);

    expect(result.outcome).toBe("no_matching_passage");
    expect(result.answer).toBeNull();
    expect(result.passages).toEqual([]);
  });

  it("carries a provider failure through with its passages intact", async () => {
    // A provider that is switched off must not cost the learner their own notes.
    respondWith({ data: { ...answered, outcome: "provider_unavailable", answer: null } });

    const result = await askStudyQuestion(TOPIC_ID, QUESTION);

    expect(result.outcome).toBe("provider_unavailable");
    expect(result.answer).toBeNull();
    expect(result.passages).toHaveLength(1);
  });

  it("reports an unknown topic as missing", async () => {
    respondWith({ error: { code: "not_found", message: "No such topic.", details: [] } }, 404);

    await expect(askStudyQuestion(TOPIC_ID, QUESTION)).rejects.toMatchObject({
      isNotFound: true,
    });
  });

  it("reports a conflict before setup has run", async () => {
    respondWith({ error: { code: "conflict", message: "No learner.", details: [] } }, 409);

    await expect(askStudyQuestion(TOPIC_ID, QUESTION)).rejects.toMatchObject({
      isConflict: true,
    });
  });

  it("reports a refused question rather than returning one", async () => {
    respondWith(
      { error: { code: "validation_error", message: "A question is required.", details: [] } },
      422,
    );

    await expect(askStudyQuestion(TOPIC_ID, "")).rejects.toBeInstanceOf(ApiError);
  });

  it("reports a malformed answer rather than returning one", async () => {
    respondWith({ data: { ...answered, passages: "not a list" } });

    await expect(askStudyQuestion(TOPIC_ID, QUESTION)).rejects.toBeInstanceOf(ApiError);
  });
});
