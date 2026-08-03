import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import styles from "@/app/curriculum/programs/[programId]/page.module.css";
import { Notice } from "@/components/Notice";
import { CurriculumTree } from "@/features/curriculum/CurriculumTree";
import { ApiError, readCurriculumTree, readLearningProgram } from "@/lib/api-client";
import type { CurriculumTree as CurriculumTreeData, LearningProgram } from "@/types/curriculum";

export const metadata: Metadata = {
  title: "Learning program",
};

export const dynamic = "force-dynamic";

interface ProgramPageProps {
  params: Promise<{ programId: string }>;
}

function Breadcrumb({ programName }: { programName: string }) {
  return (
    <nav aria-label="Breadcrumb" className={styles.breadcrumb}>
      <ol>
        <li>
          <Link href="/curriculum">Curriculum</Link>
        </li>
        <li aria-current="page">{programName}</li>
      </ol>
    </nav>
  );
}

function LoadFailure({ error }: { error: ApiError }) {
  return (
    <Notice title="The curriculum could not be loaded" tone="attention">
      <p>{error.message}</p>
      {error.isUnreachable ? (
        <p>
          Start the backend with <code>docker compose up</code>, or run it directly, and reload this
          page.
        </p>
      ) : null}
    </Notice>
  );
}

/**
 * CUR-003 -- the version's subjects, topics, and subtopics.
 *
 * Suspended by the page below, so the program's own details appear before the
 * tree arrives. Only this half is suspended: a boundary over the program lookup
 * would commit a `200` before that lookup could call `notFound()`, and a
 * mistyped program id would answer `200` instead of `404`.
 */
async function CurriculumTreeSection({ curriculumVersionId }: { curriculumVersionId: string }) {
  let tree: CurriculumTreeData;
  try {
    tree = await readCurriculumTree(curriculumVersionId);
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    return <LoadFailure error={error} />;
  }
  return <CurriculumTree tree={tree} />;
}

/**
 * CUR-002 and CUR-003 -- one learning program and its active curriculum
 * version's subjects, topics, and subtopics.
 *
 * The two calls are sequential by necessity: the tree is addressed by the
 * curriculum-version id that reading the program reveals.
 */
export default async function LearningProgramPage({ params }: ProgramPageProps) {
  const { programId } = await params;

  let program: LearningProgram;
  try {
    program = await readLearningProgram(programId);
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    // A program id that names nothing is a wrong URL, not a broken page, so it
    // is answered with the framework's 404 rather than an error panel.
    if (error.isNotFound) {
      notFound();
    }
    return (
      <>
        <h1>Learning program</h1>
        <LoadFailure error={error} />
      </>
    );
  }

  const version = program.active_curriculum_version;

  return (
    <>
      <Breadcrumb programName={program.name} />
      <h1>{program.name}</h1>
      {program.description ? <p className={styles.description}>{program.description}</p> : null}

      {version ? (
        <dl className={styles.version}>
          <div>
            <dt>Curriculum version</dt>
            <dd>{version.version_label}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{version.status}</dd>
          </div>
          {version.source_reference ? (
            <div>
              <dt>Source</dt>
              <dd>{version.source_reference}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}

      <h2>Subjects and topics</h2>
      {version ? (
        <Suspense fallback={<p role="status">Loading subjects and topics…</p>}>
          <CurriculumTreeSection curriculumVersionId={version.id} />
        </Suspense>
      ) : (
        <Notice title="No active curriculum version">
          <p>
            This program has no active curriculum version, so there are no subjects or topics to
            show yet.
          </p>
        </Notice>
      )}
    </>
  );
}
