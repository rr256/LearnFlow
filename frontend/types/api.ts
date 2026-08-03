/**
 * The response envelope every `/api/v1` endpoint uses.
 *
 * These types are derived from the public HTTP contract in
 * docs/api/conventions.md and ADR-014, not from backend persistence models.
 * Field names stay `snake_case` because that is what the contract puts on the
 * wire; renaming them here would hide the contract behind a translation layer
 * that has to be kept in step with it.
 */

/** A single record or action result, returned under `data`. */
export interface DataEnvelope<T> {
  data: T;
}

/** The window applied to a collection, and how much there is in total. */
export interface Pagination {
  limit: number;
  offset: number;
  total: number;
}

/** A page of records, returned as a `data` array beside a `pagination` block. */
export interface CollectionEnvelope<T> {
  data: T[];
  pagination: Pagination;
}

/**
 * The closed error-code catalogue from
 * docs/api/conventions.md#error-codes.
 *
 * The union stays open-ended with `(string & {})` so an unrecognised code from a
 * newer backend narrows to a string rather than failing to type-check. A client
 * that meets an unknown code should report it, not crash.
 */
export type ApiErrorCode =
  | "not_found"
  | "method_not_allowed"
  | "validation_error"
  | "internal_error"
  | "request_failed";

/** One field-level validation failure. Never carries the rejected input. */
export interface ApiErrorDetail {
  field: string;
  message: string;
  type: string;
}

/** The error envelope every failure returns, including ones no route raised. */
export interface ErrorEnvelope {
  error: {
    code: ApiErrorCode | string;
    message: string;
    details?: ApiErrorDetail[];
  };
}
