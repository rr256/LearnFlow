import Link from "next/link";

import styles from "@/app/mentor/page.module.css";
import { StudyQuestionForm } from "@/features/mentor/StudyQuestionForm";
import { topicOptions, type SubjectTopicOptions } from "@/features/resources/topic-options";
import { ApiError, listStudyGoals, readCurriculumTree } from "@/lib/api-client";

/**
 * Rendered per request rather than prerendered.
 *
 * The curriculum a learner may ask about depends on their goal, and `next build`
 * has no API to reach.
 */
export const dynamic = "force-dynamic";

/**
 * CUR-003 — the topics a learner can ask about, grouped by subject.
 *
 * A failure here is deliberately **not fatal** to the page: losing the picker
 * costs the learner the form rather than the whole screen, which is the call
 * `/resources` and `/resources/search` already make for the same read.
 */
async function askableTopics(): Promise<SubjectTopicOptions[]> {
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
 * **Ask your notes** — MNT-001, with CUR-003 and GOAL-002.
 *
 * *Ask your notes* is the canonical learner-facing name for this capability and
 * this screen (docs/domain/terminology.md). The **route** keeps `/mentor`, and
 * the endpoint family keeps `MNT-`, because both name the *service*: changing a
 * URL is a separate compatibility decision. Say *the mentor endpoint* for
 * `POST /api/v1/mentor/questions`, and *Ask your notes* for what a learner does
 * here — the word *mentor* is reserved for a broader capability, involving
 * recommendations and planning, which is not built.
 *
 * **It answers only from the learner's own notes.** LearnFlow retrieves passages
 * from their material first, and the AI model is asked **only** when something
 * was found. With nothing found, no model is asked at all and the screen says
 * so — because answering there would mean answering from whatever the model
 * happens to know, which is exactly what a grounded answer exists to avoid.
 *
 * **Nothing runs on a page load.** Rendering this screen reads the curriculum
 * and nothing else: no note is read, no passage retrieved, and no model asked
 * until the learner submits a question.
 *
 * **The model runs on this computer** (ADR-004), so a question and the passages
 * supporting it never leave the machine. Nothing else about the learner is sent:
 * no identifier, no note or resource title, no whole note, and nothing from
 * their plan, progress, revisions, or practice.
 *
 * **Nothing is stored.** No question, no answer, and no record that either
 * happened — so there is no history here, and nothing to delete. Asking the same
 * thing twice is simply asking twice.
 *
 * **Nothing is counted, ranked, or scored**, and nothing else moves: no learning
 * stage, plan, plan item, revision, or quiz.
 */
export default async function MentorPage() {
  const topicGroups = await askableTopics();

  return (
    <>
      <h1>Ask your notes</h1>
      <p className={styles.lead}>
        Choose a topic, ask a question, and LearnFlow answers from the notes you have written on
        it — showing you the passages it used. If your notes do not cover the question, it says so
        rather than answering from somewhere else.
      </p>

      <StudyQuestionForm topicGroups={topicGroups} />

      <nav aria-label="Learner actions">
        <ul className={styles.actions}>
          <li>
            <Link href="/resources/search">Find passages in your notes</Link>
          </li>
          <li>
            <Link href="/resources">Your study material</Link>
          </li>
          <li>
            <Link href="/curriculum">Browse the curriculum</Link>
          </li>
          <li>
            <Link href="/">Your study setup</Link>
          </li>
        </ul>
      </nav>
    </>
  );
}
