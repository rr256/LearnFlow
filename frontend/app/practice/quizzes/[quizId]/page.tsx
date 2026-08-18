import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import styles from "@/app/practice/quizzes/[quizId]/page.module.css";
import { Notice } from "@/components/Notice";
import { QuizForm } from "@/features/practice/QuizForm";
import { ApiError, readCheckpointQuiz } from "@/lib/api-client";
import type { CheckpointQuiz } from "@/types/practice";

export const metadata: Metadata = {
  title: "Practice quiz",
};

export const dynamic = "force-dynamic";

interface QuizPageProps {
  params: Promise<{ quizId: string }>;
}

/**
 * One checkpoint quiz, ready to answer: QZ-002.
 *
 * **The quiz sent here carries no answers.** QZ-002 has nowhere to put an
 * expected option or an explanation, so nothing on this page has to strip one,
 * and viewing the page source reveals nothing the learner has not earned. The
 * answers arrive with the result.
 *
 * The attempt is **not** started by opening this page. Reading a page must not
 * write a record, and a learner who opens a quiz and walks away should leave no
 * trace; the attempt begins when they submit, which is one form post that works
 * with no JavaScript.
 *
 * **Nothing is timed, counted, or scored here.** There is no clock and no
 * progress indicator: both measure the learner rather than describe the work.
 *
 * A quiz belonging to nobody, or to another learner, is a `404` — the rule every
 * learner-owned read follows, so a missing record and a forbidden one are
 * indistinguishable.
 */
export default async function QuizPage({ params }: QuizPageProps) {
  const { quizId } = await params;

  let quiz: CheckpointQuiz;
  try {
    quiz = await readCheckpointQuiz(quizId);
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
        <h1>Practice quiz</h1>
        <Notice title="This quiz could not be loaded" tone="attention">
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
          <li aria-current="page">{quiz.title}</li>
        </ol>
      </nav>

      <h1>{quiz.title}</h1>
      <p className={styles.lead}>
        These are the questions you wrote for{" "}
        {quiz.topics.map((topic) => topic.name).join(", ")}, in the order you wrote them.
      </p>

      <QuizForm quiz={quiz} />
    </>
  );
}
