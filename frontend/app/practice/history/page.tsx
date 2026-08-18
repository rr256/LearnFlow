import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import styles from "@/app/practice/history/page.module.css";
import { Notice } from "@/components/Notice";
import { PracticeHistory } from "@/features/practice/PracticeHistory";
import {
  HISTORY_REQUEST_LIMIT,
  readHistoryOffset,
  selectHistoryPage,
  type HistoryPage,
} from "@/features/practice/history";
import { ApiError, listQuizAttempts } from "@/lib/api-client";

export const metadata: Metadata = {
  title: "Practice history",
};

/**
 * Rendered per request rather than prerendered.
 *
 * Quiz attempts are learner data, and `next build` has no API to reach.
 */
export const dynamic = "force-dynamic";

interface HistoryPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/**
 * QZ-006 — one page of the learner's attempts, and whether an older page exists.
 *
 * One record more than a page is asked for, and the extra one is what says there
 * is more to walk back to. `pagination.total` is deliberately never read: a
 * figure for how many quizzes a learner has taken is forbidden by name in
 * docs/domain/terminology.md, and the safest way not to show one is not to hold
 * one.
 */
async function readHistory(offset: number): Promise<HistoryPage> {
  const attempts = await listQuizAttempts({ limit: HISTORY_REQUEST_LIMIT, offset });
  return selectHistoryPage(attempts, offset);
}

/**
 * The data-dependent half of the screen, suspended so the heading appears before
 * the API answers.
 *
 * The boundary is declared here rather than as a `loading.tsx` segment file, for
 * the reason recorded in docs/development/folder-structure.md: a segment file
 * also covers every nested route, and a boundary above a lookup that can call
 * `notFound()` turns a `404` into a `200`. Nothing here calls it — an offset
 * that makes no sense reads as the newest page rather than as a missing one —
 * but the rule is kept so the practice routes all read the same way.
 */
async function HistorySection({ offset }: { offset: number }) {
  let page: HistoryPage;
  try {
    page = await readHistory(offset);
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    // Handled here rather than left to the route error boundary, because a
    // production build replaces a server-side error message with a generic one.
    return (
      <Notice title="Your practice history could not be loaded" tone="attention">
        <p>{error.message}</p>
        {error.isUnreachable ? (
          <p>
            Start the backend with <code>docker compose up</code>, or run it directly, and reload
            this page.
          </p>
        ) : null}
        {error.isConflict ? (
          <p>
            More than one learner is stored, so LearnFlow cannot tell which one is yours. It is
            single-learner until accounts exist.
          </p>
        ) : null}
      </Notice>
    );
  }

  return <PracticeHistory page={page} />;
}

/**
 * The checkpoint-practice history: QZ-006, read a page at a time.
 *
 * **A reading, not a new record.** It adds no endpoint, no column, and no
 * migration, and changes nothing in the backend: every fact on it is already a
 * field of the response QZ-006 has always returned, which is the shape ADR-026,
 * ADR-029, ADR-030, and ADR-031 used for the month, the overview, the stages,
 * and the priority panel.
 *
 * **Nothing is counted, totalled, scored, or compared.** No attempt carries a
 * mark or a percentage, no attempt is set against another, and the screen never
 * says how many quizzes the learner has taken — each of those is forbidden by
 * name in docs/domain/terminology.md. There is no streak and no summary of how
 * the learner is doing.
 *
 * **Nothing is ranked or left out.** The order is QZ-006's own, newest first,
 * and paging is not a cap: every attempt is reachable by walking back, which is
 * what separates it from the capping ADR-031 refuses.
 *
 * **Read-only.** There is no control here at all — nothing to re-mark, nothing
 * to re-submit, and nothing that records a learning stage, moves a plan, or
 * schedules a review. Practising again means a new quiz, from `/practice`.
 *
 * The navigation sits outside the boundary below, so an unreachable backend
 * still leaves a learner a way forward rather than a dead screen.
 */
export default async function PracticeHistoryPage({ searchParams }: HistoryPageProps) {
  const offset = readHistoryOffset((await searchParams).offset);

  return (
    <>
      <nav aria-label="Breadcrumb" className={styles.breadcrumb}>
        <ol>
          <li>
            <Link href="/practice">Practice</Link>
          </li>
          <li aria-current="page">Your practice history</li>
        </ol>
      </nav>

      <h1>Your practice history</h1>
      <p className={styles.lead}>
        Every checkpoint quiz you have taken, most recent first, with what became of each question.
        Nothing here is added up or set against anything else: one practice quiz is one practice
        quiz, and a run of them still says nothing on its own about how well you know a topic.
      </p>

      <Suspense fallback={<p role="status">Loading your practice history…</p>}>
        <HistorySection offset={offset} />
      </Suspense>

      <nav aria-label="Learner actions">
        <ul className={styles.actions}>
          <li>
            <Link href="/practice">Back to practice</Link>
          </li>
          <li>
            <Link href="/curriculum">Record where you are with a topic</Link>
          </li>
          <li>
            <Link href="/resources">Your study material</Link>
          </li>
          <li>
            <Link href="/revisions">Your reviews</Link>
          </li>
        </ul>
      </nav>
    </>
  );
}
