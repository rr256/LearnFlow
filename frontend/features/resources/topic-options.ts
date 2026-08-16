/**
 * Flattening the curriculum into the choices a learner picks material's topics
 * from.
 *
 * CUR-003 returns subjects holding topics holding subtopics; a `<select>` groups
 * one level. Walking the tree into `<optgroup>`s is presentation, and it is a
 * plain function here so it is testable without rendering anything.
 *
 * **Nothing is sorted, ranked, or filtered.** Subjects and topics arrive in the
 * order the syllabus teaches them, and the depth of a subtopic is shown by
 * indenting its label rather than by re-ordering anything — reordering the
 * curriculum in the browser would put a curriculum rule in the frontend
 * (docs/development/coding-standards.md#ui-responsibilities).
 *
 * **A grouping topic is offered as well as a trackable one**, which is where this
 * differs from the learning-stage control. A stage claims something about
 * understanding a unit of work and a heading cannot hold one; a textbook may
 * genuinely cover a whole heading, so RES-001 accepts either.
 */

import type { Subject, Topic } from "@/types/curriculum";

/** One selectable topic, labelled for reading inside its subject's group. */
export interface TopicOption {
  id: string;
  /** Indented by depth, so a subtopic reads as one without a separate control. */
  label: string;
}

/**
 * Two no-break spaces, written as escapes so they are visible in this source.
 *
 * Ordinary spaces would not survive: a browser collapses leading whitespace
 * inside an `<option>`, so the indent would vanish in the one control it exists
 * for. A no-break space is a character rather than whitespace, so it renders and
 * is read aloud as part of the label.
 */
export const INDENT = "\u00a0\u00a0";

/** One subject's selectable topics, in syllabus order. */
export interface SubjectTopicOptions {
  subjectId: string;
  subjectName: string;
  topics: TopicOption[];
}

function walk(topics: Topic[], depth: number, into: TopicOption[]): void {
  for (const topic of topics) {
    into.push({ id: topic.id, label: `${INDENT.repeat(depth)}${topic.name}` });
    walk(topic.subtopics, depth + 1, into);
  }
}

/**
 * Every topic of the curriculum, grouped under the subject it belongs to.
 *
 * A subject with no topics is left out: an empty group is a heading a learner
 * cannot act on.
 */
export function topicOptions(subjects: Subject[]): SubjectTopicOptions[] {
  return subjects
    .map((subject) => {
      const topics: TopicOption[] = [];
      walk(subject.topics, 0, topics);
      return { subjectId: subject.id, subjectName: subject.name, topics };
    })
    .filter((group) => group.topics.length > 0);
}
