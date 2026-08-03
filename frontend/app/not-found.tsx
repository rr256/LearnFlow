import Link from "next/link";

import { Notice } from "@/components/Notice";

/** Shown for an address that matches no page, and for `notFound()`. */
export default function NotFound() {
  return (
    <>
      <h1>Page not found</h1>
      <Notice title="There is nothing at this address">
        <p>The page or record you asked for does not exist.</p>
        <p>
          <Link href="/curriculum">Browse the curriculum</Link>
        </p>
      </Notice>
    </>
  );
}
