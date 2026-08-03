import { Notice } from "@/components/Notice";
import styles from "@/features/curriculum/CurriculumTree.module.css";
import type { CurriculumTree as CurriculumTreeData, Subject, Topic } from "@/types/curriculum";

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

function TopicList({ topics }: { topics: Topic[] }) {
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
          {topic.subtopics.length > 0 ? <TopicList topics={topic.subtopics} /> : null}
        </li>
      ))}
    </ul>
  );
}

/**
 * One curriculum version's subjects, topics, and subtopics, as CUR-003 returns
 * them.
 *
 * Nothing is sorted or filtered here. Subjects and topics arrive ordered by the
 * position the syllabus teaches them in, and reordering them in the browser
 * would put a curriculum rule in the frontend.
 */
export function CurriculumTree({ tree }: { tree: CurriculumTreeData }) {
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
              <TopicList topics={subject.topics} />
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
