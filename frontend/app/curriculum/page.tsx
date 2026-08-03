import type { Metadata } from "next";
import { Suspense } from "react";

import { Notice } from "@/components/Notice";
import { LearningProgramList } from "@/features/curriculum/LearningProgramList";
import { ApiError, listLearningPrograms } from "@/lib/api-client";
import type { LearningProgramCollectionResponse } from "@/types/curriculum";

export const metadata: Metadata = {
  title: "Curriculum",
};

/**
 * Rendered per request rather than prerendered.
 *
 * The curriculum lives in the database, so a build-time snapshot would go stale
 * the moment the seed ran again -- and `next build` would need a reachable API,
 * which the container build deliberately does not have.
 */
export const dynamic = "force-dynamic";

/**
 * The list itself, suspended so the heading and the explanation appear before
 * the API answers.
 *
 * The boundary is declared here rather than as a `loading.tsx` segment file on
 * purpose: a segment file also covers every nested route, and a boundary over
 * `programs/[programId]` would commit a `200` before that page could call
 * `notFound()`, so a mistyped program id would answer `200` instead of `404`.
 */
async function LearningProgramSection() {
  let collection: LearningProgramCollectionResponse;
  try {
    collection = await listLearningPrograms();
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    // Handled here rather than left to the route error boundary, because a
    // production build replaces a server-side error message with a generic one;
    // a learner would be told only that something went wrong.
    return (
      <Notice title="The curriculum could not be loaded" tone="attention">
        <p>{error.message}</p>
        {error.isUnreachable ? (
          <p>
            Start the backend with <code>docker compose up</code>, or run it directly, and reload
            this page.
          </p>
        ) : null}
      </Notice>
    );
  }

  return <LearningProgramList programs={collection.data} />;
}

/** CUR-001 -- the learning programs LearnFlow offers. */
export default function CurriculumPage() {
  return (
    <>
      <h1>Curriculum</h1>
      <p>
        Every learning program LearnFlow offers, with the curriculum version currently active for
        it. Select a program to read its subjects and topics.
      </p>
      <Suspense fallback={<p role="status">Loading learning programs…</p>}>
        <LearningProgramSection />
      </Suspense>
    </>
  );
}
