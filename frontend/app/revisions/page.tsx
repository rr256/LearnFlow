import Link from "next/link";
import { Suspense } from "react";

import styles from "@/app/revisions/page.module.css";
import { Notice } from "@/components/Notice";
import { RevisionList } from "@/features/revision/RevisionList";
import { ScheduleRevisionsForm } from "@/features/revision/ScheduleRevisionsForm";
import { ApiError, listRevisions } from "@/lib/api-client";
import type { Revision } from "@/types/revision";

/**
 * Rendered per request rather than prerendered.
 *
 * Whether a review is due depends on the current date, so a cached copy would be
 * wrong from the first midnight after it was built. A revision is learner data
 * besides, and `next build` has no API to reach.
 */
export const dynamic = "force-dynamic";

/**
 * The learner's revisions, earliest due date first.
 *
 * One read. The order and the `is_due` flag both come from the backend, so this
 * neither sorts nor re-decides what it receives — what counts as due is a domain
 * rule, and a screen computing its own could disagree with the record.
 */
async function readRevisions(): Promise<Revision[]> {
  return listRevisions();
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
async function RevisionSection() {
  let revisions: Revision[];
  try {
    revisions = await readRevisions();
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    // Handled here rather than left to the route error boundary, because a
    // production build replaces a server-side error message with a generic one.
    return (
      <Notice title="Your reviews could not be loaded" tone="attention">
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

  return <RevisionList revisions={revisions} />;
}

/**
 * The revision screen: REV-001, REV-003, and REV-004.
 *
 * A topic comes back after work the learner finished, on a date the learning
 * stage they recorded decides. **Nothing here writes a learning stage** — a
 * completed review says the review happened, not that the topic is now
 * understood (rule 4 of the domain model).
 *
 * **Nothing schedules on its own.** The learner presses the control, exactly as
 * they press generate and update on their study plan. Nothing about their plan
 * moves either: reviews live beside a plan rather than inside one, and rebuilding
 * a plan leaves them alone.
 *
 * The navigation sits outside the boundary below, so an unreachable backend
 * still leaves a learner a way forward rather than a dead screen.
 */
export default function RevisionsPage() {
  return (
    <>
      <h1>Your reviews</h1>
      <p className={styles.lead}>
        Topics you have finished, coming back so they stay familiar. Reviews are separate from
        your study plan — rebuilding your plan leaves them exactly as they are, and marking a
        review says the review happened, not that the topic is finished with.
      </p>
      <div className={styles.panels}>
        <ScheduleRevisionsForm />
        <Suspense fallback={<p role="status">Loading your reviews…</p>}>
          <RevisionSection />
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
