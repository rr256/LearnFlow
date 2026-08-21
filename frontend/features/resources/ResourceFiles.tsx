"use client";

import { useActionState, useId } from "react";

import styles from "@/features/resources/ResourceFiles.module.css";
import {
  setResourceFileStatusAction,
  uploadResourceFileAction,
} from "@/features/resources/file-actions";
import {
  INITIAL_RESOURCE_FILE_FORM_STATE,
  INITIAL_RESOURCE_FILE_STATUS_STATE,
  type ResourceFileFormState,
  type ResourceFileStatusState,
} from "@/features/resources/file-submission";
import {
  MAX_FILE_BYTES,
  MAX_FILES_PER_RESOURCE,
  MAX_PAGE_COUNT,
  readablePages,
  readableSize,
  type ResourceFile,
} from "@/types/resource-file";

interface ResourceFilesProps {
  /** The material these files belong to. */
  resourceId: string;
  /** Its stored PDFs, newest first, as RES-015 returned them. */
  files: ResourceFile[];
  /**
   * Whether the material itself can still be changed.
   *
   * Archived material is **read-only**: its files stay listed and downloadable,
   * and neither a new upload nor a status change is offered. The learner brings
   * the material back first, which is the rule RES-004 and RES-012 already set.
   */
  writable: boolean;
}

/**
 * The PDFs a learner keeps against one piece of their study material.
 *
 * **Upload and store, and nothing else.** Nothing here extracts text, runs OCR,
 * chunks, embeds, indexes, or searches a file, and no AI model sees one. A
 * stored PDF is kept and read back.
 *
 * **The browser never reaches the backend.** The form posts to a server action,
 * which forwards the file from the Next.js server — so no API address reaches a
 * client bundle, and downloads go through LearnFlow's own route.
 *
 * **Nothing is deleted.** A learner sets a file aside with *archived*,
 * reversibly, and the bytes stay stored either way. There is no delete control
 * because there is no endpoint behind one.
 *
 * A client component only so it can report what the last submission did. Both
 * forms post natively without JavaScript.
 */
export function ResourceFiles({ resourceId, files, writable }: ResourceFilesProps) {
  const [state, uploadAction] = useActionState<ResourceFileFormState, FormData>(
    uploadResourceFileAction,
    INITIAL_RESOURCE_FILE_FORM_STATE,
  );
  const fileField = useId();
  const active = files.filter((file) => file.status === "active");
  const full = files.length >= MAX_FILES_PER_RESOURCE;

  return (
    <div className={styles.files}>
      {files.length === 0 ? (
        <p className={styles.empty}>No PDFs are stored against this material yet.</p>
      ) : (
        <ul className={styles.list}>
          {files.map((file) => (
            <StoredFile file={file} key={file.id} writable={writable} />
          ))}
        </ul>
      )}

      {writable ? (
        full ? (
          <p className={styles.full}>
            This material holds the most PDFs LearnFlow keeps against one item. Set one aside
            before adding another — nothing is deleted either way.
          </p>
        ) : (
          <form action={uploadAction} className={styles.form} encType="multipart/form-data">
            <input name="resource_id" type="hidden" value={resourceId} />
            <div className={styles.field}>
              <label htmlFor={fileField}>Add a PDF</label>
              <input accept="application/pdf,.pdf" id={fileField} name="file" type="file" />
              <p className={styles.hint}>
                PDFs only, up to {readableSize(MAX_FILE_BYTES)} and {MAX_PAGE_COUNT} pages. The
                file is stored on this computer and is never sent anywhere; nothing reads inside
                it, and no AI model sees it. A password-protected PDF cannot be stored.
              </p>
            </div>
            <button type="submit">Add this PDF</button>
          </form>
        )
      ) : (
        <p className={styles.readOnly}>
          This material is put aside, so its PDFs cannot be changed. They are still listed and
          still downloadable — bring the material back to add or set aside a file.
        </p>
      )}

      {state.error !== null ? (
        <p className={styles.error} role="alert">
          {state.error}
        </p>
      ) : null}

      {state.stored !== null ? (
        <p className={styles.stored} role="status">
          Stored {state.stored.original_filename}.
        </p>
      ) : null}

      {files.length > 0 && active.length === 0 ? (
        <p className={styles.hint}>
          Every PDF here is set aside. Nothing has been deleted — bring one back to use it.
        </p>
      ) : null}
    </div>
  );
}

/**
 * One stored PDF: what it is, where to get it, and how to set it aside.
 *
 * The download is an ordinary link to LearnFlow's own route, so it works with
 * JavaScript switched off and the browser saves the file rather than rendering
 * it in the page.
 */
function StoredFile({ file, writable }: { file: ResourceFile; writable: boolean }) {
  const [state, statusAction] = useActionState<ResourceFileStatusState, FormData>(
    setResourceFileStatusAction,
    INITIAL_RESOURCE_FILE_STATUS_STATE,
  );
  const archived = file.status === "archived";

  return (
    <li className={styles.item}>
      <p className={styles.name}>
        <a
          className={styles.download}
          download={file.original_filename}
          href={`/resources/files/${file.id}`}
        >
          {file.original_filename}
        </a>
      </p>
      <p className={styles.about}>
        {readableSize(file.byte_size)} · {readablePages(file.page_count)}
        {archived ? <span className={styles.aside}> · Set aside</span> : null}
      </p>

      {writable ? (
        <form action={statusAction} className={styles.statusForm}>
          <input name="file_id" type="hidden" value={file.id} />
          <input name="status" type="hidden" value={archived ? "active" : "archived"} />
          <button type="submit">{archived ? "Bring this PDF back" : "Set this PDF aside"}</button>
        </form>
      ) : null}

      {state.error !== null ? (
        <p className={styles.error} role="alert">
          {state.error}
        </p>
      ) : null}
    </li>
  );
}
