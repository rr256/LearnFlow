import Link from "next/link";

import styles from "@/features/resources/ResourceCatalogue.module.css";
import { ResourceForm } from "@/features/resources/ResourceForm";
import { ResourceStatusControl } from "@/features/resources/ResourceStatusControl";
import { isInCatalogue } from "@/features/resources/by-topic";
import type { SubjectTopicOptions } from "@/features/resources/topic-options";
import { resourceTypeLabel, type LearningResource } from "@/types/resource";

interface ResourceCatalogueProps {
  resources: LearningResource[];
  /** The curriculum's topics, for the edit form's picker. */
  topicGroups: SubjectTopicOptions[];
}

/**
 * Everything a learner has catalogued, in two groups: what they are using, and
 * what they have put aside.
 *
 * **Nothing is counted, ranked, or scored.** No "12 resources", no most-used
 * material, no suggestion that one piece is better than another — the line
 * docs/domain/terminology.md#plan-coverage-counts-are-not-learner-scores draws,
 * applied to a catalogue. Material is listed in the order the API returned it,
 * newest first, which is the backend's order rather than a judgement made here.
 *
 * **Nothing is deleted.** Putting material aside is reversible, and this screen
 * is where both directions live.
 *
 * **Material in the catalogue can be corrected; material put aside cannot.**
 * Editing something the learner has set down would be a change to a record they
 * have said they are not using, so the way to correct it is to put it back
 * first — one state at a time, each reversible.
 */
export function ResourceCatalogue({ resources, topicGroups }: ResourceCatalogueProps) {
  const inCatalogue = resources.filter(isInCatalogue);
  const putAside = resources.filter((resource) => !isInCatalogue(resource));

  return (
    <>
      <section aria-labelledby="your-material" className={styles.panel}>
        <h2 id="your-material">Your material</h2>
        {inCatalogue.length === 0 ? (
          <NothingYet hasAny={resources.length > 0} />
        ) : (
          <>
            <p className={styles.lead}>
              What you study from, and the topics each piece covers. Material linked to a topic
              shows up beside that topic in the curriculum and beside a review of it.
            </p>
            <ul className={styles.items}>
              {inCatalogue.map((resource) => (
                <ResourceLine key={resource.id} resource={resource} topicGroups={topicGroups} />
              ))}
            </ul>
          </>
        )}
      </section>

      {putAside.length === 0 ? null : (
        <section aria-labelledby="put-aside" className={styles.panel}>
          <h2 id="put-aside">Put aside</h2>
          <p className={styles.lead}>
            Material you are not using at the moment. It is still stored, it is left out of the
            curriculum and review screens, and you can put any of it back — put a piece back to
            change its details.
          </p>
          <ul className={styles.items}>
            {putAside.map((resource) => (
              <ResourceLine key={resource.id} resource={resource} topicGroups={topicGroups} />
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

/** One piece of material, as both lists show it. */
function ResourceLine({
  resource,
  topicGroups,
}: {
  resource: LearningResource;
  topicGroups: SubjectTopicOptions[];
}) {
  return (
    <li className={styles.item}>
      <p className={styles.title}>
        <span className={styles.kind}>{resourceTypeLabel(resource.resource_type)}</span>{" "}
        {resource.title}
      </p>
      {resource.source_label ? <p className={styles.where}>{resource.source_label}</p> : null}
      {resource.external_reference ? (
        <p className={styles.link}>
          {/*
            Opened in a new tab so a learner following a link does not lose the
            catalogue behind it. `rel` is set because `target="_blank"` otherwise
            hands the opened page a handle on this one.
          */}
          <a href={resource.external_reference} rel="noreferrer noopener" target="_blank">
            {resource.external_reference}
          </a>
        </p>
      ) : null}
      {resource.topics.length === 0 ? (
        <p className={styles.topics}>
          No topics chosen yet, so this does not appear beside a topic.
        </p>
      ) : (
        <p className={styles.topics}>
          Covers: {resource.topics.map((topic) => topic.name).join(", ")}
        </p>
      )}

      {/*
        A native disclosure rather than a toggle: `details` opens and closes with
        no JavaScript at all, so the edit form is reachable on a page that never
        hydrates -- which every write path in this product must be. Only material
        in the catalogue gets one.
      */}
      {isInCatalogue(resource) ? (
        <details className={styles.edit}>
          <summary>Edit details — {resource.title}</summary>
          <ResourceForm resource={resource} topicGroups={topicGroups} />
        </details>
      ) : null}

      <ResourceStatusControl
        resourceId={resource.id}
        status={resource.status}
        title={resource.title}
      />
    </li>
  );
}

/**
 * Why the catalogue is empty, said plainly rather than left to be inferred.
 *
 * Two situations reach this and they mean different things: a learner with
 * nothing catalogued at all has not started, while one whose material is all put
 * aside has simply set it down.
 */
function NothingYet({ hasAny }: { hasAny: boolean }) {
  if (hasAny) {
    return (
      <p className={styles.empty}>
        Everything you have added is put aside at the moment. Put a piece back below, or add
        something new above.
      </p>
    );
  }
  return (
    <p className={styles.empty}>
      Nothing here yet. Add what you study from above — your notes, a PDF, previous-year
      questions, a formula sheet, or a lecture series — and link each piece to the topics it
      covers. It will then appear beside those topics while you{" "}
      <Link href="/curriculum">browse the curriculum</Link> and beside a review of them.
    </p>
  );
}
