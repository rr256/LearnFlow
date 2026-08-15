import Link from "next/link";
import { Suspense } from "react";

import styles from "@/app/progress/page.module.css";
import { Notice } from "@/components/Notice";
import { planOfType } from "@/features/planner/plan";
import { learnerToday } from "@/features/planner/today";
import { StudyProgressOverview } from "@/features/progress/StudyProgressOverview";
import type { RecordedStages } from "@/features/progress/subject-stages";
import {
  ApiError,
  listRevisions,
  listStudyGoals,
  listStudyPlans,
  listTopicProgress,
  readCurriculumTree,
  readLearnerProfile,
  readPlanFeasibility,
  readStudyPlan,
} from "@/lib/api-client";
import type { Revision } from "@/types/revision";
import type { StudyGoal } from "@/types/study-goal";
import type { PlanFeasibility, StudyPlan } from "@/types/study-plan";

/**
 * Rendered per request rather than prerendered.
 *
 * The overview is about the learner's current situation on their current date, so
 * a cached copy would be wrong from the first midnight after it was built — the
 * reason `/plan/today` and `/plan/month` are dynamic too. Everything it reads is
 * learner data besides, and `next build` has no API to reach.
 */
export const dynamic = "force-dynamic";

interface ProgressData {
  goal: StudyGoal | null;
  roadmap: StudyPlan | null;
  week: StudyPlan | null;
  /** Whether the saved week reaches the horizon, or null when unavailable. */
  feasibility: PlanFeasibility | null;
  revisions: Revision[];
  /** The learner's own calendar date, resolved from their stored timezone. */
  today: string;
  /** The recorded stages and the curriculum placing them, or null when unread. */
  stages: RecordedStages | null;
}

/**
 * PRG-002 and CUR-003 — the stages this learner recorded, and the subjects that
 * place and order them.
 *
 * A failure here is deliberately **not fatal to the page**, which is the call the
 * curriculum view already makes about this pair: the other five panels state
 * facts of their own, and one unreadable read should cost the reader that panel
 * rather than the screen. Returning null is what the panel renders as "could not
 * be read", which it says apart from "you have recorded nothing".
 *
 * The two calls run together: neither addresses the other's result.
 *
 * `MAX_PAGE_SIZE` is not requested explicitly — the client already defaults
 * PRG-002 to it, which covers the curated GATE CSE curriculum in one page. A
 * curriculum large enough to exceed it would need paging here, and the
 * `pagination` block is what would reveal that, exactly as ADR-017 recorded for
 * the curriculum view.
 */
async function recordedStages(curriculumVersionId: string): Promise<RecordedStages | null> {
  try {
    const [records, tree] = await Promise.all([
      listTopicProgress({ curriculumVersionId }),
      readCurriculumTree(curriculumVersionId),
    ]);
    return { records, subjects: tree.subjects };
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    return null;
  }
}

/**
 * Everything the overview states, in as few round trips as the contracts allow.
 *
 * Eight existing reads and **no new endpoint**: LRN-001, GOAL-002, PLN-002,
 * PLN-003, PLN-006, REV-001, PRG-002, and CUR-003. PRG-001 — the catalogued
 * `GET /api/v1/progress/overview` — stays unimplemented: the priority focus panel
 * is drawn from facts these eight already carry, and the quiz, test, and mistake
 * evidence PRG-001's purpose also promises is still stored nowhere.
 *
 * The profile and the goals are independent, so they run together; the plans
 * cannot, because which goal's plans to read depends on the goal. PLN-002 lists
 * the active plans without their items, so the two that exist are opened with
 * PLN-003, and the feasibility reading, the revisions, and the recorded stages
 * join them — all are reads, so they cost a round trip and change nothing.
 *
 * The stages are addressed by the goal's own `curriculum_version.id`, so nothing
 * extra is read to find it, and PRG-002 is filtered to the version the learner is
 * working through rather than to every version they have ever recorded against.
 *
 * **The date comes from the learner's stored timezone, not this server's**, by
 * the same `learnerToday` the daily and monthly views use, with the same UTC
 * fallback the backend applies.
 */
async function readProgressData(): Promise<ProgressData> {
  const [profile, goals] = await Promise.all([readLearnerProfile(), listStudyGoals()]);

  // Only reachable before setup has created a learner, in which case there is no
  // goal and no plan either. UTC is the same fallback the backend applies to a
  // zone it cannot read: a date a day out is recoverable, a blank screen is not.
  const today = learnerToday(new Date(), profile?.timezone ?? "UTC");

  // GOAL-002 returns newest first. The active goal is the one being worked
  // toward; a paused or archived goal is history, and is shown only when it is
  // all the learner has.
  const goal = goals.find((candidate) => candidate.status === "active") ?? goals[0] ?? null;
  if (!goal) {
    return {
      goal: null,
      roadmap: null,
      week: null,
      feasibility: null,
      revisions: [],
      today,
      stages: null,
    };
  }

  const active = await listStudyPlans({ studyGoalId: goal.id, status: "active" });
  const summaries = { roadmap: planOfType(active, "roadmap"), week: planOfType(active, "weekly") };
  const [roadmap, week, feasibility, revisions, stages] = await Promise.all([
    summaries.roadmap ? readStudyPlan(summaries.roadmap.id) : Promise.resolve(null),
    summaries.week ? readStudyPlan(summaries.week.id) : Promise.resolve(null),
    readPlanFeasibility(goal.id),
    listRevisions(),
    recordedStages(goal.curriculum_version.id),
  ]);

  return { goal, roadmap, week, feasibility, revisions, today, stages };
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
async function StudyProgressSection() {
  let data: ProgressData;
  try {
    data = await readProgressData();
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    // Handled here rather than left to the route error boundary, because a
    // production build replaces a server-side error message with a generic one.
    return (
      <Notice title="Your progress could not be loaded" tone="attention">
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

  if (!data.goal) {
    return (
      <Notice title="Set a study goal first">
        <p>
          There is nothing to summarise until you have something to work toward.{" "}
          <Link href="/setup">Tell LearnFlow what you are aiming at</Link>, and when in the week you
          can study.
        </p>
      </Notice>
    );
  }

  return (
    <StudyProgressOverview
      // Where a stage is recorded: the program page carries the control beside
      // each trackable topic, so the panel links there rather than to the
      // program list a learner would then have to choose from.
      curriculumHref={`/curriculum/programs/${data.goal.learning_program.id}`}
      feasibility={data.feasibility}
      revisions={data.revisions}
      roadmap={data.roadmap}
      stages={data.stages}
      today={data.today}
      week={data.week}
    />
  );
}

/**
 * The progress overview: where the learner's study stands, from what is stored.
 *
 * This is the screen [FR-011](docs/requirements/functional.md) describes, built
 * as a **reading** of eight existing contracts rather than as PRG-001. It shows
 * what could use the learner's attention and why, what the plan covers, what
 * today holds, whether the saved week reaches the date, what the learner has
 * marked, the learning stage they recorded for each topic under its subject, and
 * which topics are ready to review.
 *
 * **It writes nothing at all** — no status control, no generate control, no adapt
 * control, no scheduling control — which is the read-only shape ADR-026 fixed for
 * the monthly study view. Every panel names where its action lives and links to
 * it, so the one place a thing can be changed stays the one place it is done.
 *
 * **Nothing is counted, ranked, or scored.** The figures on screen are the ones
 * the API reported.
 *
 * The navigation sits outside the boundary below, so an unreachable backend still
 * leaves a learner a way forward rather than a dead screen.
 */
export default function ProgressPage() {
  return (
    <>
      <h1>Where your study stands</h1>
      <p className={styles.lead}>
        Everything LearnFlow has recorded about where you are, in one place: what could use your
        attention and why, what your plan covers, what today holds, whether the study time you saved
        reaches the date you are working toward, what you have marked, the learning stage you
        recorded for each topic, and which topics are ready to come back. Nothing here changes
        anything — each panel links to the screen where you act on it.
      </p>
      <div className={styles.panels}>
        <Suspense fallback={<p role="status">Loading where your study stands…</p>}>
          <StudyProgressSection />
        </Suspense>
      </div>
      <nav aria-label="Learner actions">
        <ul className={styles.actions}>
          <li>
            <Link href="/plan/today">What to study today</Link>
          </li>
          <li>
            <Link href="/plan">Your study plan</Link>
          </li>
          <li>
            <Link href="/plan/month">Your month</Link>
          </li>
          <li>
            <Link href="/revisions">Your reviews</Link>
          </li>
          <li>
            <Link href="/">Your study setup</Link>
          </li>
          <li>
            <Link href="/curriculum">Browse the curriculum</Link>
          </li>
        </ul>
      </nav>
    </>
  );
}
