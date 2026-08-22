import Link from "next/link";

import styles from "@/features/resources/ResourceCatalogue.module.css";
import { ResourceForm } from "@/features/resources/ResourceForm";
import { ResourceFiles } from "@/features/resources/ResourceFiles";
import { ResourceNotes } from "@/features/resources/ResourceNotes";
import { removeResourceAction } from "@/features/resources/actions";
import { RemoveControl } from "@/features/resources/RemoveControl";
import { ResourceStatusControl } from "@/features/resources/ResourceStatusControl";
import { isInCatalogue } from "@/features/resources/by-topic";
import type { SubjectTopicOptions } from "@/features/resources/topic-options";
import { resourceTypeLabel, type LearningResource } from "@/types/resource";
import type { ResourceFile } from "@/types/resource-file";
import type { ResourceNote } from "@/types/resource-note";

interface ResourceCatalogueProps {
  resources: LearningResource[];
  /** The curriculum's topics, for the edit form's picker. */
  topicGroups: SubjectTopicOptions[];
  /**
   * Each resource's notes, keyed by resource.
   *
   * Optional, and absent means the same as empty: a piece of material with no
   * notes renders the invitation to write one rather than an error. That also
   * keeps a caller which does not read notes — a test, or a future screen —
   * from having to supply a map of nothing.
   */
  notesByResource?: Record<string, ResourceNote[]>;
  /** The PDFs stored against each resource, keyed by resource id. */
  filesByResource?: Record<string, ResourceFile[]>;
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
export function ResourceCatalogue({
  resources,
  topicGroups,
  notesByResource = {},
  filesByResource = {},
}: ResourceCatalogueProps) {
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
                <ResourceLine
                  files={filesByResource[resource.id] ?? []}
                  key={resource.id}
                  notes={notesByResource[resource.id] ?? []}
                  resource={resource}
                  topicGroups={topicGroups}
                />
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
              <ResourceLine
                files={filesByResource[resource.id] ?? []}
                key={resource.id}
                notes={notesByResource[resource.id] ?? []}
                resource={resource}
                topicGroups={topicGroups}
              />
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
  notes,
  files,
}: {
  resource: LearningResource;
  topicGroups: SubjectTopicOptions[];
  notes: ResourceNote[];
  files: ResourceFile[];
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

      {/*
        The learner's own notes on this material, shown here and on no other
        screen. A note can run to pages, and the screens that show a topic's
        material exist to help a learner *find* it -- burying those under text is
        the reason ADR-036 kept material off `/plan/month` entirely.

        Notes on material that is put aside are read-only, as the material
        itself is: the learner puts it back before writing or correcting one.
      */}
      <ResourceNotes
        notes={notes}
        resourceId={resource.id}
        writable={isInCatalogue(resource)}
      />

      {/*
        The PDFs stored against this material. Shown here and on no other
        screen, for the reason the notes above are: the screens that show a
        topic's material exist to help a learner *find* it.

        Files on material that is put aside are read-only, as its notes are --
        still listed and still downloadable, because hiding a learner's own file
        from a list is not a reason to withhold it from them.
      */}
      <details className={styles.disclosure}>
        <summary>PDFs — {resource.title}</summary>
        <ResourceFiles
          files={files}
          resourceId={resource.id}
          writable={isInCatalogue(resource)}
        />
      </details>

      <ResourceStatusControl
        resourceId={resource.id}
        status={resource.status}
        title={resource.title}
      />

      {/*
        RES-005. Last on the line and behind a disclosure, after the two answers
        that keep the material: correcting it, and putting it aside. It removes
        more than it names -- every note, every stored PDF, and their bytes --
        so the copy says what goes rather than leaving the learner to infer it.

        Offered whatever the material's status: an archived resource is as
        removable as a registered one, because requiring an archive first would
        turn the shelf into a deletion queue.
      */}
      <RemoveControl
        action={removeResourceAction}
        confirmLabel="Yes, remove this material and everything in it"
        consequence={describeLoss(notes.length, files.length)}
        fieldName="resource_id"
        fieldValue={resource.id}
        instead="To keep it but stop using it, put it aside instead — that is reversible."
        kind="material"
        label={resource.title}
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

/**
 * What removing this material takes with it, in words.
 *
 * **These figures describe what a destructive action will destroy, not the
 * learner.** Terminology's no-counting rule guards against measuring effort and
 * progress; hiding the scale of an irreversible action would be the wrong
 * instinct, and the learner needs it to decide. Nothing here is stored,
 * totalled across resources, or shown anywhere but inside this warning.
 */
export function describeLoss(noteCount: number, fileCount: number): string {
  const parts: string[] = [];
  if (fileCount > 0) {
    parts.push(fileCount === 1 ? "1 stored PDF" : `${fileCount} stored PDFs`);
  }
  if (noteCount > 0) {
    parts.push(noteCount === 1 ? "1 note" : `${noteCount} notes`);
  }
  if (parts.length === 0) {
    return "The material and the topics it covers are removed from your catalogue.";
  }
  return `This also deletes ${parts.join(" and ")} kept against it.`;
}
