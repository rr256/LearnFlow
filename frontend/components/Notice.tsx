import type { ReactNode } from "react";

import styles from "@/components/Notice.module.css";

export type NoticeTone = "neutral" | "attention";

interface NoticeProps {
  title: string;
  tone?: NoticeTone;
  children: ReactNode;
}

/**
 * A short explanatory panel for an empty or failed view.
 *
 * The tone changes the border and background, never the meaning: the heading
 * and body carry the message, so the panel does not rely on colour alone. An
 * `attention` notice is announced by assistive technology as it appears, which
 * a merely empty result is not.
 */
export function Notice({ title, tone = "neutral", children }: NoticeProps) {
  const className = tone === "attention" ? `${styles.notice} ${styles.attention}` : styles.notice;

  return (
    <div className={className} role={tone === "attention" ? "alert" : undefined}>
      <h2 className={styles.title}>{title}</h2>
      <div className={styles.body}>{children}</div>
    </div>
  );
}
