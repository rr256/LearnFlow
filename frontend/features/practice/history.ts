/**
 * Reading the checkpoint-practice history: which attempts one page holds, and
 * where the pages either side of it start.
 *
 * QZ-006 returns the learner's attempts newest first, with `limit` and `offset`.
 * Turning that into a page a learner can walk back through is presentation, and
 * it is plain functions here so it is testable without a running server — the
 * reason `features/resources/by-topic.ts` and `features/progress/stages.ts` are
 * separate modules too.
 *
 * **Nothing here counts, totals, compares, or ranks.** No attempt is set against
 * another, no page states how many attempts exist, and `pagination.total` is
 * never read: whether an older page exists is decided by asking QZ-006 for one
 * record more than a page holds and seeing whether it came back. A figure
 * describing how many quizzes a learner has taken is forbidden by name in
 * docs/domain/terminology.md, so this module never has one to leak.
 *
 * **A page is not a cap.** The order is QZ-006's own — newest first, which is
 * chronological rather than a judgement — and every attempt stays reachable by
 * walking back. That is what separates paging from the capping
 * ADR-031 refuses, where choosing which few to show would itself be a ranking.
 */

import type { PracticeTopic, QuizAttempt } from "@/types/practice";

/**
 * How many attempts one page of the history holds.
 *
 * Small, because each entry can be opened to show what became of every question
 * it asked. It bounds one screen, not the learner's history.
 */
export const HISTORY_PAGE_SIZE = 10;

/**
 * What to ask QZ-006 for: one attempt more than a page shows.
 *
 * The extra record is how an older page is detected without reading or
 * displaying a count of the learner's quizzes.
 */
export const HISTORY_REQUEST_LIMIT = HISTORY_PAGE_SIZE + 1;

/** One page of the history, and where the pages either side of it start. */
export interface HistoryPage {
  /** The attempts this page shows, in the order QZ-006 returned them. */
  attempts: QuizAttempt[];
  /** Where the next page of older attempts starts, or null at the oldest. */
  olderOffset: number | null;
  /** Where the previous page of newer attempts starts, or null at the newest. */
  newerOffset: number | null;
}

/**
 * Read the `offset` query parameter into a place in the newest-first list.
 *
 * Anything that is not a whole number of records at or after the newest — a
 * missing value, a negative one, a fraction, a word, or the repeated parameter
 * Next.js hands over as an array — reads as the newest page rather than as an
 * error. A mistyped address is a learner who wants their history, not a `404`.
 */
export function readHistoryOffset(value: string | string[] | undefined): number {
  const raw = Array.isArray(value) ? value[0] : value;
  if (raw === undefined) {
    return 0;
  }
  const parsed = Number(raw);
  if (!Number.isSafeInteger(parsed) || parsed < 0) {
    return 0;
  }
  return parsed;
}

/**
 * Split what QZ-006 returned into the page to show and the pages either side.
 *
 * `fetched` is expected to hold up to {@link HISTORY_REQUEST_LIMIT} attempts —
 * one more than a page. When that extra one arrived there is an older page; when
 * it did not, this is the oldest, and nothing is said about how many attempts
 * were passed to get here.
 *
 * The newer offset steps back by a page and stops at the newest, so an address
 * typed with an offset that falls between pages still leads somewhere real.
 */
export function selectHistoryPage(fetched: QuizAttempt[], offset: number): HistoryPage {
  const start = Math.max(0, offset);
  return {
    attempts: fetched.slice(0, HISTORY_PAGE_SIZE),
    olderOffset: fetched.length > HISTORY_PAGE_SIZE ? start + HISTORY_PAGE_SIZE : null,
    newerOffset: start === 0 ? null : Math.max(0, start - HISTORY_PAGE_SIZE),
  };
}

/** The address of one page of the history. */
export function historyHref(offset: number): string {
  return offset === 0 ? "/practice/history" : `/practice/history?offset=${offset}`;
}

/**
 * How an attempt's state reads, falling back to the stored word.
 *
 * An attempt that was never submitted is *not submitted* — never abandoned,
 * failed, or incomplete. It is a quiz the learner opened and left, which says
 * nothing about them.
 */
export function attemptStateLabel(status: string): string {
  if (status === "evaluated") {
    return "Answered";
  }
  if (status === "in_progress") {
    return "Not submitted";
  }
  return status;
}

/** When an attempt happened, and whether that moment is its submission. */
export interface AttemptMoment {
  /** `submitted` when the attempt was submitted, `started` when it never was. */
  kind: "submitted" | "started";
  /** The API's own timestamp, for the `dateTime` attribute of `<time>`. */
  iso: string;
  /** The calendar day of that timestamp, exactly as the API wrote it. */
  day: string;
}

/**
 * When an attempt happened: when it was submitted, or when it was started if it
 * never was.
 *
 * The day is the timestamp's own, as the API sent it — this performs **no
 * timezone conversion**, which is the position the practice screens have taken
 * since ADR-033. Resolving the learner's own date is `learnerToday`, which needs
 * LRN-001, and this screen deliberately reads nothing the practice area did not
 * already read.
 */
export function attemptMoment(attempt: QuizAttempt): AttemptMoment | null {
  if (attempt.submitted_at) {
    return { kind: "submitted", iso: attempt.submitted_at, day: attempt.submitted_at.slice(0, 10) };
  }
  if (attempt.started_at) {
    return { kind: "started", iso: attempt.started_at, day: attempt.started_at.slice(0, 10) };
  }
  return null;
}

/**
 * The topics an attempt covered, in the API's order, or null when it names none.
 *
 * Written the way the question bank writes them, so the same topic reads the
 * same wherever a learner meets it. The order is the backend's; re-sorting it
 * here would put a curriculum decision in the browser
 * (docs/development/coding-standards.md#ui-responsibilities).
 */
export function coveredTopics(topics: PracticeTopic[]): string | null {
  if (topics.length === 0) {
    return null;
  }
  return topics.map((topic) => `${topic.subject_name} — ${topic.name}`).join("; ");
}
