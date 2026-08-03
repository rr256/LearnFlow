import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import styles from "@/app/layout.module.css";

import "@/app/globals.css";

export const metadata: Metadata = {
  title: {
    default: "LearnFlow",
    template: "%s | LearnFlow",
  },
  description: "An AI-powered learning platform for structured study.",
};

/**
 * The application shell.
 *
 * `lang` is set on the document, and the skip link is the first focusable
 * element, so a keyboard or screen-reader user reaches the page content without
 * traversing the header on every navigation.
 */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className={styles.shell}>
          <a className="skip-link" href="#main-content">
            Skip to main content
          </a>
          <header className={styles.header}>
            <div className={styles.headerInner}>
              <Link className={styles.wordmark} href="/">
                LearnFlow
              </Link>
              <p className={styles.tagline}>Structured study, grounded in your curriculum.</p>
            </div>
          </header>
          <main className={styles.main} id="main-content">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
