import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import styles from "@/app/practice/attempts/[attemptId]/page.module.css";
import { Notice } from "@/components/Notice";
import { AttemptResult } from "@/features/practice/AttemptResult";
import { ApiError, readQuizAttempt } from "@/lib/api-client";
import type { QuizAttempt } from "@/types/practice";

export const metadata: Metadata = {
  title: "Practice result",
};

export const dynamic = "force-dynamic";

interface AttemptPageProps {
  params: Promise<{ attemptId: string }>;
}

/**
 * What became of one attempt: QZ-007.
 *
 * **Read-only.** There is no control here at all — nothing to re-mark, nothing
 * to re-submit, and nothing that records a learning stage. A result is a record
 * of what happened, and it is not edited afterwards; practising the topic again
 * means a new quiz, from `/practice`.
 *
 * **No score appears anywhere.** No total, no mark, no percentage, and no
 * comparison with an earlier attempt: `AttemptResult` renders the outcomes the
 * API returned and adds nothing up. See docs/domain/terminology.md and ADR-033.
 *
 * **This page claims nothing about understanding.** One checkpoint is one
 * checkpoint. Recording a learning stage stays the learner's own statement on the
 * curriculum screen, which is where the links below point.
 *
 * An attempt belonging to nobody, or to another learner, is a `404` — the rule
 * every learner-owned read follows.
 */
export default async function AttemptPage({ params }: AttemptPageProps) {
  const { attemptId } = await params;

  let attempt: QuizAttempt;
  try {
    attempt = await readQuizAttempt(attemptId);
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    if (error.isNotFound) {
      notFound();
    }
    // Handled here rather than left to the route error boundary, because a
    // production build replaces a server-side error message with a generic one.
    return (
      <>
        <h1>Practice result</h1>
        <Notice title="This result could not be loaded" tone="attention">
          <p>{error.message}</p>
          {error.isUnreachable ? (
            <p>
              Start the backend with <code>docker compose up</code>, or run it directly, and reload
              this page.
            </p>
          ) : null}
        </Notice>
        <nav aria-label="Learner actions">
          <ul className={styles.actions}>
            <li>
              <Link href="/practice">Back to practice</Link>
            </li>
          </ul>
        </nav>
      </>
    );
  }

  return (
    <>
      <nav aria-label="Breadcrumb" className={styles.breadcrumb}>
        <ol>
          <li>
            <Link href="/practice">Practice</Link>
          </li>
          <li aria-current="page">{attempt.quiz_title}</li>
        </ol>
      </nav>

      <h1>{attempt.quiz_title}</h1>
      <p className={styles.lead}>
        {attempt.status === "evaluated"
          ? "Here is what you answered, and what each question expected."
          : "This attempt has not been submitted, so its answers are not shown yet."}
      </p>

      <AttemptResult attempt={attempt} />

      <nav aria-label="Learner actions">
        <ul className={styles.actions}>
          <li>
            <Link href="/practice">Practise again</Link>
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
