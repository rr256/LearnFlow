import Link from "next/link";

import styles from "@/features/revision/RevisionList.module.css";
import { TopicResources } from "@/features/resources/TopicResources";
import { resourcesFor } from "@/features/resources/by-topic";
import { RevisionStatusControl } from "@/features/revision/RevisionStatusControl";
import type { LearningResource } from "@/types/resource";
import {
  REVISION_SETTLED_LABELS,
  REVISION_TRIGGER_LABELS,
  type Revision,
  type RevisionStatus,
  type RevisionTrigger,
} from "@/types/revision";

interface RevisionListProps {
  revisions: Revision[];
  /**
   * The learner's catalogued material, keyed by the topics it covers, or null
   * when it could not be read. Null renders the reviews without it, which costs
   * the reader the material rather than the list of what is due.
   */
  resources?: Map<string, LearningResource[]> | null;
}

/**
 * The revisions a learner has, in two groups: what is owed now, and what is
 * still to come or already answered.
 *
 * **A revision is a recommendation, not a failure notice**
 * (docs/domain/terminology.md). Nothing here says a learner is behind, late, or
 * forgetful; a topic returning is the schedule working, and the copy says so.
 *
 * Every revision shows the reason it exists, written when it was created and
 * never rewritten — so a learner reads what actually decided the date, not a
 * sentence recomposed from a stage they may have changed since.
 *
 * **Nothing is counted, ranked, or scored.** No "3 due", no streak, no
 * percentage — the line
 * docs/domain/terminology.md#plan-coverage-counts-are-not-learner-scores draws.
 *
 * **Whether a revision is due is read, not derived.** `is_due` comes from the
 * backend, where `select_due` owns the rule; a screen computing its own could
 * disagree with the record it is rendering.
 *
 * **The material beside a review is the learner's own, and nothing suggests
 * any.** It is what they linked to that topic in their catalogue, listed
 * read-only; LearnFlow holds no material of its own and recommends none, so a
 * topic with nothing linked shows nothing. That is the *resource suggestions*
 * half of FR-006's second criterion, met for the material a learner has
 * registered; practice suggestions still wait on FR-009.
 */
export function RevisionList({ revisions, resources = null }: RevisionListProps) {
  const due = revisions.filter((revision) => revision.is_due);
  const later = revisions.filter((revision) => !revision.is_due);

  return (
    <>
      <section aria-labelledby="due-now" className={styles.panel}>
        <h2 id="due-now">Ready to review</h2>
        {due.length === 0 ? (
          <NothingDue hasAny={revisions.length > 0} />
        ) : (
          <>
            <p className={styles.lead}>
              Topics you have finished, coming back so they stay familiar. Mark each one as you
              go, and change your mind whenever you like.
            </p>
            <ul className={styles.items}>
              {due.map((revision) => (
                <RevisionLine key={revision.id} resources={resources} revision={revision} />
              ))}
            </ul>
          </>
        )}
      </section>

      {later.length === 0 ? null : (
        <section aria-labelledby="later" className={styles.panel}>
          <h2 id="later">Later, and already answered</h2>
          <p className={styles.lead}>
            Reviews with a day still to come, and the ones you have already dealt with. Nothing
            here needs anything from you now.
          </p>
          <ul className={styles.items}>
            {later.map((revision) => (
              <RevisionLine key={revision.id} resources={resources} revision={revision} />
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

/** One revision, as both lists show it. */
function RevisionLine({
  revision,
  resources,
}: {
  revision: Revision;
  resources: Map<string, LearningResource[]> | null;
}) {
  const settled = REVISION_SETTLED_LABELS[revision.status as RevisionStatus];

  return (
    <li className={itemClassName(revision)}>
      <p className={styles.topic}>
        <span className={styles.trigger}>{describeTrigger(revision.trigger_type)}</span>{" "}
        {revision.topic ? revision.topic.name : "A topic that is no longer stored"}
      </p>
      <p className={styles.meta}>
        {revision.topic ? `${revision.topic.subject_name} · ` : ""}
        Due {revision.due_on}
      </p>
      {settled ? <p className={styles.settledLabel}>{settled}</p> : null}
      {revision.recommendation_reason ? (
        <p className={styles.why}>{revision.recommendation_reason}</p>
      ) : null}
      {/*
        The learner's own material for this topic, read-only: adding it and
        putting it aside live on the catalogue screen. Nothing is suggested --
        this is what they linked, and a topic with nothing linked shows nothing.
      */}
      {resources && revision.topic ? (
        <TopicResources
          resources={resourcesFor(resources, revision.topic.id)}
          topicName={revision.topic.name}
        />
      ) : null}
      <RevisionStatusControl
        revisionId={revision.id}
        status={revision.status}
        topicName={revision.topic ? revision.topic.name : "this review"}
      />
    </li>
  );
}

/**
 * The classes one revision gets, marked once the learner has answered.
 *
 * `styles` is a CSS Module, whose generated type is an index signature rather
 * than a named shape, so each class is read by key and falls back to nothing.
 * The mark never carries the meaning on its own: the label beside it says what
 * became of the review in words.
 */
function itemClassName(revision: Revision): string {
  const base = styles.item ?? "";
  const settled = REVISION_SETTLED_LABELS[revision.status as RevisionStatus];
  return settled ? `${base} ${styles[revision.status] ?? ""}`.trim() : base;
}

/**
 * What brought this topic back, in words.
 *
 * A trigger this build does not recognise is shown as the API sent it rather
 * than hidden, so a backend that grows a third still renders something true.
 */
function describeTrigger(trigger: string): string {
  return trigger in REVISION_TRIGGER_LABELS
    ? REVISION_TRIGGER_LABELS[trigger as RevisionTrigger]
    : trigger;
}

/**
 * Why nothing is ready, said plainly rather than left to be inferred.
 *
 * Two situations reach this and they mean opposite things: a learner with no
 * revisions at all has not finished work yet or has not asked, while one whose
 * reviews are all scheduled or answered is simply up to date.
 */
function NothingDue({ hasAny }: { hasAny: boolean }) {
  if (hasAny) {
    return (
      <p className={styles.empty}>
        Nothing is ready to review today. The reviews below have days still to come, or you have
        already dealt with them.
      </p>
    );
  }
  return (
    <p className={styles.empty}>
      No reviews are scheduled yet. Reviews come from work you have finished, so{" "}
      <Link href="/plan/today">mark some study completed</Link> and then schedule reviews above.
    </p>
  );
}
