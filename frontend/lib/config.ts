/**
 * Frontend runtime configuration.
 *
 * `API_BASE_URL` is the address this server calls the LearnFlow API on. ADR-009
 * fixes the name and separates it from the backend's `API_HOST`/`API_PORT`,
 * which are the address the backend *binds* to. It is read only on the server:
 * the curriculum views render as React Server Components, so no API address is
 * ever shipped to a browser, and the value deliberately carries no
 * `NEXT_PUBLIC_` prefix that would make it browser-visible.
 *
 * docs/deployment/environments.md is the authoritative variable catalogue.
 */

/** Matches the backend's published loopback port in `.env.example`. */
const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

/** Raised when configuration is present but unusable. */
export class FrontendConfigurationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "FrontendConfigurationError";
  }
}

/**
 * Resolve and validate the API base URL, without a trailing slash.
 *
 * The environment is a parameter rather than a global read so a test can
 * exercise validation without mutating `process.env` -- the same reason the
 * backend's `create_app` accepts injectable settings (ADR-009).
 *
 * @throws FrontendConfigurationError when the value is not an absolute HTTP URL.
 */
export function resolveApiBaseUrl(
  environment: Record<string, string | undefined> = process.env,
): string {
  const configured = environment.API_BASE_URL?.trim();
  if (!configured) {
    return DEFAULT_API_BASE_URL;
  }

  let parsed: URL;
  try {
    parsed = new URL(configured);
  } catch {
    throw new FrontendConfigurationError(
      "API_BASE_URL must be an absolute URL, such as http://127.0.0.1:8000.",
    );
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new FrontendConfigurationError(
      `API_BASE_URL must use http or https, not ${parsed.protocol.replace(":", "")}.`,
    );
  }

  return configured.replace(/\/+$/, "");
}
