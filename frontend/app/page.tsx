import Link from "next/link";

import styles from "@/app/page.module.css";

/**
 * The home page.
 *
 * It lists only what the application can actually do today. Planning, progress,
 * resources, and the mentor are not built, and advertising them here would make
 * the first screen a learner sees the least accurate one.
 */
export default function HomePage() {
  return (
    <>
      <h1>LearnFlow</h1>
      <p className={styles.lead}>
        LearnFlow is being built one capability at a time. Browsing the curriculum is the first
        one that is ready.
      </p>
      <ul className={styles.actions}>
        <li>
          <Link href="/curriculum">Browse the curriculum</Link>
        </li>
      </ul>
    </>
  );
}
