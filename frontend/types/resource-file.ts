/**
 * Stored-file types, derived from the RES-014 to RES-017 contracts in
 * docs/api/endpoints.md#resource-and-ingestion-endpoints.
 *
 * A learner keeps one or more **PDFs** against a piece of catalogued material.
 * The bytes live in a Docker named volume on the backend; what travels here is
 * the metadata describing them.
 *
 * **There is no `storage_key` in this contract, deliberately.** Where the bytes
 * are is internal to the backend, and no resource endpoint returns a storage
 * location or a filesystem path — so nothing on this side could render one.
 *
 * **Nothing here is extracted text.** No chunk, no embedding, no preview, and no
 * page content: this feature stores files and reads them back.
 *
 * **No figure here measures the learner.** A byte size and a page count describe
 * a document; neither is totalled across files or shown as progress
 * (docs/development/coding-standards.md#ui-responsibilities).
 */

import type { DataEnvelope } from "@/types/api";

/** Every status a stored file may hold. */
export const RESOURCE_FILE_STATUSES = ["active", "archived"] as const;

export type ResourceFileStatus = (typeof RESOURCE_FILE_STATUSES)[number];

/** True when the API sent a status this build knows how to describe. */
export function isKnownFileStatus(value: string): value is ResourceFileStatus {
  return (RESOURCE_FILE_STATUSES as readonly string[]).includes(value);
}

/** One PDF stored against a resource. */
export interface ResourceFile {
  id: string;
  resource_id: string;
  /** What the learner called it. Shown, and offered back on download. */
  original_filename: string;
  byte_size: number;
  page_count: number;
  content_type: string;
  checksum: string;
  status: ResourceFileStatus | string;
  created_at: string | null;
  updated_at: string | null;
}

export type ResourceFileResponse = DataEnvelope<ResourceFile>;
export type ResourceFileCollectionResponse = { data: ResourceFile[] };

/**
 * The limits the backend enforces, mirrored for the form.
 *
 * A courtesy, never the rule: the backend refuses an over-large or over-long
 * file whatever a browser allowed, and it is the only place these are decided.
 */
export const MAX_FILE_BYTES = 25 * 1024 * 1024;
export const MAX_PAGE_COUNT = 1500;
export const MAX_FILES_PER_RESOURCE = 20;

/**
 * A file's size in units a learner reads, not a measurement of them.
 *
 * Rounded to one decimal above a megabyte, and to whole kilobytes below, because
 * "1.4 MB" and "812 KB" are what a person checks against a limit.
 */
export function readableSize(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (bytes >= 1024) {
    return `${Math.round(bytes / 1024)} KB`;
  }
  return `${bytes} bytes`;
}

/**
 * How many pages, in words.
 *
 * Singular and plural, so a one-page file does not read as "1 pages". This
 * describes the document and is not a count of anything the learner did.
 */
export function readablePages(pages: number): string {
  return pages === 1 ? "1 page" : `${pages} pages`;
}
