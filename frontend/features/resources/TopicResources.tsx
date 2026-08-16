import styles from "@/features/resources/TopicResources.module.css";
import { resourceTypeLabel, type LearningResource } from "@/types/resource";

interface TopicResourcesProps {
  /** The material the learner linked to this topic, in the API's order. */
  resources: LearningResource[];
  /** Named in the list's accessible label, so several on a page stay distinct. */
  topicName: string;
}

/**
 * The material a learner linked to one topic, shown beside that topic.
 *
 * **Read-only.** Adding material, changing it, and putting it aside all live on
 * the catalogue screen, which this links to — the shape ADR-026 fixed for the
 * monthly view and ADR-029 for the progress overview: a screen that reports
 * states where its action lives rather than growing a second control for it.
 *
 * **Nothing is recommended, ranked, or scored.** This is the material the learner
 * chose to link, in the order the API returned it. LearnFlow suggests nothing of
 * its own: it holds no material, and a topic with nothing linked simply renders
 * nothing rather than an invented suggestion.
 *
 * **Nothing is counted.** No figure appears beside a topic — a count beside a
 * subject or a topic measures the learner, which
 * docs/domain/terminology.md#plan-coverage-counts-are-not-learner-scores forbids.
 */
export function TopicResources({ resources, topicName }: TopicResourcesProps) {
  if (resources.length === 0) {
    return null;
  }

  return (
    <div className={styles.material}>
      <p className={styles.heading}>Your material</p>
      <ul aria-label={`Your material for ${topicName}`} className={styles.items}>
        {resources.map((resource) => (
          <li key={resource.id}>
            <span className={styles.kind}>{resourceTypeLabel(resource.resource_type)}</span>{" "}
            {resource.external_reference ? (
              <a href={resource.external_reference} rel="noreferrer noopener" target="_blank">
                {resource.title}
              </a>
            ) : (
              <span className={styles.title}>{resource.title}</span>
            )}
            {resource.source_label ? (
              <span className={styles.where}> — {resource.source_label}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
