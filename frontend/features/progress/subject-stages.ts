/**
 * Gathering the learning stages a learner recorded into the subjects they belong
 * to.
 *
 * PRG-002 returns only the topics a learner has recorded something against, and
 * each record carries its topic's `subject_id` but **no subject name**. CUR-003
 * carries the names, and the order the syllabus teaches them in. Putting the two
 * together is the client's job — the same join `stages.ts` performs for the
 * curriculum view, read the other way round.
 *
 * Plain functions, so they are testable without a running server.
 *
 * **Nothing here counts.** No total, no per-subject tally, no percentage, no
 * ratio, and no proportion of a subject recorded. A count of a learner's topics
 * beside a subject name is a measurement of the learner rather than a
 * description of a plan, which
 * docs/domain/terminology.md#plan-coverage-counts-are-not-learner-scores forbids.
 * The group lengths below decide whether a subject has anything to show; none of
 * them reaches the screen.
 *
 * **Nothing here ranks.** Subjects and topics keep the curriculum's own order,
 * and the five stages are never compared, sorted by, or grouped under — a topic
 * at *Building foundation* is not behind one at *Practice-ready*, and ordering by
 * stage would say it was.
 */

import type { Subject, Topic } from "@/types/curriculum";
import { LEARNING_STAGE_LABELS, isLearningStage } from "@/types/progress";
import type { TopicProgress } from "@/types/progress";

/** One topic the learner has recorded a stage against. */
export interface StagedTopic {
  id: string;
  /** The topic's own name, as the API returned it. */
  name: string;
  code: string | null;
  /** The label a learner reads, from the shared stage table. */
  stageLabel: string;
}

/** The topics of one subject the learner has recorded a stage against. */
export interface SubjectStages {
  /** Stable key for rendering. It is never shown to a learner. */
  id: string;
  /** The heading a learner reads. */
  name: string;
  /** The subject's code, or null for records the tree does not place. */
  code: string | null;
  topics: StagedTopic[];
}

/**
 * The key and heading for records whose topic the curriculum tree no longer
 * holds.
 *
 * A learner's record outlives a re-seed that drops the topic it names, and
 * dropping it from the screen would under-report what is stored. Naming the
 * situation is honest where a bare identifier under a missing subject would not
 * be.
 */
const UNPLACED_GROUP_ID = "unplaced";
const UNPLACED_GROUP_NAME = "Topics no longer in your curriculum";

/** What the curriculum and progress reads returned together, when both did. */
export interface RecordedStages {
  /** PRG-002's records, for the goal's curriculum version. */
  records: TopicProgress[];
  /** CUR-003's subjects, which place and order them. */
  subjects: Subject[];
}

/** Visit every topic of a subject, subtopics included, in the tree's own order. */
function walkTopics(topics: readonly Topic[], visit: (topic: Topic) => void): void {
  for (const topic of topics) {
    visit(topic);
    walkTopics(topic.subtopics, visit);
  }
}

/**
 * Index the learner's recorded stages by the topic each belongs to.
 *
 * A stage this build does not recognise is skipped rather than shown raw, which
 * is exactly what `stages.ts` does with the same set: the API's catalogue could
 * gain a value before this build knows the label for it, and a `snake_case`
 * identifier is not something to show a learner.
 */
function stagedTopicsByTopicId(records: readonly TopicProgress[]): Map<string, StagedTopic> {
  const staged = new Map<string, StagedTopic>();

  for (const record of records) {
    if (!isLearningStage(record.learning_stage)) {
      continue;
    }
    staged.set(record.topic.id, {
      id: record.topic.id,
      name: record.topic.name,
      code: record.topic.code,
      stageLabel: LEARNING_STAGE_LABELS[record.learning_stage],
    });
  }

  return staged;
}

/**
 * The learner's recorded stages, grouped by the subject each topic belongs to.
 *
 * **The order is the curriculum's, by construction rather than by sorting.** The
 * subjects are walked in the order CUR-003 returned them and each subject's
 * topics in the order it nests them, picking up a recorded stage where one
 * exists — so the syllabus order arrives from the backend and is rendered, never
 * recomputed here (docs/development/coding-standards.md#ui-responsibilities).
 * PRG-002's own order is newest-first, which is not an order to show a syllabus
 * in.
 *
 * **Only topics with a record appear.** A topic the learner has recorded nothing
 * against reads as *Not explored* and is left where it is, in the curriculum
 * view; listing every topic here would repeat that screen. A subject with no
 * recorded topic is left out entirely rather than shown as empty, because "none
 * yet" beside a subject name invites the count this module does not make.
 *
 * A record whose topic the tree does not hold is placed in one final group. It is
 * reachable when a curriculum re-seed drops a topic a learner had already
 * recorded, and the alternative — dropping it — would under-report what is
 * stored.
 *
 * @param records PRG-002's records, ideally already filtered to the goal's
 *   curriculum version.
 * @param subjects CUR-003's subjects, which place and order them.
 */
export function selectStagesBySubject(
  records: readonly TopicProgress[],
  subjects: readonly Subject[],
): SubjectStages[] {
  const staged = stagedTopicsByTopicId(records);
  const placed = new Set<string>();
  const groups: SubjectStages[] = [];

  for (const subject of subjects) {
    const topics: StagedTopic[] = [];
    walkTopics(subject.topics, (topic) => {
      const recorded = staged.get(topic.id);
      if (recorded) {
        placed.add(topic.id);
        topics.push(recorded);
      }
    });
    if (topics.length > 0) {
      groups.push({ id: subject.id, name: subject.name, code: subject.code, topics });
    }
  }

  // Whatever the walk above did not reach, in the order PRG-002 returned it.
  const unplaced = [...staged.values()].filter((topic) => !placed.has(topic.id));
  if (unplaced.length > 0) {
    groups.push({
      id: UNPLACED_GROUP_ID,
      name: UNPLACED_GROUP_NAME,
      code: null,
      topics: unplaced,
    });
  }

  return groups;
}
