import styles from "@/features/resources/TopicNoteSearchForm.module.css";
import type { SubjectTopicOptions } from "@/features/resources/topic-options";

interface TopicNoteSearchFormProps {
  /** The curriculum's topics, grouped by subject, or empty when unavailable. */
  topicGroups: SubjectTopicOptions[];
  /** The topic already asked about, so the picker keeps the learner's choice. */
  selectedTopicId?: string;
}

/**
 * Where a learner asks for passages from their own notes on one topic.
 *
 * **A plain `GET` form, and deliberately not a server action.** A search reads
 * and writes nothing, so it needs no action, no revalidation, and no client
 * bundle: submitting puts `topic_id` in the address, and the page reads it back.
 * That is also why this is a server component with no `"use client"` — there is
 * no state to hold and nothing to hydrate, so the whole feature works with
 * JavaScript switched off by construction rather than by careful degradation.
 *
 * **The topic is the query.** There is no free-text field: a learner chooses a
 * topic and its name supplies the search terms. A typed query would be a
 * different feature, with its own question about what is recorded — and nothing
 * here records anything at all.
 *
 * The picker reuses the same `topic-options` grouping the resource form and the
 * practice screens use, rather than a third copy of the same walk.
 */
export function TopicNoteSearchForm({
  topicGroups,
  selectedTopicId,
}: TopicNoteSearchFormProps) {
  if (topicGroups.length === 0) {
    return (
      <p className={styles.unavailable}>
        The curriculum could not be read, so there are no topics to choose from. Reload the page,
        or come back once the backend is reachable.
      </p>
    );
  }

  return (
    <form action="/resources/search" className={styles.form} method="get">
      <div className={styles.field}>
        <label htmlFor="topic-id">Topic</label>
        <select defaultValue={selectedTopicId ?? ""} id="topic-id" name="topic_id" required>
          <option disabled value="">
            Choose a topic…
          </option>
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
        <p className={styles.hint}>
          Your notes are searched on this computer, only when you ask, and only where you have
          linked material to the topic you choose. Nothing is sent anywhere, and this search
          involves no AI model — to have one answer a question from these passages, ask on the
          topic question screen instead.
        </p>
      </div>

      <button type="submit">Find passages in my notes</button>
    </form>
  );
}
