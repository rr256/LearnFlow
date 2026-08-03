"use client";

import { Notice } from "@/components/Notice";

/**
 * Last-resort boundary for the curriculum routes.
 *
 * Expected API failures are handled inside the pages, which can explain what
 * went wrong. This catches what they cannot -- a render fault -- so the message
 * is deliberately generic: Next.js redacts server error text in a production
 * build, and inventing a specific cause here would be a guess.
 */
export default function CurriculumError({ reset }: { error: Error; reset: () => void }) {
  return (
    <>
      <h1>Curriculum</h1>
      <Notice title="This page could not be displayed" tone="attention">
        <p>Something went wrong while rendering the curriculum.</p>
        <p>
          <button onClick={reset} type="button">
            Try again
          </button>
        </p>
      </Notice>
    </>
  );
}
