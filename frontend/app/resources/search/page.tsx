import Link from "next/link";

import styles from "@/app/resources/search/page.module.css";
import { Notice } from "@/components/Notice";
import { NotePassages } from "@/features/resources/NotePassages";
import { TopicNoteSearchForm } from "@/features/resources/TopicNoteSearchForm";
import { topicOptions, type SubjectTopicOptions } from "@/features/resources/topic-options";
import {
  ApiError,
  listStudyGoals,
  readCurriculumTree,
  searchTopicNotes,
} from "@/lib/api-client";
import type { TopicNoteSearch } from "@/types/note-search";

/**
 * Rendered per request rather than prerendered.
 *
 * A learner's notes are learner data, and `next build` has no API to reach.
 */
export const dynamic = "force-dynamic";

interface SearchPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/**
 * The topic the learner asked about, if they have asked at all.
 *
 * A value that is not a single string is read as no request rather than as an
 * error: an address a learner edited by hand should show the empty form, not a
 * failure.
 */
function readTopicId(value: string | string[] | undefined): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

/**
 * CUR-003 — the topics a learner can search within, grouped by subject.
 *
 * A failure here is deliberately **not fatal** to the page: losing the picker
 * costs the learner the form rather than the whole screen, which is the call
 * `/resources` already makes for the same read.
 */
async function pickableTopics(): Promise<SubjectTopicOptions[]> {
  try {
    const goals = await listStudyGoals();
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
 * The search itself, run **only** when the learner asked for one.
 *
 * RES-013. Nothing here runs on a bare page load: with no `topic_id` in the
 * address, no note is read at all.
 */
async function runSearch(topicId: string | null): Promise<TopicNoteSearch | ApiError | null> {
  if (topicId === null) {
    return null;
  }
  try {
    return await searchTopicNotes(topicId);
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    return error;
  }
}

/**
 * Find passages in your own notes for a topic: RES-013 with CUR-003 and GOAL-002.
 *
 * **This is retrieval, not a mentor.** LearnFlow answers nothing, summarises
 * nothing, and suggests nothing: what appears is the learner's own writing, with
 * the material and topic it came from named beside it.
 *
 * **It is local and runs only when asked.** The search is PostgreSQL's own
 * full-text search on this machine — no AI model, no embedding service, no
 * vector database, and no external request — and it happens because the learner
 * chose a topic and submitted, never because a page rendered.
 *
 * **The whole screen is a `GET` form**, so it needs no server action, holds no
 * state, and works with JavaScript switched off by construction. Submitting puts
 * the topic in the address, which also makes a result something the learner can
 * bookmark or reload without anything being written.
 *
 * **Nothing is written, ranked, scored, or counted.** No note, resource, stage,
 * plan, revision, or record that a search happened; no relevance figure exists to
 * show; and no total says how much the learner has written.
 */
export default async function TopicNoteSearchPage({ searchParams }: SearchPageProps) {
  const topicId = readTopicId((await searchParams).topic_id);
  // The two run together: neither addresses the other's result.
  const [topicGroups, result] = await Promise.all([pickableTopics(), runSearch(topicId)]);

  return (
    <>
      <h1>Find it in your notes</h1>
      <p className={styles.lead}>
        Choose a topic and see the passages from your own notes that mention it. LearnFlow does not
        answer anything here — it shows you what you wrote, and where you wrote it.
      </p>

      <TopicNoteSearchForm selectedTopicId={topicId ?? undefined} topicGroups={topicGroups} />

      {result instanceof ApiError ? (
        <Notice title="That search could not be run" tone="attention">
          <p>{result.message}</p>
          {result.isUnreachable ? (
            <p>
              Start the backend with <code>docker compose up</code>, or run it directly, and try
              again.
            </p>
          ) : null}
          {result.isConflict ? (
            <p>
              More than one learner is stored, so LearnFlow cannot tell which one is yours. It is
              single-learner until accounts exist.
            </p>
          ) : null}
        </Notice>
      ) : null}

      {result !== null && !(result instanceof ApiError) ? (
        <NotePassages result={result} />
      ) : null}

      <nav aria-label="Learner actions">
        <ul className={styles.actions}>
          <li>
            <Link href="/mentor">Ask your notes</Link>
          </li>
          <li>
            <Link href="/resources">Your study material</Link>
          </li>
          <li>
            <Link href="/curriculum">Browse the curriculum</Link>
          </li>
          <li>
            <Link href="/revisions">Your reviews</Link>
          </li>
          <li>
            <Link href="/">Your study setup</Link>
          </li>
        </ul>
      </nav>
    </>
  );
}
