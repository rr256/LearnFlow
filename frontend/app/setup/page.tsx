import type { Metadata } from "next";
import { Suspense } from "react";

import { Notice } from "@/components/Notice";
import { LearnerSetupForm } from "@/features/onboarding/LearnerSetupForm";
import { StudyGoalSummary } from "@/features/onboarding/StudyGoalSummary";
import {
  ApiError,
  listExaminationSchedules,
  listLearningPrograms,
  listStudyGoals,
  readLearnerProfile,
} from "@/lib/api-client";
import type { LearningProgram } from "@/types/curriculum";
import type { LearnerProfile } from "@/types/learner";
import type { ExaminationSchedule, StudyGoal } from "@/types/study-goal";

export const metadata: Metadata = {
  title: "Setup",
};

/**
 * Rendered per request rather than prerendered.
 *
 * The profile and the goal are learner data that changes on submission, and
 * `next build` has no API to reach.
 */
export const dynamic = "force-dynamic";

interface SetupData {
  profile: LearnerProfile | null;
  programs: LearningProgram[];
  schedules: ExaminationSchedule[];
  goal: StudyGoal | null;
}

/**
 * Everything the setup screen needs, in as few round trips as the contract allows.
 *
 * The first three reads are independent, so they run together. The schedules
 * cannot: which program's cycles to offer depends on the goal the learner
 * already has, or on the first program when they have none.
 */
async function readSetupData(): Promise<SetupData> {
  const [profile, programCollection, goals] = await Promise.all([
    readLearnerProfile(),
    listLearningPrograms(),
    listStudyGoals(),
  ]);

  const programs = programCollection.data;
  const goal = goals.find((candidate) => candidate.status === "active") ?? goals[0] ?? null;
  const learningProgramId = goal?.learning_program.id ?? programs[0]?.id;

  const schedules = learningProgramId
    ? await listExaminationSchedules({ learningProgramId })
    : [];

  return { profile, programs, schedules, goal };
}

/**
 * The setup screen's data-dependent half, suspended so the heading and the
 * explanation appear before the API answers.
 *
 * The boundary is declared here rather than as a `loading.tsx` segment file, for
 * the reason recorded in docs/development/folder-structure.md: a segment file
 * also covers nested routes, where it would turn a `404` into a `200`.
 */
async function SetupSection() {
  let data: SetupData;
  try {
    data = await readSetupData();
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    // Handled here rather than left to the route error boundary, because a
    // production build replaces a server-side error message with a generic one.
    return (
      <Notice title="Your setup could not be loaded" tone="attention">
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
      <StudyGoalSummary goal={data.goal} />
      <LearnerSetupForm
        goal={data.goal}
        profile={data.profile}
        programs={data.programs}
        schedules={data.schedules}
      />
    </>
  );
}

/** LRN-001, LRN-002, EXM-001, and GOAL-001 to GOAL-004 -- the learner's setup. */
export default function SetupPage() {
  return (
    <>
      <h1>Setup</h1>
      <p>
        Tell LearnFlow who you are, which learning program you are studying, and what you are
        working toward. Everything here can be changed later.
      </p>
      <Suspense fallback={<p role="status">Loading your setup…</p>}>
        <SetupSection />
      </Suspense>
    </>
  );
}
