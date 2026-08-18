import { describe, expect, it } from "vitest";

import {
  HISTORY_PAGE_SIZE,
  HISTORY_REQUEST_LIMIT,
  attemptMoment,
  attemptStateLabel,
  coveredTopics,
  historyHref,
  readHistoryOffset,
  selectHistoryPage,
} from "@/features/practice/history";
import type { PracticeTopic, QuizAttempt } from "@/types/practice";

function attempt(overrides: Partial<QuizAttempt> = {}): QuizAttempt {
  return {
    id: "attempt-1",
    learner_id: "learner-1",
    checkpoint_quiz_id: "quiz-1",
    quiz_title: "Practice: CPU scheduling",
    status: "evaluated",
    started_at: "2026-08-18T09:00:00Z",
    submitted_at: "2026-08-18T09:10:00Z",
    evaluated_at: "2026-08-18T09:10:00Z",
    topics: [],
    outcomes: [],
    ...overrides,
  };
}

/** `count` attempts, each with its own identifier. */
function attempts(count: number): QuizAttempt[] {
  return Array.from({ length: count }, (_, index) => attempt({ id: `attempt-${index + 1}` }));
}

function topic(overrides: Partial<PracticeTopic> = {}): PracticeTopic {
  return {
    id: "topic-1",
    code: null,
    name: "CPU scheduling",
    subject_id: "subject-1",
    subject_name: "Operating Systems",
    ...overrides,
  };
}

describe("readHistoryOffset", () => {
  it("reads a whole number of records from the address", () => {
    expect(readHistoryOffset("20")).toBe(20);
    expect(readHistoryOffset("0")).toBe(0);
  });

  it("starts at the newest when the address says nothing", () => {
    expect(readHistoryOffset(undefined)).toBe(0);
  });

  it("starts at the newest rather than failing on an offset that makes no sense", () => {
    for (const value of ["-1", "1.5", "banana", "", "1e400"]) {
      expect(readHistoryOffset(value)).toBe(0);
    }
  });

  it("takes the first value when the parameter is repeated", () => {
    expect(readHistoryOffset(["20", "40"])).toBe(20);
    expect(readHistoryOffset([])).toBe(0);
  });
});

describe("selectHistoryPage", () => {
  it("shows a page and keeps the extra record it asked for out of it", () => {
    const page = selectHistoryPage(attempts(HISTORY_REQUEST_LIMIT), 0);

    expect(page.attempts).toHaveLength(HISTORY_PAGE_SIZE);
    expect(page.attempts.at(-1)?.id).toBe(`attempt-${HISTORY_PAGE_SIZE}`);
  });

  it("offers earlier quizzes only when the extra record came back", () => {
    expect(selectHistoryPage(attempts(HISTORY_REQUEST_LIMIT), 0).olderOffset).toBe(
      HISTORY_PAGE_SIZE,
    );
    expect(selectHistoryPage(attempts(HISTORY_PAGE_SIZE), 0).olderOffset).toBeNull();
    expect(selectHistoryPage(attempts(3), 0).olderOffset).toBeNull();
  });

  it("offers more recent quizzes only once the learner has walked back", () => {
    expect(selectHistoryPage(attempts(3), 0).newerOffset).toBeNull();
    expect(selectHistoryPage(attempts(3), HISTORY_PAGE_SIZE).newerOffset).toBe(0);
    expect(selectHistoryPage(attempts(3), HISTORY_PAGE_SIZE * 2).newerOffset).toBe(
      HISTORY_PAGE_SIZE,
    );
  });

  it("steps back to the newest rather than past it from an offset between pages", () => {
    expect(selectHistoryPage(attempts(3), 4).newerOffset).toBe(0);
  });

  it("keeps the order the API returned, and reorders nothing", () => {
    const given = attempts(4);
    const page = selectHistoryPage(given, 0);

    expect(page.attempts.map((each) => each.id)).toEqual([
      "attempt-1",
      "attempt-2",
      "attempt-3",
      "attempt-4",
    ]);
  });

  it("reports an empty page beyond the oldest attempt without failing", () => {
    const page = selectHistoryPage([], HISTORY_PAGE_SIZE);

    expect(page.attempts).toEqual([]);
    expect(page.olderOffset).toBeNull();
    expect(page.newerOffset).toBe(0);
  });

  it("states no figure about how many attempts there are", () => {
    const page = selectHistoryPage(attempts(HISTORY_REQUEST_LIMIT), HISTORY_PAGE_SIZE);

    // Everything the page carries is either an attempt or a place to walk to.
    // Nothing here is a count of the learner's quizzes, which terminology.md
    // forbids by name.
    expect(Object.keys(page).sort()).toEqual(["attempts", "newerOffset", "olderOffset"]);
  });
});

describe("historyHref", () => {
  it("addresses the newest page without an offset", () => {
    expect(historyHref(0)).toBe("/practice/history");
  });

  it("carries the offset for every other page", () => {
    expect(historyHref(20)).toBe("/practice/history?offset=20");
  });
});

describe("attemptStateLabel", () => {
  it("says an attempt was answered or was not submitted, and judges neither", () => {
    expect(attemptStateLabel("evaluated")).toBe("Answered");
    expect(attemptStateLabel("in_progress")).toBe("Not submitted");
  });

  it("falls back to the stored word for a status this build does not know", () => {
    expect(attemptStateLabel("abandoned")).toBe("abandoned");
  });
});

describe("attemptMoment", () => {
  it("reports when a submitted attempt was submitted", () => {
    expect(attemptMoment(attempt())).toEqual({
      kind: "submitted",
      iso: "2026-08-18T09:10:00Z",
      day: "2026-08-18",
    });
  });

  it("falls back to when an unsubmitted attempt was started", () => {
    expect(attemptMoment(attempt({ status: "in_progress", submitted_at: null }))).toEqual({
      kind: "started",
      iso: "2026-08-18T09:00:00Z",
      day: "2026-08-18",
    });
  });

  it("reports nothing rather than inventing a date", () => {
    expect(attemptMoment(attempt({ started_at: null, submitted_at: null }))).toBeNull();
  });

  it("prints the API's own timestamp rather than converting it", () => {
    const moment = attemptMoment(attempt({ submitted_at: "2026-08-18T23:30:00Z" }));

    expect(moment?.day).toBe("2026-08-18");
    expect(moment?.iso).toBe("2026-08-18T23:30:00Z");
  });
});

describe("coveredTopics", () => {
  it("names each topic under its subject, in the API's order", () => {
    expect(
      coveredTopics([topic(), topic({ id: "topic-2", name: "Deadlock" })]),
    ).toBe("Operating Systems — CPU scheduling; Operating Systems — Deadlock");
  });

  it("says nothing rather than something empty when an attempt names no topic", () => {
    expect(coveredTopics([])).toBeNull();
  });
});
