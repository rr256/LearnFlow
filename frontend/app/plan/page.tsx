import Link from "next/link";
import { Suspense } from "react";

import styles from "@/app/plan/page.module.css";
import { Notice } from "@/components/Notice";
import { GeneratePlanForm } from "@/features/planner/GeneratePlanForm";
import { PlanWeek } from "@/features/planner/PlanWeek";
import { StudyRoadmap } from "@/features/planner/StudyRoadmap";
import { planOfType } from "@/features/planner/plan";
import { ApiError, listStudyGoals, listStudyPlans, readStudyPlan } from "@/lib/api-client";
import type { StudyGoal } from "@/types/study-goal";
import type { StudyPlan } from "@/types/study-plan";

/**
 * Rendered per request rather than prerendered.
 *
 * A plan is learner data that changes the moment one is generated, and
 * `next build` has no API to reach.
 */
export const dynamic = "force-dynamic";

interface PlanData {
  goal: StudyGoal | null;
  roadmap: StudyPlan | null;
  week: StudyPlan | null;
}

/**
 * The learner's current plan, in as few round trips as the contract allows.
 *
 * PLN-002 says which plans are active without their items — a page of plans each
 * carrying every item would be an unbounded payload — so the two that exist are
 * read individually with PLN-003. They are independent, so they run together.
 */
async function readPlanData(): Promise<PlanData> {
  const goals = await listStudyGoals();
  // GOAL-002 returns newest first. The active goal is the one being worked
  // toward; a paused or archived goal is history, and is shown only when it is
  // all the learner has.
  const goal = goals.find((candidate) => candidate.status === "active") ?? goals[0] ?? null;
  if (!goal) {
    return { goal: null, roadmap: null, week: null };
  }

  const active = await listStudyPlans({ studyGoalId: goal.id, status: "active" });
  const summaries = { roadmap: planOfType(active, "roadmap"), week: planOfType(active, "weekly") };
  const [roadmap, week] = await Promise.all([
    summaries.roadmap ? readStudyPlan(summaries.roadmap.id) : Promise.resolve(null),
    summaries.week ? readStudyPlan(summaries.week.id) : Promise.resolve(null),
  ]);

  return { goal, roadmap, week };
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
async function StudyPlanSection() {
  let data: PlanData;
  try {
    data = await readPlanData();
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    // Handled here rather than left to the route error boundary, because a
    // production build replaces a server-side error message with a generic one.
    return (
      <Notice title="Your plan could not be loaded" tone="attention">
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
          A plan is built toward something. <Link href="/setup">Tell LearnFlow what you are
          working toward</Link>, and when in the week you can study, and a plan can be generated
          from it.
        </p>
      </Notice>
    );
  }

  return (
    <>
      <GeneratePlanForm hasPlan={data.roadmap !== null} studyGoalId={data.goal.id} />
      {data.roadmap === null ? (
        <Notice title="No plan yet">
          <p>
            Nothing has been generated for this goal. Creating one takes your curriculum, the date
            you are working toward, the study time you saved, and how you said you want to study,
            and turns them into an order to work in.
          </p>
        </Notice>
      ) : (
        <>
          <PlanWeek plan={data.week} />
          <StudyRoadmap plan={data.roadmap} />
        </>
      )}
    </>
  );
}

/**
 * The plan screen: PLN-001, PLN-002, and PLN-003.
 *
 * The plan is deterministic and explains itself. Nothing here decides what is in
 * it — this screen asks for one, then renders what came back, in the order it
 * came back in.
 *
 * The navigation sits outside the boundary above, so an unreachable backend still
 * leaves a learner a way forward rather than a dead screen.
 */
export default function PlanPage() {
  return (
    <>
      <h1>Your study plan</h1>
      <p className={styles.lead}>
        Built from your curriculum, the date you are working toward, the study time you saved, and
        how you said you want to study. Mark each item completed as you go, and change your mind
        whenever you like — nothing is re-planned around it. Monthly and daily views, and re-planning
        after a missed week, are not built yet.
      </p>
      <div className={styles.panels}>
        <Suspense fallback={<p role="status">Loading your study plan…</p>}>
          <StudyPlanSection />
        </Suspense>
      </div>
      <nav aria-label="Learner actions">
        <ul className={styles.actions}>
          <li>
            <Link href="/">Your study setup</Link>
          </li>
          <li>
            <Link href="/setup">Edit your setup</Link>
          </li>
          <li>
            <Link href="/curriculum">Browse the curriculum</Link>
          </li>
        </ul>
      </nav>
    </>
  );
}
