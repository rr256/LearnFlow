import Link from "next/link";
import { Suspense } from "react";

import styles from "@/app/plan/today/page.module.css";
import { Notice } from "@/components/Notice";
import { DailyStudyView } from "@/features/planner/DailyStudyView";
import { planOfType } from "@/features/planner/plan";
import { learnerToday } from "@/features/planner/today";
import {
  ApiError,
  listStudyGoals,
  listStudyPlans,
  readLearnerProfile,
  readStudyPlan,
} from "@/lib/api-client";
import type { StudyGoal } from "@/types/study-goal";
import type { StudyPlan } from "@/types/study-plan";

/**
 * Rendered per request rather than prerendered.
 *
 * More strongly than the other routes: this page is *about* the current date, so
 * a cached copy would be wrong from the first midnight after it was built. A
 * plan is learner data besides, and `next build` has no API to reach.
 */
export const dynamic = "force-dynamic";

interface DailyPlanData {
  goal: StudyGoal | null;
  week: StudyPlan | null;
  /** The learner's own calendar date, resolved from their stored timezone. */
  today: string;
}

/**
 * Today's work, in as few round trips as the contract allows.
 *
 * The profile and the goals are independent, so they run together; the plans
 * cannot, because which goal's plans to read depends on the goal. Only the
 * `weekly` plan is opened — the roadmap dates nothing, so it holds no work that
 * could belong to a day.
 *
 * **The date comes from the learner's stored timezone, not this server's.** A
 * container running in UTC must not show a learner in `Asia/Kolkata` tomorrow's
 * work at half past eleven at night, which is why `learners.timezone` is stored
 * and why the backend resolves its own dates the same way.
 */
async function readDailyPlanData(): Promise<DailyPlanData> {
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
    return { goal: null, week: null, today };
  }

  const active = await listStudyPlans({ studyGoalId: goal.id, status: "active" });
  const summary = planOfType(active, "weekly");
  const week = summary ? await readStudyPlan(summary.id) : null;

  return { goal, week, today };
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
async function DailyStudySection() {
  let data: DailyPlanData;
  try {
    data = await readDailyPlanData();
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    // Handled here rather than left to the route error boundary, because a
    // production build replaces a server-side error message with a generic one.
    return (
      <Notice title="Today's work could not be loaded" tone="attention">
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
          A day&apos;s work comes from a plan, and a plan is built toward something.{" "}
          <Link href="/setup">Tell LearnFlow what you are working toward</Link>, and when in the
          week you can study.
        </p>
      </Notice>
    );
  }

  if (!data.week) {
    return (
      <Notice title="No dated plan yet">
        <p>
          This goal has no plan for a week, so nothing is placed on a day. A week is generated
          when you have saved study time it can use — <Link href="/plan">generate or update your
          plan</Link> to get dated work.
        </p>
      </Notice>
    );
  }

  return <DailyStudyView plan={data.week} today={data.today} />;
}

/**
 * The daily study view: today's work, read off the active weekly plan.
 *
 * PLN-002 and PLN-003 for the plan, LRN-001 for the learner's timezone, and
 * PLN-004 for the completion control. **It writes no plan and asks for none** —
 * generating and adapting stay on `/plan`, where the learner asks for them.
 *
 * It is not a `daily` plan: that plan type is constrained and unwritten, and this
 * screen selects from the `weekly` plan the backend already generated.
 *
 * The navigation sits outside the boundary below, so an unreachable backend still
 * leaves a learner a way forward rather than a dead screen.
 */
export default function DailyPlanPage() {
  return (
    <>
      <h1>What to study today</h1>
      <p className={styles.lead}>
        Today&apos;s work from your study plan, with the reason the plan gives for each item. Mark
        each one completed as you go, and change your mind whenever you like. Nothing here rebuilds
        your plan — that stays on your study plan, where you ask for it.
      </p>
      <div className={styles.panels}>
        <Suspense fallback={<p role="status">Loading today&apos;s work…</p>}>
          <DailyStudySection />
        </Suspense>
      </div>
      <nav aria-label="Learner actions">
        <ul className={styles.actions}>
          <li>
            <Link href="/progress">Where your study stands</Link>
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
