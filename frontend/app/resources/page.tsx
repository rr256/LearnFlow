import Link from "next/link";
import { Suspense } from "react";

import styles from "@/app/resources/page.module.css";
import { Notice } from "@/components/Notice";
import { ResourceForm } from "@/features/resources/ResourceForm";
import { ResourceCatalogue } from "@/features/resources/ResourceCatalogue";
import { topicOptions, type SubjectTopicOptions } from "@/features/resources/topic-options";
import {
  ApiError,
  listResources,
  listStudyGoals,
  readCurriculumTree,
} from "@/lib/api-client";
import type { LearningResource } from "@/types/resource";

/**
 * Rendered per request rather than prerendered.
 *
 * A catalogue is learner data, and `next build` has no API to reach.
 */
export const dynamic = "force-dynamic";

interface CatalogueData {
  resources: LearningResource[];
  /** The curriculum's topics for the picker, empty when it could not be read. */
  topicGroups: SubjectTopicOptions[];
}

/**
 * CUR-003 — the topics a learner can link material to, grouped by subject.
 *
 * Addressed by the goal's own `curriculum_version.id`, so nothing extra is read
 * to find it. A failure here is deliberately **not fatal**: the picker is one
 * field of one form, and losing it should cost the learner that field rather
 * than the whole screen — they can still catalogue material and link it later.
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
 * RES-002, GOAL-002, and CUR-003 — the learner's material, and the topics they
 * can link it to.
 *
 * The two run together: neither addresses the other's result, so the page waits
 * once instead of twice.
 *
 * `MAX_PAGE_SIZE` is not requested explicitly — the client already defaults
 * RES-002 to it. A catalogue large enough to exceed it would need paging here,
 * and the `pagination` block is what would reveal that, exactly as ADR-017
 * recorded for the curriculum view.
 */
async function readCatalogue(): Promise<CatalogueData> {
  const [resources, topicGroups] = await Promise.all([listResources(), pickableTopics()]);
  return { resources, topicGroups };
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
async function CatalogueSection() {
  let data: CatalogueData;
  try {
    data = await readCatalogue();
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    // Handled here rather than left to the route error boundary, because a
    // production build replaces a server-side error message with a generic one.
    return (
      <Notice title="Your material could not be loaded" tone="attention">
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
      <ResourceForm topicGroups={data.topicGroups} />
      <ResourceCatalogue resources={data.resources} topicGroups={data.topicGroups} />
    </>
  );
}

/**
 * The learning-resource catalogue: RES-001, RES-002, and RES-004.
 *
 * **A record of where material is, never the material.** Nothing is uploaded,
 * downloaded, extracted, or indexed here, and no location on the learner's own
 * machine is stored — material that is not on the web is described in their own
 * words.
 *
 * **Nothing is recommended and nothing is counted.** A topic's material is what
 * the learner linked to it; LearnFlow suggests none of its own, ranks none
 * against another, and states no figure about how much anyone has.
 *
 * **Nothing is deleted.** Material a learner is not using is put aside, which is
 * reversible from the same control. Material in the catalogue can also be
 * corrected in place; material put aside cannot, so a learner puts it back
 * first.
 *
 * The navigation sits outside the boundary below, so an unreachable backend
 * still leaves a learner a way forward rather than a dead screen.
 */
export default function ResourcesPage() {
  return (
    <>
      <h1>Your study material</h1>
      <p className={styles.lead}>
        What you study from, kept against the topics it covers. Add a piece, correct one, or put
        one aside when you are not using it. Material you link to a topic appears beside that topic
        in the curriculum and beside a review of it, so you can find it when you need it.
      </p>
      <div className={styles.panels}>
        <Suspense fallback={<p role="status">Loading your material…</p>}>
          <CatalogueSection />
        </Suspense>
      </div>
      <nav aria-label="Learner actions">
        <ul className={styles.actions}>
          <li>
            <Link href="/curriculum">Browse the curriculum</Link>
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
          <li>
            <Link href="/">Your study setup</Link>
          </li>
        </ul>
      </nav>
    </>
  );
}
