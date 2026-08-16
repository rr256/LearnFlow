import { Notice } from "@/components/Notice";
import styles from "@/features/curriculum/CurriculumTree.module.css";
import { TopicStageControl } from "@/features/progress/TopicStageControl";
import { stageFor } from "@/features/progress/stages";
import { TopicResources } from "@/features/resources/TopicResources";
import { resourcesFor } from "@/features/resources/by-topic";
import type { CurriculumTree as CurriculumTreeData, Subject, Topic } from "@/types/curriculum";
import type { LearningStage } from "@/types/progress";
import type { LearningResource } from "@/types/resource";

/**
 * Collect every topic in the tree by id, at any depth.
 *
 * A relationship names two topic ids; without this the relationship list would
 * have to show identifiers, which say nothing to a learner.
 */
function indexTopicsById(subjects: Subject[]): Map<string, Topic> {
  const index = new Map<string, Topic>();

  function walk(topics: Topic[]): void {
    for (const topic of topics) {
      index.set(topic.id, topic);
      walk(topic.subtopics);
    }
  }

  walk(subjects.flatMap((subject) => subject.topics));
  return index;
}

/** Turn `recommended_before` into `recommended before` for reading aloud. */
function humaniseRelationshipType(relationshipType: string): string {
  return relationshipType.replace(/_/g, " ");
}

interface TopicListProps {
  topics: Topic[];
  /**
   * The learner's recorded stages, keyed by topic. Null when this view is not
   * showing progress at all -- no stage control is rendered then, which is what
   * keeps the tree usable before a learner has completed setup.
   */
  stages: Map<string, LearningStage> | null;
  /**
   * The learner's catalogued material, keyed by the topics it covers. Null when
   * it could not be read, which costs the reader the material rather than the
   * syllabus -- the call this view already makes about the stages.
   */
  resources: Map<string, LearningResource[]> | null;
}

function TopicList({ topics, stages, resources }: TopicListProps) {
  return (
    <ul className={styles.topics}>
      {topics.map((topic) => (
        <li key={topic.id}>
          <span className={styles.topicName}>
            {topic.code ? <span className={styles.topicCode}>{topic.code} </span> : null}
            {topic.name}
          </span>
          {/*
            A topic that only groups subtopics cannot hold progress of its own.
            Saying so in words keeps the distinction available to a screen
            reader, which a styling difference alone would not.
          */}
          {topic.is_trackable ? null : <span className={styles.grouping}>(grouping only)</span>}
          {topic.description ? <p className={styles.topicDescription}>{topic.description}</p> : null}
          {/*
            Only a trackable topic gets a control, which is the same rule the
            API enforces: PRG-004 refuses a stage on a grouping heading.
          */}
          {stages && topic.is_trackable ? (
            <TopicStageControl
              learningStage={stageFor(stages, topic.id)}
              topicId={topic.id}
              topicName={topic.name}
            />
          ) : null}
          {/*
            The material the learner linked to this topic, read-only: adding it
            and putting it aside live on the catalogue screen. A grouping topic
            gets it too, unlike the stage control, because a textbook may cover a
            whole heading. A topic with nothing linked renders nothing rather
            than a suggestion LearnFlow cannot support.
          */}
          {resources ? (
            <TopicResources
              resources={resourcesFor(resources, topic.id)}
              topicName={topic.name}
            />
          ) : null}
          {topic.subtopics.length > 0 ? (
            <TopicList resources={resources} stages={stages} topics={topic.subtopics} />
          ) : null}
        </li>
      ))}
    </ul>
  );
}

interface CurriculumTreeProps {
  tree: CurriculumTreeData;
  /**
   * The learner's recorded stages, keyed by topic, or null to render the tree
   * as reference data alone. Null is what a caller passes when it cannot reach
   * the progress endpoint, so an unreadable stage costs the reader the control
   * rather than the whole syllabus.
   */
  stages?: Map<string, LearningStage> | null;
  /**
   * The learner's catalogued material, keyed by the topics it covers, or null to
   * render the tree without it. Null is what a caller passes when it cannot
   * reach the resource endpoint, so unreadable material costs the reader that
   * list rather than the whole syllabus.
   */
  resources?: Map<string, LearningResource[]> | null;
}

/**
 * One curriculum version's subjects, topics, and subtopics, as CUR-003 returns
 * them, with the learner's recorded stage and their own study material beside
 * each topic.
 *
 * Nothing is sorted or filtered here. Subjects and topics arrive ordered by the
 * position the syllabus teaches them in, and reordering them in the browser
 * would put a curriculum rule in the frontend. No stage is calculated either:
 * `stages` holds what PRG-002 returned, and a topic absent from it has recorded
 * nothing. **No material is recommended**: `resources` holds what RES-002
 * returned, and a topic with nothing linked shows nothing.
 */
export function CurriculumTree({ tree, stages = null, resources = null }: CurriculumTreeProps) {
  if (tree.subjects.length === 0) {
    return (
      <Notice title="This curriculum version has no subjects yet">
        <p>
          The version exists but holds no subjects. Loading the curriculum seed will populate it.
        </p>
      </Notice>
    );
  }

  const topicsById = indexTopicsById(tree.subjects);

  return (
    <>
      <ul className={styles.subjects}>
        {tree.subjects.map((subject) => (
          <li className={styles.subject} key={subject.id}>
            <h3 className={styles.subjectHeading}>
              <span className={styles.subjectCode}>{subject.code} </span>
              {subject.name}
            </h3>
            {subject.description ? (
              <p className={styles.subjectDescription}>{subject.description}</p>
            ) : null}
            {subject.topics.length > 0 ? (
              <TopicList resources={resources} stages={stages} topics={subject.topics} />
            ) : (
              <p className={styles.empty}>No topics are recorded for this subject yet.</p>
            )}
          </li>
        ))}
      </ul>

      {tree.topic_relationships.length > 0 ? (
        <section aria-labelledby="topic-relationships" className={styles.relationships}>
          <h3 id="topic-relationships">Topic relationships</h3>
          <ul className={styles.relationshipList}>
            {tree.topic_relationships.map((relationship) => {
              const source = topicsById.get(relationship.source_topic_id);
              const target = topicsById.get(relationship.target_topic_id);
              return (
                <li
                  key={`${relationship.source_topic_id}-${relationship.target_topic_id}-${relationship.relationship_type}`}
                >
                  {/*
                    Neutral phrasing, because the three relationship types do
                    not share a verb: "prerequisite", "recommended before", and
                    "related" each read correctly between the two names, and
                    none of them reads correctly in a sentence built for
                    another.
                  */}
                  {source?.name ?? "Unknown topic"}
                  <span className={styles.relationshipType}>
                    {" — "}
                    {humaniseRelationshipType(relationship.relationship_type)}
                    {" — "}
                  </span>
                  {target?.name ?? "Unknown topic"}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
    </>
  );
}
