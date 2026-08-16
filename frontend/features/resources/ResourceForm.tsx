"use client";

import { useActionState, useId } from "react";

import styles from "@/features/resources/ResourceForm.module.css";
import { registerResourceAction, saveResourceEdit } from "@/features/resources/actions";
import { INITIAL_RESOURCE_FORM_STATE, type ResourceFormState } from "@/features/resources/submission";
import type { SubjectTopicOptions } from "@/features/resources/topic-options";
import {
  RESOURCE_TYPES,
  RESOURCE_TYPE_LABELS,
  type LearningResource,
} from "@/types/resource";

interface ResourceFormProps {
  /** The curriculum's topics, grouped by subject, or empty when unavailable. */
  topicGroups: SubjectTopicOptions[];
  /**
   * The resource being changed, or undefined to register a new one.
   *
   * Editing and registering are one form because they ask for the same six
   * things. What differs is where the answers go — RES-001 or RES-004 — and
   * whether the fields start empty or filled.
   */
  resource?: LearningResource;
}

/**
 * Where a learner records one piece of their own study material, or corrects it.
 *
 * **This records where material is, never the material itself.** Nothing is
 * uploaded: a link is a web address, and anything that is not on the web — a
 * printed book, a folder, a lecture series — is described in the learner's own
 * words. That is why no file input appears here, and why the API refuses a path
 * on the learner's own machine.
 *
 * A client component only so it can report what the last submission did. It
 * calls no API itself: the submission goes to a server action, so the browser
 * still never reaches the backend, and the form posts natively without
 * JavaScript.
 *
 * The topic picker offers every topic, including the headings that group
 * subtopics — a textbook may cover a whole subject — and choosing none is
 * allowed, because material may be catalogued before it is placed.
 *
 * **Editing sends every field, including the topics.** RES-004 replaces the
 * whole link set when one is supplied, and the picker always carries the
 * learner's current selection, so what they see is what is saved.
 */
export function ResourceForm({ topicGroups, resource }: ResourceFormProps) {
  const editing = resource !== undefined;
  const [state, submit, pending] = useActionState<ResourceFormState, FormData>(
    editing ? saveResourceEdit : registerResourceAction,
    INITIAL_RESOURCE_FORM_STATE,
  );
  const titleId = useId();
  const typeId = useId();
  const labelId = useId();
  const referenceId = useId();
  const topicsId = useId();
  const messageId = useId();

  const covered = new Set(resource?.topics.map((topic) => topic.id) ?? []);

  return (
    <form action={submit} className={styles.form}>
      {editing ? (
        <input type="hidden" name="resource_id" value={resource.id} />
      ) : (
        <h2>Add study material</h2>
      )}
      <p className={styles.hint}>
        {editing
          ? "Correct any of these and save. Your changes replace what is stored, including which topics this covers."
          : "Record what you study from, so you can find it again from a topic or a review. LearnFlow stores the details you type — a title, what kind of material it is, and where it is. It does not hold a copy of the material, and it never stores a location on this computer: for anything not on the web, say where it is in your own words."}
      </p>

      <div className={styles.field}>
        <label htmlFor={titleId}>Title</label>
        <input
          defaultValue={resource?.title ?? ""}
          id={titleId}
          maxLength={300}
          name="title"
          placeholder="Operating systems — process scheduling notes"
          required
          type="text"
        />
      </div>

      <div className={styles.field}>
        <label htmlFor={typeId}>Kind of material</label>
        <select defaultValue={resource?.resource_type ?? "note"} id={typeId} name="resource_type">
          {RESOURCE_TYPES.map((resourceType) => (
            <option key={resourceType} value={resourceType}>
              {RESOURCE_TYPE_LABELS[resourceType]}
            </option>
          ))}
          {/*
            A kind this build does not offer is still shown while it is the
            stored one, so editing a resource cannot silently change what kind
            it is. It is not offered for anything else.
          */}
          {resource && !RESOURCE_TYPES.includes(resource.resource_type as never) ? (
            <option value={resource.resource_type}>{resource.resource_type}</option>
          ) : null}
        </select>
      </div>

      <div className={styles.field}>
        <label htmlFor={labelId}>Where it is, in your own words</label>
        <input
          defaultValue={resource?.source_label ?? ""}
          id={labelId}
          maxLength={300}
          name="source_label"
          placeholder="Blue binder, chapter 3"
          type="text"
        />
      </div>

      <div className={styles.field}>
        <label htmlFor={referenceId}>Link</label>
        <input
          defaultValue={resource?.external_reference ?? ""}
          id={referenceId}
          maxLength={2000}
          name="external_reference"
          placeholder="https://…"
          type="url"
        />
        <p className={styles.note}>
          A web address, if the material is online. Give a link, a note of where it is, or both.
        </p>
      </div>

      <div className={styles.field}>
        <label htmlFor={topicsId}>Topics it covers</label>
        {topicGroups.length === 0 ? (
          <p className={styles.note}>
            {/*
              Two situations reach this and neither is a failure to report as
              one: a learner who has not set a study goal yet has no curriculum
              to choose from, and a curriculum that could not be read leaves the
              same gap. Both leave the same thing true, so the copy says that
              rather than guessing which happened.
            */}
            No topics are available to choose from yet — set up a study goal to bring in the
            curriculum. You can still {editing ? "save your other changes" : "add the material now"}{" "}
            and link topics afterwards.
          </p>
        ) : (
          <>
            <select
              defaultValue={[...covered]}
              id={topicsId}
              multiple
              name="topic_ids"
              size={8}
            >
              {topicGroups.map((group) => (
                <optgroup key={group.subjectId} label={group.subjectName}>
                  {group.topics.map((topic) => (
                    <option key={topic.id} value={topic.id}>
                      {topic.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            <p className={styles.note}>
              Choose as many as apply, or none for now. Hold Ctrl — Cmd on a Mac — to choose more
              than one.
            </p>
          </>
        )}
      </div>

      <button
        aria-describedby={state.status === "idle" ? undefined : messageId}
        disabled={pending}
        type="submit"
      >
        {editing
          ? pending
            ? "Saving…"
            : "Save changes"
          : pending
            ? "Adding…"
            : "Add to my material"}
      </button>

      {state.status === "idle" ? null : (
        <p
          className={state.status === "error" ? styles.failed : styles.saved}
          id={messageId}
          role={state.status === "error" ? "alert" : "status"}
        >
          {state.message}
        </p>
      )}
    </form>
  );
}
