import Link from "next/link";
import { Suspense } from "react";

import styles from "@/app/plan/month/page.module.css";
import { Notice } from "@/components/Notice";
import { MonthlyPlanView } from "@/features/planner/MonthlyPlanView";
import { learnerMonth } from "@/features/planner/month";
import { planOfType } from "@/features/planner/plan";
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
 * For the reason `/plan/today` needs it: this page is *about* a calendar period,
 * so a cached copy would be wrong from the first month boundary after it was
 * built. A plan is learner data besides, and `next build` has no API to reach.
 */
export const dynamic = "force-dynamic";

interface MonthlyPlanData {
  goal: StudyGoal | null;
  roadmap: StudyPlan | null;
  week: StudyPlan | null;
  /** The learner's own calendar month, resolved from their stored timezone. */
  month: string;
}

/**
 * The month's plans, in as few round trips as the contract allows.
 *
 * The profile and the goals are independent, so they run together; the plans
 * cannot, because which goal's plans to read depends on the goal. Both active
 * plans are opened — the week holds the month's dated work, and the roadmap holds
 * the order the plan works through after it.
 *
 * **The month comes from the learner's stored timezone, not this server's.** A
 * container running in UTC must not show a learner in `Pacific/Kiritimati` last
 * month on the first of theirs, which is why `learners.timezone` is stored and why
 * the backend resolves its own dates the same way.
 */
async function readMonthlyPlanData(): Promise<MonthlyPlanData> {
  const [profile, goals] = await Promise.all([readLearnerProfile(), listStudyGoals()]);

  // Only reachable before setup has created a learner, in which case there is no
  // goal and no plan either. UTC is the same fallback the backend applies to a
  // zone it cannot read: a month a day out at its boundary is recoverable, a
  // blank screen is not.
  const month = learnerMonth(new Date(), profile?.timezone ?? "UTC");

  // GOAL-002 returns newest first. The active goal is the one being worked
  // toward; a paused or archived goal is history, and is shown only when it is
  // all the learner has.
  const goal = goals.find((candidate) => candidate.status === "active") ?? goals[0] ?? null;
  if (!goal) {
    return { goal: null, roadmap: null, week: null, month };
  }

  const active = await listStudyPlans({ studyGoalId: goal.id, status: "active" });
  const summaries = { roadmap: planOfType(active, "roadmap"), week: planOfType(active, "weekly") };
  const [roadmap, week] = await Promise.all([
    summaries.roadmap ? readStudyPlan(summaries.roadmap.id) : Promise.resolve(null),
    summaries.week ? readStudyPlan(summaries.week.id) : Promise.resolve(null),
  ]);

  return { goal, roadmap, week, month };
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
async function MonthlyPlanSection() {
  let data: MonthlyPlanData;
  try {
    data = await readMonthlyPlanData();
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    // Handled here rather than left to the route error boundary, because a
    // production build replaces a server-side error message with a generic one.
    return (
      <Notice title="This month could not be loaded" tone="attention">
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
          A month&apos;s work comes from a plan, and a plan is built toward something.{" "}
          <Link href="/setup">Tell LearnFlow what you are working toward</Link>, and when in the
          week you can study.
        </p>
      </Notice>
    );
  }

  if (!data.roadmap && !data.week) {
    return (
      <Notice title="No plan yet">
        <p>
          Nothing has been generated for this goal, so this month has no work in it.{" "}
          <Link href="/plan">Generate a plan</Link> to get an order to work through and dated work
          for the week ahead.
        </p>
      </Notice>
    );
  }

  return <MonthlyPlanView month={data.month} roadmap={data.roadmap} week={data.week} />;
}

/**
 * The monthly study view: the month's dated work, and the roadmap that follows it.
 *
 * PLN-002 and PLN-003 for the plans, and LRN-001 for the learner's timezone. **It
 * writes nothing at all** — marking work stays on `/plan/today`, and generating
 * and adapting stay on `/plan`, where the learner asks for them.
 *
 * It is not a `monthly` plan: that plan type is constrained and unwritten, and
 * this screen reads the `roadmap` and `weekly` plans the backend already
 * generated.
 *
 * The navigation sits outside the boundary below, so an unreachable backend still
 * leaves a learner a way forward rather than a dead screen.
 */
export default function MonthlyPlanPage() {
  return (
    <>
      <h1>Your month</h1>
      <p className={styles.lead}>
        Where this month sits in your study plan: the days it already has work on, and the topics
        your roadmap works through next. Nothing here changes your plan — marking work stays on
        today&apos;s view, and rebuilding stays on your study plan, where you ask for it.
      </p>
      <div className={styles.panels}>
        <Suspense fallback={<p role="status">Loading your month…</p>}>
          <MonthlyPlanSection />
        </Suspense>
      </div>
      <nav aria-label="Learner actions">
        <ul className={styles.actions}>
          <li>
            <Link href="/progress">Where your study stands</Link>
          </li>
          <li>
            <Link href="/plan/today">What to study today</Link>
          </li>
          <li>
            <Link href="/plan">Your study plan</Link>
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
