import Link from "next/link";

import styles from "@/features/progress/LearningStagesBySubject.module.css";
import type { SubjectStages } from "@/features/progress/subject-stages";

interface LearningStagesBySubjectProps {
  /**
   * The learner's recorded stages by subject, or null when the curriculum or the
   * records could not be read. Null is a state of its own: it is not the same as
   * a learner who has recorded nothing, and saying so is the difference between
   * an honest panel and one that quietly reports an empty study history.
   */
  groups: SubjectStages[] | null;
  /** The curriculum screen where a stage is recorded and changed. */
  curriculumHref: string;
}

/**
 * The learning stages the learner recorded, gathered under the subject each
 * topic belongs to.
 *
 * This is [FR-011](docs/requirements/functional.md)'s first acceptance criterion
 * — progress by subject and topic — for the progress LearnFlow stores today,
 * which is the learning stage alone. It is a **reading** of PRG-002 and CUR-003,
 * joined in the client exactly as the curriculum view joins them, so it adds no
 * endpoint: PRG-001 stays unimplemented.
 *
 * **It writes nothing.** No stage control, no `<button>`, and no `<form>` — the
 * read-only shape ADR-026 fixed and ADR-029 applied to this screen, for the
 * reason both gave: recording a stage belongs where the learner records it,
 * beside the topic in the curriculum view, which this panel links to.
 *
 * **Nothing is counted, ranked, or scored.** No topic count beside a subject, no
 * percentage of a subject recorded, no ordering by stage, and no colour that
 * separates one stage from another — a longer word is not a better mark, and the
 * five stages are never compared
 * (docs/domain/terminology.md#plan-coverage-counts-are-not-learner-scores).
 *
 * **Only topics the learner recorded something against appear.** A topic with no
 * record reads as *Not explored*, which is the neutral starting state rather than
 * a gap to be filled in on their behalf.
 */
export function LearningStagesBySubject({
  groups,
  curriculumHref,
}: LearningStagesBySubjectProps) {
  return (
    <section aria-labelledby="stages-by-subject" className={styles.panel}>
      <h2 id="stages-by-subject">Learning stages you have recorded</h2>
      {groups === null ? (
        <Unreadable curriculumHref={curriculumHref} />
      ) : groups.length === 0 ? (
        <Nothing curriculumHref={curriculumHref} />
      ) : (
        <>
          <p className={styles.lead}>
            The learning stage you recorded for each topic, under the subject it belongs to. A
            topic you have recorded nothing against reads as <em>Not explored</em> and is not
            listed here.{" "}
            <Link href={curriculumHref}>Record or change a stage in the curriculum</Link>.
          </p>
          <ul className={styles.subjects}>
            {groups.map((subject) => (
              <li className={styles.subject} key={subject.id}>
                <h3 className={styles.subjectHeading}>
                  {subject.code ? (
                    <span className={styles.subjectCode}>{subject.code} </span>
                  ) : null}
                  {subject.name}
                </h3>
                <ul className={styles.topics}>
                  {subject.topics.map((topic) => (
                    <li className={styles.topic} key={topic.id}>
                      <p className={styles.topicName}>
                        {topic.code ? (
                          <span className={styles.topicCode}>{topic.code} </span>
                        ) : null}
                        {topic.name}
                      </p>
                      {/*
                       * The stage is carried in words. Every stage is styled
                       * identically on purpose: a colour scale would order the
                       * five against each other, and nothing in LearnFlow does.
                       */}
                      <p className={styles.stage}>{topic.stageLabel}</p>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

/**
 * A learner who has recorded no stage at all.
 *
 * Said plainly and pointed at the one screen where a stage is recorded, rather
 * than left as a blank panel that reads as a failure.
 */
function Nothing({ curriculumHref }: { curriculumHref: string }) {
  return (
    <p className={styles.empty}>
      You have not recorded a learning stage for any topic yet. You record one beside a topic while
      browsing the curriculum, and what you record appears here by subject.{" "}
      <Link href={curriculumHref}>Browse your curriculum</Link>.
    </p>
  );
}

/**
 * The curriculum or the records could not be read.
 *
 * Reported in the panel rather than taken out on the whole screen, which is the
 * call the curriculum view already makes about this pair: one unreadable
 * learner-owned read should cost the reader that panel, not the page.
 */
function Unreadable({ curriculumHref }: { curriculumHref: string }) {
  return (
    <p className={styles.empty}>
      Your recorded learning stages could not be read just now, so this panel is empty rather than
      complete. Everything else on this page is unaffected.{" "}
      <Link href={curriculumHref}>See them in the curriculum</Link>.
    </p>
  );
}
