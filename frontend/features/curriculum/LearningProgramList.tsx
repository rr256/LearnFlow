import Link from "next/link";

import { Notice } from "@/components/Notice";
import styles from "@/features/curriculum/LearningProgramList.module.css";
import type { LearningProgram } from "@/types/curriculum";

interface LearningProgramListProps {
  programs: LearningProgram[];
}

/**
 * The learning programs CUR-001 returns.
 *
 * Rendered as a real list so assistive technology announces how many programs
 * there are. The program name is the link text rather than a separate "view"
 * control, so the link makes sense read on its own.
 */
export function LearningProgramList({ programs }: LearningProgramListProps) {
  if (programs.length === 0) {
    return (
      <Notice title="No learning programs yet">
        <p>
          The curriculum has not been loaded into this environment. Run the curriculum seed
          described in the project README, then reload this page.
        </p>
      </Notice>
    );
  }

  return (
    <ul className={styles.list}>
      {programs.map((program) => (
        <li className={styles.card} key={program.id}>
          <h3 className={styles.name}>
            <Link href={`/curriculum/programs/${program.id}`}>{program.name}</Link>
          </h3>
          <dl className={styles.meta}>
            <div>
              <dt>Code</dt>
              <dd>{program.code}</dd>
            </div>
            <div>
              <dt>Active curriculum version</dt>
              <dd>
                {program.active_curriculum_version
                  ? program.active_curriculum_version.version_label
                  : "None published"}
              </dd>
            </div>
          </dl>
          {program.description ? <p className={styles.description}>{program.description}</p> : null}
        </li>
      ))}
    </ul>
  );
}
