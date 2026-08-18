import Link from "next/link";
import { Suspense } from "react";

import styles from "@/app/practice/page.module.css";
import { Notice } from "@/components/Notice";
import { AttemptHistory } from "@/features/practice/AttemptHistory";
import { QuestionBank } from "@/features/practice/QuestionBank";
import { QuestionForm } from "@/features/practice/QuestionForm";
import { StartQuizForm } from "@/features/practice/StartQuizForm";
import { HISTORY_PAGE_SIZE, HISTORY_REQUEST_LIMIT } from "@/features/practice/history";
import { topicOptions, type SubjectTopicOptions } from "@/features/resources/topic-options";
import {
  ApiError,
  listPracticeQuestions,
  listQuizAttempts,
  listStudyGoals,
  readCurriculumTree,
} from "@/lib/api-client";
import type { PracticeQuestion, QuizAttempt } from "@/types/practice";

/**
 * Rendered per request rather than prerendered.
 *
 * Practice questions and attempts are learner data, and `next build` has no API
 * to reach.
 */
export const dynamic = "force-dynamic";

interface PracticeData {
  questions: PracticeQuestion[];
  /** The most recent attempts. The whole history is at `/practice/history`. */
  attempts: QuizAttempt[];
  /**
   * Whether the learner has taken quizzes older than those.
   *
   * Read from whether QZ-006 returned the one extra record asked for, never from
   * `pagination.total`: a figure for how many quizzes a learner has taken is
   * forbidden by name in docs/domain/terminology.md, so none is held.
   */
  hasMoreAttempts: boolean;
  /** The curriculum's topics for the pickers, empty when it could not be read. */
  topicGroups: SubjectTopicOptions[];
}

/**
 * CUR-003 — the topics a learner can write questions against and practise.
 *
 * Addressed by the goal's own `curriculum_version.id`, so nothing extra is read
 * to find it. A failure here is deliberately **not fatal**: the picker is one
 * field of two forms, and losing it should cost the learner those fields rather
 * than the whole screen — the questions they have already written still read.
 *
 * The flattener is the one the resource catalogue uses. It is the same
 * presentation problem — a curriculum tree into one level of `<optgroup>` — and
 * a second copy would be a second thing to keep in step with CUR-003.
 */
async function pickableTopics(): Promise<SubjectTopicOptions[]> {
  try {
    const goals = await listStudyGoals();
    // GOAL-002 returns newest first. The active goal is the one being worked
    // toward; a paused or archived goal is history, and is used only when it is
    // all the learner has.
    const goal = goals.find((candidate) => candidate.status === "active") ?? goals[0] ?? null;
    if (!goal) {
      return [];
    }
    return topicOptions((await readCurriculumTree(goal.curriculum_version.id)).subjects);
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    return [];
  }
}

/**
 * QZ-009, QZ-006, GOAL-002, and CUR-003 — what the learner has written, what
 * they have taken, and the topics they can practise.
 *
 * The three run together: none addresses another's result, so the page waits
 * once instead of three times.
 *
 * One attempt more than the panel shows is asked for, so the panel can say that
 * there are earlier ones without being told — or telling anyone — how many.
 */
async function readPractice(): Promise<PracticeData> {
  const [questions, attempts, topicGroups] = await Promise.all([
    listPracticeQuestions(),
    listQuizAttempts({ limit: HISTORY_REQUEST_LIMIT }),
    pickableTopics(),
  ]);
  return {
    questions,
    attempts: attempts.slice(0, HISTORY_PAGE_SIZE),
    hasMoreAttempts: attempts.length > HISTORY_PAGE_SIZE,
    topicGroups,
  };
}

/**
 * The data-dependent half of the screen, suspended so the heading appears before
 * the API answers.
 *
 * The boundary is declared here rather than as a `loading.tsx` segment file, for
 * the reason recorded in docs/development/folder-structure.md: a segment file
 * also covers every nested route, and a boundary above a lookup that can call
 * `notFound()` turns a `404` into a `200`.
 */
async function PracticeSection() {
  let data: PracticeData;
  try {
    data = await readPractice();
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    // Handled here rather than left to the route error boundary, because a
    // production build replaces a server-side error message with a generic one.
    return (
      <Notice title="Your practice could not be loaded" tone="attention">
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

  return (
    <>
      <StartQuizForm topicGroups={data.topicGroups} />
      <QuestionForm topicGroups={data.topicGroups} />
      <QuestionBank questions={data.questions} topicGroups={data.topicGroups} />
      <AttemptHistory attempts={data.attempts} hasMore={data.hasMoreAttempts} />
    </>
  );
}

/**
 * The checkpoint-practice screen: QZ-001, QZ-006, QZ-008, QZ-009, and QZ-010.
 *
 * **Every question is the learner's own.** LearnFlow writes none, generates
 * none, and ships none: there is no AI provider behind this screen and no
 * previous-year paper bundled with the product. A quiz is assembled from what
 * the learner wrote, deterministically — the same topics give the same questions
 * in the same order.
 *
 * **Nothing is scored, counted, ranked, or recommended.** No quiz suggests
 * itself, no question is marked easier than another, and no figure appears
 * anywhere on this screen or on a result. A checkpoint says what happened to
 * each question, and nothing more.
 *
 * **Nothing is deleted.** A question the learner is finished with is set aside,
 * reversibly, and quizzes already assembled go on asking it so their results
 * stay true.
 *
 * **Nothing here claims a topic is understood.** Recording a learning stage stays
 * on the curriculum screen, which is where this links.
 *
 * The history panel shows the **most recent** quizzes the learner has taken; the
 * whole history, a page at a time and with what became of each question, is
 * `/practice/history`, which that panel links to. Nothing is out of reach from
 * here, and nothing says how many there are.
 *
 * The navigation sits outside the boundary below, so an unreachable backend
 * still leaves a learner a way forward rather than a dead screen.
 */
export default function PracticePage() {
  return (
    <>
      <h1>Practice</h1>
      <p className={styles.lead}>
        Write the questions you want to be asked, then ask for a quiz on the topics they cover.
        LearnFlow asks exactly what you wrote, marks each answer against the answer you gave it,
        and shows you what happened question by question. It keeps no score, and one quiz says
        nothing on its own about how well you know a topic.
      </p>
      <div className={styles.panels}>
        <Suspense fallback={<p role="status">Loading your practice…</p>}>
          <PracticeSection />
        </Suspense>
      </div>
      <nav aria-label="Learner actions">
        <ul className={styles.actions}>
          <li>
            <Link href="/curriculum">Browse the curriculum</Link>
          </li>
          <li>
            <Link href="/resources">Your study material</Link>
          </li>
          <li>
            <Link href="/revisions">Your reviews</Link>
          </li>
          <li>
            <Link href="/progress">Where your study stands</Link>
          </li>
          <li>
            <Link href="/plan/today">What to study today</Link>
          </li>
        </ul>
      </nav>
    </>
  );
}
