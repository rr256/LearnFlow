import Link from "next/link";
import { Suspense } from "react";

import styles from "@/app/page.module.css";
import { Notice } from "@/components/Notice";
import { PlanningPreferences } from "@/features/home/PlanningPreferences";
import { StudySetupOverview } from "@/features/home/StudySetupOverview";
import { WeeklyAvailability } from "@/features/home/WeeklyAvailability";
import {
  ApiError,
  listExaminationSchedules,
  listStudyGoals,
  readLearnerProfile,
} from "@/lib/api-client";
import type { LearnerProfile } from "@/types/learner";
import type { ExaminationSchedule, StudyGoal } from "@/types/study-goal";

/**
 * Rendered per request rather than prerendered.
 *
 * The profile and the goal are learner data that changes whenever setup is
 * saved, and `next build` has no API to reach.
 */
export const dynamic = "force-dynamic";

interface HomeData {
  profile: LearnerProfile | null;
  goal: StudyGoal | null;
  schedule: ExaminationSchedule | null;
}

/**
 * Everything the home screen shows, in as few round trips as the contract allows.
 *
 * The profile and the goals are independent, so they run together. The schedule
 * cannot: which cycle to read depends on the goal, and it is skipped entirely
 * for a learner aiming at a target date alone.
 */
async function readHomeData(): Promise<HomeData> {
  const [profile, goals] = await Promise.all([readLearnerProfile(), listStudyGoals()]);

  // GOAL-002 returns newest first. The active goal is the one being worked
  // toward; a paused or archived goal is history, and is shown only when it is
  // all the learner has.
  const goal = goals.find((candidate) => candidate.status === "active") ?? goals[0] ?? null;
  const examination = goal?.examination ?? null;

  if (!goal || !examination) {
    return { profile, goal, schedule: null };
  }

  // A goal response carries the examination window but not the dated periods, so
  // the registration and results dates come from EXM-001.
  const schedules = await listExaminationSchedules({
    learningProgramId: goal.learning_program.id,
  });
  const schedule = schedules.find((candidate) => candidate.id === examination.id) ?? null;

  return { profile, goal, schedule };
}

/**
 * The data-dependent half of the home screen, suspended so the heading and the
 * actions below it appear before the API answers.
 *
 * The boundary is declared here rather than as a `loading.tsx` segment file, for
 * the reason recorded in docs/development/folder-structure.md — and at this
 * route it matters most: a segment file at the application root would cover
 * every nested route, including `curriculum/programs/[programId]`, where it
 * would commit a `200` before that page could call `notFound()`.
 */
async function StudySetupSection() {
  let data: HomeData;
  try {
    data = await readHomeData();
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    // Handled here rather than left to the route error boundary, because a
    // production build replaces a server-side error message with a generic one.
    return (
      <Notice title="Your study setup could not be loaded" tone="attention">
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
      <StudySetupOverview goal={data.goal} profile={data.profile} schedule={data.schedule} />
      {/*
       * The saved week and the saved preferences both come off the goal GOAL-002
       * already returned, so showing them costs no further request.
       */}
      <WeeklyAvailability goal={data.goal} />
      <PlanningPreferences goal={data.goal} />
    </>
  );
}

/**
 * The home screen: LRN-001, GOAL-002, and EXM-001 -- the learner's saved setup,
 * including the weekly availability and the planning preferences the goal response
 * carries.
 *
 * The actions sit outside the boundary above, so an unreachable backend still
 * leaves a learner a way forward rather than a dead first screen.
 */
export default function HomePage() {
  return (
    <>
      <h1>Your study setup</h1>
      <p className={styles.lead}>
        What LearnFlow has saved for you, and what you are working toward. Planning, progress, and
        the mentor are not built yet.
      </p>
      <div className={styles.panels}>
        <Suspense fallback={<p role="status">Loading your study setup…</p>}>
          <StudySetupSection />
        </Suspense>
      </div>
      <nav aria-label="Learner actions">
        <ul className={styles.actions}>
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
