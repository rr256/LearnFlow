import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import styles from "@/app/curriculum/programs/[programId]/page.module.css";
import { Notice } from "@/components/Notice";
import { CurriculumTree } from "@/features/curriculum/CurriculumTree";
import { stagesByTopicId } from "@/features/progress/stages";
import { resourcesByTopicId } from "@/features/resources/by-topic";
import {
  ApiError,
  listResources,
  listTopicProgress,
  readCurriculumTree,
  readLearningProgram,
} from "@/lib/api-client";
import type { CurriculumTree as CurriculumTreeData, LearningProgram } from "@/types/curriculum";
import type { LearningStage } from "@/types/progress";
import type { LearningResource } from "@/types/resource";

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
 * PRG-002 -- the stages this learner has recorded against the version's topics.
 *
 * A failure here is deliberately not fatal. The curriculum is reference data
 * every reader can see; the stages are one learner's, and losing them should
 * cost the reader the controls rather than the whole syllabus. Returning null
 * renders the tree without them.
 *
 * `MAX_PAGE_SIZE` is not requested explicitly: the client already defaults this
 * call to it, which covers the curated GATE CSE curriculum in one page. A
 * curriculum large enough to exceed it would need paging here, and the
 * `pagination` block is what would reveal that.
 */
async function recordedStages(
  curriculumVersionId: string,
): Promise<Map<string, LearningStage> | null> {
  try {
    return stagesByTopicId(await listTopicProgress({ curriculumVersionId }));
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    return null;
  }
}

/**
 * RES-002 -- the study material this learner has catalogued, by topic.
 *
 * A failure here is not fatal either, for the reason the stages give: material
 * is one learner's, and losing it should cost the reader that list rather than
 * the whole syllabus. Returning null renders the tree without it.
 *
 * The whole catalogue is read and joined here rather than asked for a topic at a
 * time: a page showing sixty topics would otherwise make sixty requests. That is
 * the join the stages already perform, and the reason RES-002 returns each
 * resource with its topics.
 */
async function catalogued(): Promise<Map<string, LearningResource[]> | null> {
  try {
    return resourcesByTopicId(await listResources());
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    return null;
  }
}

/**
 * CUR-003, PRG-002, and RES-002 -- the version's subjects and topics, with the
 * learner's recorded stage beside each trackable one and their own material
 * beside each topic it covers.
 *
 * Suspended by the page below, so the program's own details appear before the
 * tree arrives. Only this half is suspended: a boundary over the program lookup
 * would commit a `200` before that lookup could call `notFound()`, and a
 * mistyped program id would answer `200` instead of `404`.
 *
 * The three calls run together rather than in sequence: none addresses another's
 * result, so the page waits once instead of three times.
 */
async function CurriculumTreeSection({ curriculumVersionId }: { curriculumVersionId: string }) {
  let tree: CurriculumTreeData;
  let stages: Map<string, LearningStage> | null;
  let resources: Map<string, LearningResource[]> | null;
  try {
    [tree, stages, resources] = await Promise.all([
      readCurriculumTree(curriculumVersionId),
      recordedStages(curriculumVersionId),
      catalogued(),
    ]);
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error;
    }
    return <LoadFailure error={error} />;
  }
  return <CurriculumTree resources={resources} stages={stages} tree={tree} />;
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
      {/*
        The tree shows the learner's own material beside the topics it covers but
        offers no control for it: adding material and putting it aside live on
        the catalogue screen, which this names and links to -- the shape ADR-026
        and ADR-029 both use for a screen that reports rather than writes.
      */}
      <p className={styles.materialNote}>
        Study material you add on <Link href="/resources">your study material</Link> appears here,
        beside each topic it covers.
      </p>
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
